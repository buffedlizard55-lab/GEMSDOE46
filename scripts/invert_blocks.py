#!/usr/bin/env python3
"""Solve the truth-recovery linear system with a non-negativity constraint, at block scale.

Model (derivation in scripts/invert_truth.py):

    (1 - 0.2 s_i) <C_i, lambda> - 0.8 s_i |lambda| = 0.2 s_i (S_i - M_i)

lambda >= 0 is the expected number of hidden-truth pixels per cell.  Solved by FISTA with a
non-negativity projection on a block-summed version of the C matrix (block summing preserves the
equation exactly because the left side is linear in lambda), which makes 43 leave-one-out refits
cheap.  Anchors whose fingerprint correlates above `--dedup` with the held-out one are excluded
from that fold, so the validation is not leaked by the group's repeated re-emissions.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path("/home/user/GEMSDOE46")
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402
from gems46 import xmetric as M  # noqa: E402

DATA = Path("/tmp/gems46/data")
GRID = ROOT / "data" / "raw" / "grid"


def load_rows():
    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        return [r for r in csv.DictReader(fh)
                if r["reported_score"]
                and (ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif").exists()]


def fista(op, b, iters=600, lam_l2=1e-3, cap=None, verbose=False):
    """min 0.5||A x - b||^2 + 0.5 lam_l2 ||x||^2 s.t. 0 <= x <= cap."""
    x = np.full(op["m"], max(float(b.mean()), 0.0), np.float32)
    y, t = x.copy(), 1.0
    L = op["lip"] + lam_l2
    for k in range(iters):
        r = op["A"](y) - b
        g = op["At"](r) + lam_l2 * y
        xn = np.maximum(y - g / L, 0.0)
        if cap is not None:
            np.minimum(xn, cap, out=xn)
        tn = (1 + np.sqrt(1 + 4 * t * t)) / 2
        y = xn + ((t - 1) / tn) * (xn - x)
        t, x = tn, xn
        if verbose and k % 100 == 0:
            print(f"    fista {k}: 0.5||r||^2 {0.5*(r**2).sum():.6g}")
    return x


def make_op(Cb, s, cn_b):
    """A x = (1-0.2s)(Cb x) - 0.8 s (1 . x);  adjoint and Lipschitz constant included."""
    c1 = (1.0 - 0.2 * s).astype(np.float32)
    c2 = (-0.8 * s).astype(np.float32)
    Cbf = np.ascontiguousarray(Cb, dtype=np.float32)

    def A(x):
        return c1 * (Cbf @ x) + c2 * float(x.sum())

    def At(r):
        return Cbf.T @ (c1 * r) + np.float32(c2 @ r)

    v = np.ones(Cbf.shape[1], np.float32)
    for _ in range(10):
        v = At(A(v))
        nv = float(np.linalg.norm(v))
        if nv == 0:
            break
        v /= nv
    lip = float(np.linalg.norm(A(v))) ** 2 + 1e-6     # ||A||^2 = Lipschitz of 0.5||Ax-b||^2
    return dict(A=A, At=At, m=Cbf.shape[1], n=Cbf.shape[0], lip=lip, Cbf=Cbf, c1=c1, c2=c2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", type=int, default=6)
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--dedup", type=float, default=0.95)
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--loops", type=int, default=2)
    args = ap.parse_args()
    B = args.block

    rows = load_rows()
    n = len(rows)
    with rasterio.open(GRID / "labels.tif") as ds:
        H, W = ds.height, ds.width
    N = H * W
    s = np.array([float(r["reported_score"]) for r in rows])
    S = np.zeros(n)
    for i, r in enumerate(rows):
        d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                        r["anchor_id"])
        S[i] = float(np.abs(d.raster((H, W))).sum())
        del d
    print(f"{n} anchors; S {S.min():,.0f}..{S.max():,.0f}")

    t0 = time.time()
    C = np.load(DATA / "truth_C_u8.npy", mmap_mode="r").reshape(n, N)
    hb, wb = H // B, W // B
    img = np.asarray(C[:, :hb * B * wb * B]).reshape(n, hb, B, wb, B)
    Cb = (img.astype(np.float32).sum(axis=(2, 4)) / np.float32(255.0)).reshape(n, hb * wb)
    del img
    cn_b = Cb.sum(axis=1)
    print(f"block-sum matrix {Cb.shape} in {time.time()-t0:.0f}s (block {B})")

    op = make_op(Cb, s, cn_b)

    def forward(x, M_i):
        T = op["Cbf"] @ x
        n_hat = float(x.sum())
        pred = T / (0.2 * (T + S - M_i) + 0.8 * n_hat)
        return T, n_hat, pred

    M_i = s * (0.2 * S + 0.8 * 8000.0)
    lam_px = np.zeros((H, W), np.float32)
    from scipy.ndimage import distance_transform_edt
    x = None
    cap = float(B * B)
    for it in range(args.loops + 1):
        b = (0.2 * s * (S - M_i)).astype(np.float32)
        x = fista(op, b, iters=args.iters, lam_l2=args.l2, cap=cap)
        T, n_hat, pred = forward(x, M_i)
        lam_px[:] = 0.0
        lam_px[:hb * B, :wb * B] = x.reshape(hb, wb).repeat(B, 0).repeat(B, 1)
        mask = lam_px > max(1e-4, 0.05 * lam_px.max())
        print(f"loop {it}: |G|={n_hat:,.0f} support {int((lam_px > 1e-4).sum()):,} px  "
              f"rmse {np.sqrt(((pred-s)**2).mean()):.4f} max|err| {np.abs(pred-s).max():.4f}")
        if it == args.loops or not mask.any():
            break
        dist = distance_transform_edt(~mask)
        for i, r in enumerate(rows):
            d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                            r["anchor_id"])
            M_i[i] = float((d.val * M.kernel(dist[d.row, d.col])).sum())
            del d

    from scipy.stats import pearsonr, spearmanr
    T, n_hat, pred = forward(x, M_i)
    print(f"in-sample: pearson {pearsonr(pred, s).statistic:+.3f} "
          f"spearman {spearmanr(pred, s).statistic:+.3f}")

    Z = Cb - Cb.mean(1, keepdims=True)
    Z /= np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12
    R = Z @ Z.T
    loo = np.full(n, np.nan)
    t0 = time.time()
    for j in range(n):
        keep = np.array([i for i in range(n) if i != j and abs(R[j, i]) < args.dedup])
        if len(keep) < 8:
            continue
        op_k = make_op(Cb[keep], s[keep], cn_b[keep])
        x_k = fista(op_k, (0.2 * s[keep] * (S[keep] - M_i[keep])).astype(np.float32),
                    iters=args.iters, lam_l2=args.l2, cap=cap)
        T_j = float(Cb[j] @ x_k)
        n_k = float(x_k.sum())
        loo[j] = T_j / (0.2 * (T_j + S[j] - M_i[j]) + 0.8 * n_k)
    ok = np.isfinite(loo)
    print(f"dedup-LOO ({time.time()-t0:.0f}s): n={int(ok.sum())} "
          f"pearson {pearsonr(loo[ok], s[ok]).statistic:+.3f} "
          f"spearman {spearmanr(loo[ok], s[ok]).statistic:+.3f} "
          f"rmse {np.sqrt(((loo[ok]-s[ok])**2).mean()):.4f} "
          f"max|err| {np.abs(loo[ok]-s[ok]).max():.4f}")

    np.save(DATA / "lambda_blocks.npy", x.reshape(hb, wb))
    out = dict(block=B, n_anchors=n, n_truth=float(n_hat), hb=hb, wb=wb,
               in_sample=dict(pearson=float(pearsonr(pred, s).statistic),
                              spearman=float(spearmanr(pred, s).statistic),
                              rmse=float(np.sqrt(((pred - s) ** 2).mean()))),
               loo=dict(n=int(ok.sum()), pearson=float(pearsonr(loo[ok], s[ok]).statistic),
                        spearman=float(spearmanr(loo[ok], s[ok]).statistic),
                        rmse=float(np.sqrt(((loo[ok] - s[ok]) ** 2).mean())),
                        max_abs=float(np.abs(loo[ok] - s[ok]).max())),
               anchors=[r["anchor_id"] for r in rows], reported=s.tolist(),
               predicted=pred.tolist(), loo_pred=loo.tolist(), S=S.tolist(), M=M_i.tolist(),
               lam_l2=args.l2, dedup=args.dedup)
    (ROOT / "data" / "truth_inversion.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{'aid':5s} {'rep':>7s} {'fit':>7s} {'LOO':>7s} {'err':>8s}")
    for i in np.argsort(-s)[:14]:
        print(f"{rows[i]['anchor_id']:5s} {s[i]:7.4f} {pred[i]:7.4f} {loo[i]:7.4f} "
              f"{pred[i]-s[i]:+8.4f}")
    print("-> data/truth_inversion.json, /tmp/gems46/data/lambda_blocks.npy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
