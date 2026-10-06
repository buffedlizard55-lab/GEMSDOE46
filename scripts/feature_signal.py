#!/usr/bin/env python3
"""Diagnostic: do geological features measured *where an anchor looks* explain its score?

For every scored anchor i and feature k compute the coverage-weighted mean

    zbar_ik = sum_{dots} sum_off v*k*z_k(x+off) / sum_{dots} sum_off v*k

i.e. the average value of feature k under the anchor's own coverage footprint (sampled).
Then ask two questions:

  1. univariate: does zbar_ik rank-correlate with the reported score across anchors?
  2. multivariate: can a penalised linear model on zbar predict held-out anchors' scores?

A feature that tracks the hidden label set must show positive skill here, because the only
thing that varies across these anchors (given similar mass) is *where they look*.
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
from gems46 import features as F  # noqa: E402
from gems46 import metric as M  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-anchor", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261006)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    data = ROOT / "data" / "raw"
    feats_tif = Path("/tmp/gems46/data/features_national.tif")
    lab, footprint, catalogue, raw = F.load_grid(feats_tif, data / "grid" / "labels.tif")

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    dots, scores, aids = [], [], []
    for r in rows:
        p = data / "anchors" / f"{r['anchor_id']}.tif"
        if p.exists() and r["reported_score"]:
            dots.append(A.load_dots(p, r["anchor_id"]))
            scores.append(float(r["reported_score"]))
            aids.append(r["anchor_id"])
    scores = np.array(scores)
    print(f"{len(dots)} scored anchors")

    # fixed sample of dots per anchor (uniform), to keep memory bounded
    samples, weights = [], []
    for d in dots:
        n = min(args.per_anchor, len(d))
        idx = rng.choice(len(d), size=n, replace=False)
        samples.append((d.row[idx], d.col[idx], d.val[idx]))
        weights.append(d.val[idx])

    H, W = footprint.shape
    K = len(F.FEATURE_NAMES)
    zbar = np.zeros((len(dots), K), np.float64)
    scale = np.zeros(len(dots))
    t0 = time.time()
    for ki, (name, arr) in enumerate(F.iter_features(raw, footprint, catalogue)):
        if name not in F.FEATURE_NAMES:
            continue
        k = F.FEATURE_NAMES.index(name)
        v = arr[footprint]
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, np.float32)
        ranks[order] = np.linspace(0, 1, v.size, dtype=np.float32)
        layer = np.zeros((H, W), np.float32)
        layer[footprint] = ranks
        del v, order, ranks
        for ai, (rr, cc, vv) in enumerate(samples):
            num = 0.0
            den = 0.0
            for dy, dx, kk in M.OFFSETS:
                r = rr + dy
                c = cc + dx
                ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
                if not ok.any():
                    continue
                w = vv[ok] * np.float32(kk)
                num += float((w * layer[r[ok], c[ok]]).sum())
                den += float(w.sum())
            if den > 0:
                zbar[ai, k] += num / den * (1.0 / 1.0)
            if ki == 0 and k == 0:
                scale[ai] = den
        if k % 8 == 0:
            print(f"  {name:18s} {time.time()-t0:5.0f}s")
        del layer

    # zbar[ai, k] is already the coverage-weighted mean for feature k
    np.savez("/tmp/gems46/data/feature_signal.npz", zbar=zbar, scores=scores, aids=aids,
             names=np.array(F.FEATURE_NAMES))

    from scipy.stats import spearmanr
    print(f"\n{'feature':18s} {'rho':>7s} {'p':>9s}   (Spearman vs reported score)")
    res = []
    for k, name in enumerate(F.FEATURE_NAMES):
        rho, p = spearmanr(zbar[:, k], scores)
        res.append((name, float(rho), float(p)))
    for name, rho, p in sorted(res, key=lambda t: -abs(t[1]))[:20]:
        print(f"{name:18s} {rho:+7.3f} {p:9.2e}")

    # multivariate ridge with leave-one-out
    mu, sd = zbar.mean(0), zbar.std(0) + 1e-9
    X = (zbar - mu) / sd
    best = None
    for lam in (0.1, 0.3, 1.0, 3.0, 10.0, 30.0):
        pred = np.zeros_like(scores)
        for i in range(len(scores)):
            keep = np.arange(len(scores)) != i
            A_ = X[keep].T @ X[keep] + lam * np.eye(X.shape[1])
            b_ = X[keep].T @ (scores[keep] - scores[keep].mean())
            w = np.linalg.solve(A_, b_)
            pred[i] = scores[keep].mean() + X[i] @ w
        rho = float(spearmanr(pred, scores).statistic)
        rmse = float(np.sqrt(np.mean((pred - scores) ** 2)))
        print(f"ridge lam={lam:5.1f}  LOO spearman={rho:+.3f}  rmse={rmse:.4f}")
        if best is None or rho > best[1]:
            best = (lam, rho, rmse)
    print(f"\nbest ridge lam={best[0]} LOO spearman={best[1]:+.3f} rmse={best[2]:.4f}")
    (ROOT / "data" / "feature_signal.json").write_text(json.dumps(
        dict(univariate=res, ridge_loo=dict(lam=best[0], spearman=best[1], rmse=best[2]),
             anchors=aids, scores=scores.tolist()), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
