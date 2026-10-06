"""Line-by-line verification of the official metric implementation.

Every assertion here traces to the published definitions on
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
("Mathematical representation" and "Scoring example").
"""
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46.metric import dti, distance_weighted_terms, kernel_from_distance, R_PIXELS  # noqa: E402
from gems46.window_metric import window_terms, global_truth_distance               # noqa: E402


# --------------------------------------------------------------------------
# 0. The published worked example
# --------------------------------------------------------------------------
def test_official_worked_example_arithmetic():
    """Official page: TPw=3.00, FPw=1.89, FNw=2.00 -> TI_w(0.2, 0.8) = 0.60."""
    val = 3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00)
    assert round(val, 2) == 0.60, val


def test_kernel_is_triangular_with_R3():
    d = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    k = kernel_from_distance(d)
    assert np.allclose(k, [1.0, 2 / 3, 1 / 3, 0.0, 0.0]), k
    assert R_PIXELS == 3.0


# --------------------------------------------------------------------------
# 1. Brute-force transcription (the ground truth for the unit tests)
# --------------------------------------------------------------------------
def brute_force(pred, truth):
    """Literal O(N^2) transcription of the three published sums."""
    h, w = truth.shape
    tpw = 0.0
    for gy in range(h):
        for gx in range(w):
            if not truth[gy, gx]:
                continue
            best = 0.0
            for y in range(h):
                for x in range(w):
                    if pred[y, x] <= 0:
                        continue
                    d = np.hypot(y - gy, x - gx)
                    best = max(best, pred[y, x] * max(1.0 - d / R_PIXELS, 0.0))
            tpw += best
    fpw = 0.0
    for y in range(h):
        for x in range(w):
            if pred[y, x] <= 0:
                continue
            if truth.any():
                dmin = min(np.hypot(y - gy, x - gx)
                           for gy in range(h) for gx in range(w) if truth[gy, gx])
            else:
                dmin = np.inf
            k = max(1.0 - dmin / R_PIXELS, 0.0) if np.isfinite(dmin) else 0.0
            fpw += pred[y, x] * (1.0 - k)
    fnw = 0.0
    for gy in range(h):
        for gx in range(w):
            if not truth[gy, gx]:
                continue
            best = 0.0
            for y in range(h):
                for x in range(w):
                    if pred[y, x] <= 0:
                        continue
                    d = np.hypot(y - gy, x - gx)
                    best = max(best, pred[y, x] * max(1.0 - d / R_PIXELS, 0.0))
            fnw += 1.0 - best
    denom = tpw + 0.2 * fpw + 0.8 * fnw + 1e-9
    return tpw / denom, tpw, fpw, fnw


def test_matches_brute_force_on_random_rasters():
    rng = np.random.default_rng(0)
    for trial in range(8):
        n = 11
        pred = rng.random((n, n)).astype(np.float64)
        pred[pred < 0.55] = 0.0
        truth = rng.random((n, n)) < 0.18
        if not truth.any():
            truth[5, 5] = True
        exp, etp, efp, efn = brute_force(pred, truth)
        got = dti(pred, truth)
        assert abs(got - exp) < 1e-9, (trial, got, exp)
        tpw, fpw, fnw, _g = distance_weighted_terms(pred, truth)
        assert abs(tpw - etp) < 1e-9
        assert abs(fpw - efp) < 1e-9
        assert abs(fnw - efn) < 1e-9


def test_false_negative_identity():
    """FNw == |G| - TPw, the identity used throughout the analysis."""
    rng = np.random.default_rng(1)
    for _ in range(5):
        pred = (rng.random((9, 9)) > 0.7).astype(float)
        truth = rng.random((9, 9)) < 0.2
        tpw, _fpw, fnw, g = distance_weighted_terms(pred, truth)
        assert abs(fnw - (g - tpw)) < 1e-9


# --------------------------------------------------------------------------
# 2. Boundary behaviour
# --------------------------------------------------------------------------
def test_perfect_and_empty():
    truth = np.zeros((9, 9), dtype=bool)
    truth[4, 2:7] = True
    assert abs(dti(truth.astype(float), truth) - 1.0) < 1e-6
    assert dti(np.zeros((9, 9)), truth) < 1e-6
    # one dot exactly on one truth pixel, no other truth: 1/(1+0+0)
    t2 = np.zeros((9, 9), dtype=bool)
    t2[4, 4] = True
    p2 = np.zeros((9, 9))
    p2[4, 4] = 1.0
    assert abs(dti(p2, t2) - 1.0) < 1e-6


def test_monotone_in_mass_removal():
    """Moving a dot closer to truth must not lower the index."""
    truth = np.zeros((15, 15), dtype=bool)
    truth[7, 7] = True
    near = np.zeros((15, 15))
    near[7, 8] = 1.0            # 1 px away
    far = np.zeros((15, 15))
    far[7, 12] = 1.0            # 5 px away -> outside the 3 px kernel
    assert dti(near, truth) > dti(far, truth)


# --------------------------------------------------------------------------
# 3. The windowed scorer used by the holdout must equal the full-grid scorer
# --------------------------------------------------------------------------
def test_windowed_scorer_matches_full_grid_scorer():
    rng = np.random.default_rng(7)
    H, W = 40, 40
    truth = rng.random((H, W)) < 0.06
    dots = np.argwhere(rng.random((H, W)) < 0.05).astype(np.int32)
    pred = np.zeros((H, W), dtype=float)
    if len(dots):
        pred[dots[:, 0], dots[:, 1]] = 1.0
    full = distance_weighted_terms(pred, truth)
    from gems46.window_metric import global_truth_distance
    win = window_terms(dots, truth, R_PIXELS, origin=(0, 0),
                       d_truth_global=global_truth_distance(truth))
    assert abs(win["TPw"] - full[0]) < 1e-9
    assert abs(win["FPw"] - full[1]) < 1e-9
    assert abs(win["FNw"] - full[2]) < 1e-9


def test_window_halo_accounts_for_outside_dots():
    """A dot outside the window within the kernel reach must still deliver credit."""
    truth = np.zeros((12, 12), dtype=bool)
    truth[6, 6] = True
    dots = np.array([[6, 4]], dtype=np.int32)      # 2 px from truth, outside window
    win_truth = truth[5:9, 5:9]                    # window rows 5..8, cols 5..8
    terms = window_terms(dots, win_truth, R_PIXELS, origin=(5, 5),
                         d_truth_global=global_truth_distance(truth))
    assert abs(terms["TPw"] - (1.0 - 2.0 / 3.0)) < 1e-9, terms
    assert abs(terms["FPw"] - (2.0 / 3.0)) < 1e-9, terms


def test_edt_distance_matches_kernel():
    truth = np.zeros((9, 9), dtype=bool)
    truth[4, 4] = True
    d = ndimage.distance_transform_edt(~truth)
    assert d[4, 4] == 0.0 and abs(d[4, 7] - 3.0) < 1e-9
