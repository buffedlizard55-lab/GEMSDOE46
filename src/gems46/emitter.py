"""Metric-aware sparse emitter with an explicit **spacing sweep**.

The object swept is the same one the family swept by hand as ``dot_thin(r)``
(d1.5, d2.8, ...): a **minimum-separation radius** ``r`` in pixels between emitted
dots.  This module generalises that sweep in two ways that follow from the
official metric:

1. **Ordering.**  Candidates are ordered by *expected marginal metric credit*

        dT(x) = sum_delta  pi(x + delta) * k(||delta||)

   with ``k`` the official triangular kernel (300 m support) and ``pi`` the
   belief field.  Ordering by ``pi`` alone (what ``dot_thin`` does on a ridge
   raster) emits several parallel copies of a 3-px-wide ridge and pays the
   0.2-per-dot false-positive tax on each of them; ordering by ``dT`` collapses
   the ridge to its metric-optimal crest first.  This is the first iteration of
   the exact marginal-credit greedy used by the family's EDGE emitter
   (``emitter_opt.py``), and it is cheap enough to run for every sweep arm.
2. **Explicit spacing parameter.**  ``r`` is a genuine sweep dimension:
   ``r = 1`` reproduces near-dense emission, ``r = 8`` (800 m) reproduces the
   very sparse end.  Every arm is a legal, complete submission.

Stopping rule
-------------
The metric's own first-order condition (see ``metric.py`` and
``docs/SCORE_ANALYSIS.md``) is that adding a unit of mass pays iff its realised
kernel credit exceeds ``0.2 * s`` where ``s`` is the current index.  We therefore
stop an arm when ``dT(x) < 0.2 * s_floor`` for a conservative floor, and also
when the candidate list is exhausted.  ``s_floor`` is a *pre-declared* constant,
not a tuned quantity, so it cannot be selected on the holdout.
"""

from __future__ import annotations

import numpy as np

R_PIXELS = 3.0
ALPHA = 0.2


def kernel_ball(radius_pixels: float = R_PIXELS):
    """Offsets and triangular kernel values inside the support."""
    rad = int(np.ceil(radius_pixels))
    rr, cc = np.mgrid[-rad : rad + 1, -rad : rad + 1]
    dist = np.sqrt(rr * rr + cc * cc)
    m = dist <= radius_pixels
    dy = rr[m].astype(np.int32)
    dx = cc[m].astype(np.int32)
    k = np.maximum(1.0 - dist[m] / radius_pixels, 0.0).astype(np.float32)
    return dy, dx, k


def expected_credit(pred: np.ndarray, belief: np.ndarray,
                    radius_pixels: float = R_PIXELS) -> np.ndarray:
    """dT(x) = sum_delta belief(x+delta) * k(||delta||), computed on the full grid."""
    dy, dx, k = kernel_ball(radius_pixels)
    h, w = belief.shape
    out = np.zeros((h, w), dtype=np.float32)
    for oy, ox, kv in zip(dy, dx, k):
        ys_src = slice(max(0, -oy), h - max(0, oy))
        xs_src = slice(max(0, -ox), w - max(0, ox))
        ys_dst = slice(max(0, oy), h - max(0, -oy))
        xs_dst = slice(max(0, ox), w - max(0, -ox))
        out[ys_dst, xs_dst] += belief[ys_src, xs_src] * kv
    if pred is not None:
        out *= pred  # only allow emission where the caller permits it
    return out


def nms_thin(score: np.ndarray, allow: np.ndarray, spacing: float,
             max_dots: int = 200_000, floor: float = 0.0, top_k: int | None = None):
    """Greedy NMS thinning of ``score`` with minimum separation ``spacing`` pixels.

    Returns an (n, 2) int32 array of accepted dot centres in descending-score order.

    NOTE ON ``top_k`` (a real bug fixed 2026-10-06).  This used to default to the
    packing limit ``~1.155 * area / spacing^2`` times 2.5, on the theory that no
    more than that many dots can be accepted.  The bound is true but it does *not*
    bound the number of *candidates* a score-ordered greedy must examine: the
    highest-scoring cells are spatially clustered (they trace the same ridges), so
    after a few thousand accepted dots the entire truncated candidate list sits
    inside already-blocked balls and the emission stops far short of the arm the
    stopping rule describes.  Measured on the 5,167,373-px footprint at r=8 px the
    truncated run emitted 5,596 dots against 89,000+ when every above-floor cell is
    considered.  ``top_k=None`` (the default) now means *no truncation*: the greedy
    sees every cell above ``floor``.  Passing an integer still truncates and is
    documented as lossy.
    """
    s = np.where(allow, score, -np.inf).ravel()
    if top_k is not None and np.isfinite(s).sum() > top_k:
        cut = np.argpartition(-s, top_k)[:top_k]
        keep = np.zeros(s.shape, dtype=bool)
        keep[cut] = True
        keep &= s > floor
        s = np.where(keep, s, -np.inf)
    order = np.argsort(-s, kind="stable")
    w = score.shape[1]
    blocked = np.zeros(score.shape, dtype=bool)
    rad = int(np.ceil(spacing))
    dy, dx, _k = kernel_ball(spacing)
    acc_r = []
    acc_c = []
    for idx in order:
        v = s[idx]
        if not np.isfinite(v) or v <= floor:
            break
        y, x = divmod(int(idx), w)
        if blocked[y, x]:
            continue
        acc_r.append(y)
        acc_c.append(x)
        ys = y + dy
        xs = x + dx
        ok = (ys >= 0) & (ys < score.shape[0]) & (xs >= 0) & (xs < w)
        blocked[ys[ok], xs[ok]] = True
        if len(acc_r) >= max_dots:
            break
    return np.asarray(acc_r, dtype=np.int32), np.asarray(acc_c, dtype=np.int32)


def emit_positions(belief: np.ndarray, allow: np.ndarray, spacing: float,
                   index_floor: float = 0.26, max_dots: int = 200_000,
                   radius_pixels: float = R_PIXELS):
    """One sweep arm: order by expected credit, thin with ``spacing``, stop at the bar."""
    score = expected_credit(allow, belief, radius_pixels)
    floor = ALPHA * index_floor  # 0.2 * s_floor
    return nms_thin(score, allow, spacing, max_dots=max_dots, floor=floor)
