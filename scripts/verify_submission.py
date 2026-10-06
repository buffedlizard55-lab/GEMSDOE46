#!/usr/bin/env python3
"""Independent verification of the deliverable GeoTIFF.

Checks every clause of the official submission contract, reads the file twice with two
independent libraries (rasterio and tifffile), and re-derives the uniqueness claim against
every scored anchor raster that exists locally.  Exit status is non-zero if any check fails.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
import tifffile

ROOT = Path("/home/user/GEMSDOE46")
GRID = ROOT / "data" / "raw" / "grid"
SUB = ROOT / "deliverables" / "gems46" / "gems46-ridge-37k-ridge.tif"


def main() -> int:
    checks, failures = [], 0

    def check(name, ok, detail=""):
        nonlocal failures
        checks.append(dict(check=name, ok=bool(ok), detail=str(detail)))
        if not ok:
            failures += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    with rasterio.open(GRID / "sample_submission.tif") as ref:
        ref_shape, ref_crs, ref_tr = (ref.height, ref.width), ref.crs, ref.transform
        ref_prof = dict(dtype=ref.dtypes[0], count=ref.count)

    sha = hashlib.sha256(SUB.read_bytes()).hexdigest()
    check("file exists", SUB.exists(), f"{SUB.stat().st_size:,} bytes")
    check("sha256", True, sha)

    with rasterio.open(SUB) as ds:
        a = ds.read(1)
        prof = dict(dtype=ds.dtypes[0], count=ds.count, crs=str(ds.crs),
                    shape=(ds.height, ds.width), transform=tuple(ds.transform)[:6],
                    nodata=ds.nodata, block=ds.block_shapes[0], compress=str(ds.compression))
    check("single band", prof["count"] == 1, prof["count"])
    check("float32", prof["dtype"] == "float32", prof["dtype"])
    check("EPSG:32611", "32611" in prof["crs"], prof["crs"])
    check("shape matches sample", prof["shape"] == ref_shape, f"{prof['shape']} vs {ref_shape}")
    check("transform matches sample", prof["transform"] == tuple(ref_tr)[:6], prof["transform"])
    check("100 m pixels", abs(prof["transform"][0]) == 100.0 and prof["transform"][4] == -100.0,
          f"{prof['transform'][0]}, {prof['transform'][4]}")
    check("nodata unset (no large-negative sentinel)", prof["nodata"] is None, prof["nodata"])
    check("all cells finite", bool(np.isfinite(a).all()),
          f"{int((~np.isfinite(a)).sum())} non-finite")
    check("values in [0,1]", float(a.min()) >= 0.0 and float(a.max()) <= 1.0,
          f"min {a.min()}, max {a.max()}")
    check("distinct value count small (deterministic emission)", np.unique(a).size <= 4,
          np.unique(a).tolist()[:6])

    t = tifffile.imread(SUB)
    check("second reader agrees", t.shape == ref_shape and t.dtype == np.float32,
          f"{t.shape} {t.dtype}")
    check("second reader bit-identical", bool(np.array_equal(t, a)),
          f"max abs diff {float(np.abs(t - a).max())}")

    # uniqueness against the scored anchor corpus
    sys.path.insert(0, str(ROOT / "src"))
    from gems46 import anchors as A  # noqa: E402
    import csv
    H, W = ref_shape
    mine = np.zeros(H * W, bool)
    mine.reshape(H, W)[a > 0] = True
    flat_mine = np.flatnonzero(mine)
    rows = [r for r in csv.DictReader((ROOT / "data" / "anchor_manifest.csv").open())
            if r["reported_score"]
            and (ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif").exists()]
    worst = []
    for r in rows:
        d = A.load_dots(ROOT / "data" / "raw" / "anchors" / f"{r['anchor_id']}.tif",
                        r["anchor_id"])
        other = np.zeros(H * W, bool)
        other.reshape(H, W)[d.row, d.col] = True
        inter = np.intersect1d(np.flatnonzero(other), flat_mine, assume_unique=True).size
        union = int(other.sum()) + flat_mine.size - inter
        worst.append((inter / union if union else 0.0, r["anchor_id"], int(other.sum()), inter))
    worst.sort(reverse=True)
    check("unique vs every local anchor (max Jaccard < 0.5)", worst[0][0] < 0.5,
          f"max {worst[0][0]:.4f} vs {worst[0][1]} ({worst[0][3]} shared px)")

    out = dict(submission=str(SUB), sha256=sha, bytes=SUB.stat().st_size, profile=prof,
               nonzero=int((a > 0).sum()), checks=checks, failures=failures,
               uniqueness_top5=[dict(jaccard=w[0], anchor=w[1], anchor_dots=w[2],
                                     shared=w[3]) for w in worst[:5]])
    (ROOT / "data" / "verification.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\n{len(checks) - failures}/{len(checks)} checks passed -> data/verification.json")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
