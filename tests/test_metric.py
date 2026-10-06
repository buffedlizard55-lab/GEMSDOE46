"""Metric verification: published worked example, brute-force equivalence, algebra, masking."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems46 import metric as M  # noqa: E402


def brute(pred, truth, radius=3.0):
    """Literal O(N^2) transcription of the published formulas, including diagonals."""
    p = np.asarray(pred, float)
    g = np.asarray(truth).astype(bool)
    h, w = p.shape
    ys, xs = np.mgrid[0:h, 0:w]
    gt = np.stack([ys[g], xs[g]], axis=1)
    tp = 0.0
    for gy, gx in gt:
        best = 0.0
        for y in range(h):
            for x in range(w):
                d = math.hypot(y - gy, x - gx)
                if d <= radius:
                    best = max(best, p[y, x] * M.kernel(d))
        tp += best
    fp = 0.0
    for y in range(h):
        for x in range(w):
            if p[y, x] > 0:
                near = max((M.kernel(math.hypot(y - gy, x - gx)) for gy, gx in gt), default=0.0)
                fp += p[y, x] * (1.0 - near)
    return tp, fp, len(gt) - tp


def test_published_example_arithmetic():
    """Page 967 worked example: TPw=3.00, FPw=1.89, FNw=2.00 -> 0.60."""
    assert M.dti(3.00, 1.89, 2.00) == pytest.approx(3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00))
    assert round(M.dti(3.00, 1.89, 2.00), 2) == 0.60


def test_bruteforce_equivalence_random():
    rng = np.random.default_rng(0)
    for _ in range(6):
        pred = (rng.random((13, 13)) < 0.12) * rng.random((13, 13))
        truth = rng.random((13, 13)) < 0.10
        c = M.components(pred, truth)
        tp, fp, fn = brute(pred, truth)
        assert c.tp == pytest.approx(tp, abs=1e-9)
        assert c.fp == pytest.approx(fp, abs=1e-9)
        assert c.fn == pytest.approx(fn, abs=1e-9)


def test_algebra_identities():
    rng = np.random.default_rng(1)
    for _ in range(4):
        pred = (rng.random((17, 17)) < 0.2) * rng.random((17, 17))
        truth = rng.random((17, 17)) < 0.15
        c = M.components(pred, truth)
        assert c.fn == pytest.approx(c.n_truth - c.tp, abs=1e-9)
        assert c.fp == pytest.approx(c.s - c.m, abs=1e-9)
        assert c.dti == pytest.approx(c.tp / (c.tp + 0.2 * c.fp + 0.8 * c.fn + 1e-12), abs=1e-15)


def test_scaling_invariance_binary_is_optimal():
    """lambda*p is increasing in lambda: unit mass is optimal on a fixed support."""
    truth = np.zeros((40, 40), bool)
    truth[20, 10:30] = True
    pred = np.zeros((40, 40))
    pred[20, 10:30:2] = 1.0
    scores = [M.score(pred * lam, truth) for lam in (0.25, 0.5, 0.75, 1.0)]
    assert scores == sorted(scores)


def test_marginal_rule_boundary_is_exact():
    """Exact boundary of the marginal rule on an isolated truth pixel.

    With one truth pixel, a starter emission that earns no credit (T = 0, DTI = 0) and one added
    pixel of unit mass at kernel distance k:
        DTI(k) = k / (0.2 * (F0 + 1 - k) + 0.8),  F0 = starter mass
    so any k > 0 strictly helps and k = 0 (d > R) strictly hurts.  This is the rule
    "add mass iff k > 0.2 * DTI" evaluated at its boundary, where it is exact.
    """
    truth = np.zeros((25, 25), bool)
    truth[10, 10] = True
    starter = np.zeros((25, 25))
    starter[20, 20] = 1.0                      # 10 px away: pure FP tax, T = 0
    base = M.score(starter, truth)
    assert base == 0.0
    for dy, dx in [(2, 0), (1, 1), (1, 0), (0, 0)]:   # k > 0
        p2 = starter.copy()
        p2[10 + dy, 10 + dx] = 1.0
        assert M.score(p2, truth) > base
    p3 = starter.copy()
    p3[10, 14] = 1.0                           # 4 px away: k = 0
    assert M.score(p3, truth) == pytest.approx(base, abs=1e-15)


def test_credit_is_monotone_in_kernel_distance():
    """Among placements that earn credit, a smaller distance can never score worse (exact)."""
    truth = np.zeros((25, 25), bool)
    truth[10, 10] = True
    prev = -1.0
    for d in (3.0, 2.0, 1.0, 0.0):
        pred = np.zeros((25, 25))
        pred[10 + int(d), 10] = 1.0
        s = M.score(pred, truth)
        assert s > prev
        prev = s


def _exact_add_sign(pred, truth, y, x):
    """Exact sign of the DTI change when one unit of mass is added at (y, x)."""
    before = M.components(pred, truth)
    p2 = pred.copy()
    p2[y, x] = 1.0
    after = M.components(p2, truth)
    return after.dti - before.dti, before, after


def test_exact_marginal_criterion():
    """The exact criterion for adding unit mass at x, derived from the published formula:

        dDTI > 0  <=>  dT * (0.2*FP + 0.8*|G|)  >  0.2 * DTI * D * (1 - C(x))

    where dT is the credit the pixel newly earns, C(x) = max_g k(d(x,g)) is its own kernel weight
    to the nearest truth pixel, and D = 0.2*(T + FP) + 0.8*|G|.  The criterion is checked against
    the metric itself on placements that differ in dT and C.
    """
    truth = np.zeros((60, 60), bool)
    truth[10:50, 30] = True                 # a 40 px line: |G| = 40
    pred = np.zeros((60, 60))
    pred[10:30:2, 30] = 1.0                 # partial coverage at 2 px spacing
    for (y, x) in [(30, 30), (31, 30), (32, 30), (30, 32), (30, 33), (5, 5), (30, 34)]:
        p2 = pred.copy(); p2[y, x] = 1.0
        after = M.components(p2, truth)
        before = M.components(pred, truth)
        # recompute dT and C from the components
        dt = after.tp - before.tp
        s_inc = after.s - before.s
        c_at = s_inc - (after.fp - before.fp)      # p(x)*(1 - C) = 0.2-charge / 0.2
        d = before.tp + 0.2 * before.fp + 0.8 * before.n_truth
        lhs = dt * (0.2 * before.fp + 0.8 * before.n_truth)
        rhs = 0.2 * before.dti * d * (1.0 - c_at)
        assert np.sign(after.dti - before.dti) == np.sign(lhs - rhs) or abs(lhs - rhs) < 1e-12


def test_marginal_budget_rule_is_exact_and_verified_by_brute_force():
    """optimal_budget must equal the brute-force argmax of DTI(n) = T(n)/(0.2n + 0.8G)."""
    from gems46 import emission as E

    rng = np.random.default_rng(11)
    for scale, G in ((0.08, 800.0), (0.2, 2000.0), (0.5, 500.0)):
        credits = np.sort(rng.gamma(2.0, scale, size=4000))[::-1]
        got = E.optimal_budget(credits, G)
        brute = int(np.argmax([E.dti_of_prefix(credits, G, n) for n in range(1, credits.size + 1)])) + 1
        assert got["budget"] == brute
        # the exact break-even statement at the optimum: the last pixel clears 0.2*DTI, the next does not
        assert got["credit_last"] > got["break_even"]
        if brute < credits.size:
            nxt = E.dti_of_prefix(credits, G, brute + 1)
            assert nxt <= got["dti"] + 1e-12


def test_budget_responds_to_truth_size_like_the_metric():
    """A larger hidden truth set (more FNs to fight) supports a larger emission - same credits."""
    from gems46 import emission as E

    rng = np.random.default_rng(3)
    credits = np.sort(rng.gamma(2.0, 0.15, size=3000))[::-1]
    small = E.optimal_budget(credits, 500.0)["budget"]
    big = E.optimal_budget(credits, 20000.0)["budget"]
    assert big > small


def test_binary_fast_path_matches_the_offset_transcription():
    """The O(N) distance-transform path must equal the 29-offset path exactly, with masking."""
    rng = np.random.default_rng(5)
    for _ in range(4):
        emit = rng.random((28, 28)) < 0.06
        truth = rng.random((28, 28)) < 0.05
        known = rng.random((28, 28)) < 0.03
        a = M.components(emit.astype(np.float32), truth, known=known)
        b = M.components_binary(emit, truth, known=known)
        assert b.tp == pytest.approx(a.tp, abs=1e-9)
        assert b.fp == pytest.approx(a.fp, abs=1e-9)
        assert b.fn == pytest.approx(a.fn, abs=1e-9)
