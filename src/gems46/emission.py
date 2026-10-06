"""Emission: turning an evidence field into a [0, 1] prediction raster under the metric's own algebra.

Theory (all steps are consequences of the published metric; see gems46.metric):

(1) Binary emission is optimal for a *fixed* support.  If p -> lambda p then
    DTI = lambda*T / (lambda*T + 0.2*lambda*FP + 0.8*FN) which is increasing in lambda, so the
    best value on any chosen pixel is 1.0.  Everything here therefore emits 0/1.

(2) Marginal rule: adding a unit of mass at a pixel whose best kernel weight to the truth set is k
    raises DTI exactly when k > alpha * DTI = 0.2 * DTI.  At a live score of ~0.26-0.33 the bar is
    0.052-0.067, so mass whose expected credit is below ~0.05 should not be emitted at all.

(3) Dot spacing.  For a predicted trace of unit length that is collinear with truth, dots every s
    pixels give T = q*L*(1 - s/12) (the triangular kernel leaves an average weight 1 - s/12 on the
    segment between two dots, s <= 6 px) and S = L/s, M = T, hence
        DTI(s) = q*L*(1 - s/12) / (0.2*L/s + 0.8*G).
    The optimum is therefore set by the *marginal* credit, not by the spacing itself:
    :func:`optimal_budget` maximises DTI(n) = T(n)/(0.2n + 0.8G) exactly, and the exact condition
    for the n-th pixel to help is e_n > 0.2 * DTI(n).  Spacing enters only through mutual
    shadowing: two dots closer than the kernel support can earn credit for the *same* truth pixel,
    and the metric takes the max, so the shadowed dot pays the 0.2 FP tax for nothing.

(4) Mass budget.  Greedy maximum-coverage of the evidence field, restricted to pixels whose
    expected credit exceeds the bar, with a hard spacing constraint.  ``greedy_emit``.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .metric import ALPHA


def dti_of_prefix(credits: np.ndarray, truth_px: float, n: int | None = None) -> float:
    """DTI of the top-``n`` emission under the stated model.

    Model (stated so it can be falsified):
      * each emitted pixel has unit mass and an *expected credit* ``e_i`` (its probability of being
        within the kernel support of a hidden fault, weighted by the kernel);
      * credits are sorted descending, so T(n) = sum_{i<n} e_i, S(n) = n;
      * M(n) = T(n) is the conservative assumption that every credit-earning pixel best-covers a
        distinct truth pixel (true while emissions are sparser than the truth line);
      * G = truth_px is the hidden truth size (calibrated, with uncertainty, from the group's own
        scored submissions - see registry/emission_model.json).
    Then DTI(n) = T(n) / (0.2 * (T(n) + S(n) - M(n)) + 0.8 G) = T(n) / (0.2 n + 0.8 G).
    """
    c = np.asarray(credits, dtype=np.float64)
    n = c.size if n is None else min(int(n), c.size)
    if n <= 0:
        return 0.0
    T = float(c[:n].sum())
    if T <= 0:
        return 0.0
    return T / (0.2 * n + 0.8 * float(truth_px))


def optimal_budget(credits: np.ndarray, truth_px: float, max_budget: int | None = None) -> dict:
    """Budget that maximises :func:`dti_of_prefix` - and the exact break-even rule that defines it.

    DTI(n) is non-decreasing at step n  <=>  e_n > 0.2 * DTI(n),  exactly, under the model above.
    Because credits are sorted descending and DTI(n) typically rises, the optimum is the last n
    whose credit still clears 0.2 * DTI(n); we locate it by evaluating the (convex-then-decreasing)
    sequence exactly rather than by trusting that shape.
    """
    c = np.asarray(credits, dtype=np.float64)
    if max_budget is not None and c.size > max_budget:
        c = c[: int(max_budget)]
    if c.size == 0:
        return dict(budget=0, dti=0.0, credit_last=0.0, break_even=0.0)
    prefix = np.cumsum(c)
    n = np.arange(1, c.size + 1)
    denom = 0.2 * n + 0.8 * float(truth_px)
    dti = prefix / denom
    k = int(np.argmax(dti))
    return dict(budget=k + 1, dti=float(dti[k]), credit_last=float(c[k]),
                marginal_at_budget=float(c[k]), break_even=float(0.2 * dti[k]),
                dti_at_zero=0.0, credit_mean=float(prefix[k] / (k + 1)),
                credit_first=float(c[0]), n_evaluated=int(c.size))


def _rank_candidates(field: np.ndarray, domain: np.ndarray, smooth_px: float, top_k: int | None):
    """Rank candidate pixels by 'coverage demand': the field blurred by the credit scale."""
    f = np.where(domain, np.nan_to_num(field, nan=0.0), 0.0).astype(np.float32)
    if smooth_px and smooth_px > 0:
        demand = ndimage.gaussian_filter(f, smooth_px, mode="constant")
    else:
        demand = f
    n_px = int(domain.sum())
    k = n_px if top_k is None else min(int(top_k), n_px)
    flat = demand.ravel()
    cand = np.flatnonzero(domain.ravel())
    vals = flat[cand]
    keep = vals > 0
    cand = cand[keep]
    vals = vals[keep]
    if cand.size > k:
        idx = np.argpartition(-vals, k - 1)[:k]
        cand, vals = cand[idx], vals[idx]
    order = np.argsort(-vals, kind="stable")
    return cand[order], vals[order]


def greedy_emit(field: np.ndarray, domain: np.ndarray, budget: int, min_dist: int = 3,
                smooth_px: float = 1.85, top_k: int | None = None, dti_estimate: float = 0.28,
                min_credit: float | None = None):
    """Spacing-constrained greedy emission of ``budget`` unit-mass pixels.

    Parameters
    ----------
    field        : evidence in [0, 1] on the full raster grid (higher = more likely a fault).
    domain       : boolean grid of emittable pixels (footprint minus masked catalogue pixels).
    budget       : maximum number of emitted pixels (unit mass each).
    min_dist     : minimum Chebyshev separation between accepted pixels (px). 2 -> 1 dot / 2 px,
                   3 -> 1 dot / 3 px.  See ``optimal_spacing``.
    smooth_px    : blur applied to the evidence before ranking (matched filter for partial credit).
    top_k        : candidate cap (memory/speed only).
    min_credit   : optional hard floor; candidates whose *normalised* evidence is below it are
                   never emitted (the metric's break-even rule in normalised units).

    Returns (mask, trace) with trace a list of dicts for the receipt.
    """
    h, w = field.shape
    candidate, value = _rank_candidates(field, domain, smooth_px, top_k)
    if min_credit is not None:
        if value.size and value.max() > 0:
            keep = value >= (min_credit * value.max())
            candidate, value = candidate[keep], value[keep]
    occ = np.zeros((h, w), dtype=bool)
    emitted = np.zeros((h, w), dtype=bool)
    r = int(min_dist)
    accepted = 0
    trace = []
    for idx, pos in enumerate(candidate):
        if accepted >= budget:
            break
        y, x = divmod(int(pos), w)
        y0, y1 = max(0, y - r + 1), min(h, y + r)
        x0, x1 = max(0, x - r + 1), min(w, x + r)
        if occ[y0:y1, x0:x1].any():
            continue
        occ[y0:y1, x0:x1] = True
        emitted[y, x] = True
        accepted += 1
        if len(trace) < 8:
            trace.append(dict(y=int(y), x=int(x), rank=int(idx), value=float(value[idx])))
    trace.append(dict(emitted=int(accepted), budget=int(budget), min_dist=int(r),
                      candidates=int(candidate.size)))
    return emitted, trace


def thinner(mask: np.ndarray, min_dist: int = 3, score: np.ndarray | None = None) -> np.ndarray:
    """Score-blind or score-aware thinning of a binary mask: keep pixels at least ``min_dist`` apart."""
    ys, xs = np.nonzero(mask)
    if score is not None:
        order = np.argsort(-np.asarray(score, dtype=np.float64)[mask], kind="stable")
        ys, xs = ys[order], xs[order]
    keep = np.zeros(mask.shape, bool)
    occ = np.zeros(mask.shape, bool)
    h, w = mask.shape
    r = int(min_dist)
    for y, x in zip(ys, xs):
        y0, y1 = max(0, y - r + 1), min(h, y + r)
        x0, x1 = max(0, x - r + 1), min(w, x + r)
        if occ[y0:y1, x0:x1].any():
            continue
        occ[y0:y1, x0:x1] = True
        keep[y, x] = True
    return keep


def normalise(x: np.ndarray, mask: np.ndarray | None = None, lo_pct: float = 0.0,
              hi_pct: float = 99.9) -> np.ndarray:
    """Robust min-max normalisation to [0, 1] over the valid (masked) domain."""
    x = np.asarray(x, dtype=np.float32)
    v = x if mask is None else x[mask]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return np.zeros_like(x)
    lo = float(np.percentile(v, lo_pct))
    hi = float(np.percentile(v, hi_pct))
    if hi <= lo:
        hi = lo + 1e-6
    out = np.clip((np.nan_to_num(x, nan=lo) - lo) / (hi - lo), 0.0, 1.0)
    return out.astype(np.float32)
