#!/usr/bin/env python3
"""Pairwise similarity of every anchor + a target raster (uniqueness instrument).

Implements the project's uniqueness rule taken from the brief: a shipped candidate must be
*different from the collection of GEMSDOE sites*, checked as Pearson < 0.85 and
positive-support Jaccard < 0.50 against every prior artifact.  Use:

    python scripts/similarity.py [target.tif]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> np.ndarray:
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    return a


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    anchors = []
    for r in rows:
        p = ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif"
        if p.exists():
            anchors.append((r["anchor_id"], r["reported_score"], load(p)))

    if target is not None:
        t = load(target)
        print(f"target {target.name}  mass={float(t.sum()):.1f}  positives={int((t > 0).sum())}")
        print(f"{'anchor':6s} {'score':>7s} {'pearson':>9s} {'jaccard':>9s} {'mass_ovl':>9s}  verdict")
        worst = {"pearson": 0.0, "jaccard": 0.0}
        for aid, score, a in anchors:
            tp = float((t * a).sum())
            denom = float(np.sqrt((t * t).sum() * (a * a).sum()))
            pear = tp / denom if denom else 0.0
            inter = int(((t > 0) & (a > 0)).sum())
            union = int(((t > 0) | (a > 0)).sum())
            jac = inter / union if union else 0.0
            worst["pearson"] = max(worst["pearson"], pear)
            worst["jaccard"] = max(worst["jaccard"], jac)
            flag = "OK" if (pear < 0.85 and jac < 0.50) else "**ANCHOR-LIKE**"
            print(f"{aid:6s} {str(score):>7s} {pear:9.4f} {jac:9.4f} {inter:9d}  {flag}")
        print(f"\nworst pearson={worst['pearson']:.4f}  worst jaccard={worst['jaccard']:.4f}")
        ok = worst["pearson"] < 0.85 and worst["jaccard"] < 0.50
        print("UNIQUENESS RULE: " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 2

    # all-pairs among anchors
    n = len(anchors)
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            a1, a2 = anchors[i][2], anchors[j][2]
            denom = float(np.sqrt((a1 * a1).sum() * (a2 * a2).sum()))
            pear = float((a1 * a2).sum()) / denom if denom else 0.0
            inter = int(((a1 > 0) & (a2 > 0)).sum())
            union = int(((a1 > 0) | (a2 > 0)).sum())
            out.append({"a": anchors[i][0], "b": anchors[j][0], "pearson": round(pear, 4),
                        "jaccard": round(inter / union if union else 0.0, 4)})
    out.sort(key=lambda r: -r["pearson"])
    for r in out[:25]:
        print(f"{r['a']:5s} vs {r['b']:5s}  pearson={r['pearson']:.4f}  jaccard={r['jaccard']:.4f}")
    (ROOT / "data" / "anchor_similarity.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\n-> data/anchor_similarity.json ({len(out)} pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
