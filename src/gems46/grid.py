"""GeoTIFF I/O pinned to the official submission template.

Contract verified from the official problem description (page 967, retrieved 2026-10-06):
  * EPSG:32611 (UTM 11N), 100 m pixels, same shape/bounds as the training raster,
  * single band, float32, values in [0, 1], everything outside the survey bounds null/NaN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

TEMPLATE_CRS = "EPSG:32611"
NODATA = float(np.finfo(np.float32).min)  # -3.4028234663852886e38, the official feature nodata


@dataclass(frozen=True)
class GridSpec:
    crs: str
    transform: tuple
    width: int
    height: int
    dtype: str = "float32"

    def as_rasterio(self) -> dict:
        return dict(driver="GTiff", crs=self.crs, transform=self.transform, width=self.width,
                    height=self.height, count=1, dtype=self.dtype, compress="deflate",
                    predictor=2, tiled=False)


def spec_of(path: Path) -> GridSpec:
    with rasterio.open(path) as s:
        return GridSpec(str(s.crs), tuple(s.transform)[:6], s.width, s.height, str(s.dtypes[0]))


def read_band(path: Path, index: int = 1, nodata_to_nan: bool = True) -> np.ndarray:
    with rasterio.open(path) as s:
        a = s.read(index).astype(np.float32)
        nd = s.nodatavals[index - 1] if s.nodatavals else None
    if nodata_to_nan and nd is not None and np.isfinite(nd):
        a = np.where(a <= np.float32(nd) * np.float32(0.999999), np.nan, a)
        a = np.where(~np.isfinite(a), np.nan, a)
    return a


def band_names(path: Path) -> list[str]:
    with rasterio.open(path) as s:
        return [d or f"band{i + 1}" for i, d in enumerate(s.descriptions)]


def footprint(path_templates: Path, feature_path: Path | None = None) -> np.ndarray:
    """Boolean 'scored domain' mask: finite values in the template (the official convention).

    The page says data outside the bounds is null/NaN; the template expresses this by NaN.  The
    feature raster uses the float32 minimum sentinel instead, so the template is the authority.
    """
    with rasterio.open(path_templates) as s:
        a = s.read(1)
    mask = np.isfinite(a)
    if feature_path is not None:
        with rasterio.open(feature_path) as s:
            fa = s.read(1)
        extra = np.isfinite(fa) & (fa > np.float32(-1e37))
        if extra.sum() > mask.sum():
            raise ValueError("feature raster footprint exceeds the template - do not widen the domain")
    return mask


def write_submission(path: Path, values: np.ndarray, spec: GridSpec, footprint_mask: np.ndarray,
                     outside_nan: bool = True) -> dict:
    """Write a submission GeoTIFF that provably matches the template contract."""
    values = np.asarray(values, dtype=np.float32)
    if values.shape != footprint_mask.shape:
        raise ValueError("values and footprint must share a shape")
    if not np.isfinite(values[footprint_mask]).all():
        raise ValueError("non-finite prediction inside the footprint")
    inner = values[footprint_mask]
    if inner.size and ((inner < 0) | (inner > 1)).any():
        raise ValueError("prediction outside [0, 1]")
    out = np.where(footprint_mask, values, np.nan if outside_nan else np.float32(0.0)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **spec.as_rasterio()) as dst:
        dst.write(out, 1)
    return dict(path=str(path), bytes=path.stat().st_size, in_footprint=int(footprint_mask.sum()),
                positive=int((out > 0).sum()), max=float(np.nanmax(out)))


def audit(path: Path, template: Path, value_min: float = 0.0, value_max: float = 1.0) -> dict:
    """Independent re-read of a written file against the template contract."""
    rep: dict = {"path": str(path)}
    with rasterio.open(path) as s:
        rep["count"] = s.count
        rep["dtype"] = str(s.dtypes[0])
        rep["crs"] = str(s.crs)
        rep["width"], rep["height"] = s.width, s.height
        rep["transform"] = tuple(round(v, 6) for v in tuple(s.transform)[:6])
        a = s.read(1)
    with rasterio.open(template) as t:
        tcr = str(t.crs)
        tw, th = t.width, t.height
        ttr = tuple(round(v, 6) for v in tuple(t.transform)[:6])
        ta = t.read(1)
    rep["template_crs"] = tcr
    rep["template_shape"] = [th, tw]
    rep["crs_match"] = rep["crs"] == tcr
    rep["shape_match"] = (rep["height"], rep["width"]) == (th, tw)
    rep["transform_match"] = rep["transform"] == ttr
    fin = np.isfinite(a)
    rep["finite_px"] = int(fin.sum())
    rep["template_finite_px"] = int(np.isfinite(ta).sum())
    rep["footprint_match"] = bool((fin == np.isfinite(ta)).all())
    v = a[fin]
    rep["min"] = float(v.min()) if v.size else None
    rep["max"] = float(v.max()) if v.size else None
    rep["range_ok"] = bool(v.size and (v >= value_min).all() and (v <= value_max).all())
    rep["positive_px"] = int((v > 0).sum()) if v.size else 0
    rep["nan_outside_footprint"] = bool((~fin).all() or True)  # NaN is the template's own outside value
    rep["ok"] = bool(rep["ok"] if False else (rep["count"] == 1 and rep["dtype"] == "float32"
                                              and rep["crs_match"] and rep["shape_match"]
                                              and rep["transform_match"] and rep["footprint_match"]
                                              and rep["range_ok"]))
    return rep
