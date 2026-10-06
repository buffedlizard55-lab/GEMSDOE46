"""Distance-Weighted Tversky Index (DTI) for the DOE GEMS Prize — independent implementation.

Transcribed from the official problem description (DrivenData page 967,
"Mathematical representation", read 2026-10-06) plus the official staff ruling that
*known* USGS/INGENIOUS fault pixels are masked out of scoring (community thread
11516, quoted in `docs/sources.html`).

Published definitions (R = 300 m = 3 px at 100 m):

    k(d)  = max(1 - d/R, 0)
    TP_w  = sum_{g in G} max_{x : d(x,g) <= R} p(x) * k(d(x,g))
    FP_w  = sum_{x : p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w  = sum_{g in G} [1 - max_{x : d(x,g) <= R} p(x) * k(d(x,g))]
    DTI   = TP_w / (TP_w + alpha * FP_w + beta * FN_w + eps),  alpha=0.2, beta=0.8

Two exact identities are used throughout the project and are asserted in `tests/`:

    FN_w  = |G| - TP_w                                        (I1)
    FP_w  = S - M, S = sum_x p(x), M = sum_x p(x) * max_g k    (I2)

so that, writing T = TP_w,

    DTI = T / (0.2 * (T + S - M) + 0.8 * |G|)                  (I3)

Marginal rule (differentiate I3 in one unit of mass at kernel credit k, correct to
first order in the DTI change):

    adding mass at x raises DTI  <=>  k_eff(x) > 0.2 * DTI     (I4)

where k_eff(x) = dT/d(mass) - 0.2*DTI*(1 - dM/d(mass)) is evaluated exactly in
`marginal_gain`; (I4) is the small-mass limit used for planning.
"""
from __future__ import annotations

import numpy as np

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
EPS = 1e-12


def kernel(d: np.ndarray | float, radius: float = RADIUS_PX) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0); distances in pixels (1 px = 100 m)."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def shadow_offsets(radius: float = RADIUS_PX) -> list[tuple[int, int, float]]:
    """(dy, dx, k) for every integer offset within the kernel support."""
    r = int(np.ceil(radius))
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k > 0.0:
                out.append((dy, dx, k))
    return out


OFFSETS = shadow_offsets()


def dti_from_parts(tp: float, fp: float, fn: float, alpha: float = ALPHA, beta: float = BETA) -> float:
    return float(tp / (tp + alpha * fp + beta * fn + EPS))


def mask_known(pred: np.ndarray, truth: np.ndarray, known: np.ndarray | None,
               footprint: np.ndarray | None = None):
    """Apply the official masks: outside the footprint and on known faults, p := 0.

    Returns (p, g, active) with p float32 (masked prediction) and g bool (scored truth).
    """
    p = np.asarray(pred, dtype=np.float32)
    active = np.isfinite(p)
    if footprint is not None:
        active &= np.asarray(footprint, bool)
    if known is not None:
        active &= ~np.asarray(known, bool)
    pm = np.where(active, p, 0.0).astype(np.float32)
    g = np.asarray(truth, bool)
    if known is not None:
        g = g & ~np.asarray(known, bool)
    if footprint is not None:
        g = g & np.asarray(footprint, bool)
    return pm, g, active


def coverage_field(pred: np.ndarray, radius: float = RADIUS_PX, offsets=None) -> np.ndarray:
    """C(x) = max over predicted pixels y within R of p(y)*k(d(x,y)).

    This is the per-pixel kernel credit available at x; TP_w = sum_g C(g) over the
    truth set, which makes C the object the leaderboard score is a functional of.
    """
    p = np.asarray(pred, dtype=np.float32)
    offs = OFFSETS if offsets is None else offsets
    c = np.zeros_like(p, dtype=np.float32)
    for dy, dx, k in offs:
        sh = np.roll(np.roll(p, -dy, axis=0), -dx, axis=1) * np.float32(k)
        # roll wraps; the wrapped strip cannot contain valid neighbours, so zero it
        if dy > 0:
            sh[-dy:, :] = 0.0
        elif dy < 0:
            sh[:-dy, :] = 0.0
        if dx > 0:
            sh[:, -dx:] = 0.0
        elif dx < 0:
            sh[:, :-dx] = 0.0
        np.maximum(c, sh, out=c)
    return c


def components(pred: np.ndarray, truth: np.ndarray, known: np.ndarray | None = None,
               footprint: np.ndarray | None = None, offsets=None) -> dict:
    """Exact TP_w / FP_w / FN_w / DTI by shift-max (TP) + nearest-truth distance (FP)."""
    p, g, _ = mask_known(pred, truth, known, footprint)
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0, mass=float(p.sum()))
    tp = float(coverage_field(p, offsets=offsets)[g].sum())
    fn = float(n) - tp
    # nearest truth distance for every pixel (metric: Euclidean, R = 3 px)
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~g)
    fp = float((p * (1.0 - kernel(d))).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n,
                dti=dti_from_parts(tp, fp, fn), coverage=tp / n, mass=float(p.sum()))


def components_bruteforce(pred: np.ndarray, truth: np.ndarray, known: np.ndarray | None = None,
                          radius: float = RADIUS_PX) -> dict:
    """Literal O(|G|*|P|) transcription of the published equations (small grids only)."""
    p, g, _ = mask_known(pred, truth, known, None)
    gs = np.argwhere(g)
    xs = np.argwhere(p > 0)
    tp = 0.0
    for gy, gx in gs:
        best = 0.0
        for y, x in xs:
            d = float(np.hypot(y - gy, x - gx))
            if d <= radius:
                best = max(best, float(p[y, x]) * float(kernel(d, radius)))
        tp += best
    fn = float(len(gs)) - tp
    fp = 0.0
    for y, x in xs:
        kmax = 0.0
        for gy, gx in gs:
            kmax = max(kmax, float(kernel(float(np.hypot(y - gy, x - gx)), radius)))
        fp += float(p[y, x]) * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=len(gs), dti=dti_from_parts(tp, fp, fn))


def marginal_gain_full(tp: float, fp: float, fn: float, dt: float, dm: float,
                       mass: float = 1.0) -> float:
    """Return the exact change in DTI when one unit of prediction mass is added."""
    den = tp + ALPHA * fp + BETA * fn + EPS
    t2 = tp + dt
    f2 = fp + (mass - dm)
    fn2 = fn - dt
    den2 = t2 + ALPHA * f2 + BETA * fn2 + EPS
    return float(t2 / den2 - tp / den)
