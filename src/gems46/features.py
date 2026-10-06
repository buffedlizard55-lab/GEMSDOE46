"""Multi-scale structural / curvature feature stack from the official GeoDAWN bands.

All 19 input bands come from the organizer's ``training_features.tif``
(sha256 4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5,
19 bands, EPSG:32611, 100 m, 3730 x 3292 -- see ``docs/SOURCES.md``).

Physical signatures computed here
---------------------------------
1. **L2 ridge / scarp curvature**  (Lindeberg 1998, "Edge detection and ridge
   detection with scale-space properties", IJCV 30(2):117-154).  For a smoothed
   field ``G`` with Hessian ``H`` and gradient ``g``, the second directional
   derivative along the gradient direction ``n`` is

        L_nn = (Gxx*gx^2 + 2*Gxy*gx*gy + Gyy*gy^2) / (gx^2 + gy^2)

   and the ridge response is ``-L_nn``: it is large and positive on *crests*
   (fault scarps, fault-line ridges, magnetic lineament crests) and negative in
   valleys.  This is a curvature transform, not an edge detector.
2. **Gradient-magnitude edge response** at matched scales (classic lineament
   edge detection on magnetic and gravity grids).
3. **Scale-space laplacian** ``grad^2 G`` (blob/edge energy).
4. **Cover / concealment proxies**: depth-to-basement surface (band 15) and
   conductivity surface (band 17), smoothed -- the family's H-34-01 concealment
   direction, data already inside the official stack.

Deliberate exclusion
--------------------
**Distance-to-catalogue is NOT a model feature.**  The family's own
post-mortem (GEMSDOE32, IR-32-PROXY-01) shows that any field built on a
proximity-to-catalogue prior scores well on a catalogue-truth proxy and then
transfers badly, because the scored truth is the *new-fault* population.  Using
it here would make the blocked holdout optimistic for a reason we already know
is spurious.  The ablation flag ``include_distance_to_catalogue`` exists only so
that the drift can be *measured* rather than assumed.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

SENTINEL = -3.0e38

# band index (1-based, as in the official GeoTIFF) -> short name
BANDS = {
    1: "mag_anom",
    2: "rtp",
    3: "tmi_hgrad",
    4: "geod_2ndinv",
    5: "iso_grav_slope",
    6: "tilt_curv",
    7: "geod_shear",
    8: "geod_dilat",
    9: "tmi_vgrad",
    10: "eq_dist",
    11: "iso_grav_vgrad",
    12: "detrend_elev",
    13: "iso_grav",
    14: "tmi",
    15: "depth_basement",
    16: "eq_density",
    17: "conductivity",
    18: "iso_grav_hgrad",
    19: "detrend_elev_slope",
}


def _read_band(src, idx: int) -> np.ndarray:
    a = src.read(idx).astype(np.float32)
    bad = ~np.isfinite(a) | (a < SENTINEL)
    if bad.any():
        med = np.nanmedian(np.where(bad, np.nan, a))
        if not np.isfinite(med):
            med = 0.0
        a[bad] = med
        a = ndimage.gaussian_filter(a, 0.0)  # no-op; keeps dtype/contiguity
    return a


def _gradients(g: np.ndarray):
    gy, gx = np.gradient(g)
    return gx.astype(np.float32), gy.astype(np.float32)


def ridge_and_edges(g: np.ndarray, sigma: float):
    """Return (ridge, gradmag, lap) for a field smoothed at ``sigma`` pixels."""
    gs = ndimage.gaussian_filter(g, sigma) if sigma > 0 else g
    gx, gy = _gradients(gs)
    gxx = ndimage.gaussian_filter(gs, sigma, order=(0, 2))
    gyy = ndimage.gaussian_filter(gs, sigma, order=(2, 0))
    gxy = ndimage.gaussian_filter(gs, sigma, order=(1, 1))
    g2 = gx * gx + gy * gy
    denom = g2 + 1e-12
    l_nn = (gxx * gx * gx + 2.0 * gxy * gx * gy + gyy * gy * gy) / denom
    ridge = -l_nn
    gradmag = np.sqrt(g2)
    lap = ndimage.gaussian_filter(gs, sigma, order=(0, 2)) + ndimage.gaussian_filter(
        gs, sigma, order=(2, 0)
    )
    return ridge.astype(np.float32), gradmag.astype(np.float32), lap.astype(np.float32)


FEATURE_PLAN = [
    # (kind, band_index, sigma)  -- kind in {raw, smooth, ridge, gradmag, lap}
    ("raw", 12, 0.0),
    ("ridge", 12, 1.0),
    ("ridge", 12, 2.0),
    ("ridge", 12, 4.0),
    ("gradmag", 12, 2.0),
    ("gradmag", 19, 1.0),
    ("smooth", 19, 1.0),
    ("ridge", 6, 1.0),          # official tilt-angle / total-curvature edge band
    ("ridge", 6, 2.0),
    ("smooth", 6, 1.0),
    ("ridge", 14, 1.5),         # TMI
    ("ridge", 2, 1.5),          # RTP
    ("gradmag", 3, 1.0),        # TMI horizontal gradient band
    ("smooth", 9, 1.0),         # TMI vertical gradient band
    ("ridge", 13, 2.0),         # isostatic gravity
    ("gradmag", 18, 1.0),       # iso gravity horizontal gradient band
    ("smooth", 11, 1.0),        # iso gravity vertical gradient band
    ("smooth", 15, 2.0),        # depth to basement (concealment proxy)
    ("gradmag", 15, 2.0),
    ("smooth", 17, 2.0),        # conductivity surface
    ("smooth", 4, 2.0),         # geodetic second invariant
    ("smooth", 7, 2.0),         # shear rate
    ("smooth", 8, 2.0),         # dilatation rate
    ("smooth", 16, 2.0),        # earthquake density
    ("smooth", 1, 2.0),         # magnetic anomaly
]


def build_feature_stack(features_path: str, footprint: np.ndarray,
                        include_distance_to_catalogue: np.ndarray | None = None,
                        progress=print):
    """Build the (n_footprint_pixels, n_features) float32 matrix.

    Returns ``(X, names)``.  ``footprint`` is the boolean scored-domain mask
    (5,167,373 True cells, identical to ``np.isfinite(sample_submission.tif)``);
    only those pixels are stacked, so peak RAM stays bounded on a 4 GB box.
    """
    import rasterio

    n_pix = int(footprint.sum())
    plan = list(FEATURE_PLAN)
    names = [f"{k}:{BANDS[b]}:s{s:g}" for (k, b, s) in plan]
    if include_distance_to_catalogue is not None:
        plan.append(("raw", -1, 0.0))
        names.append("dist_to_catalogue")

    X = np.empty((n_pix, len(plan)), dtype=np.float32)
    with rasterio.open(features_path) as src:
        needed = sorted({b for (_k, b, _s) in plan if b > 0})
        cache: dict[int, np.ndarray] = {}
        col = 0
        for kind, band, sigma in plan:
            if band == -1:
                X[:, col] = include_distance_to_catalogue[footprint]
                col += 1
                continue
            if band not in cache:
                # keep at most 4 bands resident
                if len(cache) >= 4:
                    cache.pop(next(iter(cache)))
                cache[band] = _read_band(src, band)
            g = cache[band]
            if kind == "raw":
                out = g
            elif kind == "smooth":
                out = ndimage.gaussian_filter(g, sigma) if sigma > 0 else g
            elif kind == "gradmag":
                gs = ndimage.gaussian_filter(g, sigma) if sigma > 0 else g
                gx, gy = _gradients(gs)
                out = np.sqrt(gx * gx + gy * gy)
            elif kind == "ridge":
                r, _gm, _lp = ridge_and_edges(g, sigma)
                out = r
            elif kind == "lap":
                _r, _gm, lp = ridge_and_edges(g, sigma)
                out = lp
            else:
                raise ValueError(kind)
            X[:, col] = np.asarray(out, dtype=np.float32)[footprint]
            col += 1
            progress(f"  feature {col}/{len(plan)} {names[col-1]}")
    return X, names


def standardise(X: np.ndarray, mask: np.ndarray | None = None):
    """Robust standardisation (median / IQR) computed on ``mask`` rows."""
    ref = X if mask is None else X[mask]
    med = np.median(ref, axis=0)
    q1 = np.percentile(ref, 25, axis=0)
    q3 = np.percentile(ref, 75, axis=0)
    scale = np.where((q3 - q1) > 1e-9, (q3 - q1) / 1.349, 1.0)
    return med.astype(np.float32), scale.astype(np.float32)
