"""Official Distance-Weighted Tversky Index (DTI) for the DOE GEMS Prize Challenge.

Transcribed line by line from the official problem description, retrieved 2026-10-06 UTC:
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric

    k(d) = (1 - d/R)_+ = max(1 - d/R, 0),   R = 300 m = 3 px at the 100 m grid

    TPw = sum_{g in G} max_{x : d(x,g) <= R} p(x) k(d(x,g))
    FPw = sum_{x : p(x) > 0} p(x) [ 1 - max_{g in G} k(d(x,g)) ]
    FNw = sum_{g in G} [ 1 - max_{x : d(x,g) <= R} p(x) k(d(x,g)) ]
    DTI = TPw / (TPw + alpha FPw + beta FNw + eps),   alpha = 0.2, beta = 0.8

Organiser clarifications applied here (DrivenData staff, forum thread 11516, 2026-09-16):
  * "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation,
    so they do not count towards penalty terms."
  * "Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults."
This is implemented by passing ``known`` (a boolean grid of the published catalogue, dilated as
used by the scorer is *not* assumed: only the catalogue pixels themselves are excluded).

Identities used for fast evaluation (proved by the brute-force transcription in tests/):
    FNw = |G| - TPw
    FPw = S - M   with S = sum_x p(x) and M = sum_x p(x) * max_g k(d(x,g))
so that
    DTI = TPw / ( 0.2 (TPw + FPw) + 0.8 |G| + eps )
and the first-order marginal rule for adding one unit of mass at a pixel whose best-kernel weight
to the truth is k is
    d(DTI) > 0  <=>  k > 0.2 * DTI.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_M: float = 300.0
PIXEL_M: float = 100.0
RADIUS_PX: float = RADIUS_M / PIXEL_M  # 3.0
EPS: float = 1e-12


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
    return Components(tp, fp, fn, n, s, m, dti(tp, fp, fn, alpha, beta))


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
    # distance from each pixel to the nearest emitted pixel (0 where emitted)
    d_pred = ndimage.distance_transform_edt(~e)
    tp = float(kernel(d_pred[g]).sum())
    d_truth = ndimage.distance_transform_edt(~g)
    m = float(kernel(d_truth[e]).sum())
    fp = s - m
    fn = float(n) - tp
    return Components(tp, fp, fn, n, s, m, dti(tp, fp, fn, alpha, beta))


def dti(tp: float, fp: float, fn: float, alpha: float = ALPHA, beta: float = BETA) -> float:
    """DTI from the three weighted counts (the published formula)."""
    return float(tp) / (float(tp) + alpha * float(fp) + beta * float(fn) + EPS)


def score(pred, truth, valid=None, known=None, **kw) -> float:
    return components(pred, truth, valid, known, **kw).dti


def marginal_bar(current_dti: float, alpha: float = ALPHA) -> float:
    """Break-even kernel weight for adding emission mass: k > alpha * DTI."""
    return alpha * float(current_dti)
