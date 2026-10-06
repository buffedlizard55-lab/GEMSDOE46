#!/usr/bin/env python3
"""Two-stage credit model.

Stage A (validated by leave-one-anchor-out): penalised linear fit of the reported score on
the *coverage-weighted feature means* of each anchor:

    zbar_ik = sum_{dots,off} v*k*z_k / sum_{dots,off} v*k
    s_i    ~ a + w . zbar_i

Stage B: turn the fitted direction into a pixel-level truth density

    q(x) = lam * relu( w . z(x) + c0 ),     w, z in centred rank space ([-1, 1])

and calibrate the two scalars (lam, c0) so the *exact* metric applied to q reproduces the
reported ladder.  q is the object the emission optimiser maximises coverage of; its integral
is the model's estimate of |G|, the number of hidden fault pixels.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402
from gems46 import credit2 as C2  # noqa: E402
from gems46 import metric as M  # noqa: E402

DATA = Path("/tmp/gems46/data")


def weighted_mean(tables, weights, mask=None):
    """zbar_ik = sum(w*z)/sum(w) in centred rank space."""
    K = tables[0].shape[1]
    out = np.zeros((len(tables), K), np.float64)
    for i, (t, w) in enumerate(zip(tables, weights)):
        z = C2._zs(t)
        if mask is not None:
            z = z[:, mask]
        ww = w.astype(np.float64)
        out[i] = (z * ww[:, None]).sum(axis=0) / ww.sum()
    return out


def ridge_loo(X, y, lams=(0.03, 0.1, 0.3, 1.0, 3.0, 10.0)):
    from scipy.stats import spearmanr
    best = None
    for lam in lams:
        pred = np.zeros_like(y)
        for i in range(len(y)):
            keep = np.arange(len(y)) != i
            g = X[keep].T @ X[keep] + lam * np.eye(X.shape[1])
            b = X[keep].T @ (y[keep] - y[keep].mean())
            w = np.linalg.solve(g, b)
            pred[i] = y[keep].mean() + X[i] @ w
        rho = float(spearmanr(pred, y).statistic)
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        if best is None or rho > best[1]:
            best = (lam, rho, rmse, pred.copy())
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=20, help="features kept in the pixel model")
    ap.add_argument("--m-iter", type=int, default=2)
    args = ap.parse_args()

    feats_tif = DATA / "features_national.tif"
    labels_tif = ROOT / "data" / "raw" / "grid" / "labels.tif"
    z = np.load(DATA / "dot_tables.npz", allow_pickle=True)
    n_anch = sum(1 for k in z.files if k.startswith("t"))
    tables = [z[f"t{i}"] for i in range(n_anch)]
    weights = [z[f"w{i}"] for i in range(n_anch)]
    scale = z["scale"]
    fp_matrix = z["fp"]
    names = [str(s) for s in z["names"]]

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["reported_score"] and (ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif").exists()]
    aids = [r["anchor_id"] for r in rows]
    scores = np.array([float(r["reported_score"]) for r in rows])
    masses = np.array([a for a in scale])          # coverage mass ~ emitted mass for binary dots
    with __import__("rasterio").open(ROOT / "data" / "raw" / "grid" / "labels.tif") as ds:
        lab = ds.read(1)
    footprint = lab >= 0
    fp_ratio = float(footprint.sum()) / len(fp_matrix)
    print(f"{len(tables)} anchors, {len(names)} features, footprint ratio {fp_ratio:.2f}")

    Zbar = weighted_mean(tables, weights)
    mu, sd = Zbar.mean(0), Zbar.std(0) + 1e-12
    X = (Zbar - mu) / sd
    lam, rho, rmse, pred = ridge_loo(X, scores)
    print(f"stage A ridge: lam={lam} LOO spearman={rho:+.3f} rmse={rmse:.4f}")
    # refit on all data with the selected penalty
    g = X.T @ X + lam * np.eye(X.shape[1])
    b = X.T @ (scores - scores.mean())
    w_std = np.linalg.solve(g, b)
    a_std = scores.mean()
    print("stage A coefficients (standardised zbar):")
    for i in np.argsort(-np.abs(w_std))[:args.top_k]:
        print(f"  {names[i]:18s} {w_std[i]:+7.4f}  (rho_univariate)")

    keep = np.argsort(-np.abs(w_std))[:args.top_k]
    np.savez(DATA / "zbar.npz", Zbar=Zbar, scores=scores, names=np.array(names), keep=keep,
             w_std=w_std, a_std=a_std, ridge_lam=lam, loo_spearman=rho, loo_rmse=rmse,
             mu=mu, sd=sd)

    # ---------- stage B: calibrate lam, c0 against the exact metric -----------------
    # direction in *centred rank* space: beta_k = w_std_k / sd_k ; feature rank values are
    # centred to [-1,1] by C2._zs, so zbar = mean of z; the pixel score is w.( (z-mu)/sd ).
    beta_rank = w_std / sd
    zbar_rank = Zbar.mean(axis=0)

    def predict_with(lam_q, c0, m_anchor):
        tt = np.zeros(len(tables))
        for i, (t, w) in enumerate(zip(tables, weights)):
            u = C2._zs(t) @ beta_rank + c0
            pos = np.clip(u, 0, None)
            tt[i] = float(scale[i] * (w * pos).sum() / w.sum()) * lam_q
        u_fp = C2._zs(fp_matrix) @ beta_rank + c0
        n = float(np.clip(u_fp, 0, None).sum() * fp_ratio) * lam_q
        den = tt + M.ALPHA * (masses - m_anchor) + M.BETA * (n - tt)
        return np.where(den > 0, tt / np.maximum(den, 1e-30), 0.0), tt, n

    from scipy.optimize import minimize

    def make_loss(m_anchor):
        def loss(p):
            lam_q, c0 = np.exp(p[0]), p[1]
            pred_i, _, _ = predict_with(lam_q, c0, m_anchor)
            return float(((pred_i - scores) ** 2).sum())
        return loss

    m_anchor = np.zeros(len(scores))
    for it in range(args.m_iter + 1):
        # grid-then-local search on (log lam, c0)
        best = None
        for lq in (0.5, 1, 2, 4, 8, 16, 32):
            for c0 in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.4):
                loss = make_loss(m_anchor)
                v = loss(np.array([np.log(lq), c0]))
                if best is None or v < best[0]:
                    best = (v, lq, c0)
        res = minimize(make_loss(m_anchor), np.array([np.log(best[1]), best[2]]),
                       method="Nelder-Mead",
                       options=dict(maxiter=2000, xatol=1e-4, fatol=1e-12))
        lam_q, c0 = float(np.exp(res.x[0])), float(res.x[1])
        pred_i, tt, n = predict_with(lam_q, c0, m_anchor)
        from scipy.stats import spearmanr
        rho2 = float(spearmanr(scores, pred_i).statistic)
        rmse2 = float(np.sqrt(np.mean((pred_i - scores) ** 2)))
        print(f"stage B iter {it}: lam={lam_q:.3f} c0={c0:.3f} n_truth={n:.0f} "
              f"spearman={rho2:+.3f} rmse={rmse2:.4f}")
        if it >= args.m_iter:
            break
        # update M from the calibrated density
        from scipy.ndimage import distance_transform_edt
        u_fp = C2._zs(fp_matrix) @ beta_rank + c0
        q = np.clip(u_fp, 0, None) * fp_ratio * lam_q
        fy, fx = z["fpy"], z["fpx"]
        order = np.argsort(-q)
        k = int(np.searchsorted(np.arange(1, len(q) + 1), max(n, 1)))
        mask = np.zeros(footprint.shape, bool)
        mask[fy[order[:k]], fx[order[:k]]] = True
        d = distance_transform_edt(~mask)
        dots = [A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{a}.tif") for a in aids]
        m_new = np.array([float((dd.val * M.kernel(d[dd.row, dd.col])).sum()) for dd in dots])
        print(f"  |dM|max={np.abs(m_new-m_anchor).max():.0f}  "
              f"M in [{m_new.min():.0f},{m_new.max():.0f}]")
        m_anchor = m_new

    out = dict(
        stage_a=dict(ridge_lam=lam, loo_spearman=rho, loo_rmse=rmse,
                     beta_standardised=w_std.tolist(), intercept=a_std,
                     names=names, keep=keep.tolist()),
        stage_b=dict(lam=lam_q, c0=c0, beta_rank=beta_rank.tolist(), n_truth=n,
                     spearman=rho2, rmse=rmse2),
        anchors=aids, reported=scores.tolist(), predicted=pred_i.tolist(),
        m_anchor=m_anchor.tolist(), model_mass=tt.tolist(),
    )
    (ROOT / "data" / "credit_model.json").write_text(json.dumps(out, indent=1) + "\n")
    np.savez(DATA / "credit_model.npz", beta_rank=beta_rank, c0=c0, lam=lam_q,
             fp_matrix=fp_matrix, fpy=z["fpy"], fpx=z["fpx"], footprint=footprint,
             names=np.array(names), keep=keep)
    print(f"\n{'anchor':5s} {'reported':>9s} {'model':>9s} {'resid':>9s}")
    for a, s, p in zip(aids, scores, pred_i):
        print(f"{a:5s} {s:9.4f} {p:9.4f} {p-s:+9.4f}")
    print("-> data/credit_model.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
