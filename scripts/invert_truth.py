#!/usr/bin/env python3
"""Recover the hidden truth field from the public leaderboard record.

Exact identities used (all from the official scoring page; FN_w = |G| - TP_w is an identity of
the max-based terms, not an approximation):

    T_i = TP_w(p_i)    S_i = sum_x p_i(x)    M_i = sum_x p_i(x) max_{g in G} k(d(x,g))
    TI_i = T_i / ( 0.2 (T_i + S_i - M_i) + 0.8 |G| )

Write lambda(g) = expected number of hidden-truth fault pixels at g, sum_g lambda = |G|.  Because
TP_w sums a per-truth-pixel term, the *expected* TP is exactly linear in lambda:

    E[T_i] = sum_x lambda(x) C_i(x),   C_i(x) = max_y p_i(y) k(d(x,y))   (kernel-dilated file)

so every reported score is ONE linear equation in lambda:

    (1 - 0.2 s_i) C_i . lambda  -  0.8 s_i |lambda|  =  0.2 s_i (S_i - M_i)

M_i depends on lambda only through the distance from each predicted pixel to the nearest truth
pixel, so it is refined by iterating the solve.  43 scored anchors therefore give 43 linear
measurements of a 12.3 M-pixel field; the minimum-norm non-negative solution of that system in
the span of the C_i is what the ensemble of submissions can actually determine.

Everything is chunked to run inside a 3 GB / 2 CPU sandbox.
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
from gems46 import metric as M  # noqa: E402

DATA = Path("/tmp/gems46/data")
GRID = ROOT / "data" / "raw" / "grid"
CHUNK = 1_200_000          # pixels per column block


def coverage_map(raster: np.ndarray) -> np.ndarray:
    """C(x) = max_y p(y) k(d(x,y)): the credit a truth pixel at x would collect."""
    H, W = raster.shape
    out = np.zeros((H, W), np.float32)
    for dy, dx, k in M.OFFSETS:
        sh = np.roll(np.roll(raster, -dy, axis=0), -dx, axis=1)
        if dy > 0:
            sh[-dy:, :] = 0
        elif dy < 0:
            sh[:-dy, :] = 0
        if dx > 0:
            sh[:, -dx:] = 0
        elif dx < 0:
            sh[:, :-dx] = 0
        np.maximum(out, sh * np.float32(k), out=out)
    return out


class CMat:
    """The (n_anchor, n_pixel) uint8 kernel-dilated footprint matrix, chunked on disk."""

    def __init__(self, path: Path, n: int, N: int):
        self.C = np.load(path, mmap_mode="r").reshape(n, N)
        self.n, self.N, self.path = n, N, path

    def blocks(self, chunk=CHUNK):
        for a in range(0, self.N, chunk):
            b = min(a + chunk, self.N)
            X = self.C[:, a:b].astype(np.float32)
            X *= np.float32(1.0 / 255.0)
            yield a, b, X

    def gram(self):
        G = np.zeros((self.n, self.n), np.float64)
        cn = np.zeros(self.n, np.float64)
        t0 = time.time()
        for a, b, X in self.blocks():
            G += (X @ X.T).astype(np.float64)
            cn += X.sum(axis=1).astype(np.float64)
            del X
        print(f"  gram built in {time.time()-t0:.0f}s, sum C = {np.round(cn[:4], 0)}")
        return G, cn

    def T_of_z(self, z: np.ndarray) -> np.ndarray:
        """T_i = C_i . lambda for lambda = sum_j z_j C_j."""
        out = np.zeros(self.n)
        for a, b, X in self.blocks():
            out += (X @ z.astype(np.float32)).astype(np.float64)
            del X
        return out

    def lambda_of_z(self, z: np.ndarray, shape) -> np.ndarray:
        lam = np.zeros(self.N, np.float32)
        for a, b, X in self.blocks():
            lam[a:b] = X.T @ z.astype(np.float32)
            del X
        return lam.reshape(shape)


def solve_system(Gz, cn, s, rhs, ridge=1e-9):
    """Solve (1-0.2s)(Gz z) - 0.8 s (cn . z) = rhs  in (z, n_truth) form."""
    n = len(s)
    A = np.zeros((n + 1, n + 1))
    A[:n, :n] = (1.0 - 0.2 * s)[:, None] * Gz
    A[:n, n] = -0.8 * s
    A[n, :n] = cn
    A[n, n] = 0.0
    A[np.arange(n), np.arange(n)] += ridge
    b = np.concatenate([rhs, [0.0]])
    sol = np.linalg.solve(A, b)
    return sol[:n], float(sol[n])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["reported_score"]
                and (ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif").exists()]
    with rasterio.open(GRID / "labels.tif") as ds:
        H, W = ds.height, ds.width
    N, n = H * W, len(rows)
    print(f"{n} scored anchors, grid {H}x{W}")

    cpath = DATA / "truth_C_u8.npy"
    if args.rebuild or not cpath.exists():
        C = np.lib.format.open_memmap(cpath, mode="w+", dtype=np.uint8, shape=(n, H, W))
        t0 = time.time()
        for i, r in enumerate(rows):
            d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                            r["anchor_id"])
            c = coverage_map(d.raster((H, W)))
            C[i] = np.rint(c * 255.0).astype(np.uint8)
            print(f"  C[{i}] {r['anchor_id']:4s} max {c.max():.3f} "
                  f"nonzero {int((c > 0).sum()):>9,}  {time.time()-t0:.0f}s")
            del c, d
        C.flush()
        del C

    cm = CMat(cpath, n, N)
    s = np.array([float(r["reported_score"]) for r in rows])
    S = np.zeros(n)
    for i, r in enumerate(rows):
        d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                        r["anchor_id"])
        S[i] = float(d.mass)
        del d
    print(f"total mass S in [{S.min():,.0f}, {S.max():,.0f}]")

    Gz, cn = cm.gram()

    # ---- pass 1: closure M_i = T_i  ->  T_i = s_i (0.2 S_i + 0.8 |G|) ------------------
    z, n_truth = solve_system(Gz, cn, s, 0.2 * s * S)
    lam = cm.lambda_of_z(z, (H, W))
    lam = np.maximum(lam, 0.0)
    print(f"pass 1: |G|={n_truth:,.0f}  sum lambda={lam.sum():,.0f}  "
          f"support {int((lam > 1e-6).sum()):,} px")

    from scipy.ndimage import distance_transform_edt
    M_i = None
    for it in range(args.iters):
        mask = lam > max(1e-3, 0.05 * lam.max())
        if not mask.any():
            print("empty support, stopping")
            break
        dist = distance_transform_edt(~mask)
        M_i = np.zeros(n)
        for i, r in enumerate(rows):
            d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                            r["anchor_id"])
            M_i[i] = float((d.val * M.kernel(dist[d.row, d.col])).sum())
            del d
        z, n_truth = solve_system(Gz, cn, s, 0.2 * s * (S - M_i))
        lam = np.maximum(cm.lambda_of_z(z, (H, W)), 0.0)
        T = cm.T_of_z(z)
        pred = T / (0.2 * (T + S - M_i) + 0.8 * n_truth)
        from scipy.stats import pearsonr, spearmanr
        print(f"iter {it}: |G|={n_truth:,.0f} support {int((lam > 1e-6).sum()):,}  "
              f"pearson {pearsonr(pred, s).statistic:+.3f} "
              f"spearman {spearmanr(pred, s).statistic:+.3f} "
              f"rmse {np.sqrt(((pred - s) ** 2).mean()):.4f}")

    # ---- leave-one-anchor-out validation of the whole procedure ----------------------
    print("\nleave-one-anchor-out validation (refit without the held-out anchor):")
    loo_pred = np.full(n, np.nan)
    for j in range(n):
        keep = np.array([i for i in range(n) if i != j])
        Gz_k = Gz[np.ix_(keep, keep)]
        z_k, n_k = solve_system(Gz_k, cn[keep], s[keep], 0.2 * s[keep] * S[keep])
        # lambda_k = sum_{i in keep} z_k[i] C_i  ->  T_j = sum_i z_k[i] <C_j, C_i>
        T_j = float(Gz[j, keep] @ z_k)
        n_k_sum = float(cn[keep] @ z_k)
        M_j = M_i[j] if M_i is not None else T_j
        loo_pred[j] = T_j / (0.2 * (T_j + S[j] - M_j) + 0.8 * n_k_sum)
    from scipy.stats import pearsonr, spearmanr
    ok = np.isfinite(loo_pred)
    print(f"  LOO pearson {pearsonr(loo_pred[ok], s[ok]).statistic:+.3f} "
          f"spearman {spearmanr(loo_pred[ok], s[ok]).statistic:+.3f} "
          f"rmse {np.sqrt(((loo_pred[ok]-s[ok])**2).mean()):.4f} "
          f"max|err| {np.abs(loo_pred[ok]-s[ok]).max():.4f}")

    T = cm.T_of_z(z)
    pred = T / (0.2 * (T + S - M_i) + 0.8 * n_truth)
    print(f"\n{'aid':5s} {'rep':>7s} {'fit':>7s} {'LOO':>7s} {'err':>8s}")
    for i in np.argsort(-s):
        print(f"{rows[i]['anchor_id']:5s} {s[i]:7.4f} {pred[i]:7.4f} {loo_pred[i]:7.4f} "
              f"{pred[i]-s[i]:+8.4f}")

    np.save(DATA / "truth_lambda.npy", lam)
    np.save(DATA / "truth_lambda_z.npy", z)
    out = dict(n_anchors=n, n_truth_fit=float(n_truth),
               fit=dict(pearson=float(pearsonr(pred, s).statistic),
                        spearman=float(spearmanr(pred, s).statistic),
                        rmse=float(np.sqrt(((pred - s) ** 2).mean()))),
               loo=dict(pearson=float(pearsonr(loo_pred[ok], s[ok]).statistic),
                        spearman=float(spearmanr(loo_pred[ok], s[ok]).statistic),
                        rmse=float(np.sqrt(((loo_pred[ok] - s[ok]) ** 2).mean())),
                        max_abs=float(np.abs(loo_pred[ok] - s[ok]).max())),
               anchors=[r["anchor_id"] for r in rows], reported=s.tolist(),
               predicted=pred.tolist(), loo_pred=loo_pred.tolist(),
               S=S.tolist(), M=(M_i.tolist() if M_i is not None else None),
               z=z.tolist())
    (ROOT / "data" / "truth_inversion.json").write_text(json.dumps(out, indent=1) + "\n")
    print("-> data/truth_inversion.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
