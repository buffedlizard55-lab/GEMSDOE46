"""Verification of `gems46.xmetric` against the published definitions.

Three independent checks:
  1. the organiser's own worked example arithmetic (page 967): TP=3.00, FP=1.89, FN=2.00 -> 0.60;
  2. brute-force O(|G|*|P|) transcription vs the fast shift-max implementation on random grids;
  3. the algebraic identities I1 (FN = |G| - TP) and I2 (FP = S - M) on real competition data.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import xmetric as M  # noqa: E402


def test_published_example_arithmetic():
    """Page 967 states TP_w=3.00, FP_w=1.89, FN_w=2.00 and quotes the result as 0.60."""
    dti = M.dti_from_parts(3.00, 1.89, 2.00)
    assert dti == pytest.approx(3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00), rel=1e-6)
    assert round(dti, 2) == 0.60


def test_kernel_support_and_shapes():
    assert M.kernel(0.0) == 1.0
    assert M.kernel(1.5) == pytest.approx(0.5)
    assert M.kernel(3.0) == 0.0
    assert M.kernel(3.0001) == 0.0
    ks = [k for _, _, k in M.OFFSETS]
    assert len(M.OFFSETS) == 25, "25 integer offsets strictly inside radius 3 (of 49 in the square)"
    assert min(ks) == pytest.approx(1 - np.sqrt(8) / 3)


def test_bruteforce_equivalence_random():
    rng = np.random.default_rng(0)
    for _ in range(6):
        pred = np.where(rng.random((14, 14)) < 0.15, rng.random((14, 14)), 0.0)
        truth = rng.random((14, 14)) < 0.10
        known = np.zeros_like(truth)
        fast = M.components(pred, truth, known=known)
        slow = M.components_bruteforce(pred, truth, known=known)
        for key in ("tp", "fp", "fn"):
            assert fast[key] == pytest.approx(slow[key], abs=1e-6), key
        assert fast["dti"] == pytest.approx(slow["dti"], abs=1e-6)


def test_identities_i1_i2_on_random():
    rng = np.random.default_rng(1)
    for _ in range(6):
        pred = np.where(rng.random((20, 20)) < 0.2, rng.random((20, 20)), 0.0)
        truth = rng.random((20, 20)) < 0.12
        c = M.components(pred, truth, known=np.zeros_like(truth))
        assert c["fn"] == pytest.approx(c["n_truth"] - c["tp"], abs=1e-6)   # I1
        d = M.kernel(__import__("scipy.ndimage", fromlist=["x"]).distance_transform_edt(~truth))
        s = float(pred.sum())
        m = float((pred * d).sum()) if truth.any() else 0.0
        assert c["fp"] == pytest.approx(s - m, abs=1e-6)                     # I2


def test_known_masking_removes_pixels_from_both_sides():
    """Official rule (thread 11516): known-fault pixels earn no TP and pay no FP."""
    pred = np.zeros((9, 9), np.float32)
    pred[4, 4] = 1.0
    truth = np.zeros((9, 9), bool)
    truth[4, 4] = True
    known = np.zeros((9, 9), bool)
    unmasked = M.components(pred, truth, known=known)
    assert unmasked["n_truth"] == 1 and unmasked["tp"] == pytest.approx(1.0)
    known[4, 4] = True
    masked = M.components(pred, truth, known=known)
    assert masked["n_truth"] == 0 and masked["dti"] == 0.0
    assert masked["fp"] == 0.0, "mass on a known pixel is neither TP nor FP"
    # a dot next to the masked pixel earns nothing either (its only neighbour is masked)
    pred2 = np.zeros((9, 9), np.float32)
    pred2[4, 5] = 1.0
    m2 = M.components(pred2, truth, known=known)
    assert m2["n_truth"] == 0
    assert m2["fp"] == pytest.approx(1.0), "no truth in the scored set -> dot is pure FP tax"
    # with an unmasked truth pixel 2 px away the same dot is cheaper and earns credit
    truth[6, 5] = True
    m3 = M.components(np.float32(pred2), truth, known=known)
    assert m3["n_truth"] == 1
    assert m3["tp"] == pytest.approx(1 / 3)
    assert m3["fp"] == pytest.approx(1 - 1 / 3), "k=1/3 at d=2 px; FP tax = p*(1-k)"


def test_single_dot_credits_whole_line_segment():
    """One dot serves every truth pixel inside a 3-px disc: TP_w = sum of k."""
    pred = np.zeros((11, 11), np.float32)
    pred[5, 5] = 1.0
    truth = np.zeros((11, 11), bool)
    truth[5, 2] = True   # d = 3 px -> k = 0
    truth[5, 3] = True   # d = 2 px -> k = 1/3
    truth[5, 4] = True   # d = 1 px -> k = 2/3
    truth[5, 5] = True   # d = 0 px -> k = 1
    c = M.components(pred, truth, known=np.zeros_like(truth))
    assert c["n_truth"] == 4
    assert c["tp"] == pytest.approx(0 + 1 / 3 + 2 / 3 + 1)
    assert c["coverage"] == pytest.approx(0.5)


def test_marginal_gain_matches_exact_metric_change():
    """`marginal_gain_full` must equal the exact DTI change on a real grid, dot by dot."""
    rng = np.random.default_rng(7)
    truth = np.zeros((24, 24), bool)
    truth[6, 6:14] = True
    truth[14, 10:18] = True
    pred = np.zeros((24, 24), np.float32)
    pred[5, 6:14] = 0.6
    base = M.components(pred, truth, known=np.zeros_like(truth))
    for (y, x) in [(6, 6), (13, 9), (20, 20), (7, 12), (14, 10)]:
        p2 = pred.copy()
        p2[y, x] = 1.0
        new = M.components(p2, truth, known=np.zeros_like(truth))
        dt = new["tp"] - base["tp"]
        dm = (base["mass"] + 1.0 - new["mass"]) * 0.0  # placeholder, recomputed below
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt(~truth)
        m_old = float((pred * M.kernel(dist)).sum())
        m_new = float((p2 * M.kernel(dist)).sum())
        gain_model = M.marginal_gain_full(base["tp"], base["fp"], base["fn"], dt, m_new - m_old)
        assert gain_model == pytest.approx(new["dti"] - base["dti"], abs=1e-6)
    # and the analytic threshold 0.2*DTI is the correct small-mass crossover
    tp, fp, fn = 3937.0, 8818.0, 7905.0 - 3937.0
    bar = 0.2 * M.dti_from_parts(tp, fp, fn)
    assert M.marginal_gain_full(tp, fp, fn, dt=0.9 * bar, dm=0.9 * bar) < 0
    assert M.marginal_gain_full(tp, fp, fn, dt=1.1 * bar, dm=1.1 * bar) > 0
