"""R11-D matched-filter tests: locked synthetic gates D-S1..S3 + NCC units."""
import numpy as np

from gems46 import matchedfilter as M


def test_ncc_finds_clean_step_exactly():
    a = np.zeros((64, 64))
    a[:, 32:] = 1.0
    r, ok = M.masked_ncc(a, np.ones_like(a, bool), 0)
    assert ok[32, 32]
    assert abs(r[32, 32] - 1.0) < 1e-9
    # the edge lies between pixels 31 and 32: both centerings match perfectly
    peaks = set(np.nonzero(r[32].astype(float) > 1 - 1e-9)[0].tolist())
    assert peaks <= {31, 32} and len(peaks) == 2
    # reversed polarity still matches in |r|
    r2, _ = M.masked_ncc(-a, np.ones_like(a, bool), 0)
    assert abs(abs(r2[32, 32]) - 1.0) < 1e-9


def test_ncc_constant_and_masked():
    r, ok = M.masked_ncc(np.full((32, 32), 7.0), np.ones((32, 32), bool), 90)
    assert (r == 0).all()
    a = np.zeros((64, 64))
    a[:, 32:] = 1.0
    v = np.ones_like(a, bool)
    v[:, :40] = False  # step buried in the invalid region
    _, ok2 = M.masked_ncc(a, v, 0)
    assert not ok2[32, 32]
    assert ok2[32, 52]  # fully-valid footprint far from the mask
    assert not ok2[32, 60]  # edge-truncated footprint (<80% taps) uncovered


def test_d1_step_recovery():
    from gems46 import emission
    tmi, grav, lines = M.synthetic_d1()
    valid = np.ones(tmi.shape, bool)
    field, support, _ = M.score_pair(tmi, grav, valid)
    emit, _ = emission.greedy_emit(field, support, 200, min_dist=3, smooth_px=1.85)
    assert emit.sum() == 200
    ys, xs = np.nonzero(emit)
    d = np.min([np.abs(xs - ln) for ln in lines], axis=0)
    frac = float((d <= 3).mean())
    assert frac >= 0.70, f"D-S1 recovery {frac}"


def test_d2_noise_stays_quiet_and_scattered():
    from gems46 import emission
    tmi, grav = M.synthetic_d2()
    valid = np.ones(tmi.shape, bool)
    field, support, _ = M.score_pair(tmi, grav, valid)
    assert float(field.max()) < 0.5, f"D-S2 not quiet: max {field.max()}"
    emit, _ = emission.greedy_emit(field, support, 200, min_dist=3, smooth_px=1.85)
    if emit.sum() >= 20:
        ys, xs = np.nonzero(emit)
        worst = max(float((((xs >= lo) & (xs < lo + 6)).mean())) for lo in range(0, 256, 6))
        assert worst <= 0.25, f"D-S2 worst strip {worst}"


def test_d3_separated_sources_no_phantom():
    tmi, grav = M.synthetic_d3()
    valid = np.ones(tmi.shape, bool)
    field, _, _ = M.score_pair(tmi, grav, valid)
    assert float(field.max()) < 0.3, f"D-S3 max {field.max()}"


def test_determinism():
    tmi, grav, _ = M.synthetic_d1()
    valid = np.ones(tmi.shape, bool)
    f1, _, _ = M.score_pair(tmi, grav, valid)
    f2, _, _ = M.score_pair(tmi, grav, valid)
    np.testing.assert_array_equal(f1, f2)
