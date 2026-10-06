"""Localized DFA regime-boundary scorer (R11-A, Amendment 1).

Method basis: Peng et al. DFA (Physical Review E 49, 1685, 1994;
https://doi.org/10.1103/PhysRevE.49.1685) via the PhysioNet definition
(integrate, box, least-squares detrend, RMS fluctuation, log-log slope;
https://archive.physionet.org/physiotools/dfa/). The fluctuation math is
identical to :mod:`gems46.crossover` (exact least-squares residuals on the
standardized cumulative profile). Locked parameters and the Amendment-1
record (why the crossover product and the 2-point secant were dropped after
measuring 5.6 km mislocalization on the locked synthetic) are in
docs/research/session-r11-plan.md.

R11-A in one paragraph: raw RTP / isostatic-gravity row and column
transects, 128-sample (12.8 km) windows on a 4-pixel (400 m) center grid,
full-range DFA1 slope over scales 4..32 samples (0.4-3.2 km). Per
orientation and physics, the exponent is z-scored against its
WITHIN-ACQUISITION-BLOCK background (survey-processing control) and the
score is the p99-normalized |grad z| boundary magnitude. Orientations
combine by MAX, physics combine by MEAN.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

SCALES = (4, 8, 16, 32)
WINDOW = 128
STRIDE = 4
MIN_BLOCK_CELLS = 25


def fluctuations(windows: np.ndarray, scales=SCALES):
    """RMS DFA1 fluctuation per window and scale (exact residual math).

    Returns (f, valid): f (n_windows, n_scales) RMS residuals, valid bool.
    Per-window standardization changes only the intercept, never the slope.
    """
    a = np.asarray(windows, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] < 4 * max(scales):
        raise ValueError("need 2-D windows and at least four largest-scale blocks")
    finite = np.isfinite(a).all(axis=1)
    centered = a - a.mean(axis=1, keepdims=True)
    sd = centered.std(axis=1, keepdims=True)
    valid = finite & (sd[:, 0] > 0)
    profile = np.cumsum(np.divide(centered, sd, out=np.zeros_like(a), where=sd > 0), axis=1)
    out = []
    for n in scales:
        nblocks = a.shape[1] // n
        b = profile[:, : nblocks * n].reshape(len(a), nblocks, n)
        t = np.arange(n, dtype=float) - (n - 1) / 2
        b = b - b.mean(axis=2, keepdims=True)
        trend = (b * t).sum(axis=2, keepdims=True) / np.dot(t, t) * t
        out.append(np.sqrt(np.mean((b - trend) ** 2, axis=(1, 2))))
    f = np.stack(out, axis=1)
    return f, valid


def fit_full(f: np.ndarray, window_valid: np.ndarray, scales=SCALES):
    """Full-range log-log slope per window. NaN where unusable."""
    f = np.asarray(f, dtype=np.float64)
    wvalid = np.asarray(window_valid, dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        lf = np.log(f)
    x = np.log(np.asarray(scales, dtype=float))
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    ok = wvalid & np.isfinite(lf).all(axis=1)
    out = np.full(len(f), np.nan)
    if ok.any() and denom > 0:
        yc = lf[ok] - lf[ok].mean(axis=1, keepdims=True)
        out[ok] = (yc * xc).sum(axis=1) / denom
    out[~np.isfinite(out)] = np.nan
    return out


def slopes(windows: np.ndarray, scales=SCALES):
    """Full-range DFA exponent per window (NaN for constant/invalid windows)."""
    f, valid = fluctuations(windows, scales)
    return fit_full(f, valid, scales)


def coarse_maps(band: np.ndarray, valid: np.ndarray, window: int = WINDOW,
                stride: int = STRIDE, scales=SCALES):
    """Full-range DFA exponent on the shared (rows x cols) center grid.

    Returns (maps, rows, cols): maps (2, n_rows, n_cols) with maps[0] =
    row-transect exponents, maps[1] = column-transect exponents. A window is
    evaluated only if every sample is valid (no invented data).
    """
    band = np.asarray(band, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    h, w = band.shape
    rows = np.arange(window // 2, h - window // 2 + 1, stride)
    cols = np.arange(window // 2, w - window // 2 + 1, stride)
    if len(rows) == 0 or len(cols) == 0:
        raise ValueError("grid too small for window")
    out = np.full((2, len(rows), len(cols)), np.nan, dtype=np.float32)
    for orientation in range(2):
        a, v = (band, valid) if orientation == 0 else (band.T, valid.T)
        across, along = (rows, cols) if orientation == 0 else (cols, rows)
        for i, pos in enumerate(across):
            starts = along - window // 2
            win = np.lib.stride_tricks.sliding_window_view(a[pos], window)[starts]
            good = np.lib.stride_tricks.sliding_window_view(v[pos], window)[starts].all(axis=1)
            if not good.any():
                continue
            al = slopes(win[good], scales)
            assert al.shape == (int(good.sum()),)
            if orientation == 0:
                out[0, i, good] = al
            else:
                out[1, good, i] = al
    return out, rows, cols


def _block_z(alpha: np.ndarray, support: np.ndarray, blocks: np.ndarray,
             min_cells: int = MIN_BLOCK_CELLS):
    """Within-block z-score of the exponent. Small/outside blocks give z=0."""
    z = np.zeros(alpha.shape, dtype=np.float32)
    big = np.zeros(support.shape, dtype=bool)
    for bid in (1, 2, 3, 4):
        cells = support & (blocks == bid)
        n = int(cells.sum())
        if n < min_cells:
            continue
        x = alpha[cells].astype(np.float64)
        med = float(np.median(x))
        mad = float(np.median(np.abs(x - med))) * 1.4826
        if not np.isfinite(mad) or mad <= 1e-9:
            mad = float(x.std()) or 1.0
        z[cells] = ((x - med) / mad).astype(np.float32)
        big[cells] = True
    return z, big


def score_physics(maps: np.ndarray, blocks: np.ndarray,
                  min_cells: int = MIN_BLOCK_CELLS):
    """Per-orientation R11-A boundary scores for one physics band.

    score_o = p99-normalized |grad z| with z block-stratified.
    Returns (scores, masks): (2, nr, nc) float32 in [0,1], (2, nr, nc) bool.
    The gradient is evaluated only on the 1-eroded support (anti-edge artifact).
    """
    maps = np.asarray(maps, dtype=np.float32)
    blocks = np.asarray(blocks)
    _, nr, nc = maps.shape
    assert blocks.shape == (nr, nc)
    scores = np.zeros((2, nr, nc), dtype=np.float32)
    masks = np.zeros((2, nr, nc), dtype=bool)
    for o in range(2):
        alpha = maps[o]
        support = np.isfinite(alpha) & (blocks >= 1) & (blocks <= 4)
        if not support.any():
            continue
        z, big = _block_z(alpha, support, blocks, min_cells)
        gy, gx = np.gradient(z.astype(np.float64))
        bnd = np.hypot(gy, gx)
        mask = ndimage.binary_erosion(support & big, iterations=1)
        if not mask.any():
            continue
        bs = float(np.percentile(bnd[mask], 99))
        scores[o][mask] = np.clip(bnd[mask] / max(bs, 1e-12), 0, 1).astype(np.float32)
        masks[o] = mask
    return scores, masks


def combine_orientations(scores: np.ndarray, masks: np.ndarray):
    """MAX over orientations (strike-preserving). Returns (score, mask)."""
    m = np.asarray(masks, dtype=bool)
    s = np.where(m, np.asarray(scores, dtype=np.float32), 0.0)
    return s.max(axis=0).astype(np.float32), m.any(axis=0)


def combine_physics(scores, masks):
    """MEAN over available physics (coverage fix vs a strict minimum)."""
    s = np.stack([np.asarray(x, dtype=np.float32) for x in scores], axis=0)
    m = np.stack([np.asarray(x, dtype=bool) for x in masks], axis=0)
    n = m.sum(axis=0)
    field = np.where(n > 0, (s * m).sum(axis=0) / np.maximum(n, 1), 0.0)
    return field.astype(np.float32), (n > 0)


def sliding_1d(x: np.ndarray, window: int = WINDOW, stride: int = STRIDE,
               scales=SCALES):
    """1-D sliding DFA exponents (synthetic gates). Returns centers, alpha."""
    x = np.asarray(x, dtype=np.float64)
    starts = np.arange(0, len(x) - window + 1, stride)
    win = np.lib.stride_tricks.sliding_window_view(x, window)[starts]
    return starts + window // 2, slopes(win, scales)


def score_1d(alpha: np.ndarray):
    """1-D analog of score_physics with a global background (synthetics)."""
    alpha = np.asarray(alpha, dtype=np.float64)
    support = np.isfinite(alpha)
    score = np.zeros(alpha.shape, dtype=np.float64)
    mask = ndimage.binary_erosion(support, iterations=1)
    if not mask.any() or support.sum() < 8:
        return score, mask
    x = alpha[support]
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) * 1.4826 or float(x.std()) or 1.0
    z = np.zeros(alpha.shape)
    z[support] = (x - med) / mad
    bnd = np.abs(np.gradient(z))
    bs = float(np.percentile(bnd[mask], 99))
    score[mask] = np.clip(bnd[mask] / max(bs, 1e-12), 0, 1)
    return score, mask


# ---------------------------------------------------------------------------
# Locked synthetic fixtures (Amendment 1: stationary fGn; seeds fixed)
# ---------------------------------------------------------------------------

def fgn(n: int, hurst: float, rng: np.random.Generator):
    """Stationary fractional Gaussian noise via Fourier filtering (unit variance).

    DFA exponent alpha ~= hurst (verified: 0.38/0.55/0.90 for H=0.3/0.5/0.9).
    """
    white = rng.normal(size=n)
    freqs = np.fft.rfftfreq(n)
    freqs[0] = freqs[1]
    filt = freqs ** (0.5 - float(hurst))
    x = np.fft.irfft(np.fft.rfft(white) * filt, n)
    return ((x - x.mean()) / x.std()).astype(np.float64)


def synthetic_s1(seed: int = 1101, n: int = 512, boundary: int = 256):
    """fGn H=0.3 | H=0.9 texture step (stationary, sharp, no amplitude step)."""
    rng = np.random.default_rng(seed)
    return np.concatenate([fgn(boundary, 0.3, rng), fgn(n - boundary, 0.9, rng)]), boundary


def synthetic_s2(seed: int = 1102, n: int = 512):
    """Ramp + stationary noise (texture-stationary gradient control)."""
    rng = np.random.default_rng(seed)
    return np.linspace(0, 10, n) + 0.1 * rng.normal(size=n)


def synthetic_s3(seed: int = 1103, n: int = 256, boundary: int = 128):
    """2-D fGn half-planes: independent per-row fGn H=0.3 | H=0.9.

    Row transects see the step; column transects see uniform white noise
    (rows are independent), which exercises the orientation-MAX design.
    """
    rng = np.random.default_rng(seed)
    left = np.stack([fgn(boundary, 0.3, rng) for _ in range(n)])
    right = np.stack([fgn(n - boundary, 0.9, rng) for _ in range(n)])
    return np.concatenate([left, right], axis=1).astype(np.float32), boundary
