"""Matched-filter contact detector (R11-D = preregistered H3).

A contact juxtaposing contrasting susceptibilities/densities imprints a
step on the RTP anomaly and on isostatic gravity. The detector correlates
each grid with a zero-mean step template (Pearson r: fully
amplitude-invariant, so weak-contrast buried contacts match as well as
strong ones) at four strike angles, takes max |r| over angles and the
geometric mean over the two physics (dual-physics coincidence). Template
integration over 24 taps suppresses grid noise analytically (noise floor
1/sqrt(24)); the |r| >= 0.8 floor is Bonferroni family-wise 5%
significance (df=22, M ~= footprint x 4 angles ~= 2e7 tests). Locked
design: Addendum 4 + Amendment 5 of docs/research/session-r11-plan.md;
synthetic gates D-S1..S3.
"""

from __future__ import annotations

import numpy as np

HALF = 12
STEP = np.array([-1.0] * HALF + [0.0] + [1.0] * HALF, dtype=np.float64)
R_FLOOR = 0.8
MIN_VALID_FRAC = 0.8
ANGLES = (0, 45, 90, 135)


def _offsets(angle: int):
    taps = [(i - HALF, STEP[i]) for i in range(2 * HALF + 1) if STEP[i] != 0.0]
    if angle == 0:
        return [(0, dx, k) for dx, k in taps]
    if angle == 90:
        return [(dy, 0, k) for dy, k in taps]
    if angle == 45:
        return [(d, d, k) for d, k in taps]
    if angle == 135:
        return [(d, -d, k) for d, k in taps]
    raise ValueError(angle)


def masked_ncc(band: np.ndarray, valid: np.ndarray, angle: int,
               min_valid_frac: float = MIN_VALID_FRAC):
    """Pearson r of ``band`` with the step template along ``angle``.

    Masked normalized cross-correlation over valid pixels only (positions
    with fewer than ``min_valid_frac`` of taps valid are marked uncovered).
    Returns (r, covered): r float32 in [-1, 1] (0 where unusable), covered bool.
    """
    x = np.asarray(band, dtype=np.float64)
    m = np.asarray(valid, dtype=bool)
    assert x.shape == m.shape
    h, w = x.shape
    xc = np.where(m, x - float(np.median(x[m])) if m.any() else x, 0.0).astype(np.float32)
    mf = m.astype(np.float32)
    n = np.zeros((h, w), dtype=np.int32)
    sx = np.zeros((h, w), dtype=np.float64)
    sxx = np.zeros((h, w), dtype=np.float64)
    skx = np.zeros((h, w), dtype=np.float64)
    sk = np.zeros((h, w), dtype=np.float64)
    skk = np.zeros((h, w), dtype=np.float64)
    for dy, dx, k in _offsets(angle):
        ys0, ys1 = max(0, dy), min(h, h + dy)
        yd0, yd1 = max(0, -dy), min(h, h - dy)
        xs0, xs1 = max(0, dx), min(w, w + dx)
        xd0, xd1 = max(0, -dx), min(w, w - dx)
        mv = mf[ys0:ys1, xs0:xs1]
        xv = xc[ys0:ys1, xs0:xs1]
        sl = (slice(yd0, yd1), slice(xd0, xd1))
        n[sl] += mv.astype(np.int32, copy=False)
        sx[sl] += xv
        sxx[sl] += xv * xv
        skx[sl] += k * xv
        sk[sl] += k * mv
        skk[sl] += (k * k) * mv
    req = int(np.ceil(min_valid_frac * sum(1 for _ in _offsets(angle))))
    ok = n >= req
    r = np.zeros((h, w), dtype=np.float32)
    nn = n.astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        xbar = np.divide(sx, nn, out=np.zeros_like(sx), where=ok)
        kbar = np.divide(sk, nn, out=np.zeros_like(sk), where=ok)
        num = skx - nn * xbar * kbar
        denx = sxx - nn * xbar * xbar
        denk = skk - nn * kbar * kbar
        den = np.sqrt(np.maximum(denx, 0) * np.maximum(denk, 0))
        good = ok & (den > 1e-9)
        r[good] = np.clip(num[good] / den[good], -1, 1)
    return r, ok


def score_physics(band: np.ndarray, valid: np.ndarray,
                  angles=ANGLES, r_floor: float = R_FLOOR):
    """Per-physics contact score: max over angles of |r|, floored.

    Returns (score, covered): score float32 in [0, 1], covered bool.
    """
    best = None
    covered = None
    for a in angles:
        r, ok = masked_ncc(band, valid, a)
        ar = np.abs(r)
        best = ar if best is None else np.maximum(best, ar)
        covered = ok if covered is None else (covered | ok)
    return (np.where(best >= r_floor, best, 0.0).astype(np.float32), covered)


def score_pair(rtp: np.ndarray, grav: np.ndarray, valid: np.ndarray):
    """Full R11-D field. Returns (field, support, diagnostics)."""
    valid = np.asarray(valid, dtype=bool)
    st, ct = score_physics(rtp, valid)
    sg, cg = score_physics(grav, valid)
    field = np.sqrt(st * sg).astype(np.float32) * valid
    support = valid & ct & cg
    diag = dict(tmi_cov=float(ct.mean()), grav_cov=float(cg.mean()),
                field_max=float(field.max()),
                field_mean=float(field[support].mean()) if support.any() else 0.0)
    return field, support, diag


# ---------------------------------------------------------------------------
# Locked synthetic fixtures (Addendum 4; fresh seeds)
# ---------------------------------------------------------------------------

COMB_LINES = (64, 96, 128, 160, 192)


def synthetic_d1(seed: int = 1301, n: int = 256, lines=COMB_LINES):
    """Coincident N-S step comb (alternating 0|1) + white noise sigma=0.1."""
    rng = np.random.default_rng(seed)
    prof = np.zeros(n)
    hi = False
    edges = [0] + list(lines) + [n]
    for lo, hi_e in zip(edges[:-1], edges[1:]):
        if hi:
            prof[lo:hi_e] = 1.0
        hi = not hi
    tmi = np.tile(prof, (n, 1)) + 0.1 * rng.normal(size=(n, n))
    grav = np.tile(prof, (n, 1)) + 0.1 * rng.normal(size=(n, n))
    return tmi, grav, tuple(lines)


def synthetic_d2(seed: int = 1302, n: int = 256):
    """Pure-noise control: no contacts."""
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, n)), rng.normal(size=(n, n))


def synthetic_d3(seed: int = 1303, n: int = 256):
    """Separated steps 16 px apart (TMI x=120, gravity x=136)."""
    rng = np.random.default_rng(seed)
    pt = (np.arange(n, dtype=float) >= 120).astype(float)
    pg = (np.arange(n, dtype=float) >= 136).astype(float)
    tmi = np.tile(pt, (n, 1)) + 0.1 * rng.normal(size=(n, n))
    grav = np.tile(pg, (n, 1)) + 0.1 * rng.normal(size=(n, n))
    return tmi, grav
