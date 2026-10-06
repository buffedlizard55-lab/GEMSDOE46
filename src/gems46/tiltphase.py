"""Tilt-phase zero-crossing coincidence scorer (R11-C).

Physics: the tilt angle T = atan(VDR / THDR) of a potential field is zero
directly over a contact edge (vertical derivative zero, horizontal gradient
maximal; Salem et al. 2007, standard contact mapping). The zero contour is a
PHASE property: it locates the edge independent of the anomaly's amplitude,
so weak-contrast buried contacts carry the same phase signature as strong
ones. R11-C requires the VDR zero-crossings of TMI (band 9) and isostatic
gravity (band 11) to coincide within the metric's 300 m kernel. Ranking is
phase-pure (signs only); the THDR grids (bands 3/18) enter solely as a
binary significance gate, per the published tilt method (Salem et al. 2007:
tilt zero AND large horizontal gradient). Locked design: Addendum 1 +
Amendments 3/3b (range hysteresis measured useless at density 0.89;
multi-scale persistence still percolated at 0.29-0.57, so the literature
THDR gate was restored) of docs/research/session-r11-plan.md; synthetic
gates: Addendum 2 + Amendment 3.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

THDR_MAD_K = 3.0  # robust-z significance gate on the pixel THDR (Amendment 3c)
DECAY_PX = 3.0  # 300 m kernel-matched decay


def _sign_crossings(pos: np.ndarray, valid: np.ndarray):
    """4-neighbourhood sign-change pixels (no wraparound; neighbors valid)."""
    neg = ~pos & valid
    pos = pos & valid
    cross = np.zeros(valid.shape, dtype=bool)
    h, w = valid.shape
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ys0, ys1 = max(0, dy), min(h, h + dy)
        xs0, xs1 = max(0, dx), min(w, w + dx)
        yd0, yd1 = max(0, -dy), min(h, h - dy)
        xd0, xd1 = max(0, -dx), min(w, w - dx)
        if ys0 >= ys1 or xs0 >= xs1:
            continue
        pv = np.zeros_like(pos)
        nv = np.zeros_like(neg)
        vv = np.zeros_like(valid)
        pv[ys0:ys1, xs0:xs1] = pos[yd0:yd1, xd0:xd1]
        nv[ys0:ys1, xs0:xs1] = neg[yd0:yd1, xd0:xd1]
        vv[ys0:ys1, xs0:xs1] = valid[yd0:yd1, xd0:xd1]
        cross |= valid & vv & ((pos & nv) | (neg & pv))
    return cross


def tilt_contacts(vdr: np.ndarray, thdr: np.ndarray, valid: np.ndarray,
                  mad_k: float = THDR_MAD_K):
    """Tilt contacts: raw-scale VDR zero-crossings AND significant THDR.

    Keeps a sign crossing only where the pixel THDR exceeds
    median + mad_k * MAD over valid (robust-z significance gate; the
    published tilt criterion). Returns (mask, diagnostics dict).
    """
    vdr = np.asarray(vdr, dtype=np.float64)
    thdr = np.asarray(thdr, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    assert vdr.shape == thdr.shape == valid.shape
    cross = _sign_crossings(vdr >= 0, valid)
    t = thdr[valid]
    med = float(np.median(t)) if t.size else 0.0
    mad = float(np.median(np.abs(t - med))) * 1.4826 if t.size else 0.0
    gate = med + mad_k * (mad if mad > 1e-12 else (float(t.std()) or 1.0))
    mask = cross & valid & (thdr > gate)
    diag = dict(raw=int(cross.sum()), kept=int(mask.sum()),
                gate=float(gate),
                density=float(mask.sum() / max(valid.sum(), 1)))
    return mask, diag


def decay_score(mask: np.ndarray, valid: np.ndarray, radius_px: float = DECAY_PX):
    """Kernel-matched proximity score: max(0, 1 - d/radius), zero outside valid."""
    mask = np.asarray(mask, dtype=bool)
    valid = np.asarray(valid, dtype=bool)
    if not mask.any():
        return np.zeros(valid.shape, dtype=np.float32)
    d = ndimage.distance_transform_edt(~mask)
    return (np.clip(1.0 - d / radius_px, 0, 1) * valid).astype(np.float32)


def coincidence(score_a: np.ndarray, score_b: np.ndarray):
    """Geometric-mean coincidence of two [0,1] proximity scores."""
    return np.sqrt(np.clip(score_a, 0, 1) * np.clip(score_b, 0, 1)).astype(np.float32)


def score_pair(tmi_vg: np.ndarray, grav_vg: np.ndarray,
               tmi_thdr: np.ndarray, grav_thdr: np.ndarray, valid: np.ndarray):
    """Full R11-C field for one grid. Returns (field, support, diagnostics)."""
    valid = np.asarray(valid, dtype=bool)
    mt, dt = tilt_contacts(tmi_vg, tmi_thdr, valid)
    mg, dg = tilt_contacts(grav_vg, grav_thdr, valid)
    st = decay_score(mt, valid)
    sg = decay_score(mg, valid)
    field = coincidence(st, sg) * valid
    diag = dict(tmi=dt, gravity=dg, field_max=float(field.max()),
                field_mean=float(field[valid].mean()) if valid.any() else 0.0)
    return field.astype(np.float32), valid.copy(), diag


# ---------------------------------------------------------------------------
# Locked synthetic fixtures (Addendum 2; seeds fixed)
# ---------------------------------------------------------------------------

def _wavelet(n: int, contact: int, sigma: float):
    x = np.arange(n, dtype=float) - contact
    return -(x / sigma ** 2) * np.exp(-(x ** 2) / (2 * sigma ** 2))


def _ridge(n: int, contact: int, sigma: float):
    x = np.arange(n, dtype=float) - contact
    return np.exp(-(x ** 2) / (2 * sigma ** 2))


NOISE_SIGMA_PX = 2.5  # fixture noise correlation ~= survey line spacing
NOISE_STD = 0.05


def _smooth_noise(n: int, rng: np.random.Generator):
    z = ndimage.gaussian_filter(rng.normal(size=(n, n)), NOISE_SIGMA_PX,
                                mode="nearest")
    return (z / z.std() * NOISE_STD).astype(np.float64)


def _with_thdr(vdr_1d: np.ndarray, n: int, contact: int, sigma: float,
               rng: np.random.Generator):
    vdr = np.tile(vdr_1d, (n, 1)) + _smooth_noise(n, rng)
    thdr = np.abs(np.tile(_ridge(n, contact, sigma), (n, 1))
                  + _smooth_noise(n, rng))
    return vdr.astype(np.float64), thdr.astype(np.float64)


def synthetic_c1(seed: int = 1201, n: int = 256, contact: int = 128):
    """Coincident contacts: TMI sigma=3, gravity sigma=4 + independent noise."""
    rng = np.random.default_rng(seed)
    tmi, tmi_h = _with_thdr(_wavelet(n, contact, 3.0), n, contact, 3.0, rng)
    grav, grav_h = _with_thdr(_wavelet(n, contact, 4.0), n, contact, 4.0, rng)
    return tmi, grav, tmi_h, grav_h, contact


def synthetic_c2(seed: int = 1202, n: int = 256):
    """Pure-noise control: no contacts (instrument-realistic smooth noise)."""
    rng = np.random.default_rng(seed)
    return (_smooth_noise(n, rng), _smooth_noise(n, rng),
            np.abs(_smooth_noise(n, rng)), np.abs(_smooth_noise(n, rng)))


def synthetic_c3(seed: int = 1203, n: int = 256):
    """Separated contacts 16 px apart (TMI x=120, gravity x=136)."""
    rng = np.random.default_rng(seed)
    tmi, tmi_h = _with_thdr(_wavelet(n, 120, 3.0), n, 120, 3.0, rng)
    grav, grav_h = _with_thdr(_wavelet(n, 136, 4.0), n, 136, 4.0, rng)
    return tmi, grav, tmi_h, grav_h
