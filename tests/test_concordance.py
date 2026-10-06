"""Unit tests for the R11 concordance module (src/gems46/concordance.py).

These are deterministic, dependency-free checks of the numerical operators; they do
not touch the 419 MB competition rasters.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems46.concordance import (
    AXES,
    MORPH_BANDS,
    RAD_BANDS,
    assemble,
    build_field,
    gradmag,
    prepare_inputs,
    rank01,
    structure_orientation,
    thin_axis,
)


def _toy(n=64):
    """A synthetic scene: one horizontal 'scarp' with a coincident regolith break."""
    y, x = np.mgrid[0:n, 0:n]
    morph = {b: np.zeros((n, n), np.float32) for b in MORPH_BANDS}
    rad = {b: np.zeros((n, n), np.float32) for b in RAD_BANDS}
    band = (np.abs(y - n // 2) <= 1).astype(np.float32)
    for b in MORPH_BANDS:
        morph[b] = (band * 200.0 + np.random.default_rng(1).normal(0, 3, (n, n))).astype(np.float32)
    for b in RAD_BANDS:
        rad[b] = (band * 180.0 + np.random.default_rng(2).normal(0, 3, (n, n))).astype(np.float32)
    morph["valid"] = np.ones((n, n), np.float32) * 255.0
    domain = np.ones((n, n), bool)
    return morph, rad, domain


# --------------------------------------------------------------------------- rank01
def test_rank01_constant_channel_has_no_ordering_information():
    a = np.full((20, 20), 7.0, np.float32)
    out = rank01(a, np.ones((20, 20), bool))
    assert out.max() == 0.0, "a constant channel must not produce an arbitrary tie-broken ramp"


def test_rank01_is_monotone_and_unit_range():
    a = np.arange(400, dtype=np.float32).reshape(20, 20)
    out = rank01(a, np.ones((20, 20), bool))
    assert out.min() == 0.0 and out.max() == 1.0
    assert np.all(np.diff(out.ravel()) >= 0)


def test_rank01_zero_outside_mask():
    a = np.arange(400, dtype=np.float32).reshape(20, 20)
    mask = np.zeros((20, 20), bool)
    mask[:, 10:] = True
    out = rank01(a, mask)
    assert np.all(out[:, :10] == 0.0)
    assert out[:, 10:].max() == 1.0


# --------------------------------------------------------------------------- thinning
def test_thin_axis_collapses_a_wide_response_onto_its_axis():
    n = 48
    y, x = np.mgrid[0:n, 0:n]
    d = np.abs(y - n // 2).astype(np.float32)
    f = np.maximum(1.0 - 0.3 * d, 0.0).astype(np.float32)      # horizontal ridge, ~4 px wide
    theta, coh = structure_orientation(f)
    keep = thin_axis(f, theta)
    assert keep.any()
    rows = np.unique(np.nonzero(keep)[0])
    src_rows = np.unique(np.nonzero(f > 0.5)[0])
    assert len(rows) < len(src_rows), "thinning must narrow the response band"
    assert np.all(np.abs(rows - n // 2) <= 1), "kept pixels must sit on the ridge axis"


def test_thin_axis_axes_are_the_four_connected_directions():
    assert set(AXES) == {(0, 1), (1, 1), (1, 0), (1, -1)}


def test_structure_orientation_recovers_a_horizontal_ridge():
    n = 64
    y, _ = np.mgrid[0:n, 0:n]
    f = np.exp(-0.5 * ((y - n // 2) / 2.0) ** 2).astype(np.float32)
    theta, coh = structure_orientation(f)
    core = slice(n // 2 - 2, n // 2 + 3)
    # gradient direction of a horizontal ridge is vertical: |theta| near pi/2 (mod pi)
    t = np.mod(theta[core, n // 4:3 * n // 4], np.pi)
    assert np.median(np.minimum(t, np.pi - t)) > np.pi / 4
    assert coh[core, n // 4:3 * n // 4].mean() > 0.5


# --------------------------------------------------------------------------- field
def test_gradmag_zero_fills_outside_valid():
    a = np.ones((20, 20), np.float32)
    valid = np.zeros((20, 20), bool)
    valid[:, :10] = True
    g = gradmag(a, 1.0, valid)
    assert np.all(np.isfinite(g))
    # the zero-fill creates a step at column 9/10, so the strongest gradient must sit there,
    # not in the middle of the valid half
    col_of_max = int(np.argmax(g[10]))
    assert 7 <= col_of_max <= 11, col_of_max
    assert g[10, 2] < g[10, col_of_max]


def test_concordance_weight_zero_recovers_morphology_only():
    morph, rad, domain = _toy()
    prep = prepare_inputs(morph, rad, np.ones_like(domain), domain)
    s_w0, _ = assemble(prep, w=0.0, fallback_quantile=0.0, thin=False)
    s_w1, _ = assemble(prep, w=1.0, fallback_quantile=0.0, thin=False)
    assert not np.array_equal(s_w0, s_w1), "the concordance term must change the ranking"
    # with w = 0 the field is the (renormalised) morphology score, so its support is
    # exactly the morphology support
    assert np.array_equal(s_w0 > 0, prep["lid"] > 0)


def test_field_is_unit_bounded_and_zero_off_domain():
    morph, rad, domain = _toy()
    domain[0:4, :] = False
    f, diag = build_field(morph, rad, np.ones_like(domain), domain, w=0.5,
                          fallback_quantile=0.9)
    assert f.min() >= 0.0 and f.max() <= 1.0
    assert np.all(f[~domain] == 0.0)
    assert diag["max"] == pytest.approx(1.0)


def test_fallback_only_fills_pixels_without_lidar():
    morph, rad, domain = _toy()
    lidar_ok = np.ones_like(domain)
    lidar_ok[:, 40:] = False                       # right third has no LiDAR
    f_nofb, _ = build_field(morph, rad, lidar_ok, domain, w=0.5, fallback_quantile=0.0)
    f_fb, diag = build_field(morph, rad, lidar_ok, domain, w=0.5, fallback_quantile=0.99)
    assert np.all(f_nofb[:, 40:] == 0.0), "without a fallback, LiDAR gaps must stay empty"
    assert (f_fb[:, 40:] > 0).any(), "the fallback must populate LiDAR gaps"
    assert np.array_equal(f_nofb[:, :40] > 0, f_fb[:, :40] > 0)
    assert diag["fallback_scale"] > 0.0
    # fallback candidates are capped so they cannot outrank good morphology candidates:
    # compared in the same (normalised) units as the shipped field
    assert diag["fallback_max"] <= diag["morph_p99"] + 1e-6
    assert f_fb[:, 40:].max() <= diag["morph_p99"] + 1e-6


def test_invalid_weight_rejected():
    morph, rad, domain = _toy()
    prep = prepare_inputs(morph, rad, np.ones_like(domain), domain)
    with pytest.raises(ValueError):
        assemble(prep, w=1.5)


def test_prepare_inputs_requires_both_sensors():
    morph, _rad, domain = _toy()
    with pytest.raises(ValueError):
        prepare_inputs(morph, {}, np.ones_like(domain), domain)
    with pytest.raises(ValueError):
        prepare_inputs({}, {"TC": morph["valid"]}, np.ones_like(domain), domain)
