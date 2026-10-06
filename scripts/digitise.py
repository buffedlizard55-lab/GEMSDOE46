#!/usr/bin/env python3
"""Emit a unique candidate submission from a geological raster layer.

Turns any continuous layer into a dot field along its locally extreme ridges (local maxima of
a smoothed response, i.e. what a geological edge/curvature transform does to a fault), then
spends the mass where the dots are expected to earn most, and scores the result with the exact
metric (in-sample, on the known catalogue) plus the anchor-calibrated ridge predictor.

    digitise.py --layer <tif> [--radius 1] [--stride 3] [--top 1.0]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402
from gems46 import emission as E  # noqa: E402
from gems46 import metric as M  # noqa: E402
from gems46 import rasters as R  # noqa: E402

DATA = Path("/tmp/gems46/data")


def load_model():
    z = np.load(DATA / "credit_model.npz", allow_pickle=True)
    return z


def credit_direction(keep, w_std, mu, sd):
    """Pixel direction in centred-rank space, from the ridge fit on coverage-weighted means."""
    beta_std = np.zeros_like(w_std)
    beta_std[keep] = w_std[keep]
    return beta_std / sd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True)
    ap.add_argument("--smooth", type=float, default=0.0)
    ap.add_argument("--max-dots", type=int, default=45000)
    ap.add_argument("--batch", type=int, default=4000)
    ap.add_argument("--out", default=str(DATA / "candidate"))
    args = ap.parse_args()

    z = load_model()
    lab, _, _, _ = __import__("gems46.features", fromlist=["x"]).load_grid(
        DATA / "features_national.tif", ROOT / "data" / "raw" / "grid" / "labels.tif")
    print("loaded grid")

    with rasterio.open(args.layer) as ds:
        raw = ds.read(1, masked=True).filled(np.nan).astype(np.float32)
        tr, crs = ds.transform, ds.crs
    print(f"layer {Path(args.layer).name}: {np.isfinite(raw).sum():,} finite cells")

    footprint = np.isfinite(raw)
    # rank-normalise inside the footprint (monotone: preserves every ridge)
    v = raw[footprint]
    order = np.argsort(v, kind="stable")
    rk = np.empty(v.size, np.float32)
    rk[order] = np.linspace(0, 1, v.size, dtype=np.float32)
    rank = np.full(raw.shape, np.nan, np.float32)
    rank[footprint] = rk
    print(f"  rank range {np.nanmin(rank):.2f}..{np.nanmax(rank):.2f}")

    # local-maximum ridge mask at a small scale + value map
    from scipy.ndimage import maximum_filter, gaussian_filter
    rf = np.where(footprint, rank, -np.inf)
    if args.smooth:
        rf = gaussian_filter(np.where(footprint, rank, 0.0), args.smooth)
        rf = np.where(footprint, rf, -np.inf)
    mx = maximum_filter(rf, size=5, mode="constant", cval=-np.inf)
    ridge = footprint & (rf >= mx - 1e-9)
    val = np.where(ridge, np.clip(rank, 0, 1), 0.0).astype(np.float32)
    print(f"  ridge pixels {int(ridge.sum()):,}")

    best = None
    hist = []

    def report(it, rows, cols, cov):
        nonlocal best
        stats = M.components(cov, None)
        if best is None or stats["dti"] > best[0]:
            best = (stats["dti"], len(rows), it, stats)
        hist.append(dict(round=it, n_dots=len(rows), **{k: float(vv) for k, vv in stats.items()}))

    E.greedy_rounds(val, rounds=int(np.ceil(args.max_dots / args.batch)), batch=args.batch,
                    on_round=report)
    print(f"  in-sample TP_w={best[3]['tp']:.1f} FP_w={best[3]['fp']:.1f} "
          f"|G|={best[3]['g_size']} dti={best[0]:.4f} at n_dots={best[1]} (round {best[2]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
