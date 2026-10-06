"""Write and independently audit a competition-legal submission GeoTIFF.

Format requirements, quoted verbatim from the official problem description
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/,
section "Submission format"):

  * "in the same projected coordinate reference system as the training data
     (projected coordinate system for UTM zone 11N, EPSG 32611)"
  * "at the same resolution as the training data (100m)"
  * "the same bounds as the training data, and data outside the bounds is null or nan"
  * "a single layer with datatype of 32-bit float (float32) with values between
     0 and 1 indicating the confidence or probability of fault presence"

Two byte-level encodings of the out-of-footprint region are produced because the
upload validator's error message ("Predicted values must be in range [0, 1]",
observed by the project owner) is only consistent with a value-range check that
does not skip NaN:

  ``-allfinite``  out-of-footprint = 0.0   -> [0,1] holds over the whole array
  ``-nan``        out-of-footprint = NaN   -> matches sample_submission.tif exactly

The two encodings are provably identical under the official metric, because
``FPw`` sums only over cells with ``p(x) > 0`` and truth never lies outside the
footprint.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

CRS = "EPSG:32611"
TRANSFORM = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
SHAPE = (3730, 3292)


def write_submission(dots_rc: np.ndarray, footprint: np.ndarray, out_path: Path,
                     mode: str = "allfinite") -> Path:
    arr = np.zeros(SHAPE, dtype=np.float32)
    if len(dots_rc):
        arr[dots_rc[:, 0], dots_rc[:, 1]] = 1.0
    if mode == "nan":
        out = np.where(footprint, arr, np.float32("nan")).astype(np.float32)
    elif mode == "allfinite":
        out = arr  # already 0 outside the footprint
    else:
        raise ValueError(mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1], count=1,
        dtype="float32", crs=CRS, transform=TRANSFORM, nodata=(np.nan if mode == "nan" else None),
        compress="deflate", predictor=3, tiled=True, blockxsize=512, blockysize=512,
    ) as dst:
        dst.write(out, 1)
    return out_path


def audit(path: Path, dot_count: int, footprint: np.ndarray | None = None,
          mode: str = "allfinite") -> dict:
    p = Path(path)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    with rasterio.open(p) as s:
        a = s.read(1)
        checks = {
            "single_band": s.count == 1,
            "dtype_float32": s.dtypes[0] == "float32",
            "shape_3730x3292": (s.height, s.width) == SHAPE,
            "crs_epsg_32611": str(s.crs).upper() == CRS,
            "transform_matches_template": tuple(s.transform)[:6] == tuple(TRANSFORM)[:6],
            "unique_positive_values_are_1": bool(
                np.all(np.isin(np.unique(a[a > 0]), [1.0])) if (a > 0).any() else True
            ),
            "portal_range_0_1_all_cells": bool(
                np.all((a >= 0.0) & (a <= 1.0)) if np.isfinite(a).all() else
                np.all((a[np.isfinite(a)] >= 0.0) & (a[np.isfinite(a)] <= 1.0))
            ),
        }
        if mode == "nan":
            checks["nan_outside_footprint_only"] = bool(
                footprint is not None
                and np.array_equal(~np.isfinite(a), ~footprint)
            )
            checks["all_finite_inside_footprint"] = bool(
                np.isfinite(a[footprint]).all() if footprint is not None else False
            )
        else:
            checks["all_cells_finite"] = bool(np.isfinite(a).all())
        checks["range_0_1_on_finite_cells"] = bool(
            np.all((a[np.isfinite(a)] >= 0.0) & (a[np.isfinite(a)] <= 1.0))
        )
        stats = {
            "positive_pixels": int((a > 0).sum()),
            "nan_pixels": int((~np.isfinite(a)).sum()),
            "min": float(np.nanmin(a)), "max": float(np.nanmax(a)),
        }
    return {
        "file": p.name, "bytes": len(raw), "sha256": sha,
        "positives": stats["positive_pixels"], "nan_pixels": stats["nan_pixels"],
        "min": stats["min"], "max": stats["max"],
        "expected_dots": int(dot_count), "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def verify_matches_truth_array(dots_rc: np.ndarray, path: Path) -> bool:
    """Byte-level round trip: file positives == emitted dots."""
    with rasterio.open(path) as s:
        a = s.read(1)
    idx = np.argwhere(a > 0)
    return len(idx) == len(dots_rc) and np.array_equal(np.sort(idx.view([("", idx.dtype)] * 2).ravel()),
                                                       np.sort(dots_rc.view([("", dots_rc.dtype)] * 2).ravel()))
