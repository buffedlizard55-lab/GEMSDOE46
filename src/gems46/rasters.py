"""Georeferenced I/O for the emission stage: dot fields -> legal submission rasters."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

GRID = dict(crs="EPSG:32611", transform=Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0),
            height=3730, width=3292)


def read_grid(path: Path):
    with rasterio.open(path) as ds:
        a = ds.read(1, masked=True)
        return a.filled(np.nan).astype(np.float32), ds.transform, ds.crs


def write_submission(path: Path, arr: np.ndarray, transform=None, crs=None,
                     nodata=None) -> dict:
    """Write a single-band float32 GeoTIFF that satisfies the portal contract.

    Guarantees: every cell finite, values clipped to [0, 1], zeros outside the footprint
    (negative nodata sentinel is never written).
    """
    a = np.asarray(arr, np.float32).copy()
    if not np.isfinite(a).all():
        raise ValueError(f"{int((~np.isfinite(a)).sum())} non-finite cells")
    np.clip(a, 0.0, 1.0, out=a)
    tr = transform if transform is not None else GRID["transform"]
    cr = crs if crs is not None else GRID["crs"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1],
                       count=1, dtype="float32", crs=cr, transform=tr,
                       compress="deflate", predictor=2, tiled=True,
                       blockxsize=512, blockysize=512) as ds:
        ds.write(a, 1)
    return dict(path=str(path), shape=list(a.shape), min=float(a.min()), max=float(a.max()),
                nonzero=int((a > 0).sum()), finite=bool(np.isfinite(a).all()),
                bytes=path.stat().st_size)


def dots_to_raster(rows, cols, shape=None) -> np.ndarray:  # pragma: no cover
    H, W = shape if shape is not None else (GRID["height"], GRID["width"])
    out = np.zeros((H, W), np.float32)
    out[np.asarray(rows), np.asarray(cols)] = 1.0
    return out
