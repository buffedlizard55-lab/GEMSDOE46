"""Detrended fluctuation analysis (DFA) - reference and vectorised sliding-window estimators.

Method source (the DFA of Peng et al.):
  Peng, C.-K., Buldyrev, S. V., Havlin, S., Simons, M., Stanley, H. E., Goldberger, A. L. (1994).
  "Mosaic organization of DNA nucleotides." Physical Review E 49(2), 1685-1689.
  https://doi.org/10.1103/PhysRevE.49.1685
The theoretical calibration used in tests/ is the standard one for this estimator:
  uncorrelated (white-noise) series            -> exponent alpha ~ 0.5
  fractional Gaussian noise with Hurst H       -> exponent alpha ~ H
  random walk / fBm(H=0.5)                     -> exponent alpha ~ 1.5

Two implementations are provided so the fast one can be checked against the slow one:

``alpha_reference``  straight transcription of the DFA algorithm (O(N * scales) Python loops over
                     blocks).  Used only in tests and on short series.

``transect_alpha``   vectorised sliding-window DFA for a long 1-D transect.  All scales must divide
                     the block stride, which lets every window's residuals be assembled from
                     globally indexed blocks with prefix sums (no per-window Python loop).

``alpha_map``        runs ``transect_alpha`` down every row and across every column of a 2-D band
                     and returns two coarse exponent maps (row-transect and column-transect).
"""

from __future__ import annotations

import numpy as np

DEFAULT_SCALES = (8, 16, 32, 64)


def _profile(y: np.ndarray) -> np.ndarray:
    """DFA profile: cumulative sum of the mean-removed series."""
    y = np.asarray(y, dtype=np.float64)
    return np.cumsum(y - y.mean())


def _block_rss(y: np.ndarray, n: int) -> np.ndarray:
    """Residual sum of squares of the least-squares linear fit inside each non-overlapping block.

    Returns an array of length len(y) // n (the tail that does not fill a block is dropped).
    """
    m = y.size // n
    if m == 0:
        return np.zeros(0, dtype=np.float64)
    a = y[: m * n].reshape(m, n).astype(np.float64)
    t = np.arange(n, dtype=np.float64)
    tsum = t.sum()
    ttsum = float((t * t).sum())
    denom = n * ttsum - tsum * tsum
    s = a.sum(axis=1)
    st = a @ t
    slope = (n * st - s * tsum) / denom
    inter = (s - slope * tsum) / n
    ssq = (a * a).sum(axis=1)
    # RSS = sum a^2 - 2*inter*sum a - 2*slope*sum(t a) + n*inter^2 + 2*inter*slope*tsum + slope^2*ttsum
    return ssq - 2.0 * inter * s - 2.0 * slope * st + n * inter ** 2 + 2.0 * inter * slope * tsum \
        + slope ** 2 * ttsum


def fluct(y: np.ndarray, n: int) -> float:
    """DFA fluctuation F(n) for scale ``n`` on series ``y`` (non-overlapping blocks)."""
    y = np.asarray(y, dtype=np.float64)
    prof = _profile(y)
    rss = _block_rss(prof, n)
    m = rss.size
    if m == 0:
        return float("nan")
    return float(np.sqrt(rss.sum() / (m * n)))


def alpha_reference(y: np.ndarray, scales=DEFAULT_SCALES) -> float:
    """Reference DFA exponent: least-squares slope of log F(n) vs log n."""
    y = np.asarray(y, dtype=np.float64)
    f = np.array([fluct(y, int(n)) for n in scales], dtype=np.float64)
    good = np.isfinite(f) & (f > 0)
    if good.sum() < 2:
        return float("nan")
    return float(np.polyfit(np.log(np.asarray(scales, dtype=np.float64)[good]),
                            np.log(f[good]), 1)[0])


def transect_alpha(y, window: int = 128, stride: int = 8, scales=DEFAULT_SCALES,
                   min_blocks: int = 2):
    """Sliding-window DFA exponent along one transect.

    Parameters
    ----------
    y          : 1-D series (must be finite; the caller fills non-finite samples).
    window     : window length in samples.
    stride     : step between window starts (any positive integer).
    scales     : block lengths.  A window contributes to a scale only through the blocks that lie
                 *wholly* inside it, so ``stride`` is unconstrained (a fine stride buys localisation
                 resolution; it does not change the estimator).
    min_blocks : a scale is dropped from a window if fewer than this many blocks fit inside it.

    Returns
    -------
    centers : window-centre sample indices
    alpha   : local least-squares slope of log F(n) vs log n (NaN where unusable)
    """
    y = np.asarray(y, dtype=np.float64)
    if not np.isfinite(y).all():
        raise ValueError("transect contains non-finite samples; fill them first")
    ln = y.size
    scales = tuple(int(s) for s in scales)
    if ln < window:
        return np.zeros(0, int), np.zeros(0, np.float64)
    prof = np.cumsum(y - y.mean())
    starts = np.arange(0, ln - window + 1, stride)
    if starts.size == 0:
        starts = np.array([ln - window], dtype=int)
    cum = {}
    for s in scales:
        rss = _block_rss(prof, s)
        cum[s] = np.concatenate([[0.0], np.cumsum(rss)])
    f = np.full((starts.size, len(scales)), np.nan, dtype=np.float64)
    for j, s in enumerate(scales):
        a = np.ceil(starts / s).astype(np.int64)
        m = (starts + window) // s - a
        good = m >= int(min_blocks)
        if not good.any():
            continue
        c = cum[s]
        a_g, m_g = a[good], m[good]
        ok = (a_g + m_g) < c.size
        rss_sum = np.full(a_g.shape, np.nan)
        rss_sum[ok] = c[a_g[ok] + m_g[ok]] - c[a_g[ok]]
        with np.errstate(invalid="ignore"):
            f[good, j] = np.where(rss_sum > 0, np.sqrt(rss_sum / (m_g * s)), np.nan)
    logn = np.log(np.asarray(scales, dtype=np.float64))
    alpha = np.full(starts.size, np.nan, dtype=np.float64)
    ok = np.isfinite(f).all(axis=1) & (f > 0).all(axis=1)
    if ok.any():
        lf = np.log(f[ok])
        lf_c = lf - lf.mean(axis=1, keepdims=True)
        logn_c = logn - logn.mean()
        alpha[ok] = (lf_c * logn_c).sum(axis=1) / float((logn_c ** 2).sum())
    centers = starts + window // 2
    return centers, alpha


def _runs(mask: np.ndarray):
    """Contiguous True runs of a 1-D boolean array as (start, stop) pairs."""
    m = np.asarray(mask, dtype=bool)
    if not m.any():
        return []
    edges = np.flatnonzero(np.diff(np.concatenate([[0], m.view(np.int8), [0]])))
    return list(zip(edges[0::2], edges[1::2]))


def transect_alpha_runs(values: np.ndarray, valid: np.ndarray, window: int = 128, stride: int = 8,
                        scales=DEFAULT_SCALES):
    """DFA exponent along a transect, computed only inside contiguous valid runs.

    No interpolation of gaps is performed: a window is evaluated only if it lies wholly inside one
    contiguous valid run of the transect, so the exponent never sees invented samples.  Returns
    (center_indices_global, alpha) with NaN omitted.
    """
    idx, vals = [], []
    for a, b in _runs(valid):
        if b - a < window:
            continue
        y = np.nan_to_num(values[a:b].astype(np.float64), nan=0.0)
        c, al = transect_alpha(y, window=window, stride=stride, scales=scales)
        idx.append(c + a)
        vals.append(al)
    if not idx:
        return np.zeros(0, int), np.zeros(0, np.float64)
    return np.concatenate(idx), np.concatenate(vals)


def alpha_map(band: np.ndarray, valid: np.ndarray, window: int = 128, stride: int = 8,
              scales=DEFAULT_SCALES):
    """Local DFA exponent along every row and every column transect inside ``valid``.

    Returns ``(row_map, col_map, row_centers, col_centers)``:
      * ``row_map``  (n_rows, n_windows) with NaN outside the valid runs,
      * ``col_map``  (n_windows, n_cols) likewise.
    The window centre index of window j is ``j * stride + window // 2`` (rows and columns may differ
    in length, hence separate centre arrays).
    """
    band = np.asarray(band, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if band.shape != valid.shape:
        raise ValueError("band and valid must have the same shape")
    nrows, ncols = band.shape
    n_win_r = max(0, (ncols - window) // stride + 1)
    n_win_c = max(0, (nrows - window) // stride + 1)
    row_map = np.full((nrows, n_win_r), np.nan, dtype=np.float32)
    col_map = np.full((n_win_c, ncols), np.nan, dtype=np.float32)
    for i in range(nrows):
        c, a = transect_alpha_runs(band[i], valid[i], window, stride, scales)
        if c.size:
            cols = c // stride
            inb = cols < n_win_r
            row_map[i, cols[inb]] = a[inb].astype(np.float32)
    for j in range(ncols):
        c, a = transect_alpha_runs(band[:, j], valid[:, j], window, stride, scales)
        if c.size:
            rows = c // stride
            inb = rows < n_win_c
            col_map[rows[inb], j] = a[inb].astype(np.float32)
    row_centers = np.arange(n_win_r) * stride + window // 2
    col_centers = np.arange(n_win_c) * stride + window // 2
    return row_map, col_map, row_centers, col_centers
