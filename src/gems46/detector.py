"""The H46 detector: local DFA scaling-exponent breaks along magnetic and gravity transects.

This module contains no external data access: every quantity is computed from the 19 official
feature bands, the official template/labels rasters, or the group's restored prior submissions.

H46-1 (shipped, new hypothesis)
    ``dfa_break_field`` - local DFA exponent along every row/column transect, differenced against a
    large-window median background and scaled by a local MAD estimate, plus the regime-boundary
    transform |grad z|.  The estimator itself lives in :mod:`gems46.dfa`.

H46-2 (shipped, recommended)
    the geometric-mean corroboration of edge/curvature transforms, built in
    ``scripts/build_submission.py`` from the same official bands, with a DFA portfolio slice.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import dfa as D

# ---------------------------------------------------------------------------------------------
# Official band order, verified from the GeoTIFF band descriptions on 2026-10-06.
# The raster's sha256 is pinned in registry/data_manifest.json.
# ---------------------------------------------------------------------------------------------
BAND_INDEX = {
    "mag_anom": 1,
    "rtp": 2,
    "tmi_hg": 3,
    "geod_2ndinv": 4,
    "iso_grav_anom_slope": 5,
    "tc": 6,
    "geod_shearrate": 7,
    "geod_dilaterate": 8,
    "tmi_vg": 9,
    "deq_n100a15": 10,
    "iso_grav_anom_vg": 11,
    "det_elev": 12,
    "iso_grav_anom": 13,
    "tmi": 14,
    "depth_to_base_surf": 15,
    "ieq_n100a15": 16,
    "cond_surf": 17,
    "iso_grav_anom_hg": 18,
    "det_elev_slope": 19,
}

MAGNETIC = ("mag_anom", "rtp", "tmi", "tmi_hg", "tmi_vg")
GRAVITY = ("iso_grav_anom", "iso_grav_anom_hg", "iso_grav_anom_slope", "iso_grav_anom_vg")


def robust_z(x: np.ndarray, mad_scale: float = 1.4826) -> np.ndarray:
    """Robust z-score against the median and the scaled median absolute deviation."""
    x = np.asarray(x, dtype=np.float32)
    fin = np.isfinite(x)
    if not fin.any():
        return np.zeros_like(x)
    med = float(np.median(x[fin]))
    mad = float(np.median(np.abs(x[fin] - med))) * mad_scale
    if mad <= 0:
        mad = float(x[fin].std()) or 1.0
    z = np.zeros_like(x, dtype=np.float32)
    z[fin] = (x[fin] - med) / mad
    return z


def background_anomaly(alpha_coarse: np.ndarray, bg_size: int = 31, mad_size: int = 9) -> np.ndarray:
    """Scale-regime anomaly: local exponent minus a large-window median background, in local MADs.

    ``bg_size`` is measured in coarse-grid cells (window centres), so the physical background scale
    is ``bg_size * stride`` pixels: with the shipped stride of 8 px, ``bg_size = 31`` is 248 cells
    = 24.8 km.  Cells where the exponent is undefined contribute 0 to the anomaly.
    """
    a = np.asarray(alpha_coarse, dtype=np.float32)
    fin = np.isfinite(a)
    if fin.sum() < 25:
        return np.zeros_like(a)
    filled = np.where(fin, a, np.nanmedian(a[fin])).astype(np.float32)
    bg = ndimage.median_filter(filled, size=int(bg_size), mode="nearest")
    dev = filled - bg
    absdev = np.abs(dev)
    scale = ndimage.median_filter(absdev, size=int(mad_size), mode="nearest") * 1.4826
    med_scale = float(np.median(scale[scale > 0])) if (scale > 0).any() else float(absdev.std() or 1.0)
    scale = np.where(scale > 1e-6, scale, med_scale)
    z = (dev / scale).astype(np.float32)
    z[~fin] = 0.0
    return z


def _window_index(centers, n_windows: int, length: int) -> np.ndarray:
    """Nearest-window index for every pixel along the transect axis."""
    c = np.asarray(centers, dtype=np.float64)
    if n_windows <= 1:
        return np.zeros(length, dtype=int)
    edges = np.concatenate([[0.0], (c[:-1] + c[1:]) / 2.0, [length - 1.0]])
    return np.clip(np.searchsorted(edges, np.arange(length), side="right") - 1, 0, n_windows - 1)


def upsample(coarse: np.ndarray, axis: int, shape: tuple[int, int], centers) -> np.ndarray:
    """Nearest-neighbour placement of a coarse transect-window map onto the full raster grid."""
    c = np.asarray(coarse, dtype=np.float32)
    h, w = shape
    if c.size == 0 or not np.isfinite(c).any():
        return np.full(shape, np.nan, dtype=np.float32)
    if axis == 0:      # (n_rows, n_windows) -> (h, w)
        idx = _window_index(centers, c.shape[1], w)
        return c[:, idx].astype(np.float32)
    idx = _window_index(centers, c.shape[0], h)   # (n_windows, n_cols) -> (h, w)
    return c[idx, :].astype(np.float32)


def dfa_break_field(band: np.ndarray, valid: np.ndarray, window: int = 128, stride: int = 8,
                    scales=D.DEFAULT_SCALES, bg_size: int = 31, mad_size: int = 9,
                    regime_boundary: bool = True) -> dict:
    """H46-1 field for one band: local DFA exponent break relative to its background regime.

    Steps
    -----
    1. sliding-window DFA exponent along every row and column transect, computed only inside
       contiguous valid runs (no interpolation across gaps),
    2. background-relative robust z-score: alpha(x) minus the median over a large neighbourhood,
       divided by a local MAD-based scale -> the break from the surrounding scaling regime,
    3. optional regime-boundary transform |grad z|: the boundary of a scaling regime is a curve,
       which is a different object from an amplitude gradient of the band itself.

    Returns full-grid fields (NaN where invalid) plus the raw coarse maps and window centres.
    """
    band = np.asarray(band, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    row_map, col_map, row_centers, col_centers = D.alpha_map(band, valid, window=window,
                                                             stride=stride, scales=scales)
    z_row_c = background_anomaly(row_map, bg_size=bg_size, mad_size=mad_size)
    z_col_c = background_anomaly(col_map.T, bg_size=bg_size, mad_size=mad_size).T
    z_row = upsample(z_row_c, 0, band.shape, row_centers)
    z_col = upsample(z_col_c, 1, band.shape, col_centers)
    fin_r, fin_c = np.isfinite(z_row), np.isfinite(z_col)
    z = np.where(fin_r & fin_c, 0.5 * (np.nan_to_num(z_row) + np.nan_to_num(z_col)),
                 np.where(fin_r, np.nan_to_num(z_row),
                          np.where(fin_c, np.nan_to_num(z_col), np.nan))).astype(np.float32)
    absz = np.abs(z).astype(np.float32)
    boundary = np.full(band.shape, np.nan, dtype=np.float32)
    if regime_boundary:
        filled = np.where(np.isfinite(absz), absz, 0.0).astype(np.float32)
        gy, gx = np.gradient(filled)
        boundary = np.hypot(gy, gx).astype(np.float32)
        boundary[~np.isfinite(absz)] = np.nan
    return dict(z=z, absz=absz, boundary=boundary, coarse_row=row_map, coarse_col=col_map,
                row_centers=row_centers, col_centers=col_centers)


def group_mean(fields, min_valid: int = 1) -> np.ndarray:
    """Mean of a list of fields, ignoring NaNs; NaN where fewer than ``min_valid`` are finite."""
    stack = np.stack([np.asarray(f, dtype=np.float32) for f in fields])
    fin = np.isfinite(stack)
    cnt = fin.sum(axis=0)
    tot = np.where(fin, np.nan_to_num(stack), 0.0).sum(axis=0)
    out = np.where(cnt >= int(min_valid), tot / np.maximum(cnt, 1), np.nan)
    return out.astype(np.float32)


def group_min(fields) -> np.ndarray:
    """Elementwise minimum (corroboration): NaN if any input is NaN."""
    stack = np.stack([np.asarray(f, dtype=np.float32) for f in fields])
    return np.nanmin(stack, axis=0).astype(np.float32)
