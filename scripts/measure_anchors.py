#!/usr/bin/env python3
"""Measure the anchor corpus: mass, dot count, catalogue overlap, distance statistics.

Writes `data/measurements.json` and prints a table.  Every number is computed from the
byte-hashed rasters in `data/raw/anchors/`; the reported score column is the *user-reported*
value from the brief and is never treated as a receipt.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402


def main() -> int:
    grid = ROOT / "data" / "raw" / "grid"
    with rasterio.open(grid / "labels.tif") as ds:
        labels = ds.read(1)
        shape = labels.shape
    known = labels > 0
    footprint = labels >= 0
    print(f"grid {shape}  footprint {int(footprint.sum())}  catalogue {int(known.sum())}")

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))

    out = []
    for r in rows:
        p = ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif"
        if not p.exists():
            out.append({**r, "status": "missing"})
            continue
        d = A.load_dots(p, r["anchor_id"])
        with rasterio.open(p) as ds:
            arr = ds.read(1)
            finite = int(np.isfinite(arr).sum())
        on_cat = A.mass_on_mask(d, known)
        dist = A.distance_to_mask(d, known)
        rec = {
            **r,
            "status": "ok",
            "dots": len(d),
            "mass": round(d.mass, 3),
            "on_catalogue_dots": int((dist == 0).sum()),
            "on_catalogue_mass": round(on_cat, 3),
            "finite_cells": finite,
            "median_dist_to_catalogue_px": float(np.median(dist)) if len(d) else None,
            "frac_within_3px_of_catalogue": float((dist <= 3).mean()) if len(d) else None,
            "binary": bool(np.all(d.val == d.val[0])) if len(d) else None,
            "max_value": float(d.val.max()) if len(d) else None,
        }
        out.append(rec)
        print(f"{r['anchor_id']:4s} score={r['reported_score'] or '-':>6s} dots={len(d):8d} "
              f"mass={d.mass:10.1f} on_cat={rec['on_catalogue_dots']:6d} "
              f"med_d={rec['median_dist_to_catalogue_px']:.1f}px")

    (ROOT / "data" / "measurements.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\n-> data/measurements.json  ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
