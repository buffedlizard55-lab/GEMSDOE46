"""Emission: turning a belief field into the dot set the published metric rewards.

The rule implemented here is a direct consequence of the metric algebra in
``src/gems46/metric.py`` (transcribed from the official problem description):

    DTI = T / (T + a*FP + b*FN),   a = 0.2, b = 0.8,   R = 3 px (300 m), kernel k(d) = (1 - d/R)+.

Adding one unit of mass at pixel x changes the two numerator-relevant quantities by
``dT = c(x)`` (the kernel credit the new dot is the arg-max for, summed over truth pixels) and
``d(S - M) = 1 - k(x)`` (the dot's own distance-to-truth weight).  Hence

    dDTI > 0   <=>   c(x) > a * DTI * (1 + (1 - k(x))/c(x))   ~   a * DTI   when k(x) -> 1,

i.e. a dot pays only when its expected credit exceeds ``0.2 * DTI`` (~0.055 at the live operating
point of the 0.26-0.28 files).  Two consequences drive the code below:

1. **Mass must be sparse.**  A probability surface charges 0.2 per unit mass everywhere it is
   emitted, including where it delivers no credit; only dots do not.
2. **Dots must not shadow each other.**  ``T`` is a max over predictions, so two dots closer than
   the kernel support can earn credit for the same truth pixel; the shadowed dot pays the 0.2 tax
   and returns nothing.  A minimum separation of ``min_dist`` pixels removes the shadowed copies.

The empirical counterpart of the marginal rule - the score->credit calibration and the resulting
budget - lives in the run receipt, not in this file: the emission code only takes a field, a
domain, a separation and a budget, so that the same rule can be applied identically to a candidate
field and to a comparator field.
"""

from __future__ import annotations

import numpy as np

from gems46 import metric as M


def disk_offsets(radius: int) -> np.ndarray:
    rr, cc = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    m = (rr * rr + cc * cc) <= radius * radius
    return np.c_[rr[m], cc[m]]


def emit_dots(field: np.ndarray, domain: np.ndarray, budget: int, min_dist: int = 3,
              score_floor: float | None = None, candidate_cap: int = 4_000_000) -> np.ndarray:
    """Greedy, max-credit-safe dot emission.

    Pixels are considered in descending order of ``field``; a candidate is accepted when it is not
    inside the minimum-separation disk of an already accepted dot, which is exactly the shadowing
    condition the metric's max-operation implies.  ``domain`` already encodes every mask the
    experiment applies (footprint, catalogue masking, collar), so masking is never implicit.
    """
    field = np.asarray(field, dtype=np.float32)
    domain = np.asarray(domain, dtype=bool)
    if field.shape != domain.shape:
        raise ValueError("field and domain must share a shape")
    cand = np.flatnonzero((domain & np.isfinite(field)).reshape(-1))
    values = field.reshape(-1)[cand]
    if score_floor is not None:
        keep = values >= float(score_floor)
        cand, values = cand[keep], values[keep]
    if cand.size == 0 or budget <= 0:
        return np.zeros(field.shape, dtype=bool)
    if cand.size > candidate_cap:
        part = np.argpartition(-values, candidate_cap)[:candidate_cap]
        cand, values = cand[part], values[part]
    order = np.argsort(-values, kind="stable")
    cand = cand[order]
    H, W = field.shape
    rows, cols = np.divmod(cand, W)
    emit = np.zeros(field.shape, dtype=bool)
    blocked = np.zeros(field.shape, dtype=bool)
    offs = disk_offsets(int(min_dist))
    accepted = 0
    for r, c in zip(rows, cols):
        if blocked[r, c]:
            continue
        emit[r, c] = True
        accepted += 1
        rr = np.clip(r + offs[:, 0], 0, H - 1)
        cc = np.clip(c + offs[:, 1], 0, W - 1)
        blocked[rr, cc] = True
        if accepted >= budget:
            break
    return emit


def calibrate_score_to_credit(scores: np.ndarray, credit: np.ndarray, n_bins: int = 20):
    """Monotone empirical map score -> E[kernel credit] measured on the calibration rows.

    Returns (bin_edges, bin_credit) with the caller responsible for interpolating.  Bins with no
    samples are filled with the previous bin's value so the map stays monotone enough for the
    budget rule.
    """
    s = np.asarray(scores, dtype=np.float64)
    c = np.asarray(credit, dtype=np.float64)
    if s.size == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 0.0])
    qs = np.quantile(s, np.linspace(0, 1, n_bins + 1))
    qs = np.unique(qs)
    idx = np.clip(np.searchsorted(qs, s, side="right") - 1, 0, qs.size - 2)
    vals = np.zeros(qs.size - 1)
    for i in range(qs.size - 1):
        sel = idx == i
        vals[i] = c[sel].mean() if sel.any() else (vals[i - 1] if i else 0.0)
    return qs, vals


def credit_at(qs: np.ndarray, vals: np.ndarray, score: np.ndarray) -> np.ndarray:
    idx = np.clip(np.searchsorted(qs, score, side="right") - 1, 0, vals.size - 1)
    return vals[idx]


def predicted_dti(credits_sorted: np.ndarray, own_credit_sorted: np.ndarray,
                  truth_px: float) -> np.ndarray:
    """Model DTI(n) for a sparse dot set, as a function of budget n.

    With ``credits_sorted`` the per-dot expected credit ``c_i`` (descending) and
    ``own_credit_sorted`` the per-dot ``k(x_i)``:
        T(n)  = sum_{i<n} c_i
        S(n)  = n,  M(n) = sum_{i<n} k(x_i)   (the dot's own best-coverage weight)
        D(n)  = 0.2*(T(n) + S(n) - M(n)) + 0.8*G   (G = truth pixels, corrected by alpha/beta)
    """
    n = np.arange(1, credits_sorted.size + 1)
    T = np.cumsum(credits_sorted)
    Mc = np.cumsum(own_credit_sorted)
    D = 0.2 * (T + n - Mc) + 0.8 * float(truth_px)
    return T / np.maximum(D, 1e-9)
