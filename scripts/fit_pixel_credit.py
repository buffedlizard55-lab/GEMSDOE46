#!/usr/bin/env python3
"""Fit the pixel-level credit model to the leaderboard record, with leave-one-out skill."""
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
from gems46 import xfeatures as F  # noqa: E402
from gems46 import xmetric as M  # noqa: E402

DATA = Path("/tmp/gems46/data")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-anchor", type=int, default=1200)
    ap.add_argument("--lam", type=float, default=0.05)
    ap.add_argument("--loo", action="store_true")
    ap.add_argument("--m-iter", type=int, default=2)
    args = ap.parse_args()

    feats_tif = DATA / "features_national.tif"
    labels_tif = ROOT / "data" / "raw" / "grid" / "labels.tif"
    cache = DATA / "dot_tables.npz"

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    dots, scores, masses, aids = [], [], [], []
    for r in rows:
        p = ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif"
        if p.exists() and r["reported_score"]:
            d = A.load_dots(p, r["anchor_id"])
            dots.append(d); scores.append(float(r["reported_score"]))
            masses.append(d.mass); aids.append(r["anchor_id"])
    scores = np.array(scores)
    masses = np.array(masses)
    print(f"{len(dots)} scored anchors")

    t0 = time.time()
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        tables = [z[f"t{i}"] for i in range(len(dots))]
        weights = [z[f"w{i}"] for i in range(len(dots))]
        scale = z["scale"]; fp_matrix = z["fp"]; fp_idx = (z["fpy"], z["fpx"])
        names = [str(s) for s in z["names"]]
        print(f"loaded cached tables ({time.time()-t0:.0f}s)")
    else:
        names = list(F.FEATURE_NAMES)
        pack = C2.sample_dot_tables(dots, None, feats_tif, labels_tif,
                                    per_anchor=args.per_anchor, feature_names=names)
        tables, weights, scale = pack["tables"], pack["weights"], pack["scale"]
        fp_idx = pack["fp_index"]
        fp_matrix = C2.footprint_sample_matrix(feats_tif, labels_tif, fp_idx, names)
        np.savez_compressed(cache, scale=scale, fp=fp_matrix, names=np.array(names),
                            fpy=fp_idx[0], fpx=fp_idx[1],
                            **{f"t{i}": t for i, t in enumerate(tables)},
                            **{f"w{i}": w for i, w in enumerate(weights)})
        print(f"built tables ({time.time()-t0:.0f}s): "
              f"{sum(len(t) for t in tables)} sampled pairs")

    lab, footprint, catalogue, raw = F.load_grid(feats_tif, labels_tif)
    fp_ratio = float(footprint.sum()) / len(fp_idx[0])

    m_anchor = np.zeros(len(dots))
    fit = None
    for it in range(max(args.m_iter, 1)):
        fit = C2.fit_pixel_credit(tables, weights, scale, masses, scores, fp_matrix,
                                  fp_ratio, lam=args.lam, m_anchor=m_anchor, verbose=True)
        # truth set from the fitted density, for the FP-relief term M_i
        from scipy.ndimage import distance_transform_edt
        beta, b, n = fit["beta"], fit["b"], fit["n_truth"]
        u = b + C2._zs(fp_matrix) @ beta
        q = np.clip(u, 0, None) * fp_ratio
        order = np.argsort(-q)
        csum = np.cumsum(np.ones_like(q))
        k = int(np.searchsorted(csum, n))
        mask = np.zeros(footprint.shape, bool)
        mask[fp_idx[0][order[:max(k, 1)]], fp_idx[1][order[:max(k, 1)]]] = True
        d = distance_transform_edt(~mask)
        m_new = np.array([float((dd.val * M.kernel(d[dd.row, dd.col])).sum()) for dd in dots])
        delta = float(np.abs(m_new - m_anchor).max())
        print(f"  outer {it}: |dM|max={delta:.1f} M in [{m_new.min():.0f}, {m_new.max():.0f}] "
              f"n_truth={n:.0f}")
        m_anchor = m_new
        if delta < 1.0:
            break

    pred = fit["pred"]
    print(f"\n{'anchor':5s} {'reported':>9s} {'model':>9s} {'resid':>9s}")
    for aid, s, p in zip(aids, scores, pred):
        print(f"{aid:5s} {s:9.4f} {p:9.4f} {p-s:+9.4f}")
    from scipy.stats import spearmanr
    rho = float(spearmanr(scores, pred).statistic)
    rmse = float(np.sqrt(np.mean((pred - scores) ** 2)))
    print(f"\nin-sample spearman={rho:.3f} rmse={rmse:.4f} n_truth={fit['n_truth']:.0f}")
    print("\ncoefficients (centred rank features, [-1,1]):")
    for i in np.argsort(-np.abs(fit["beta"]))[:18]:
        print(f"  {names[i]:18s} {fit['beta'][i]:+7.3f}")
    print(f"  {'intercept':18s} {fit['b']:+7.3f}")

    out = dict(lam=args.lam, per_anchor=args.per_anchor, n_anchors=len(dots),
               names=names, beta=fit["beta"].tolist(), b=fit["b"],
               n_truth=fit["n_truth"], in_sample_spearman=rho, in_sample_rmse=rmse,
               anchors=aids, reported=scores.tolist(), predicted=pred.tolist(),
               m_anchor=m_anchor.tolist())
    if args.loo:
        t0 = time.time()
        r = C2.loo_pixel(tables, weights, scale, masses, scores, fp_matrix, fp_ratio,
                         lam=args.lam, m_anchor=m_anchor, verbose=True)
        out["loo"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()}
        print(f"  LOO took {time.time()-t0:.0f}s")
    (ROOT / "data" / "pixel_credit_fit.json").write_text(json.dumps(out, indent=1) + "\n")
    print("-> data/pixel_credit_fit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
