"""Candidate hypotheses (H46-1..H46-5) and the DFA detector they are ranked by.

This module contains no external data access: every quantity is computed from the 19 official
feature bands, the official template/labels rasters, or the group's restored prior submissions.

H46-1 (shipped): DFA scaling-exponent break along magnetic and gravity transects.
The estimator lives in :mod:`gems46.dfa`; the field construction is :func:`dfa_break_field`.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import dfa as D

# ---------------------------------------------------------------------------------------------
# Official band order (verified from the GeoTIFF band descriptions on 2026-10-06; see
# registry/data_manifest.json for the pinned sha256 of the raster).
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
    """Scale-regime anomaly: local exponent minus a large-window median background.

    ``bg_size`` is in coarse-grid cells (window centres), so the physical background scale is
    ``bg_size * stride`` pixels = ``bg_size * stride * 100 m``.
    """
    a = np.asarray(alpha_coarse, dtype=np.float32)
    fin = np.isfinite(a)
    if fin.sum() < 25:
        return np.zeros_like(a)
    filled = np.where(fin, a, np.nanmedian(a[fin])).astype(np.float32)
    bg = ndimage.median_filter(filled, size=int(bg_size), mode="nearest")
    dev = filled - bg
    # local robust scale of the deviation field
    absdev = np.abs(dev)
    scale = ndimage.median_filter(absdev, size=int(mad_size), mode="nearest") * 1.4826
    med_scale = float(np.median(scale[scale > 0])) if (scale > 0).any() else float(absdev.std() or 1.0)
    scale = np.where(scale > 1e-6, scale, med_scale)
    z = dev / scale
    z[~fin] = 0.0
    return z.astype(np.float32)


def _window_index(centers, n_windows, length):
    """Nearest-window index for every pixel along the transect axis."""
    c = np.asarray(centers, dtype=np.float64)
    if n_windows <= 0:
        return np.zeros(length, dtype=int)
    if n_windows == 1:
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
    """Scale-regime anomaly: local exponent minus a large-window median background.

    ``bg_size`` is in coarse-grid cells (window centres), so the physical background scale is
    ``bg_size * stride`` pixels = ``bg_size * stride * 100 m``.
    """
    a = np.asarray(alpha_coarse, dtype=np.float32)
    fin = np.isfinite(a)
    if fin.sum() < 25:
        return np.zeros_like(a)
    filled = np.where(fin, a, np.nanmedian(a[fin])).astype(np.float32)
    bg = ndimage.median_filter(filled, size=int(bg_size), mode="nearest")
    dev = filled - bg
    # local robust scale of the deviation field
    absdev = np.abs(dev)
    scale = ndimage.median_filter(absdev, size=int(mad_size), mode="nearest") * 1.4826
    med_scale = float(np.median(scale[scale > 0])) if (scale > 0).any() else float(absdev.std() or 1.0)
    scale = np.where(scale > 1e-6, scale, med_scale)
    z = dev / scale
    z[~fin] = 0.0
    return z.astype(np.float32)


def _upsample_coarse(coarse: np.ndarray, axis_zero_is_rows: bool, shape: tuple[int, int],
                     row_centers=None, col_centers=None) -> np.ndarray:
    """Nearest-neighbour place a coarse exponent map back onto the full raster grid."""
    h, w = shape
    c = np.asarray(coarse, dtype=np.float32)
    if c.size == 0:
        return np.zeros(shape, np.float32)
    if axis_zero_is_rows:  # (n_rows, n_windows) -> rows full, columns windowed
        out = np.repeat(c, int(np.ceil(h / c.shape[0])), axis=0)[:h]
        idx = _center_indices(c.shape[1], w, col_centers)
        out = out[:, idx]
    else:  # (n_windows, n_cols) -> rows windowed, columns full
        idx = _center_indices(c.shape[0], h, row_centers)
        out = c[idx, :]
        out = np.repeat(out, int(np.ceil(w / c.shape[1])), axis=1)[:, :w]
    return out.astype(np.float32)


def _center_indices(n_windows: int, length: int, centers) -> np.ndarray:
    if centers is not None and len(centers) == n_windows and n_windows > 1:
        # extend the centre list to the ends and take the nearest centre for every pixel
        c = np.asarray(centers, dtype=np.float64)
        edges = np.concatenate([[0.0], (c[:-1] + c[1:]) / 2.0, [length - 1.0]])
        idx = np.searchsorted(edges, np.arange(length), side="right") - 1
        return np.clip(idx, 0, n_windows - 1)
    # fallback: linear placement
    return np.clip((np.arange(length) * n_windows // max(length, 1)).astype(int), 0, n_windows - 1)


def dfa_break_field(band: np.ndarray, valid: np.ndarray, window: int = 128, stride: int = 8,
                    scales=D.DEFAULT_SCALES, bg_size: int = 31, mad_size: int = 9,
                    regime_boundary: bool = True):
    """H46-1 field for one band: local DFA exponent break relative to its background regime.

    Steps
    -----
    1. sliding-window DFA exponent along every row transect and every column transect, computed
       only inside contiguous valid runs (no interpolation across gaps),
    2. background-relative robust z-score: alpha(x) minus the median over a large neighbourhood,
       divided by a local MAD-based scale -> the "break from the surrounding scaling regime",
    3. optional regime-boundary transform |grad z|: the *boundary of a scaling regime* is a curve,
       which is a different object from the amplitude gradient of the band itself.

    Returns a dict of full-grid fields (NaN where invalid) plus the raw coarse maps.
    """
    band = np.asarray(band, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    row_map, col_map, row_centers, col_centers = D.alpha_map(band, valid, window=window,
                                                             stride=stride, scales=scales)
    z_row_c = background_anomaly(row_map, bg_size=bg_size, mad_size=mad_size)
    z_col_c = background_anomaly(col_map.T, bg_size=bg_size, mad_size=mad_size).T
    z_row = upsample(z_row_c, 0, band.shape, row_centers)
    z_col = upsample(z_col_c, 1, band.shape, col_centers)
    both = np.isfinite(z_row) & np.isfinite(z_col)
    z = np.where(both, 0.5 * (np.nan_to_num(z_row) + np.nan_to_num(z_col)),
                 np.where(np.isfinite(z_row), np.nan_to_num(z_row), np.nan_to_num(z_col)))
    z = np.where(np.isfinite(z_row) | np.isfinite(z_col), z, np.nan).astype(np.float32)
    a = np.abs(z).astype(np.float32)
    boundary = np.full(band.shape, np.nan, dtype=np.float32)
    if regime_boundary:
        filled = np.where(np.isfinite(a), a, 0.0).astype(np.float32)
        gy, gx = np.gradient(filled)
        boundary = np.hypot(gy, gx).astype(np.float32)
        boundary[~np.isfinite(a)] = np.nan
    return dict(z=z, absz=a, boundary=boundary, coarse_row=row_map, coarse_col=col_map,
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


