#!/usr/bin/env python3
"""Fit the GEMS46 credit model to the leaderboard record and report honest validation.

    python scripts/fit_credit.py [--lam 3.0] [--loo]

Outputs `data/credit_fit.json` (+ `data/credit_q_blocks.npy`) and prints the fit, the
per-anchor residuals, the feature coefficients and the leave-one-out skill.
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
from gems46 import credit as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", type=float, default=3.0)
    ap.add_argument("--loo", action="store_true")
    ap.add_argument("--outer", type=int, default=3)
    ap.add_argument("--no-bands", action="store_true", help="derived features only")
    args = ap.parse_args()

    data = ROOT / "data" / "raw"
    npz = np.load("/tmp/gems46/data/blocks.npz")
    Z, names = npz["Z"], [str(s) for s in npz["names"]]
    meta = {k: (int(npz[k]) if npz[k].ndim == 0 else npz[k]) for k in
            ("block", "ny", "nx", "H", "W", "Hc", "Wc")}
    counts = npz["counts"]
    if args.no_bands:
        keep = [i for i, n in enumerate(names) if not n.startswith("band_")]
        Z, names = Z[:, :, keep], [names[i] for i in keep]

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    dots, scores, aids = [], [], []
    for r in rows:
        p = data / "anchors" / f"{r['anchor_id']}.tif"
        if not p.exists():
            continue
        dots.append(A.load_dots(p, r["anchor_id"]))
        scores.append(float(r["reported_score"]) if r["reported_score"] else None)
        aids.append(r["anchor_id"])
    print(f"{len(dots)} anchors, {sum(s is not None for s in scores)} with reported scores")

    t0 = time.time()
    cw = C.coverage_weights(dots, scores, aids, meta)
    print(f"coverage weights {cw.W.shape} in {time.time()-t0:.1f}s")

    fit = C.fit_iterative(Z, counts, cw, dots, meta, lam=args.lam, n_outer=args.outer)
    print(f"n_truth={fit['n_truth']:.0f}")
    obs = np.isfinite(cw.score)
    t = cw.W @ fit["q_blocks"]
    n = fit["n_truth"]
    den = t + 0.2 * (cw.mass - fit["m_anchor"]) + 0.8 * (n - t)
    pred = np.where(den > 0, t / np.maximum(den, 1e-30), 0.0)
    print(f"\n{'anchor':5s} {'reported':>9s} {'model':>9s} {'resid':>9s}")
    for aid, s, p in zip(aids, cw.score, pred):
        if np.isfinite(s):
            print(f"{aid:5s} {s:9.4f} {p:9.4f} {p-s:+9.4f}")
    from scipy.stats import spearmanr
    rho = float(spearmanr(cw.score[obs], pred[obs]).statistic)
    rmse = float(np.sqrt(np.mean((pred[obs] - cw.score[obs]) ** 2)))
    print(f"\nin-sample: spearman={rho:.3f} rmse={rmse:.4f} n_truth={n:.0f}")
    print("\ntop coefficients:")
    order = np.argsort(-np.abs(fit["beta"]))
    for i in order[:15]:
        print(f"  {names[i]:18s} {fit['beta'][i]:+8.3f}")

    out = dict(lam=args.lam, n_features=len(names), names=names,
               beta=fit["beta"].tolist(), beta0=fit["beta0"],
               n_truth=fit["n_truth"], in_sample_spearman=rho, in_sample_rmse=rmse,
               anchors=aids, reported=cw.score.tolist(), predicted=pred.tolist())
    if args.loo:
        t0 = time.time()
        r = C.loo(Z, counts, cw, lam=args.lam)
        print(f"\nLOO: spearman={r['spearman']:.3f} rmse={r['rmse']:.4f} "
              f"max_abs={r['max_abs_error']:.4f}  ({time.time()-t0:.0f}s)")
        out["loo"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()}
    np.save("/tmp/gems46/data/credit_q_blocks.npy", fit["q_blocks"])
    (ROOT / "data" / "credit_fit.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("-> data/credit_fit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
