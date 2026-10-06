#!/usr/bin/env python3
"""Probe: does DTI measured on a local truth/mask raster reproduce the reported anchor scores?

If yes, the hidden objective is solvable locally.  If no, the reported scores come from a
truth set we do not hold and any detector must be validated by an empirical surrogate.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path("/home/user/GEMSDOE46")
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402
from gems46 import metric as M  # noqa: E402

GRID = ROOT / "data" / "raw" / "grid"


def load(path, ):
    with rasterio.open(path) as ds:
        a = ds.read(1, masked=True).filled(0.0)
    return a


def main() -> int:
    lab = (load(GRID / "labels.tif") > 0)
    print(f"labels.tif positives: {lab.sum():,}")
    masks = {}
    for name in ["qfaults_prior_u8", "derived_sgmc_faults_100m_u8", "lidar_scarp_features_u8",
                 "geodawn_extensions_u8", "geodawn_rad_u8", "sample_submission"]:
        p = GRID / f"{name}.tif"
        if not p.exists():
            continue
        a = load(p)
        pos = a > 0
        masks[name] = pos
        print(f"{name:32s} positives {pos.sum():7,d}  overlap_with_labels "
              f"{(pos & lab).sum():7,d}  outside_labels {(pos & ~lab).sum():7,d}")

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = [r for r in csv.DictReader(fh) if r["reported_score"]]
    picks = rows  # all scored anchors
    print("\n=== DTI on local rasters vs reported ===")
    print(f"{'anc':5s} {'rep':>7s} {'dots':>7s} | " +
          " | ".join(f"{k[:14]:>14s}" for k in ["labels_only"] + list(masks)))
    out = {}
    for r in picks:
        p = ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif"
        if not p.exists():
            continue
        d = A.load_dots(p, r["anchor_id"])
        row = [f"{r['anchor_id']:5s} {float(r['reported_score']):7.4f} {len(d):7d}"]
        vals = {}
        c = M.components(d.raster(lab.shape), lab, None)
        vals["labels_only"] = c["dti"]
        row.append(f"{c['dti']:14.4f}")
        for name, mk in masks.items():
            cc = M.components(d.raster(lab.shape), lab, mk)
            vals[name] = cc["dti"]
            row.append(f"{cc['dti']:14.4f}")
        out[r["anchor_id"]] = vals
        print(" | ".join(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
