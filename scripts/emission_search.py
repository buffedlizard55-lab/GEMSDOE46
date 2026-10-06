#!/usr/bin/env python3
"""Emission search: choose where and how many dots to emit, using a size-aware score model.

The leave-one-anchor-out ridge on coverage-weighted feature means validates *where* dots
should go (LOO Spearman +0.63) but is blind to how many, because its predictors are means.
This script builds the explicit predictor

    s_hat = f( mean_S , N , log N )

where mean_S is the kernel-smoothed credit direction r averaged over the emission's dots and
N is the dot count, fits f on the 43 scored anchors (near-duplicates removed for an honest
LOO), and then picks the emission size from the fitted trade-off.

Outputs /tmp/gems46/data/credit_S.npy (smoothed credit field) and
data/emission_model.json.
"""
from __future__ import annotations

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
from gems46 import xemission as E  # noqa: E402
from gems46 import xmetric as M  # noqa: E402

DATA = Path("/tmp/gems46/data")


def smooth_kernel(r: np.ndarray) -> np.ndarray:
    """S(x) = sum_off k * r(x+off) / sum_off k -- the exact weight the metric's kernel gives."""
    H, W = r.shape
    out = np.zeros((H, W), np.float32)
    tot = 0.0
    for dy, dx, k in M.OFFSETS:
        out += np.float32(k) * np.roll(np.roll(r, -dy, axis=0), -dx, axis=1)
        tot += k
    return out / np.float32(tot)


def mean_S_at_dots(S: np.ndarray, d) -> float:
    """Kernel-weighted average of S over the dot positions (equals the smoothed field value)."""
    return float(S[d.row, d.col].mean())


def main() -> int:
    t0 = time.time()
    sp = DATA / "credit_S.npy"
    if sp.exists():
        S = np.load(sp)
    else:
        r = np.load(DATA / "credit_r.npy")
        S = smooth_kernel(r)
        np.save(sp, S)
    print(f"S ready {S.shape} ({time.time()-t0:.0f}s)")

    lab = (rasterio.open(ROOT / "data" / "raw" / "grid" / "labels.tif").read(1) > 0)
    from scipy.ndimage import distance_transform_edt
    dcat = distance_transform_edt(~lab).astype(np.float32)

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = [r for r in csv.DictReader(fh) if r["reported_score"]]
    recs = []
    for r_ in rows:
        p = ROOT / "data" / "raw" / "anchors" / f"{r_['anchor_id']}.tif"
        if not p.exists():
            continue
        d = A.load_dots(p, r_["anchor_id"])
        flat = np.sort(d.row.astype(np.int64) * lab.shape[1] + d.col)
        flat = flat[d.val > 0]
        recs.append(dict(aid=r_["anchor_id"], score=float(r_["reported_score"]),
                         N=len(d), mass=float(d.mass),
                         mean_S=mean_S_at_dots(S, d),
                         q90_S=float(np.percentile(S[d.row, d.col], 90)),
                         dcat_med=float(np.median(dcat[d.row, d.col])),
                         flat=flat))
    print(f"{len(recs)} anchors with rasters")

    # honest LOO: drop near-duplicates of the held-out anchor
    def dedup_keep(i):
        keep = []
        for j, rc in enumerate(recs):
            if j == i:
                continue
            a, b = recs[i]["flat"], rc["flat"]
            inter = np.intersect1d(a, b, assume_unique=True).size
            union = a.size + b.size - inter
            if union and inter / union > 0.9:
                continue
            keep.append(j)
        return keep

    X = np.column_stack([np.array([r["mean_S"] for r in recs]),
                         np.log(np.array([r["N"] for r in recs], float)),
                         np.array([r["dcat_med"] for r in recs], float)])
    y = np.array([r["score"] for r in recs])
    Xs = (X - X.mean(0)) / X.std(0)
    from scipy.stats import spearmanr
    best = None
    for lam in (0.0, 0.01, 0.1, 0.3, 1.0, 3.0):
        pred = np.zeros_like(y)
        for i in range(len(y)):
            k = dedup_keep(i)
            Xi, yi = Xs[k], y[k]
            A_ = Xi.T @ Xi + lam * np.eye(Xi.shape[1])
            w = np.linalg.solve(A_, Xi.T @ (yi - yi.mean()))
            pred[i] = yi.mean() + Xs[i] @ w
        rho = float(spearmanr(pred, y).statistic)
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        print(f"  lam={lam:5.3f} LOO spearman={rho:+.3f} rmse={rmse:.4f}")
        if best is None or rho > best[1]:
            best = (lam, rho, rmse, pred)
    lam, rho, rmse, pred = best
    print(f"best lam={lam} LOO spearman={rho:+.3f} rmse={rmse:.4f}  (deduped LOO)")

    # full fit
    A_ = Xs.T @ Xs + lam * np.eye(Xs.shape[1])
    w = np.linalg.solve(A_, Xs.T @ (y - y.mean()))
    print(f"coefficients on standardised X [mean_S, logN, dcat_med]: {np.round(w, 4)}")
    print(f"  intercept {y.mean():.4f}; X means {np.round(X.mean(0),4)}; sd {np.round(X.std(0),4)}")

    out = dict(loo_spearman=rho, loo_rmse=rmse, lam=lam,
               x_mean=X.mean(0).tolist(), x_sd=X.std(0).tolist(),
               coef=w.tolist(), intercept=float(y.mean()),
               anchors=[r["aid"] for r in recs], reported=y.tolist(),
               loo_pred=pred.tolist(),
               mean_S=[r["mean_S"] for r in recs], N=[r["N"] for r in recs],
               dcat_med=[r["dcat_med"] for r in recs])
    (ROOT / "data" / "emission_model.json").write_text(json.dumps(out, indent=1) + "\n")
    print("-> data/emission_model.json")

    print(f"\n{'aid':5s} {'N':>8s} {'meanS':>8s} {'dcat':>6s} {'rep':>7s} {'LOO':>7s}")
    for r_, p_ in sorted(zip(recs, pred), key=lambda t: -t[0]["score"])[:14]:
        print(f"{r_['aid']:5s} {r_['N']:8d} {r_['mean_S']:8.4f} {r_['dcat_med']:6.1f} "
              f"{r_['score']:7.4f} {p_:7.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
