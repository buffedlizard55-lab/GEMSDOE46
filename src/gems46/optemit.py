"""Expected-credit emission: choose the dot set that maximises the *metric* directly.

Why this module exists
----------------------
The published metric is, for a binary prediction and a truth set G,

    DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw),
    TPw = Σ_{g∈G} max_{x: d(x,g)≤300 m} p(x)·k(d(x,g)),   k(d) = max(1 − d/300 m, 0)

and the competition masks the *already known* faults, so the scored truth is only the hidden set.
This repository previously emitted dots with a heuristic: blur the evidence field, rank pixels by
blurred value, accept while a Chebyshev minimum-distance rule passes, stop at a fixed budget
(:func:`gems46.emission.greedy_emit`).  That is a *proxy* for the real objective, and two of its
choices are demonstrably not metric-optimal:

1. a blurred field ranks by "credit of a fresh dot", not by "credit *gained* given the dots already
   placed", so clusters are over-emitted (the second dot in a cluster is charged 0.2 and often
   returns almost nothing — the metric takes a max over predictions);
2. the budget is fixed in advance instead of stopping at the metric's own break-even rule.

This module solves the actual sparse-metric problem.  With a per-pixel hidden-fault probability
``q`` (the field), the expected numerator for a dot set S is

    E[T](S) = Σ_x q(x) · c_S(x),        c_S(x) = max_{s∈S} k(d(x,s))

and the expected score is  E[DTI](S) = E[T](S) / (0.2·|S| + 0.8·Ĝ),  Ĝ = Σ_x q(x).

Marginal gain of adding a dot at s:

    Δ(s | S) = Σ_{o ∈ kernel} q(s+o) · max(0, k_o − c_S(s+o))

so the *exact* first-order condition to add a dot is Δ(s) > 0.2·E[DTI], and greedy maximisation of
the submodular coverage E[T] followed by that stop rule is the natural algorithm.  ``emit``
implements it with lazy re-evaluation against a refreshed candidate pool.

Every assumption is falsifiable and stated: independent per-pixel truth, the sparse identity
(no two dots best-cover the same truth pixel), and a calibrated ``q``.  If ``q`` is over-confident
by a factor λ the stop rule fires late by the same factor, which is why ``calibrate_scale`` exists
and why the receipt reports a sensitivity sweep instead of a single mass.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

R_PIXELS = 3.0


def kernel_offsets(radius_px: float = R_PIXELS) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Integer (dy, dx) offsets with k > 0, plus their kernel weights."""
    r = int(np.ceil(radius_px))
    dys, dxs, ks = [], [], []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = max(1.0 - float(np.hypot(dy, dx)) / radius_px, 0.0)
            if k > 0.0:
                dys.append(dy)
                dxs.append(dx)
                ks.append(k)
    return np.array(dys, int), np.array(dxs, int), np.array(ks, float)


@dataclass
class EmissionResult:
    mask: np.ndarray
    gains: np.ndarray          # marginal gain of each accepted dot, in kernel-credit units
    accepted: int
    stopped: str
    g_hat: float
    predicted_dti_curve: list   # (n, predicted_dti) sampled every `curve_every` acceptances
    order: list = None          # acceptance order as (y, x), for receipts and tests


def expected_credit(q: np.ndarray, radius_px: float = R_PIXELS) -> np.ndarray:
    """E[T] for a single dot at each pixel: the kernel-weighted sum of ``q`` around it."""
    dys, dxs, ks = kernel_offsets(radius_px)
    out = np.zeros_like(q, dtype=np.float32)
    for dy, dx, k in zip(dys, dxs, ks):
        out += np.float32(k) * _shift(q, dy, dx)
    return out


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """b[y, x] = a[y + dy, x + dx], zero-filled outside (exactly what a kernel tap needs)."""
    out = np.zeros_like(a)
    h, w = a.shape
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    if ys0 < ys1 and xs0 < xs1:
        out[ys0:ys1, xs0:xs1] = a[ys0 + dy: ys1 + dy, xs0 + dx: xs1 + dx]
    return out


def _kernel_patch(radius_px: float = R_PIXELS):
    """Dense (2r+1)² kernel array and a boolean mask of its non-zero support."""
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r: r + 1, -r: r + 1]
    k = np.maximum(1.0 - np.hypot(yy, xx) / radius_px, 0.0)
    return k.astype(np.float32)


def emit(q: np.ndarray, domain: np.ndarray, budget: int, *, radius_px: float = R_PIXELS,
         break_even_dti: float | None = 0.28, margin: float = 0.2,
         floor: float = 0.01, curve_every: int = 500,
         max_candidates: int = 800_000) -> EmissionResult:
    """Exact greedy expected-credit emission under the competition metric.

    Each iteration accepts the pixel with the largest *current* marginal gain
    Δ(s) = Σ_o q(s+o)·max(0, k_o − c(s+o)) and then updates the coverage field ``c`` inside the
    kernel's footprint (the only place where Δ can change).  Because Δ only ever decreases,
    pixels whose initial gain is below ``floor`` can never be accepted and are dropped from the
    candidate set up front (a pure speed optimisation: gains are monotone non-increasing).

    Parameters
    ----------
    q : float32 array in [0, 1]
        Calibrated hidden-fault probability per pixel (values outside ``domain`` are ignored).
    domain : bool array
        Emittable pixels: inside the footprint and not on the masked catalogue.
    budget : int
        Hard cap on the number of unit-mass dots.
    break_even_dti : float or None
        If given, stop when the best remaining marginal gain falls below
        ``margin · DTI(current set)`` (the metric's own first-order condition).  From the second
        dot onward the current DTI is used; the first dot is judged against ``break_even_dti``.
    floor : float
        Candidate floor on the initial gain (must stay well below ``margin·break_even_dti``).
    max_candidates : int
        Cap on the candidate set, applied by keeping the ``max_candidates`` pixels with the largest
        *initial* gain (a pure speed bound; every stored gain is an upper bound on that pixel's
        current gain, so a dropped pixel can only be accepted after the cap is exhausted).

    Returns
    -------
    EmissionResult with the binary mask and the marginal gain of every accepted dot.
    """
    q = np.asarray(q, dtype=np.float32)
    domain = np.asarray(domain, dtype=bool)
    if q.shape != domain.shape:
        raise ValueError("q and domain must share a shape")
    h, w = q.shape
    g_hat = float(q[domain].sum())
    if g_hat <= 0:
        return EmissionResult(np.zeros(q.shape, bool), np.zeros(0), 0, "empty-domain", 0.0, [], [])

    k_patch = _kernel_patch(radius_px)
    r = (k_patch.shape[0] - 1) // 2
    qd = np.where(domain, q, 0.0).astype(np.float32)
    pad_q = np.pad(qd, r, mode="constant")
    pad_c = np.zeros((h + 2 * r, w + 2 * r), dtype=np.float32)
    pad_dom = np.pad(domain, r, mode="constant", constant_values=False)

    initial = expected_credit(qd, radius_px).ravel()
    ok = domain.ravel() & (initial >= np.float32(floor))
    cand = np.flatnonzero(ok)
    if cand.size > int(max_candidates):
        thr = np.partition(initial[cand], cand.size - int(max_candidates))[cand.size - int(max_candidates)]
        cand = cand[initial[cand] >= thr]
    if cand.size == 0:
        return EmissionResult(np.zeros(q.shape, bool), np.zeros(0), 0, "no-candidates", g_hat, [], [])
    slot = np.full(q.size, -1, dtype=np.int32)
    slot[cand] = np.arange(cand.size, dtype=np.int32)
    gains = initial[cand].astype(np.float32)

    mask = np.zeros(q.shape, bool)
    accepted_gains: list[float] = []
    accepted_order: list[tuple[int, int]] = []
    curve: list[tuple[int, float]] = []
    stopped = "budget"
    accepted = 0
    running_credit = 0.0
    bar = margin * float(break_even_dti or 0.0)

    def local_gain(y: int, x: int) -> float:
        # E[Δ] = Σ_o q(x+o)·(k_o − c(x+o))⁺  — linear in q, because the metric's credit is a
        # max over predictions for each truth pixel (see the module docstring's derivation).
        qw = pad_q[y: y + 2 * r + 1, x: x + 2 * r + 1]
        cw = pad_c[y: y + 2 * r + 1, x: x + 2 * r + 1]
        dw = pad_dom[y: y + 2 * r + 1, x: x + 2 * r + 1]
        return float((qw * np.maximum(k_patch - cw, 0.0) * dw).sum())

    while accepted < budget:
        i = int(np.argmax(gains))
        if float(gains[i]) <= 0.0:
            stopped = "no-positive-gain"
            break
        pos = int(cand[i])
        y, x = divmod(pos, w)
        if mask[y, x]:
            gains[i] = 0.0
            continue
        # Lazy greedy needs an upper bound, not a guess: stored gains can only be *too high*,
        # so a candidate may be safely accepted or rejected only once its stored value is the
        # largest in the array (all other stored values then dominate their true gains).
        g = local_gain(y, x)
        gains[i] = g
        if g < float(gains.max()):
            continue                     # someone else's stale bound is higher: keep going
        if g <= 0.0:
            stopped = "no-positive-gain"
            break
        if break_even_dti is not None and g < bar:
            stopped = "break-even"
            break
        mask[y, x] = True
        accepted += 1
        running_credit += g
        accepted_gains.append(g)
        accepted_order.append((int(y), int(x)))
        if accepted % curve_every == 0:
            curve.append((accepted, running_credit / (0.2 * accepted + 0.8 * g_hat)))
        if break_even_dti is not None and accepted >= 1:
            bar = margin * (running_credit / (0.2 * accepted + 0.8 * g_hat))
        # place the dot in the coverage field and refresh every affected candidate gain
        ys, xs = slice(y, y + 2 * r + 1), slice(x, x + 2 * r + 1)
        pad_c[ys, xs] = np.maximum(pad_c[ys, xs], k_patch)
        gains[i] = 0.0
        y0, x0 = y - r, x - r
        for yy in range(max(0, y0), min(h, y0 + 2 * r + 1)):
            for xx in range(max(0, x0), min(w, x0 + 2 * r + 1)):
                if mask[yy, xx]:
                    continue
                j = slot[yy * w + xx]
                if j < 0:
                    continue
                gains[j] = local_gain(yy, xx)
    if accepted and (not curve or curve[-1][0] != accepted):
        curve.append((accepted, running_credit / (0.2 * accepted + 0.8 * g_hat)))
    return EmissionResult(mask, np.asarray(accepted_gains), accepted, stopped, g_hat, curve,
                          accepted_order)


def predicted_curve(gains: np.ndarray, g_hat: float, n_max: int | None = None) -> np.ndarray:
    """Predicted DTI(n) = Σ_{i<n} gain_i / (0.2n + 0.8·Ĝ) for the greedy gain sequence."""
    g = np.asarray(gains, float)
    if n_max is not None:
        g = g[: int(n_max)]
    if g.size == 0:
        return np.zeros(0)
    n = np.arange(1, g.size + 1)
    return np.cumsum(g) / (0.2 * n + 0.8 * float(g_hat))


def optimal_prefix(gains: np.ndarray, g_hat: float) -> tuple[int, float]:
    """n maximising the predicted DTI under the stated model, and that value."""
    curve = predicted_curve(gains, g_hat)
    if curve.size == 0:
        return 0, 0.0
    n = int(np.argmax(curve)) + 1
    return n, float(curve[n - 1])


def calibrate_scale(gains: np.ndarray, g_hat: float, target_dti: float, mass: int) -> float:
    """Global multiplier λ on ``q`` (hence on gains and Ĝ) that reproduces a target DTI at ``mass``.

    Used only to translate the field's *relative* ranking into the absolute credit scale that the
    metric's break-even rule needs.  The target is anchored to the family's measured live operating
    point, never to the proxy.
    """
    g = np.asarray(gains, float)
    if g.size < mass or g_hat <= 0 or target_dti <= 0:
        return 1.0
    t = float(g[:mass].sum())
    # DTI(λ) = λT/(0.2N + 0.8λĜ) = target  ->  λ (T − 0.8·target·Ĝ) = 0.2·target·N
    denom = t - 0.8 * target_dti * g_hat
    if denom <= 0:
        return 1.0
    return float(0.2 * target_dti * mass / denom)


def analytic_ceiling(n_dots: int, truth_px: float) -> float:
    """G/(0.2N + 0.8G): the largest DTI obtainable with N unit-mass dots (T ≤ G)."""
    return truth_px / (0.2 * n_dots + 0.8 * truth_px)


def thin_by_gain(mask: np.ndarray, order: np.ndarray, keep: int) -> np.ndarray:
    """Keep the ``keep`` dots with the largest supplied ordering score (helper for ablations)."""
    ys, xs = np.nonzero(mask)
    if keep >= ys.size:
        return mask.copy()
    idx = np.argsort(-np.asarray(order))[:keep]
    out = np.zeros_like(mask)
    out[ys[idx], xs[idx]] = True
    return out


def local_max_filter(a: np.ndarray, size: int = 3) -> np.ndarray:
    """Maximum filter used to test that the emitter never places two dots inside one kernel cell."""
    return ndimage.maximum_filter(a, size=size)
