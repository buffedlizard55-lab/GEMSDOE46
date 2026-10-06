"""Geological feature stack for the GEMS46 credit model (memory-frugal).

Inputs: the official 19-band `training_features.tif` (EPSG:32611, 100 m) and the official
catalogue raster `labels.tif`.  Everything else is a named transform of those two files.

Two products:
  * `build_blocks()`  - block-averaged feature table for fitting the credit model
                        (default 10 px = 1 km blocks; ~123k rows x K features, ~20 MB)
  * `build_pixel_memmap()` - rank-normalised uint8 pixel stack on disk for the emission stage

Hypothesis groups (see docs/hypotheses.html):
  A off-catalogue along-strike context   dist_cat, catdens_15/40, offcat_weight, beyond_core
  B magnetic & gravity edge boundaries   edge_tc, edge_rtp, edge_grav, tmi_hg, grav_hg,
                                         mag_source_edge, euler
  C geomorphic scarp/lineament signature ridge_s3/s7/s15, curv_s7, coherence_s7, slope
  D strain-rate localisation             strain_grad, shear_grad, dila
  E crustal/thermal/structural bounds    dzb_grad, cond_grad, ieq, deq
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

BANDS = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "grav_slope",
    6: "tc", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg", 10: "deq",
    11: "grav_vg", 12: "det_elev", 13: "grav_anom", 14: "tmi", 15: "depth_to_base",
    16: "ieq", 17: "cond_surf", 18: "grav_hg", 19: "det_elev_slope",
}
NODATA = np.float32(-3.4028234663852886e38)
DERIVED_ONLY = [
    "dist_cat", "catdens_15", "catdens_40", "offcat_weight", "beyond_core",
    "edge_tc", "edge_rtp", "edge_grav", "tmi_hg", "grav_hg", "mag_source_edge", "euler",
    "ridge_s3", "ridge_s7", "ridge_s15", "curv_s7", "coherence_s7", "slope",
    "strain_grad", "shear_grad", "dila",
    "dzb_grad", "cond_grad", "ieq", "deq",
]
BAND_FEATURES = [f"band_{BANDS[i]}" for i in sorted(BANDS)]

FEATURE_NAMES = DERIVED_ONLY + BAND_FEATURES


def _g(a, s):
    return ndi.gaussian_filter(a, s, mode="nearest")


def _grad(a, s=1.0):
    sm = _g(a, s) if s else a
    gy, gx = np.gradient(sm)
    return np.hypot(gy, gx)


def _ridge(a, s):
    """Largest absolute Hessian eigenvalue of the smoothed field (lineament detector)."""
    sm = _g(a, s)
    dyy = ndi.gaussian_filter(sm, s, order=(0, 2), mode="nearest")
    dxx = ndi.gaussian_filter(sm, s, order=(2, 0), mode="nearest")
    dxy = ndi.gaussian_filter(sm, s, order=(1, 1), mode="nearest")
    tr = dyy + dxx
    det = dyy * dxx - dxy * dxy
    return np.abs(tr / 2.0) + np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))


def _coherence(a, s):
    sm = _g(a, s)
    gy, gx = np.gradient(sm)
    jxx = _g(gx * gx, 2 * s)
    jyy = _g(gy * gy, 2 * s)
    jxy = _g(gx * gy, 2 * s)
    tr = jxx + jyy
    return np.sqrt(np.maximum((jxx - jyy) ** 2 + 4 * jxy * jxy, 0.0)) / (tr + 1e-12)


def load_grid(features_tif: Path, labels_tif: Path):
    """Return (labels_int8, footprint_bool, catalogue_bool, raw_bands float32 (19,H,W))."""
    import rasterio
    with rasterio.open(labels_tif) as ds:
        lab = ds.read(1)
    with rasterio.open(features_tif) as ds:
        raw = ds.read().astype(np.float32)
    raw[raw == NODATA] = np.nan
    footprint = lab >= 0
    raw[:, ~footprint] = np.nan
    for i in range(raw.shape[0]):
        b = raw[i]
        bad = ~np.isfinite(b)
        if bad.any():
            b[bad] = np.nanmedian(b)
    return lab, footprint, lab > 0, raw


def iter_features(raw: np.ndarray, footprint: np.ndarray, catalogue: np.ndarray):
    """Yield (name, float32 full-grid array) one feature at a time, low peak memory."""
    H, W = footprint.shape
    dist_cat = ndi.distance_transform_edt(~catalogue).astype(np.float32)
    yield "dist_cat", np.minimum(dist_cat, 100.0)
    for rad in (15, 40):
        yield f"catdens_{rad}", ndi.uniform_filter(
            catalogue.astype(np.float32), size=2 * rad + 1) * (2 * rad + 1) ** 2
    cat21 = ndi.uniform_filter(catalogue.astype(np.float32), size=21)
    yield "offcat_weight", (np.minimum(dist_cat, 60.0) / 60.0) * (1.0 - cat21)
    core = ndi.uniform_filter(catalogue.astype(np.float32), size=61) > 0.02
    del cat21
    yield "beyond_core", ndi.distance_transform_edt(~core).astype(np.float32)

    yield "edge_tc", _grad(raw[5], 1.0)
    yield "edge_rtp", _grad(raw[1], 1.0)
    yield "edge_grav", _grad(_g(raw[12], 4.0), 1.0)
    yield "tmi_hg", np.abs(raw[2])
    yield "grav_hg", np.abs(raw[17])
    yield "mag_source_edge", np.abs(-ndi.gaussian_laplace(raw[13], 5.0, mode="nearest"))
    yield "euler", _grad(raw[13], 5.0) * np.maximum(7.0 - raw[14], 0.0)

    det = raw[11]
    for s in (3.0, 7.0, 15.0):
        yield f"ridge_s{int(s)}", _ridge(det, s)
    yield "curv_s7", np.abs(-ndi.gaussian_laplace(det, 7.0, mode="nearest"))
    yield "coherence_s7", _coherence(det, 7.0)
    yield "slope", np.abs(raw[18])

    yield "strain_grad", _grad(raw[3], 5.0)
    yield "shear_grad", _grad(raw[6], 5.0)
    yield "dila", np.abs(raw[7])

    yield "dzb_grad", _grad(raw[14], 5.0)
    yield "cond_grad", _grad(raw[16], 5.0)
    yield "ieq", raw[15].copy()
    yield "deq", raw[9].copy()
    for i in sorted(BANDS):
        yield f"band_{BANDS[i]}", raw[i - 1].copy()


def build_blocks(features_tif: Path, labels_tif: Path, block: int = 10,
                 include_bands: bool = True):
    """Block-mean feature table + block geometry.  Returns dict of arrays."""
    lab, footprint, catalogue, raw = load_grid(features_tif, labels_tif)
    H, W = footprint.shape
    ny, nx = H // block, W // block
    Hc, Wc = ny * block, nx * block
    names, cols = [], []
    for name, arr in iter_features(raw, footprint, catalogue):
        if not include_bands and name.startswith("band_"):
            continue
        # block mean over the cropped grid, counting only footprint cells
        a = arr[:Hc, :Wc].reshape(ny, block, nx, block)
        f = footprint[:Hc, :Wc].reshape(ny, block, nx, block)
        cnt = f.sum(axis=(1, 3))
        s = np.where(f, a, 0.0).sum(axis=(1, 3))
        cols.append(np.where(cnt > 0, s / np.maximum(cnt, 1), 0.0).astype(np.float32))
        names.append(name)
    Z = np.stack(cols, axis=-1)                      # (ny, nx, K)
    cnt = footprint[:Hc, :Wc].reshape(ny, block, nx, block).sum(axis=(1, 3))
    cat = catalogue[:Hc, :Wc].reshape(ny, block, nx, block).sum(axis=(1, 3))
    meta = dict(block=block, ny=ny, nx=nx, H=H, W=W, Hc=Hc, Wc=Wc,
                names=names, counts=cnt.astype(np.int32),
                catalogue_counts=cat.astype(np.int32))
    return Z, meta


def build_pixel_memmap(features_tif: Path, labels_tif: Path, out_prefix: Path,
                       include_bands: bool = True) -> dict:
    """Write rank-normalised uint8 features to <out_prefix>.npy (K, H, W) on disk."""
    lab, footprint, catalogue, raw = load_grid(features_tif, labels_tif)
    H, W = footprint.shape
    names = [n for n in FEATURE_NAMES if include_bands or not n.startswith("band_")]
    K = len(names)
    mm = np.lib.format.open_memmap(f"{out_prefix}.npy", mode="w+", dtype=np.uint8, shape=(K, H, W))
    idx = 0
    for name, arr in iter_features(raw, footprint, catalogue):
        if name not in names:
            continue
        v = arr[footprint]
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, dtype=np.float32)
        ranks[order] = np.linspace(0, 255, v.size, dtype=np.float32)
        layer = np.zeros((H, W), np.float32)
        layer[footprint] = ranks
        mm[idx] = np.rint(layer).astype(np.uint8)
        idx += 1
        del v, order, ranks, layer
    mm.flush()
    np.save(f"{out_prefix}_names.npy", np.array(names))
    return dict(K=K, names=names, path=f"{out_prefix}.npy", footprint=footprint,
                shape=(H, W), H=H, W=W)
