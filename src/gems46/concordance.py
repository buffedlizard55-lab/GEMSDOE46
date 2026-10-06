"""R11 field construction: two-sensor scarp/regolith concordance plus a ridge-axis thinning operator.

Physical basis
--------------
1. **Scarp morphology (2 m LiDAR-derived).**  A normal fault scarp is an *oriented* slope break.
   The mirrored GeoDAWN/3DEP product supplies band-passed slope steps measured along the regional
   downslope direction (``downface_max``), against it (``upface_max``), the 10 m-vs-50 m step
   (``step_max``) and base concavity (``lappos_max``).  Averaging their ranks gives a
   morphology score that is not an amplitude or a curvature maximum of a potential field.
2. **Near-surface radiochemistry (airborne gamma-ray spectrometry).**  Gamma rays sample the top
   ~0.3-0.5 m, so a fault that juxtaposes or alters regolith (gouge, breccia, clay alteration,
   moisture) produces a linear break in total count and in the Th/K ratio.  This is an independent
   sensor, not a transform of the topography or of the magnetic field.
3. **Asymmetric concordance.**  An exploratory screen measured a *symmetric* rank product to be
   worse than either part, so the weaker sensor is used as a multiplicative corroboration of the
   stronger one, never as an equal partner:  ``score = lid * (1 - w + w * boost)``.
4. **Coverage-aware fallback.**  LiDAR covers 75.3 % of the scored footprint and gamma rays 100 %.
   Where there is no LiDAR the radiometric score is admitted at a capped quantile so that fallback
   candidates cannot outrank good morphology candidates.

Every input is rank-transformed before use because the mirrored products are uint8 quantised over
the 1st-99th percentile of each channel: ordering is meaningful, physical units are not.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

MORPH_BANDS = ("downface_max", "upface_max", "step_max", "lappos_max")
RAD_BANDS = ("ThK", "TC", "Th")

#: 4-connected axis directions used for non-maximum suppression, as (dy, dx).
AXES = ((0, 1), (1, 1), (1, 0), (1, -1))


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Monotone rank transform of ``a`` to [0, 1] over ``mask``; zero elsewhere.

    Rank rather than min-max so that quantised uint8 channels and heavy-tailed
    potential-field channels are treated identically and robustly.  A channel with
    no variation inside ``mask`` carries no ordering information and returns zeros
    rather than an arbitrary tie-broken ramp.
    """
    a = np.asarray(a, dtype=np.float32)
    mask = np.asarray(mask, dtype=bool)
    out = np.zeros(a.shape, np.float32)
    v = np.nan_to_num(a[mask], nan=0.0)
    if v.size == 0 or float(v.max()) == float(v.min()):
        return out
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, np.float32)
    r[order] = np.linspace(0.0, 1.0, v.size, dtype=np.float32)
    out[mask] = r
    return out


def gradmag(a: np.ndarray, sigma: float, valid: np.ndarray) -> np.ndarray:
    """Gradient magnitude of ``a`` after zero-filling outside ``valid`` and smoothing at ``sigma``."""
    f = np.where(valid, np.nan_to_num(np.asarray(a, dtype=np.float32)), 0.0).astype(np.float32)
    if sigma > 0:
        f = ndimage.gaussian_filter(f, sigma)
    gy, gx = np.gradient(f)
    return np.hypot(gy, gx).astype(np.float32)


def structure_orientation(f: np.ndarray, sigma: float = 1.0, rho: float = 2.0):
    """Structure-tensor orientation (radians, gradient direction) and coherence in [0, 1]."""
    g = ndimage.gaussian_filter(np.nan_to_num(f.astype(np.float32)), sigma) if sigma > 0 else f
    gy, gx = np.gradient(g)
    jxx = ndimage.gaussian_filter(gx * gx, rho)
    jyy = ndimage.gaussian_filter(gy * gy, rho)
    jxy = ndimage.gaussian_filter(gx * gy, rho)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr - 4.0 * det, 0.0))
    l1 = 0.5 * (tr + disc)
    l2 = 0.5 * (tr - disc)
    coh = np.where(l1 > 0, ((l1 - l2) / (l1 + l2 + 1e-12)) ** 2, 0.0)
    return theta.astype(np.float32), coh.astype(np.float32)


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """b[y, x] = a[y + dy, x + dx], zero outside."""
    out = np.zeros_like(a)
    h, w = a.shape
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    if ys0 < ys1 and xs0 < xs1:
        out[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    return out


def thin_axis(f: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """Non-maximum suppression perpendicular to strike: collapse a response band onto its axis.

    ``theta`` is the *gradient* direction, i.e. perpendicular to the lineament, so the comparison
    is made along ``theta``.  The direction is quantised to the 4 connected axes.
    """
    f = np.asarray(f, dtype=np.float32)
    # map theta (mod pi) to the nearest of the 4 axes: 0 -> (0,1), 1 -> (1,1), 2 -> (1,0), 3 -> (1,-1)
    t = np.mod(np.asarray(theta, dtype=np.float32), np.pi)
    idx = np.rint(t / (np.pi / 4.0)).astype(np.int8) % 4
    keep = np.zeros(f.shape, bool)
    for k, (dy, dx) in enumerate(AXES):
        sel = idx == k
        if not sel.any():
            continue
        a = _shift(f, dy, dx)
        b = _shift(f, -dy, -dx)
        keep |= sel & (f >= a) & (f >= b) & ((a > 0) | (b > 0))
    return keep


def prepare_inputs(morph: dict[str, np.ndarray], rad: dict[str, np.ndarray],
                   lidar_ok: np.ndarray, domain: np.ndarray, corr_sigma: float = 2.0,
                   rad_sigma: float = 2.0) -> dict:
    """Expensive, configuration-independent part of :func:`build_field`.

    Returns a dict with ``lid`` (morphology rank score), ``radm`` (radiometric rank score),
    ``corr`` (smoothed radiometric score) and ``boost`` (corroboration in [0, 1]).
    """
    dl = domain & lidar_ok
    morph_scores = [rank01(morph[b], dl) for b in MORPH_BANDS if b in morph]
    if not morph_scores:
        raise ValueError("no morphology bands supplied")
    lid = np.mean(morph_scores, axis=0).astype(np.float32)

    rad_scores = [rank01(gradmag(rad[b], rad_sigma, domain), domain) for b in RAD_BANDS if b in rad]
    if not rad_scores:
        raise ValueError("no radiometric bands supplied")
    radm = np.mean(rad_scores, axis=0).astype(np.float32)
    corr = ndimage.gaussian_filter(radm, corr_sigma).astype(np.float32)
    ref = corr[domain]
    lo, hi = float(np.median(ref)), float(np.percentile(ref, 99.0))
    boost = np.clip((corr - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)
    return dict(lid=lid, radm=radm, corr=corr, boost=boost, dl=dl, domain=domain,
                corr_sigma=corr_sigma, rad_sigma=rad_sigma)


def assemble(prep: dict, w: float = 0.5, fallback_quantile: float = 0.0,
             thin: bool = False) -> tuple[np.ndarray, dict]:
    """Cheap, configuration-dependent part of :func:`build_field` (see its docstring)."""
    if not 0.0 <= w <= 1.0:
        raise ValueError("w must be in [0, 1]")
    lid, boost, dl, domain = prep["lid"], prep["boost"], prep["dl"], prep["domain"]
    score = (lid * (1.0 - w + w * boost)).astype(np.float32)
    diag: dict = {"w": float(w), "corr_sigma": prep["corr_sigma"], "rad_sigma": prep["rad_sigma"],
                  "thin": bool(thin), "fallback_quantile": float(fallback_quantile),
                  "lidar_domain_px": int(dl.sum()),
                  "median_lidar_score": float(np.median(score[dl])) if dl.any() else 0.0}
    if thin:
        theta, _coh = structure_orientation(ndimage.gaussian_filter(score, 1.0))
        keep = thin_axis(score, theta)
        diag["thinned_px"] = int(keep.sum())
        score = np.where(keep, score, 0.0).astype(np.float32)

    if fallback_quantile and fallback_quantile > 0.0:
        cap = float(np.quantile(score[dl], fallback_quantile)) if dl.any() else 0.0
        radm = prep["radm"]
        rmax = float(np.max(radm[domain])) if domain.any() else 0.0
        scale = cap / rmax if rmax > 0 else 0.0
        fb = (radm * scale).astype(np.float32)
        score = np.where(dl, score, np.where(domain, fb, 0.0)).astype(np.float32)
        diag["fallback_scale"] = scale
        diag["fallback_cap"] = cap
    else:
        score = np.where(dl, score, 0.0).astype(np.float32)

    hi_all = float(np.max(score[domain])) if domain.any() else 0.0
    diag["prescore_max"] = hi_all
    if hi_all > 0:
        score = (score / hi_all).astype(np.float32)
    score[~domain] = 0.0
    diag["max"] = float(score.max())
    # post-normalisation record of the cap the fallback was held under, so a caller can
    # verify that radiometric-only candidates cannot outrank good morphology candidates
    gap = domain & ~dl
    diag["fallback_max"] = float(score[gap].max()) if gap.any() else 0.0
    diag["morph_p99"] = float(np.quantile(score[dl], 0.99)) if dl.any() else 0.0
    return score, diag


def build_field(morph: dict[str, np.ndarray], rad: dict[str, np.ndarray], lidar_ok: np.ndarray,
                domain: np.ndarray, w: float = 0.5, corr_sigma: float = 2.0,
                fallback_quantile: float = 0.0, rad_sigma: float = 2.0,
                thin: bool = False) -> tuple[np.ndarray, dict]:
    """Return the R11 evidence field in [0, 1] on ``domain`` and a diagnostics dict.

    Parameters
    ----------
    morph, rad : dict of raw channel arrays keyed by band name (uint8 quantised is fine).
    lidar_ok   : where the LiDAR product has data.
    domain     : emittable pixels (footprint minus the fixed catalogue exclusion).
    w          : concordance weight, 0 = morphology alone, 1 = fully gated by radiochemistry.
    corr_sigma : smoothing of the radiometric corroboration, in pixels (2 px = 200 m).
    fallback_quantile : cap for radiometric-only candidates, as a quantile of the morphology
                 score over LiDAR-covered domain pixels. 0 disables the fallback.
    thin       : apply ridge-axis non-maximum suppression before emission.
    """
    prep = prepare_inputs(morph, rad, lidar_ok, domain, corr_sigma, rad_sigma)
    return assemble(prep, w=w, fallback_quantile=fallback_quantile, thin=thin)
