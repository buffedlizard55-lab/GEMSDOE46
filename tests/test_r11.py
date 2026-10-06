"""R11-A localized DFA tests: math equivalence, placement, stratification, synthetics."""
import numpy as np

from gems46 import local_dfa as L
from gems46 import crossover as C
from gems46.dfa import alpha_reference


def test_fluctuation_math_matches_reference():
    rng = np.random.default_rng(7)
    win = rng.normal(size=(20, 512))
    scales = (8, 16, 32, 64, 96, 128)
    got = L.slopes(win, scales)
    np.testing.assert_allclose(
        got[:3], [alpha_reference(x, scales) for x in win[:3]], atol=1e-9)
    # full fit also matches crossover's full fit on its own scale set
    full, _, _ = C.slopes(win)
    np.testing.assert_allclose(got, full, atol=1e-12)
    # affine invariance, constants -> NaN, too-short raises
    np.testing.assert_allclose(L.slopes(win * 13 + 700, scales), got, atol=1e-11)
    assert np.isnan(L.slopes(np.ones((2, 512)), scales)).all()
    try:
        L.slopes(win[:, :100], scales)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for short windows")


def test_coarse_placement_nonsquare_transpose():
    rng = np.random.default_rng(11)
    a = rng.normal(size=(192, 256)).astype("float32")
    v = np.ones_like(a, bool)
    m, r, c = L.coarse_maps(a, v, window=128, stride=8)
    mt, rt, ct = L.coarse_maps(a.T, v.T, window=128, stride=8)
    assert m.shape == (2, len(r), len(c)) and len(r) != len(c)
    np.testing.assert_allclose(m[0], mt[1].T, rtol=1e-5)
    np.testing.assert_allclose(m[1], mt[0].T, rtol=1e-5)
    # gaps propagate as NaN, never invented
    v2 = v.copy()
    v2[64, :150] = False
    m2, _, _ = L.coarse_maps(a, v2, window=128, stride=8)
    assert np.isnan(m2[0, 0, 0])


def test_block_stratified_z_removes_block_offset():
    rng = np.random.default_rng(5)
    nr = nc = 40
    blocks = np.ones((nr, nc), int)
    blocks[:, nc // 2:] = 2
    alpha = 1.0 + 0.5 * blocks + 0.05 * rng.normal(size=(nr, nc))
    maps = np.stack([alpha, alpha]).astype("float32")
    scores, masks = L.score_physics(maps, blocks)
    assert masks.sum() > 1000
    from gems46.local_dfa import _block_z
    sup = np.isfinite(alpha)
    z, big = _block_z(alpha, sup, blocks)
    assert abs(z[blocks == 1].mean()) < 0.3 and abs(z[blocks == 2].mean()) < 0.3
    # small blocks contribute z=0
    tiny = np.where(blocks == 1, 1, 2)
    tiny[5:9, 5:9] = 3  # 16 cells < 25
    z2, big2 = _block_z(alpha, sup, tiny)
    assert not big2[5:9, 5:9].any() and (z2[5:9, 5:9] == 0).all()


def test_combine_helpers():
    s1 = np.array([[0.2, 0.8], [0.0, 0.4]], dtype="float32")
    m1 = np.array([[True, True], [False, True]])
    s2 = np.array([[0.6, 0.0], [0.9, 0.2]], dtype="float32")
    m2 = np.array([[True, False], [True, True]])
    mx, mm = L.combine_orientations(np.stack([s1, s2]), np.stack([m1, m2]))
    np.testing.assert_allclose(mx, [[0.6, 0.8], [0.9, 0.4]], atol=1e-6)
    assert mm.all()
    f, sup = L.combine_physics([s1, s2], [m1, m2])
    np.testing.assert_allclose(f[0, 0], 0.4, atol=1e-6)  # mean of available
    np.testing.assert_allclose(f[0, 1], 0.8, atol=1e-6)  # single-physics kept
    assert sup.all()


def test_determinism():
    rng = np.random.default_rng(3)
    a = rng.normal(size=(192, 208)).astype("float32")
    v = np.ones_like(a, bool)
    m1, _, _ = L.coarse_maps(a, v, window=128, stride=8)
    m2, _, _ = L.coarse_maps(a, v, window=128, stride=8)
    np.testing.assert_array_equal(np.nan_to_num(m1), np.nan_to_num(m2))


def test_fgn_calibration():
    rng = np.random.default_rng(0)
    for hurst, lo, hi in ((0.3, 0.25, 0.5), (0.5, 0.4, 0.65), (0.9, 0.75, 1.05)):
        got = alpha_reference(L.fgn(2048, hurst, rng), (4, 8, 16, 32, 64, 128))
        assert lo < got < hi, (hurst, got)


def test_s1_documents_mislocalization_futility():
    # Amendment 2: bar was peak within 8 samples of the step. Measured
    # Delta=44 (peak 300 vs 256) on the locked fixture: windowed-DFA
    # boundary detection cannot localize to the metric's 300 m kernel.
    # This test fails only if localization ever reaches the bar (re-examine!).
    x, boundary = L.synthetic_s1()
    centers, alpha = L.sliding_1d(x)
    score, mask = L.score_1d(alpha)
    peak = int(centers[int(np.argmax(score))])
    assert abs(peak - boundary) >= 32, f"unexpectedly good: peak {peak}"


def test_s2_stationary_ramp_has_no_localized_firing():
    x = L.synthetic_s2()
    centers, alpha = L.sliding_1d(x)
    score, mask = L.score_1d(alpha)
    top20 = np.argsort(score[mask])[-20:]
    spread = float(centers[mask][top20].std())
    assert spread >= 100, f"spurious clustering, spread {spread}"


def test_s3_2d_boundary_concentration():
    from gems46 import emission
    grid, boundary = L.synthetic_s3()
    valid = np.ones_like(grid, bool)
    maps, rows, cols = L.coarse_maps(grid, valid)
    blocks = np.ones((len(rows), len(cols)), int)
    scores, masks = L.score_physics(maps, blocks)
    phys, pmask = L.combine_orientations(scores, masks)
    field_c, sup_c = L.combine_physics([phys], [pmask])
    field, support = C.expand(field_c, sup_c, rows, cols, grid.shape)
    emit, _ = emission.greedy_emit(field, support, 200, min_dist=3, smooth_px=1.85)
    assert emit.sum() == 200
    ys, xs = np.nonzero(emit)
    frac = float((np.abs(xs - boundary) <= 10).mean())
    # Amendment 2: bar was >= 0.50. Measured 0.18: futility documented.
    assert frac < 0.30, f"unexpectedly good: concentration {frac}"
