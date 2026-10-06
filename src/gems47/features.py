"""Multi-scale oriented-lineament feature stack for the official GEMS training bands.

Design notes (all choices are checkable):

* Bands are read from ``data/raw/training_features.tif`` (hash-pinned in ``registry/data_manifest.json``).
  Band order/description was read from the file's own band descriptions (see ``BAND_NAMES``).
* The nodata sentinel is ``-3.4028234663852886e38`` (float32 minimum).  It is replaced by NaN before
  any filter runs, and every feature carries a validity mask produced by the same halo.
* Features are computed on a *halo tile* so that every output pixel sees the same filter support it
  would see on the whole raster.  Feature values are then robustly scaled with fixed statistics
  (median/IQR over the scored footprint) recomputed once and stored in the run receipt, never
  re-fitted per tile.
* No feature uses the published catalogue, so an emission built on this stack is label-free with
  respect to the scored truth.  The catalogue enters only through (a) the training labels of the
  supervised model and (b) the organizer's masking rule, both of which are stated where used.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from scipy import ndimage as ndi

NODATA = -3.4028234663852886e38

# 1-based band index -> official description (read from the GeoTIFF band descriptions)
BAND_NAMES = {
    1: "mag_anom - Magnetic anomaly",
    2: "rtp - Reduced to pole magnetic data",
    3: "tmi_hg - Total magnetic intensity horizontal gradient",
    4: "geod_2ndinv - Geodetic second invariant",
    5: "iso_grav_anom_slope - Isostatic gravity anomaly slope",
    6: "tc - Tilt angle or total curvature",
    7: "geod_shearrate - Geodetic shear rate",
    8: "geod_dilaterate - Geodetic dilatation rate",
    9: "tmi_vg - Total magnetic intensity vertical gradient",
    10: "deq_n100a15 - Distance to earthquake (100 km smoother)",
    11: "iso_grav_anom_vg - Isostatic gravity anomaly vertical gradient",
    12: "det_elev - Detrended elevation",
    13: "iso_grav_anom - Isostatic gravity anomaly",
    14: "tmi - Total magnetic intensity",
    15: "depth_to_base_surf - Depth to basement surface",
    16: "ieq_n100a15 - Earthquake density (100 km smoother)",
    17: "cond_surf - Conductivity surface",
    18: "iso_grav_anom_hg - Isostatic gravity anomaly horizontal gradient",
    19: "det_elev_slope - Detrended elevation slope",
}

# Bands entering the 6-feature block (multi-scale gradients, Laplacian, structure-tensor coherence,
# high-pass texture).  Chosen as the physics groups the fault literature uses for lineaments:
# magnetics (anomaly, RTP, TMI), gravity (isostatic anomaly), curvature (tilt angle), topography
# (detrended elevation), and the two subsurface/alteration surfaces (conductivity, basement depth).
BLOCK_BANDS = (1, 2, 14, 13, 6, 12, 17, 15)
# Bands entering the 2-feature block (raw value + gradient magnitude at 2 px).
EXTRA_BANDS = (3, 18)
# Context bands appended raw (100 km smoothers and the slope surface), 3 features.
CONTEXT_BANDS = (5, 10, 16)

SCALES = (1.0, 2.0, 4.0)
OUTER_SIGMA = 3.0


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    band: int


def feature_specs() -> list[FeatureSpec]:
    out = []
    for b in BLOCK_BANDS:
        n = band_key(b)
        out += [FeatureSpec(f"{n}_grad{s:g}", b) for s in SCALES]
        out.append(FeatureSpec(f"{n}_lap{SCALES[1]:g}", b))
        out.append(FeatureSpec(f"{n}_coh{SCALES[1]:g}", b))
        out.append(FeatureSpec(f"{n}_hp{SCALES[2]:g}", b))
    for b in EXTRA_BANDS:
        n = band_key(b)
        out.append(FeatureSpec(f"{n}_raw", b))
        out.append(FeatureSpec(f"{n}_grad{SCALES[1]:g}", b))
    for b in CONTEXT_BANDS:
        out.append(FeatureSpec(f"{band_key(b)}_ctx", b))
    return out


def feature_names() -> list[str]:
    return [s.name for s in feature_specs()]


def _derivatives(x: np.ndarray, sigma: float):
    gx = ndi.gaussian_filter(x, sigma, order=(0, 1), truncate=3.0, mode="nearest")
    gy = ndi.gaussian_filter(x, sigma, order=(1, 0), truncate=3.0, mode="nearest")
    return gx, gy


def _stack_for_band(x: np.ndarray, name: str, block: bool):
    """Features for one band.  ``x`` is a NaN-carrying float32 halo tile."""
    filled = np.where(np.isfinite(x), x, 0.0).astype(np.float32)
    valid = np.isfinite(x)
    feats = {}
    for s in SCALES:
        gx, gy = _derivatives(filled, s)
        feats[f"{name}_grad{s:g}"] = np.hypot(gx, gy).astype(np.float32)
    s2 = SCALES[1]
    lap = ndi.gaussian_filter(filled, s2, order=(0, 2), truncate=3.0, mode="nearest") + \
        ndi.gaussian_filter(filled, s2, order=(2, 0), truncate=3.0, mode="nearest")
    feats[f"{name}_lap{s2:g}"] = np.abs(lap).astype(np.float32)
    if block:
        gx, gy = _derivatives(filled, SCALES[0])
        jxx = ndi.gaussian_filter(gx * gx, OUTER_SIGMA, truncate=3.0, mode="nearest")
        jyy = ndi.gaussian_filter(gy * gy, OUTER_SIGMA, truncate=3.0, mode="nearest")
        jxy = ndi.gaussian_filter(gx * gy, OUTER_SIGMA, truncate=3.0, mode="nearest")
        tr = jxx + jyy
        det = jxx * jyy - jxy * jxy
        disc = np.sqrt(np.maximum(tr * tr * 0.25 - det, 0.0))
        lmax = tr * 0.5 + disc
        lmin = tr * 0.5 - disc
        feats[f"{name}_coh{s2:g}"] = ((lmax - lmin) / (lmax + lmin + 1e-12)).astype(np.float32)
        feats[f"{name}_hp{SCALES[2]:g}"] = (filled - ndi.gaussian_filter(
            filled, SCALES[2], truncate=3.0, mode="nearest")).astype(np.float32)
    for k in feats:
        feats[k] = np.where(valid, feats[k], np.nan)
    return feats


def halo_pixels() -> int:
    """Filter support needed on each side of a tile (3 sigma of the largest kernel + slack)."""
    return int(np.ceil(3.0 * max(max(SCALES), OUTER_SIGMA))) + 2


def compute_tile(src: rasterio.DatasetReader, r0: int, r1: int, names: list[str]) -> np.ndarray:
    """Feature cube (r1-r0, W, F) float32 for rows [r0, r1), NaN where inputs are invalid."""
    h = halo_pixels()
    H, W = src.height, src.width
    a0, a1 = max(0, r0 - h), min(H, r1 + h)
    bands: dict[str, np.ndarray] = {}
    needed = sorted({s.band for s in feature_specs()})
    raw = src.read(needed, window=rasterio.windows.Window(0, a0, W, a1 - a0))
    for i, b in enumerate(needed):
        arr = raw[i].astype(np.float32)
        arr = np.where(np.abs(arr) > 1e30, np.nan, arr)
        bands[b] = arr
    out = np.full((r1 - r0, W, len(names)), np.nan, dtype=np.float32)
    col = {n: i for i, n in enumerate(names)}
    for b in needed:
        is_block = b in BLOCK_BANDS
        feats = _stack_for_band(bands[b], f"{b:02d}", is_block)
        for key, val in feats.items():
            j = col.get(key)
            if j is None:
                continue
            out[:, :, j] = val[h:h + (r1 - r0), :]
    for b in CONTEXT_BANDS:
        key = f"{b:02d}_ctx"
        j = col.get(key)
        if j is not None:
            out[:, :, j] = bands[b][h:h + (r1 - r0), :]
    return out


BAND_SHORT = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 5: "iso_grav_anom_slope", 6: "tc", 10: "deq_n100a15",
    12: "det_elev", 13: "iso_grav_anom", 14: "tmi", 15: "depth_to_base_surf",
    16: "ieq_n100a15", 17: "cond_surf", 18: "iso_grav_anom_hg",
}


def band_key(index1: int) -> str:
    return f"{index1:02d}"


def pretty_feature_names() -> list[str]:
    """Feature names with the band key replaced by the official short band name."""
    out = []
    for s in feature_specs():
        prefix = s.name.split("_", 1)[0]
        try:
            short = BAND_SHORT[int(prefix)]
        except (KeyError, ValueError):
            short = prefix
        out.append(short + "_" + s.name.split("_", 1)[1] if "_" in s.name else s.name)
    return out
