"""Tests for the GEMSDOE47 arm: metric accelerator, instruments, emission rule, shipped file."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import metric as M          # noqa: E402
from gems47 import emission as E        # noqa: E402
from gems47 import proxy as P           # noqa: E402


def _random_case(seed=3, shape=(48, 52)):
    rng = np.random.default_rng(seed)
    emit = rng.random(shape) < 0.02
    truth = rng.random(shape) < 0.05
    valid = rng.random(shape) < 0.9
    known = (rng.random(shape) < 0.1) & ~truth
    return emit, truth, valid, known


def test_binary_metric_matches_soft_transcription():
    """The distance-transform binary path must reproduce the offset-loop transcription exactly."""
    emit, truth, valid, known = _random_case()
    a = M.components_binary(emit, truth, valid=valid, known=known)
    b = M.components(emit.astype(np.float64), truth, valid=valid, known=known)
    assert a.tp == pytest.approx(b.tp, abs=1e-6)
    assert a.fp == pytest.approx(b.fp, abs=1e-6)
    assert a.fn == pytest.approx(b.fn, abs=1e-6)
    assert a.dti == pytest.approx(b.dti, abs=1e-9)


def test_known_fault_masking_is_excluded_from_every_term():
    """Organizer rule (thread 11516): pixels on known faults leave the scored domain entirely."""
    emit, truth, valid, _ = _random_case()
    known = truth  # worst case: every truth pixel is a known fault
    comp = M.components_binary(emit, truth, valid=valid, known=known)
    assert comp.n_truth == 0 and comp.tp == 0.0 and comp.fn == 0.0
    expect_s = float((emit & valid & ~known).sum())
    assert comp.s == pytest.approx(expect_s)
    # and a dot placed on a known fault changes nothing
    base = M.components_binary(emit & ~known, truth, valid=valid, known=known)
    assert base.dti == pytest.approx(comp.dti, abs=1e-12)


def test_emit_dots_budget_separation_and_domain():
    rng = np.random.default_rng(11)
    field = rng.random((80, 90)).astype(np.float32)
    domain = np.ones_like(field, bool)
    domain[:, :5] = False
    emit = E.emit_dots(field, domain, budget=40, min_dist=3)
    n = int(emit.sum())
    assert 0 < n <= 40
    assert not (emit & ~domain).any()
    rr, cc = np.nonzero(emit)
    if n > 1:
        d = np.hypot(rr[:, None] - rr[None, :], cc[:, None] - cc[None, :])
        d += np.eye(n) * 1e9
        assert d.min() >= 3.0 - 1e-9


def test_emit_dots_orders_by_field():
    field = np.zeros((20, 20), np.float32)
    field[10, 10] = 0.9
    field[10, 14] = 0.5
    emit = E.emit_dots(field, np.ones_like(field, bool), budget=2, min_dist=3, score_floor=0.4)
    assert emit[10, 10] and emit[10, 14]


def test_emit_dots_empty_domain_is_empty():
    field = np.ones((10, 10), np.float32)
    assert E.emit_dots(field, np.zeros((10, 10), bool), budget=5, min_dist=3).sum() == 0


def test_instrument_sgmc_stratification_and_masking():
    shape = (60, 60)
    labels = np.zeros(shape, bool)
    labels[10, 10:40] = True          # a catalogue line
    sgmc = labels.copy()
    sgmc[50, 10:40] = True            # a far-away SGMC line
    footprint = np.ones(shape, bool)
    d_cat = P.distance_to(labels)
    truth, known, domain = P.instrument_sgmc_stratified(sgmc, labels, footprint, d_cat, 5.0)
    assert truth[50, 20] and not truth[10, 20]
    assert known[10, 20] and not domain[10, 20]


def test_scores_of_empty_and_full_emissions_are_sane():
    shape = (40, 40)
    truth = np.zeros(shape, bool)
    truth[20, 10:30] = True
    known = np.zeros(shape, bool)
    domain = np.ones(shape, bool)
    empty = P.score_emission(np.zeros(shape, bool), truth, known, domain)
    assert empty["dti"] == 0.0
    perfect = P.score_emission(truth.copy(), truth, known, domain)
    assert perfect["dti"] > 0.9
    shifted = np.zeros(shape, bool)
    shifted[22, 10:30] = True          # 2 px away: kernel (1 - 2/3) > 0
    off = P.score_emission(shifted, truth, known, domain)
    assert 0.0 < off["dti"] < perfect["dti"]
    far = np.zeros(shape, bool)
    far[24, 10:30] = True              # 4 px away: outside the 300 m support
    outside = P.score_emission(far, truth, known, domain)
    assert outside["dti"] == 0.0


def test_score_to_credit_calibration_is_monotone_in_the_mean():
    rng = np.random.default_rng(5)
    s = rng.random(20_000)
    c = np.clip(s + rng.normal(0, 0.05, 20_000), 0, 1)
    qs, vals = E.calibrate_score_to_credit(s, c, n_bins=10)
    assert vals[0] < vals[-1]
    got = E.credit_at(qs, vals, np.array([0.05, 0.5, 0.95]))
    assert got[0] < got[1] < got[2]


def test_predicted_dti_uses_the_marginal_rule():
    credit = np.array([0.9, 0.8, 0.5, 0.0])
    own = credit.copy()                  # a dot's own kernel credit is its distance-to-truth weight
    curve = E.predicted_dti(credit, own, truth_px=1_000.0)
    assert curve[0] > 0
    assert curve[1] > curve[0]           # a dot with credit above the bar raises DTI
    assert curve[3] < curve[2]           # a zero-credit dot pays 0.2 and returns nothing
    # the bar itself: at this operating point only credit above 0.2*DTI pays
    assert curve[2] > 0.0


def test_shipped_h47_file_format_and_uniqueness():
    files = sorted((ROOT / "docs" / "downloads" / "h47").glob("*.tif")) if (
        ROOT / "docs" / "downloads" / "h47").exists() else []
    if not files:
        pytest.skip("no H47 artifact in this checkout")
    import rasterio
    with rasterio.open(ROOT / "data" / "raw" / "sample_submission.tif") as t:
        tpl = (t.shape, str(t.crs), tuple(round(v, 6) for v in t.transform[:6]))
    for path in files:
        with rasterio.open(path) as d:
            arr = d.read(1)
            assert d.count == 1 and d.dtypes[0] == "float32"
            assert (d.shape, str(d.crs), tuple(round(v, 6) for v in d.transform[:6])) == tpl
        fin = np.isfinite(arr)
        assert fin.any()
        inside = arr[fin]
        assert inside.min() >= 0.0 and inside.max() <= 1.0
        assert np.unique(inside).size <= 3      # a dot set: 0 and 1 (and maybe NaN outside)


def test_h47_is_not_any_incumbent_file():
    """Uniqueness gate: the shipped dot set must not be pixel-identical to a family incumbent."""
    mirror = ROOT / ".mirror"
    if not mirror.exists():
        pytest.skip("family mirrors not present in this checkout")
    files = sorted((ROOT / "docs" / "downloads" / "h47").glob("*-zeros.tif"))
    if not files:
        pytest.skip("no H47 artifact in this checkout")
    import rasterio
    ours = rasterio.open(files[0]).read(1) > 0
    inc = [p for p in
           list(mirror.glob("GEMSDOE25/docs/downloads/*-zeros.tif")) +
           list(mirror.glob("GEMSDOE31/docs/downloads/*-allfinite.tif")) +
           list(mirror.glob("GEMSDOE32/docs/downloads/*-zeros.tif")) if p.is_file()]
    if not inc:
        # CI restores only the two data mirrors into .mirror; the method-family clones (and their
        # scored artifacts) are a local research input, so the uniqueness check skips there.
        pytest.skip("family incumbent files not present in this checkout")
    for path in inc:
        with rasterio.open(path) as d:
            other = d.read(1) > 0
        assert not np.array_equal(ours, other), f"pixel-identical to {path.name}"
        j = (ours & other).sum() / max(1, (ours | other).sum())
        assert j < 0.5, f"overlap with {path.name} is {j:.3f} (this would be a relabelled file)"
