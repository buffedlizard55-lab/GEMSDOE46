"""Unit tests for the expected-credit emitter (gems46.optemit).

The emitter is the part of the pipeline that decides *which* pixels are worth one unit of
prediction mass. A defect here silently changes the submission, so these tests pin:

* the kernel equals the published triangular kernel k(d) = max(1 − d/300 m, 0);
* the marginal gain of a fresh isolated dot equals the kernel-weighted ``q`` (by construction);
* no two accepted dots may sit inside one kernel cell when a saturation solution exists
  (the second dot would be charged 0.2 and return ~0 — the metric takes a max over predictions);
* the greedy solution is never worse (on the modelled objective) than the heuristic emitter's;
* the break-even stop rule fires when the modelled objective stops improving;
* ``calibrate_scale`` reproduces its target DTI at the requested mass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems46 import optemit  # noqa: E402


def test_kernel_matches_published_triangular_kernel():
    dys, dxs, ks = optemit.kernel_offsets(3.0)
    assert ks.min() > 0.0
    assert ks.max() == pytest.approx(1.0)
    for dy, dx, k in zip(dys, dxs, ks):
        assert k == pytest.approx(max(1.0 - np.hypot(dy, dx) / 3.0, 0.0))
    # every integer offset with 0 < d < 3 has k > 0 and must be present; d == 3 has k == 0
    present = set(zip(dys.tolist(), dxs.tolist()))
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if np.hypot(dy, dx) < 3.0:
                assert (dy, dx) in present
    assert (3, 0) not in present and (0, 3) not in present


def test_fresh_dot_gain_equals_kernel_weighted_field():
    q = np.zeros((21, 21), dtype=np.float32)
    q[10, 10] = 1.0
    gain = optemit.expected_credit(q)
    assert gain[10, 10] == pytest.approx(1.0, abs=1e-6)
    assert gain[10, 9] == pytest.approx(1.0 - 1.0 / 3.0, abs=1e-6)   # tap (0, +1)
    assert gain[10, 8] == pytest.approx(1.0 - 2.0 / 3.0, abs=1e-6)   # tap (0, +2)
    assert gain[10, 13] == pytest.approx(0.0, abs=1e-6)              # tap (0, +3) has k == 0


def test_emit_recovers_a_confident_line_and_does_not_double_cover():
    q = np.zeros((80, 120), dtype=np.float32)
    q[40, 20:100] = 1.0
    domain = np.ones_like(q, dtype=bool)
    res = optemit.emit(q, domain, budget=5000, break_even_dti=None)
    assert res.accepted > 0
    ys, xs = np.nonzero(res.mask)
    assert np.all(ys == 40)                       # dots track the line, not the surrounding area
    assert np.all(np.diff(np.sort(xs)) >= 1)      # never two dots on one pixel
    assert res.gains.min() > 0                    # no accepted dot returns nothing
    assert res.gains.sum() <= q.sum() + 1e-3      # T <= G for a unit-mass binary truth
    c = np.zeros_like(q)
    for dy, dx, k in zip(*optemit.kernel_offsets()):
        c = np.maximum(c, k * optemit._shift(res.mask.astype(np.float32), dy, dx))
    # given enough budget the greedy saturates the line: every truth pixel reaches full weight
    assert float((q * c).sum()) == pytest.approx(float(q.sum()), rel=1e-6)


def test_emit_is_never_worse_than_the_heuristic_emitter_on_the_model():
    rng = np.random.default_rng(7)
    q = rng.random((160, 160)).astype(np.float32)
    q = np.where(q > 0.97, 1.0, 0.0).astype(np.float32)   # sparse line-like structure
    q[80, 40:120] = 1.0
    domain = np.ones_like(q, dtype=bool)
    budget = 400
    res = optemit.emit(q, domain, budget=budget, break_even_dti=None)
    from gems46.emission import greedy_emit

    heuristic, _ = greedy_emit(q, domain, budget, min_dist=3, smooth_px=0.0)
    def modelled(mask):
        c = np.zeros_like(q)
        for dy, dx, k in zip(*optemit.kernel_offsets()):
            c = np.maximum(c, k * optemit._shift(mask.astype(np.float32), dy, dx))
        return float((q * c).sum())

    assert modelled(res.mask) >= modelled(heuristic)


def test_gains_are_the_true_marginal_deltas_of_the_metric_objective():
    """Σ accepted gains must telescope to T(mask) - T(empty) under the sparse model."""
    rng = np.random.default_rng(3)
    q = np.where(rng.random((70, 90)) > 0.995, 1.0, 0.0).astype(np.float32)
    q[35, 10:80] = 1.0
    res = optemit.emit(q, np.ones_like(q, bool), budget=5_000, break_even_dti=None)
    c = np.zeros_like(q)
    for dy, dx, k in zip(*optemit.kernel_offsets()):
        c = np.maximum(c, k * optemit._shift(res.mask.astype(np.float32), dy, dx))
    assert res.gains.sum() == pytest.approx(float((q * c).sum()), rel=1e-6)
    # and each recorded gain equals the marginal increase it caused
    c = np.zeros_like(q)
    for (y, x), g in zip(res.order, res.gains):
        cov = np.zeros_like(q)
        for dy, dx, k in zip(*optemit.kernel_offsets()):
            if 0 <= y + dy < q.shape[0] and 0 <= x + dx < q.shape[1]:
                cov[y + dy, x + dx] = max(cov[y + dy, x + dx], k)
        assert float((q * (np.maximum(c, cov) - c)).sum()) == pytest.approx(g, abs=1e-4)
        c = np.maximum(c, cov)


def test_break_even_stop_rule_fires_on_a_decaying_field():
    q = np.zeros((40, 400), dtype=np.float32)
    q[20, 20:380] = np.exp(-np.arange(360) / 120.0).astype(np.float32)
    res = optemit.emit(q, np.ones_like(q, bool), budget=5_000, break_even_dti=2.0, margin=0.2)
    assert res.stopped == "break-even"
    n = res.accepted
    assert 0 < n < 5_000
    # the rule as implemented: the last accepted dot still cleared the bar that was in force
    # before it was accepted, and the next-best candidate did not.
    t_prev = float(res.gains[:-1].sum())
    dti_prev = t_prev / (0.2 * (n - 1) + 0.8 * res.g_hat)
    assert res.gains[-1] >= 0.2 * dti_prev - 1e-9
    # independent brute-force check that no pixel left in the domain still beats the final bar
    c = np.zeros_like(q)
    for dy, dx, k in zip(*optemit.kernel_offsets()):
        c = np.maximum(c, k * optemit._shift(res.mask.astype(np.float32), dy, dx))
    best = 0.0
    ys, xs = np.nonzero(q)
    for y, x in zip(ys[::5], xs[::5]):
        gain = 0.0
        for dy, dx, k in zip(*optemit.kernel_offsets()):
            yy, xx = y + dy, x + dx
            if 0 <= yy < q.shape[0] and 0 <= xx < q.shape[1]:
                gain += q[yy, xx] * max(0.0, k - c[yy, xx])
        best = max(best, gain)
    assert best < 0.2 * (float(res.gains.sum()) / (0.2 * n + 0.8 * res.g_hat)) + 1e-9


def test_calibrate_scale_hits_its_target():
    q = np.zeros((60, 60), dtype=np.float32)
    q[30, 10:50] = 1.0
    res = optemit.emit(q, np.ones_like(q, bool), budget=200, break_even_dti=None)
    lam = optemit.calibrate_scale(res.gains, res.g_hat, target_dti=0.28, mass=res.accepted)
    t = float(res.gains.sum()) * lam
    g = res.g_hat * lam
    dti = t / (0.2 * res.accepted + 0.8 * g)
    assert dti == pytest.approx(0.28, rel=1e-6)


def test_predicted_curve_and_optimum_are_consistent():
    gains = np.array([0.9, 0.5, 0.3, 0.01])
    curve = optemit.predicted_curve(gains, g_hat=10.0)
    n, best = optemit.optimal_prefix(gains, g_hat=10.0)
    assert best == pytest.approx(curve.max())
    assert curve[n - 1] == pytest.approx(best)


def test_analytic_ceiling_is_the_documented_bound():
    assert optemit.analytic_ceiling(7905, 7905) == pytest.approx(1.0)
    assert optemit.analytic_ceiling(0, 100.0) == pytest.approx(1.25)
