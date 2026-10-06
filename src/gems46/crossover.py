"""Window-local DFA1 crossover. No amplitude or spatial derivative enters the score."""
import numpy as np
from scipy import ndimage

SCALES = (8, 16, 32, 64, 96, 128)


def slopes(windows, scales=SCALES):
    """Exact least-squares residuals, avoiding cancellation of large RSS terms.

    Returns full, short and long log-log slopes. Constant/invalid windows give NaN.
    """
    a = np.asarray(windows, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] < 4 * max(scales):
        raise ValueError('need 2-D windows and at least four largest-scale blocks')
    finite = np.isfinite(a).all(axis=1)
    centered = a - a.mean(axis=1, keepdims=True)
    sd = centered.std(axis=1, keepdims=True)
    valid = finite & (sd[:, 0] > 0)
    # Standardizing changes F's intercept, never its slope; improves numerical stability.
    profile = np.cumsum(np.divide(centered, sd, out=np.zeros_like(a), where=sd > 0), axis=1)
    fluctuations = []
    for n in scales:
        nblocks = a.shape[1] // n
        b = profile[:, :nblocks*n].reshape(len(a), nblocks, n)
        t = np.arange(n, dtype=float) - (n-1)/2
        b = b - b.mean(axis=2, keepdims=True)
        trend = (b*t).sum(axis=2, keepdims=True)/np.dot(t,t)*t
        fluctuations.append(np.sqrt(np.mean((b-trend)**2, axis=(1,2))))
    f = np.stack(fluctuations, axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        lf = np.log(f)
    lf[~valid] = np.nan
    def fit(ids):
        x = np.log(np.asarray(scales)[ids]); x -= x.mean()
        y = lf[:, ids]
        out = ((y-y.mean(axis=1, keepdims=True))*x).sum(axis=1)/np.dot(x,x)
        out[~valid | ~np.isfinite(out)] = np.nan
        return out
    return fit(slice(None)), fit(slice(0,3)), fit(slice(2,None))


def coarse_maps(band, valid, window=512, stride=16):
    """Both orientations on identical physical centers; no invented values across gaps."""
    h,w = band.shape
    rows = np.arange(window//2, h-window//2+1, stride)
    cols = np.arange(window//2, w-window//2+1, stride)
    output = np.full((2,3,len(rows),len(cols)), np.nan, dtype=np.float32)
    for orientation in range(2):
        a,v = (band,valid) if orientation == 0 else (band.T,valid.T)
        across,along = (rows,cols) if orientation == 0 else (cols,rows)
        for i, pos in enumerate(across):
            starts = along-window//2
            windows = np.lib.stride_tricks.sliding_window_view(a[pos], window)[starts]
            good = np.lib.stride_tricks.sliding_window_view(v[pos], window)[starts].all(axis=1)
            if good.any():
                result = np.stack(slopes(windows[good]))
                if orientation == 0:
                    output[orientation,:,i,good] = result.T
                else:
                    output[orientation,:,good,i] = result.T
    return output, rows, cols


def score_maps(maps):
    """Require both orientations; median background is a descriptive local reference."""
    valid = np.isfinite(maps).all(axis=(0,1))
    long = np.mean(maps[:,2], axis=0)
    cross = np.mean(np.abs(maps[:,2]-maps[:,1]), axis=0)
    if not valid.any():
        return np.zeros(long.shape, np.float32), valid
    filled = np.where(valid,long,np.median(long[valid]))
    background = ndimage.median_filter(filled, size=31, mode='nearest')
    score = np.sqrt(np.maximum(0, cross*np.abs(long-background)))
    scale = np.percentile(score[valid],99)
    score = np.where(valid,np.clip(score/max(scale,1e-12),0,1),0)
    return score.astype(np.float32),valid


def expand(coarse, valid, rows, cols, shape):
    """Nearest-center placement; do not extrapolate outside evaluated center extent."""
    yy = np.abs(np.arange(shape[0])[:,None]-rows).argmin(axis=1)
    xx = np.abs(np.arange(shape[1])[:,None]-cols).argmin(axis=1)
    out = coarse[yy[:,None],xx]
    support = valid[yy[:,None],xx].copy()
    support[:rows[0]] = False; support[rows[-1]+1:] = False
    support[:,:cols[0]] = False; support[:,cols[-1]+1:] = False
    return np.where(support,out,0).astype(np.float32),support
