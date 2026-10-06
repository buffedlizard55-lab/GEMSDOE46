"""R11F evidence families: fixed, named transforms of hash-pinned layers.

Three of the four families are new relative to the inspected GEMSDOE record:

* ``lidar_scarp_score``        the 12-channel 1 m-lidar terrain-descriptor stack
                               (``lidar_scarp_features_u8.tif``, 706/716 USGS 3DEP tiles),
                               combined as a *scarp* matched filter and multiplied by the
                               structure-tensor coherence, so that point-like features (pits,
                               mines, landslide toes) are suppressed and linear ones survive;
* ``radiometric_contrast``     the GeoDAWN contractor K/Th/U grids and their ratios
                               (DOI 10.5066/P93LGLVQ, ScienceBase 657e1d85d34e23d3533209f7).
                               The competition's own 19-band stack contains only the total-count
                               grid (band ``tc``), whose official description calls it a magnetic
                               curvature; this module treats the K/Th/U grids on their own terms;
* ``topographic_lineament``    the official detrended-elevation bands (a known family, kept as the
                               control that also covers the 25 % of the footprint without lidar);
* ``potential_field_lineament`` RTP magnetics and isostatic gravity horizontal gradients.

Every family returns a float32 array normalised by *rank* inside its valid mask, so the fused score
is a weighted sum of ranks and cannot be dominated by one layer's units.  ``to_probability`` turns
a fused score into the per-pixel expected-truth-mass field the emitter consumes.
"""

from __future__ import annotations

import numpy as np
import rasterio
from scipy import ndimage

NODATA_GUARD = -1e37


def read_layer(path, index: int = 1, guard: float = NODATA_GUARD) -> np.ndarray:
    """Read one band, mapping the float32-minimum sentinel (which *is* finite) to NaN."""
    with rasterio.open(path) as src:
        a = src.read(index).astype(np.float32)
        nd = src.nodatavals[index - 1] if src.nodatavals else None
    if nd is not None and np.isfinite(nd):
        a = np.where(a <= np.float32(nd) * np.float32(0.999999), np.nan, a)
    if guard is not None:
        a = np.where(a <= np.float32(guard), np.nan, a)
    return a


def quantised_to_unit(a: np.ndarray, qmax: float = 255.0) -> np.ndarray:
    """Undo the external mirrors' stored quantisation: 0 = nodata, 1..255 = clipped range."""
    out = np.where(a > 0, (a - 1.0) / (qmax - 1.0), np.nan)
    return out.astype(np.float32)


def rank_norm(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Uniform-rank transform of ``a`` inside ``mask`` -> [0, 1]; 0 outside."""
    out = np.zeros(a.shape, dtype=np.float32)
    sel = mask & np.isfinite(a)
    if not sel.any():
        return out
    v = a[sel]
    order = np.argsort(v, kind="stable")
    ranks = np.empty(v.size, dtype=np.float32)
    ranks[order] = np.arange(v.size, dtype=np.float32) / max(v.size - 1, 1)
    out[sel] = ranks
    return out


def gaussian(a: np.ndarray, sigma: float) -> np.ndarray:
    return ndimage.gaussian_filter(np.nan_to_num(a, nan=0.0), sigma, mode="nearest")


def grad_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    g = gaussian(a, sigma)
    gy, gx = np.gradient(g)
    return np.hypot(gy, gx).astype(np.float32)


def laplacian_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    return np.abs(ndimage.gaussian_laplace(np.nan_to_num(a, nan=0.0), sigma)).astype(np.float32)


def structure_coherence(a: np.ndarray, sigma: float = 3.0) -> np.ndarray:
    """(λ1 − λ2)/(λ1 + λ2) of the structure tensor of ``a`` — 1 for a perfect line, 0 for a blob."""
    g = gaussian(a, sigma)
    gy, gx = np.gradient(g)
    jxx = gaussian(gx * gx, sigma * 1.5)
    jyy = gaussian(gy * gy, sigma * 1.5)
    jxy = gaussian(gx * gy, sigma * 1.5)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    coh = np.where(tr > 0, (l1 - l2) / np.maximum(tr, 1e-12), 0.0)
    return np.clip(coh, 0.0, 1.0).astype(np.float32)


def fuse(parts: list[tuple[np.ndarray, float]], shape) -> np.ndarray:
    """Weighted sum of rank-normalised parts (weights are preregistered, not fitted)."""
    out = np.zeros(shape, dtype=np.float32)
    total = float(sum(w for _, w in parts)) or 1.0
    for a, w in parts:
        out += np.float32(w) * np.nan_to_num(a, nan=0.0).astype(np.float32)
    return (out / total).astype(np.float32)


def to_probability(score: np.ndarray, domain: np.ndarray, target_mass: float) -> np.ndarray:
    """Scale a score into an expected-truth-mass field: Σ q = ``target_mass`` over ``domain``.

    ``q(x)`` is then the probability that pixel ``x`` is one of the hidden truth pixels under the
    stated total mass, which is what the emitter's break-even rule needs.
    """
    s = np.where(domain, np.nan_to_num(score, nan=0.0), 0.0).astype(np.float64)
    total = s.sum()
    if total <= 0:
        return np.zeros(score.shape, dtype=np.float32)
    return (s / total * float(target_mass)).astype(np.float32)


# --------------------------------------------------------------------------------------------
# Families
# --------------------------------------------------------------------------------------------
LIDAR_SCARP_CHANNELS = ("step_max", "downface_max", "lappos_max", "lapneg_max", "ex_max",
                        "ex_mean", "cross_max", "upface_max")


def lidar_scarp_score(lidar_path, valid: np.ndarray, coherence_sigma: float = 3.0) -> np.ndarray:
    """Multi-channel scarp matched filter: step + crest convexity + base concavity + facing.

    ``relief`` and ``strike`` are deliberately excluded: relief is a *where-faults-are* covariate
    (a mountain prior) rather than a localiser, and a raw strike value is not evidence of anything.
    """
    with rasterio.open(lidar_path) as src:
        names = list(src.descriptions)
        data = {n: src.read(i + 1).astype(np.float32) for i, n in enumerate(names)}
    lidar_valid = (data["valid"] > 0) & valid
    parts = []
    for ch in LIDAR_SCARP_CHANNELS:
        unit = quantised_to_unit(data[ch])
        parts.append((rank_norm(unit, lidar_valid), 1.0))
    combined = fuse(parts, valid.shape)
    coh = structure_coherence(combined, coherence_sigma)
    return (combined * np.sqrt(coh)).astype(np.float32)


def topographic_lineament(valid: np.ndarray, det_elev: np.ndarray, det_elev_slope: np.ndarray,
                          coherence_sigma: float = 3.0) -> np.ndarray:
    mask = valid & np.isfinite(det_elev) & np.isfinite(det_elev_slope)
    parts = [
        (rank_norm(grad_mag(det_elev, 2.0), mask), 1.0),
        (rank_norm(grad_mag(det_elev, 6.0), mask), 0.7),
        (rank_norm(laplacian_mag(det_elev, 2.0), mask), 0.7),
        (rank_norm(grad_mag(det_elev_slope, 2.0), mask), 1.0),
        (rank_norm(laplacian_mag(det_elev_slope, 2.0), mask), 0.7),
    ]
    combined = fuse(parts, valid.shape)
    coh = structure_coherence(combined, coherence_sigma)
    return (combined * np.sqrt(coh)).astype(np.float32)


def radiometric_contrast(rad_path, extensions_path, valid: np.ndarray,
                         coherence_sigma: float = 3.0) -> np.ndarray:
    """Compositional-contrast lineaments: gradients of K, U and the Th/K and U/K ratios."""
    with rasterio.open(rad_path) as src:
        rad = {n: quantised_to_unit(src.read(i + 1).astype(np.float32))
               for i, n in enumerate(src.descriptions)}
    with rasterio.open(extensions_path) as src:
        ext = {n: quantised_to_unit(src.read(i + 1).astype(np.float32))
               for i, n in enumerate(src.descriptions)}
    k, th = rad["K"], rad["Th"]
    ratio_thk = np.where((th > 0) & (k > 0), th / np.maximum(k, 1e-6), np.nan)
    ratio_uk = ext.get("UK")
    mask = valid & np.isfinite(k) & np.isfinite(th)
    parts = [
        (rank_norm(grad_mag(k, 2.0), mask), 1.0),
        (rank_norm(grad_mag(ratio_thk, 2.0), mask), 1.0),
    ]
    if ratio_uk is not None:
        parts.append((rank_norm(grad_mag(ratio_uk, 2.0), mask), 0.5))
    combined = fuse(parts, valid.shape)
    coh = structure_coherence(combined, coherence_sigma)
    return (combined * np.sqrt(coh)).astype(np.float32)


def potential_field_lineament(valid: np.ndarray, rtp: np.ndarray, gravity: np.ndarray,
                              coherence_sigma: float = 3.0) -> np.ndarray:
    """Magnetic and gravity horizontal-gradient lineaments, rank-combined then coherence-filtered."""
    mask = valid & np.isfinite(rtp) & np.isfinite(gravity)
    parts = [
        (rank_norm(grad_mag(rtp, 2.0), mask), 1.0),
        (rank_norm(grad_mag(gravity, 2.0), mask), 1.0),
    ]
    combined = fuse(parts, valid.shape)
    coh = structure_coherence(combined, coherence_sigma)
    return (combined * np.sqrt(coh)).astype(np.float32)
