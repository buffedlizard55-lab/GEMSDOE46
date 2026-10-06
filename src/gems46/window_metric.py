"""Exact, windowed evaluation of the official metric on a sparse emission.

For a set of unit-mass dots ``D`` and a binary truth window ``T`` the three
published terms are

    TPw = sum_{g in T} max_{x in D, d(x,g)<=R} k(d(x,g))
    FPw = sum_{x in D} (1 - k(d(x, nearest truth in G)))
    FNw = sum_{g in T} (1 - max_{x in D} k(d(x,g)))   ==  |T| - TPw  (exact)

Two implementation points matter for correctness:

1. **FPw is measured against the whole truth raster G**, never just the window's
   slice of it.  ``max_{g in G} k(d(x,g))`` is a property of the dot and the full
   truth; a dot sitting next to a fault that happens to lie in a neighbouring
   spatial block is *not* a full false positive.  Callers therefore pass a global
   distance-to-truth field, and the window supplies only the TP/FN truth subset.
2. The window is padded by ``ceil(R)+1`` pixels so dots just outside it still
   deliver their kernel credit to truth inside it.

DPTI is evaluated at float64 throughout.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

R_PIXELS = 3.0


def _ball(radius_pixels: float):
    rad = int(np.ceil(radius_pixels))
    rr, cc = np.mgrid[-rad : rad + 1, -rad : rad + 1]
    dist = np.sqrt((rr.astype(np.float64)) ** 2 + (cc.astype(np.float64)) ** 2)
    m = dist <= radius_pixels
    return rr[m], cc[m], np.maximum(1.0 - dist[m] / radius_pixels, 0.0)


def coverage_field(dots_rc: np.ndarray, shape, radius_pixels: float = R_PIXELS,
                   origin=(0, 0)) -> np.ndarray:
    """max over dots of k(d) at every cell of a ``shape`` window (float64).

    ``dots_rc`` are (row, col) in global coordinates; ``origin`` = (r0, c0) of
    the window in global coordinates.
    """
    out = np.zeros(shape, dtype=np.float64)
    if len(dots_rc) == 0:
        return out
    dy, dx, kv = _ball(radius_pixels)
    h, w = shape
    r0, c0 = int(origin[0]), int(origin[1])
    for (y, x) in np.asarray(dots_rc):
        ly = int(y) - r0
        lx = int(x) - c0
        if ly < -int(np.ceil(radius_pixels)) - 1 or lx < -int(np.ceil(radius_pixels)) - 1 \
                or ly > h + int(np.ceil(radius_pixels)) or lx > w + int(np.ceil(radius_pixels)):
            continue
        ys = ly + dy
        xs = lx + dx
        ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
        np.maximum.at(out, (ys[ok], xs[ok]), kv[ok])
    return out


def global_truth_distance(truth: np.ndarray) -> np.ndarray:
    """Euclidean distance (pixels) from every cell of the full grid to nearest truth."""
    return ndimage.distance_transform_edt(~np.asarray(truth, dtype=bool)).astype(np.float64)


def window_terms(dots_rc: np.ndarray, truth_win: np.ndarray,
                 radius_pixels: float = R_PIXELS, origin=(0, 0),
                 d_truth_global: np.ndarray | None = None,
                 alpha: float = 0.2, beta: float = 0.8, eps: float = 1e-9) -> dict:
    """Official metric terms for a window's truth subset.

    ``dots_rc`` global (row, col); ``truth_win`` the boolean truth raster that
    this window scores; ``origin`` the window's global (row, col) offset;
    ``d_truth_global`` the full-grid distance-to-truth field (required for a
    correct ``FPw``; if omitted the window's own truth is used and the caller
    must ensure every dot lies inside the window).
    """
    truth_win = np.asarray(truth_win, dtype=bool)
    n_truth = int(truth_win.sum())
    dots_rc = np.asarray(dots_rc).reshape(-1, 2)

    cov = coverage_field(dots_rc, truth_win.shape, radius_pixels, origin)
    tpw = float(cov[truth_win].sum())
    fnw = float(n_truth) - tpw

    if len(dots_rc) == 0:
        fpw = 0.0
    elif d_truth_global is not None:
        dd = d_truth_global[dots_rc[:, 0].astype(np.int64), dots_rc[:, 1].astype(np.int64)].astype(np.float64)
        dd[~np.isfinite(dd)] = np.inf
        kk = np.maximum(1.0 - dd / radius_pixels, 0.0)
        kk[~np.isfinite(dd)] = 0.0
        fpw = float((1.0 - kk).sum())
    else:
        d_loc = ndimage.distance_transform_edt(~truth_win)
        r0, c0 = int(origin[0]), int(origin[1])
        ly = dots_rc[:, 0] - r0
        lx = dots_rc[:, 1] - c0
        inb = (ly >= 0) & (ly < truth_win.shape[0]) & (lx >= 0) & (lx < truth_win.shape[1])
        kk = np.zeros(len(ly), dtype=np.float64)
        kk[inb] = np.maximum(1.0 - d_loc[ly[inb], lx[inb]] / radius_pixels, 0.0)
        fpw = float((1.0 - kk).sum())

    val = tpw / (tpw + alpha * fpw + beta * fnw + eps)
    return {"DTI": val, "TPw": tpw, "FPw": fpw, "FNw": fnw, "G": n_truth,
            "emitted_px": int(len(dots_rc))}
