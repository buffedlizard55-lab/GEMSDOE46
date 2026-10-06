"""Exact implementation of the official GEMS Prize distance-weighted Tversky index.

Transcribed line-by-line from the official problem description
(https://www.drivendive... -> actually:
 https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
 section "Mathematical representation"), which states verbatim:

    k(d) = (1 - d/R)_+ = max(1 - d/R, 0),  R = 300 m  (3 pixels at 100 m)
    TPw = sum_{g in G} max_{x: d(x,g)<=R} p(x) k(d(x,g))
    FPw = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
    FNw = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) k(d(x,g))]
    DTI = TPw / (TPw + alpha*FPw + beta*FNw + eps),   alpha = 0.2, beta = 0.8

Notes on the transcription
--------------------------
* ``FNw`` as published has no explicit ``g``-weight, but for a binary truth raster
  every g contributes ``1 - coverage(g)``; the total truth mass is ``G = |G|``.
* All three sums are over the *scored* domain: the competition excludes pixels that
  belong to the given USGS/INGENIOUS catalogue (organizer clarification, DrivenData
  community thread 11516, quoted in the family's own docs).  We never mask inside
  ``DTI`` itself: the caller passes the truth raster it wants scored.
* Coordinates: pixels, 100 m spacing, 8-connected distance (Euclidean in metres).

Verified against the official worked example in ``tests/test_metric.py``:
    TPw = 3.00, FPw = 1.89, FNw = 2.00  ->  DTI(0.2, 0.8) = 0.60
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import ndimage

R_METRES = 300.0
PIXEL_METRES = 100.0
R_PIXELS = R_METRES / PIXEL_METRES  # 3.0
ALPHA = 0.2
BETA = 0.8
EPS = 1e-9


# --- aliases so the two API generations in this file share one source of truth -------------
RADIUS_M = R_METRES
PIXEL_M = PIXEL_METRES
RADIUS_PX = R_PIXELS


def kernel_from_distance(d_pixels: np.ndarray) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0) with d in pixels."""
    return np.maximum(1.0 - d_pixels / R_PIXELS, 0.0)


def _nearest_truth_distance(truth: np.ndarray) -> np.ndarray:
    """Euclidean distance (in pixels) from every cell to the nearest truth cell.

    ``ndimage.distance_transform_edt`` called on the *complement* gives exactly
    ``d(x) = min_{g in G} ||x - g||`` in pixel units.
    """
    return ndimage.distance_transform_edt(~truth)


def distance_weighted_terms(pred: np.ndarray, truth: np.ndarray):
    """Return (TPw, FPw, FNw, G) exactly as published.

    Parameters
    ----------
    pred : float array, values in [0, 1]
    truth : bool array, same shape
    """
    pred = np.asarray(pred, dtype=np.float64)
    truth = np.asarray(truth, dtype=bool)
    if pred.shape != truth.shape:
        raise ValueError("pred and truth must have the same shape")

    g_mass = float(truth.sum())
    if g_mass == 0.0:
        return 0.0, float(pred[pred > 0].sum()), 0.0, 0.0

    # distance from every cell to nearest truth cell (pixels)
    d = _nearest_truth_distance(truth)
    k = kernel_from_distance(d)  # k(d(x,g*)) per cell

    # --- TPw -----------------------------------------------------------------
    # sum over truth pixels of the best (max) weighted prediction within R.
    # For a truth cell g, the max over x is attained at the cell x maximising
    # p(x)*k(d(x,g)).  Computed by iterating a 3x3 (7x7 metre window) max-filter
    # over the "sparse-set" transform of pred, but we do it exactly with a
    # distance-limited dilation of the credit field.
    # credit(x) = p(x); contribution to truth cell g is max_x p(x) k(d(x,g)).
    # Because k is radial and decreases with d, this is a max-plus convolution.
    # Exact evaluation: only cells within R can contribute, so we build the
    # (R_pixels rounded up +1) ball offsets.
    tpw = _max_plus_kernel_sum(pred, truth)

    # --- FPw -----------------------------------------------------------------
    fpw = float((pred * (1.0 - k))[pred > 0].sum())

    # --- FNw -----------------------------------------------------------------
    covered = np.zeros_like(pred)
    _fill_best_coverage(pred, truth, covered)
    fnw = float((1.0 - covered[truth]).sum())

    return tpw, fpw, fnw, g_mass


def _ball_offsets(radius_cells: int):
    rr, cc = np.mgrid[-radius_cells : radius_cells + 1, -radius_cells : radius_cells + 1]
    m = np.sqrt(rr * rr + cc * cc) <= radius_cells
    return rr[m], cc[m]


def _max_plus_kernel_sum(pred: np.ndarray, truth: np.ndarray) -> float:
    """sum_g max_{x: d<=R} p(x) k(d(x,g)), exactly."""
    rad = int(np.ceil(R_PIXELS))
    offs = _ball_offsets(rad)
    h, w = pred.shape
    total = 0.0
    # For every candidate displacement delta, truth cells that can be reached by
    # an emitted cell at delta share the value p(x)*k(||delta||).  Taking the max
    # over deltas replicates max_x.
    best = np.zeros(pred.shape, dtype=np.float64)
    for dy, dx in zip(*offs):
        dist = float(np.hypot(dy, dx))
        kval = max(1.0 - dist / R_PIXELS, 0.0)
        if kval <= 0.0:
            continue
        shifted = np.zeros_like(pred)
        ys_src = slice(max(0, -dy), h - max(0, dy))
        xs_src = slice(max(0, -dx), w - max(0, dx))
        ys_dst = slice(max(0, dy), h - max(0, -dy))
        xs_dst = slice(max(0, dx), w - max(0, -dx))
        shifted[ys_dst, xs_dst] = pred[ys_src, xs_src] * kval
        np.maximum(best, shifted, out=best)
    total = float(best[truth].sum())
    return total


def _fill_best_coverage(pred: np.ndarray, truth: np.ndarray, out: np.ndarray) -> None:
    """out[g] = max_{x: d(x,g)<=R} p(x) k(d(x,g)) for truth cells g."""
    rad = int(np.ceil(R_PIXELS))
    offs = _ball_offsets(rad)
    h, w = pred.shape
    best = np.zeros(pred.shape, dtype=np.float64)
    for dy, dx in zip(*offs):
        dist = float(np.hypot(dy, dx))
        kval = max(1.0 - dist / R_PIXELS, 0.0)
        if kval <= 0.0:
            continue
        shifted = np.zeros_like(pred)
        ys_src = slice(max(0, -dy), h - max(0, dy))
        xs_src = slice(max(0, -dx), w - max(0, dx))
        ys_dst = slice(max(0, dy), h - max(0, -dy))
        xs_dst = slice(max(0, dx), w - max(0, -dx))
        shifted[ys_dst, xs_dst] = pred[ys_src, xs_src] * kval
        np.maximum(best, shifted, out=best)
    out[...] = best


def dti(pred: np.ndarray, truth: np.ndarray, alpha: float = ALPHA, beta: float = BETA):
    """Official distance-weighted Tversky index. Returns a float."""
    tpw, fpw, fnw, _ = distance_weighted_terms(pred, truth)
    return tpw / (tpw + alpha * fpw + beta * fnw + EPS)


def dti_terms(pred: np.ndarray, truth: np.ndarray, alpha: float = ALPHA, beta: float = BETA):
    tpw, fpw, fnw, g = distance_weighted_terms(pred, truth)
    val = tpw / (tpw + alpha * fpw + beta * fnw + EPS)
    return {
        "DTI": val,
        "TPw": tpw,
        "FPw": fpw,
        "FNw": fnw,
        "G": g,
        "emitted_px": float((np.asarray(pred) > 0).sum()),
    }


# ---------------------------------------------------------------------------
# Fast path used by the emitter/optimiser.  The *sparse* regime assumption is
# explicit here: the caller emits a set of unit-mass dots; the credit each dot
# delivers to truth pixels is computed with the same max-plus rule, but the
# truth-side max is taken over the accepted dot set only.
# ---------------------------------------------------------------------------
def sparse_terms_from_credit(credit: np.ndarray, n_dots: int, n_truth: int,
                             alpha: float = ALPHA, beta: float = BETA,
                             fp_mass: float | None = None):
    """DTI for a sparse binary emission.

    ``credit`` : per-truth-pixel delivered coverage in [0, 1] (sum -> TPw).
    ``n_dots`` : number of unit-mass emitted pixels.
    ``n_truth``: number of scored truth pixels G.
    ``fp_mass``: sum_x (1 - k(x)); defaults to the exact sparse identity
                 FPw = n_dots - TPw  which holds when no two dots share a
                 best-cover truth pixel (the regime a thin dotted line targets).
    """
    tpw = float(credit.sum())
    if fp_mass is None:
        fp_mass = float(n_dots) - tpw
    fnw = float(n_truth) - tpw
    val = tpw / (tpw + alpha * fp_mass + beta * fnw + EPS)
    return val, tpw, fp_mass, fnw


# ===============================================================================================
# Exact component-level API.  ``known`` accepts the published catalogue so that the staff
# clarification (known USGS/INGENIOUS faults are masked from the penalty terms) can be
# evaluated directly; ``valid`` restricts scoring to the template's finite cells.
# ===============================================================================================


def kernel(d, radius: float = RADIUS_PX):
    """Triangular kernel k(d) = max(1 - d/R, 0). ``d`` in pixels, R in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def _offsets(radius: float = RADIUS_PX):
    """All integer offsets with k(offset) > 0, as (dy, dx, k)."""
    r = int(np.ceil(radius))
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            kv = float(kernel(np.hypot(dy, dx), radius))
            if kv > 0.0:
                out.append((dy, dx, kv))
    return tuple(out)


OFFSETS = _offsets()


def _shift(a: np.ndarray, dy: int, dx: int, fill=0.0) -> np.ndarray:
    """Return b with b[y, x] = a[y + dy, x + dx] (zero outside)."""
    out = np.full(a.shape, fill, dtype=a.dtype)
    h, w = a.shape
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    if ys0 < ys1 and xs0 < xs1:
        out[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    return out


def prepare(pred, truth, valid=None, known=None):
    """Apply the validity + known-fault masking rules; return (p, g, active) float/bool grids."""
    pred = np.asarray(pred, dtype=np.float64)
    truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("prediction and truth must be equal-shaped 2-D grids")
    valid = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    if valid.shape != pred.shape or known.shape != pred.shape:
        raise ValueError("mask grid mismatch")
    active = valid & ~known
    vals = pred[active & np.isfinite(pred)]
    if vals.size and ((vals < 0).any() or (vals > 1).any()):
        raise ValueError("predictions inside the scored domain must be in [0, 1]")
    p = np.where(active & np.isfinite(pred), pred, 0.0).astype(np.float64)
    g = active & (np.asarray(truth) > 0)
    return p, g, active


@dataclass
class Components:
    """Metric components. ``s``/``m``/``k`` are the algebra terms used for fast scoring."""

    tp: float
    fp: float
    fn: float
    n_truth: int
    s: float          # total emitted mass
    m: float          # emitted mass that best-covers a truth pixel
    dti: float

    def as_dict(self) -> dict:
        return asdict(self)


def components(pred, truth, valid=None, known=None, alpha: float = ALPHA,
               beta: float = BETA) -> Components:
    """Exact DTI components for a soft prediction grid (O(N) with the 3 px kernel)."""
    p, g, _ = prepare(pred, truth, valid, known)
    ktruth = g.astype(np.float64)
    s = float(p.sum())
    n = int(g.sum())
    if n == 0:
        # no labelled pixels inside the scored domain: DTI is defined as 0 with FP mass only
        return Components(0.0, s, 0.0, 0, s, 0.0, 0.0)
    # nearest-kernel-weight map C[x] = max_g k(d(x,g)) (0 where no truth within R)
    c = np.zeros(p.shape, dtype=np.float64)
    for dy, dx, kv in OFFSETS:
        c = np.maximum(c, _shift(ktruth, dy, dx) * kv)
    m = float((p * c).sum())
    fp = s - m
    # credit per truth pixel: max over offsets of p at the offset x, weighted by k
    credit = np.zeros(p.shape, dtype=np.float64)
    for dy, dx, kv in OFFSETS:
        credit = np.maximum(credit, _shift(p, dy, dx) * kv)
    tp = float(credit[g].sum())
    fn = float(n) - tp
    return Components(tp, fp, fn, n, s, m, dti_from_terms(tp, fp, fn, alpha, beta))


def components_binary(emit, truth, valid=None, known=None, alpha: float = ALPHA,
                      beta: float = BETA) -> Components:
    """Exact DTI components for a *binary* prediction, in O(N) via two Euclidean distance transforms.

    For binary p the published max reduces to the nearest emitted pixel, because k is decreasing in
    d:  max_{x} p(x) k(d(x,g)) = k(min_x d(x,g)) over emitted x.  Likewise
    max_g k(d(x,g)) = k(min_g d(x,g)).  scipy's exact Euclidean distance transform therefore gives
    the same numbers as the 29-offset transcription, at a fraction of the cost.
    """
    from scipy import ndimage

    emit = np.asarray(emit, dtype=bool)
    truth = np.asarray(truth)
    if emit.shape != truth.shape:
        raise ValueError("emit and truth must share a shape")
    valid = np.ones(emit.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(emit.shape, bool) if known is None else np.asarray(known, bool)
    active = valid & ~known
    e = emit & active
    g = active & (np.asarray(truth) > 0)
    s = float(e.sum())
    n = int(g.sum())
    if n == 0:
        return Components(0.0, s, 0.0, 0, s, 0.0, 0.0)
    if s == 0:
        return Components(0.0, 0.0, float(n), n, 0.0, 0.0, 0.0)
    # distance from each pixel to the nearest emitted pixel (0 where emitted)
    d_pred = ndimage.distance_transform_edt(~e)
    tp = float(kernel(d_pred[g]).sum())
    d_truth = ndimage.distance_transform_edt(~g)
    m = float(kernel(d_truth[e]).sum())
    fp = s - m
    fn = float(n) - tp
    return Components(tp, fp, fn, n, s, m, dti_from_terms(tp, fp, fn, alpha, beta))


def dti_from_terms(tp: float, fp: float, fn: float, alpha: float = ALPHA, beta: float = BETA) -> float:
    """DTI from the three weighted counts (the published formula)."""
    return float(tp) / (float(tp) + alpha * float(fp) + beta * float(fn) + EPS)


def score(pred, truth, valid=None, known=None, **kw) -> float:
    return components(pred, truth, valid, known, **kw).dti


def marginal_bar(current_dti: float, alpha: float = ALPHA) -> float:
    """Break-even kernel weight for adding emission mass: k > alpha * DTI."""
    return alpha * float(current_dti)
