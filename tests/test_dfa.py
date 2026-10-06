"""DFA verification against the standard calibrations of the estimator (synthetic series)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems46 import dfa as D  # noqa: E402


def fgn(n: int, H: float, seed: int = 0, J: int = 50) -> np.ndarray:
    """Fractional Gaussian noise by exact spectral synthesis (Percival & Walden spectrum).

    S(f) = (2 sin(pi f))^2 * sum_{j=-J..J} |2 pi (f + j)|^{-(2H+1)},  f in (0, 1/2].

    The exact form is used (not the |f|^{-(2H-1)} approximation) because it is valid on both sides
    of H = 1/2; the checks below cover H = 0.2 (anti-correlated), 0.5 (white) and 0.8.
    """
    rng = np.random.default_rng(seed)
    k = np.arange(1, n // 2 + 1)
    f = k / n
    j = np.arange(-J, J + 1)
    power = np.abs(2 * np.pi * (f[:, None] + j[None, :])) ** (-(2 * H + 1))
    S = (2 * np.sin(np.pi * f)) ** 2 * power.sum(axis=1)
    phase = rng.uniform(0, 2 * np.pi, size=k.size)
    y = np.fft.irfft(np.concatenate([[0.0], np.sqrt(S) * np.exp(1j * phase)]), n=n)
    return (y - y.mean()) / y.std()


def test_white_noise_half():
    rng = np.random.default_rng(1)
    est = [D.alpha_reference(rng.normal(size=4096)) for _ in range(6)]
    assert np.mean(est) == pytest.approx(0.5, abs=0.05)


def test_random_walk_three_halves():
    rng = np.random.default_rng(2)
    est = [D.alpha_reference(np.cumsum(rng.normal(size=4096))) for _ in range(4)]
    assert np.mean(est) == pytest.approx(1.5, abs=0.10)


@pytest.mark.parametrize("H", [0.2, 0.5, 0.8])
def test_fgn_exponent_equals_hurst(H):
    """DFA of fractional Gaussian noise recovers the Hurst exponent (Peng et al. 1994)."""
    est = [D.alpha_reference(fgn(8192, H, seed=100 + i)) for i in range(4)]
    assert np.mean(est) == pytest.approx(H, abs=0.08)


def test_exponent_covers_the_documented_transition_range():
    """The 0.5 -> 0.9 shift the hypothesis is about is measurable end to end."""
    low = np.mean([D.alpha_reference(fgn(8192, 0.5, seed=200 + i)) for i in range(3)])
    high = np.mean([D.alpha_reference(fgn(8192, 0.9, seed=300 + i)) for i in range(3)])
    assert low < 0.6 and high > 0.85 and (high - low) > 0.3


def test_vectorised_matches_reference_exactly_on_one_window():
    """One window spanning the whole series must reproduce the reference estimator exactly."""
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.normal(size=4096))
    ref = D.alpha_reference(y, scales=D.DEFAULT_SCALES)
    centers, alphas = D.transect_alpha(y, window=4096, stride=4096)
    assert alphas.size == 1
    assert float(alphas[0]) == pytest.approx(ref, abs=1e-9)


def test_vectorised_local_windows_are_within_sampling_error():
    """Local windows use fewer blocks than the whole series, so allow estimator sampling error."""
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.normal(size=4096))
    ref = D.alpha_reference(y, scales=D.DEFAULT_SCALES)
    centers, alphas = D.transect_alpha(y, window=1024, stride=512)
    assert alphas.size >= 4
    assert np.nanmean(alphas) == pytest.approx(ref, abs=0.15)


def test_transect_alpha_windows_track_local_regime():
    """Half white noise, half long-range correlated: the local exponent must separate them."""
    rng = np.random.default_rng(3)
    y = np.concatenate([rng.normal(size=2048), fgn(2048, 0.9, seed=5)])
    centers, a = D.transect_alpha(y, window=512, stride=64)
    left = a[centers < 1800]
    right = a[centers > 2300]
    assert np.nanmean(left) == pytest.approx(0.5, abs=0.15)
    assert np.nanmean(right) > np.nanmean(left) + 0.15


def test_fine_stride_is_supported_and_consistent():
    """A fine stride must not be rejected and must reproduce the coarse-stride estimates."""
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.normal(size=2048))
    c_c, a_c = D.transect_alpha(y, window=512, stride=64)
    c_f, a_f = D.transect_alpha(y, window=512, stride=8)
    assert c_f.size > c_c.size
    shared = np.isin(c_f, c_c)
    pairs = np.interp(c_c, c_f, np.nan_to_num(a_f, nan=0.0))
    assert np.corrcoef(a_c, pairs)[0, 1] > 0.95


def test_non_finite_transect_is_rejected():
    with pytest.raises(ValueError):
        D.transect_alpha(np.array([1.0, np.nan, 2.0] * 300), window=128, stride=8)


def test_masked_runs_never_interpolate_across_gaps():
    """A window that straddles a gap must not be evaluated (no invented samples)."""
    y = np.zeros(1000)
    valid = np.ones(1000, bool)
    valid[400:600] = False
    idx, al = D.transect_alpha_runs(y, valid, window=128, stride=8)
    assert idx.size > 0
    # every evaluated window must lie wholly inside a valid run
    for c in idx:
        a, b = c - 64, c + 64
        assert valid[a:b].all()


def test_runs_helper():
    m = np.array([0, 1, 1, 0, 1, 1, 1, 0], bool)
    assert D._runs(m) == [(1, 3), (4, 7)]
