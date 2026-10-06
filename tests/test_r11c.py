"""R11-C tilt-contact tests: locked synthetic gates C-S1..S3 + unit behavior."""
import numpy as np

from gems46 import tiltphase as T


def test_contacts_find_step_and_ignore_flats():
    vdr = np.full((32, 64), -1.0)
    vdr[:, 32:] = 1.0
    thdr = np.zeros((32, 64))
    thdr[:, 30:34] = 5.0  # significant ridge straddling the step
    valid = np.ones_like(vdr, bool)
    mask, diag = T.tilt_contacts(vdr, thdr, valid)
    assert mask.any()
    ys, xs = np.nonzero(mask)
    assert set(np.unique(xs)) <= {31, 32}, np.unique(xs)
    assert diag["kept"] <= diag["raw"]
    # same step, insignificant THDR everywhere: gate drops everything
    mask2, _ = T.tilt_contacts(vdr, np.full_like(thdr, 0.01), valid)
    assert not mask2.any()
    # perfectly flat field: no sign change anywhere
    mask3, _ = T.tilt_contacts(np.full((16, 16), 2.0),
                               np.full((16, 16), 9.0), np.ones((16, 16), bool))
    assert not mask3.any()


def test_decay_score_geometry():
    mask = np.zeros((16, 16), bool)
    mask[8, 8] = True
    s = T.decay_score(mask, np.ones_like(mask))
    assert s[8, 8] == 1.0
    assert abs(s[8, 9] - (1 - 1 / 3)) < 1e-6
    assert s[8, 11] == 0.0 and s[0, 0] == 0.0
    assert T.decay_score(np.zeros((4, 4), bool), np.ones((4, 4), bool)).max() == 0.0


def test_c1_documents_recovery_failure_suspended():
    # Addendum 4: H1 SUSPENDED. Bar was >= 0.70; measured 0.23 on the
    # locked fixture. Fails only if recovery ever reaches the bar.
    from gems46 import emission
    tmi, grav, tmih, gravh, contact = T.synthetic_c1()
    valid = np.ones(tmi.shape, bool)
    field, support, _ = T.score_pair(tmi, grav, tmih, gravh, valid)
    emit, _ = emission.greedy_emit(field, support, 200, min_dist=3, smooth_px=1.85)
    assert emit.sum() == 200
    ys, xs = np.nonzero(emit)
    frac = float((np.abs(xs - contact) <= 3).mean())
    assert frac < 0.50, f"unexpectedly good: C-S1 recovery {frac}"


def test_c2_noise_stays_quiet_and_scattered():
    from gems46 import emission
    tmi, grav, tmih, gravh = T.synthetic_c2()
    valid = np.ones(tmi.shape, bool)
    field, support, _ = T.score_pair(tmi, grav, tmih, gravh, valid)
    # Addendum 4: H1 SUSPENDED. Bar was max < 0.5; measured 0.82.
    assert float(field.max()) >= 0.5, "unexpectedly quiet"
    emit, _ = emission.greedy_emit(field, support, 200, min_dist=3, smooth_px=1.85)
    if emit.sum() >= 20:
        ys, xs = np.nonzero(emit)
        worst = max(float((((xs >= lo) & (xs < lo + 6)).mean())) for lo in range(0, 256, 6))
        assert worst <= 0.25, f"C-S2 worst strip {worst}"


def test_c3_separated_sources_no_phantom():
    tmi, grav, tmih, gravh = T.synthetic_c3()
    valid = np.ones(tmi.shape, bool)
    field, _, _ = T.score_pair(tmi, grav, tmih, gravh, valid)
    # Addendum 4: H1 SUSPENDED. Bar was max < 0.3; measured 1.0.
    assert float(field.max()) >= 0.3, "unexpectedly clean"


def test_determinism():
    tmi, grav, tmih, gravh, _ = T.synthetic_c1()
    valid = np.ones(tmi.shape, bool)
    f1, _, _ = T.score_pair(tmi, grav, tmih, gravh, valid)
    f2, _, _ = T.score_pair(tmi, grav, tmih, gravh, valid)
    np.testing.assert_array_equal(f1, f2)
