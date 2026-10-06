"""GeoTIFF grid, input, and submission validation helpers."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio


class RasterValidationError(ValueError):
    """Raised when a raster violates a documented project/competition gate."""


@dataclass(frozen=True)
class GridSignature:
    width: int
    height: int
    count: int
    dtypes: tuple[str, ...]
    crs: str | None
    epsg: int | None
    transform: tuple[float, ...]
    bounds: tuple[float, float, float, float]
    nodata: float | int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe_nodata(value: float | None) -> float | int | str | None:
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def grid_signature(path: str | Path) -> GridSignature:
    with rasterio.open(path) as dataset:
        epsg = dataset.crs.to_epsg() if dataset.crs else None
        nodata = _json_safe_nodata(dataset.nodata)
        return GridSignature(
            width=dataset.width,
            height=dataset.height,
            count=dataset.count,
            dtypes=tuple(dataset.dtypes),
            crs=dataset.crs.to_string() if dataset.crs else None,
            epsg=epsg,
            transform=tuple(float(value) for value in dataset.transform[:6]),
            bounds=(
                float(dataset.bounds.left),
                float(dataset.bounds.bottom),
                float(dataset.bounds.right),
                float(dataset.bounds.top),
            ),
            nodata=nodata,
        )


def _same_grid(left: rasterio.io.DatasetReader, right: rasterio.io.DatasetReader) -> bool:
    return (
        left.width == right.width
        and left.height == right.height
        and left.crs == right.crs
        and np.allclose(
            np.asarray(left.transform[:6], dtype=np.float64),
            np.asarray(right.transform[:6], dtype=np.float64),
            rtol=0.0,
            atol=1e-8,
        )
        and np.allclose(
            np.asarray([left.bounds.left, left.bounds.bottom, left.bounds.right, left.bounds.top]),
            np.asarray(
                [right.bounds.left, right.bounds.bottom, right.bounds.right, right.bounds.top]
            ),
            rtol=0.0,
            atol=1e-6,
        )
    )


def require_competition_grid(dataset: rasterio.io.DatasetReader) -> None:
    if dataset.crs is None or dataset.crs.to_epsg() != 32611:
        raise RasterValidationError("CRS must be EPSG:32611")
    transform = dataset.transform
    if abs(transform.b) > 1e-9 or abs(transform.d) > 1e-9:
        raise RasterValidationError("competition grid must be north-up (no rotation/shear)")
    if not math.isclose(transform.a, 100.0, rel_tol=0.0, abs_tol=1e-6):
        raise RasterValidationError("x pixel size must be +100 m")
    if not math.isclose(transform.e, -100.0, rel_tol=0.0, abs_tol=1e-6):
        raise RasterValidationError("y pixel size must be -100 m (north-up)")


def preflight_inputs(
    features_path: str | Path,
    labels_path: str | Path,
    sample_path: str | Path,
) -> dict[str, Any]:
    """Check inputs share the official projected 100 m grid and label semantics."""
    features_path = Path(features_path)
    labels_path = Path(labels_path)
    sample_path = Path(sample_path)
    for path in (features_path, labels_path, sample_path):
        if not path.is_file():
            raise RasterValidationError(f"required input does not exist: {path}")

    with (
        rasterio.open(features_path) as features,
        rasterio.open(labels_path) as labels,
        rasterio.open(sample_path) as sample,
    ):
        require_competition_grid(sample)
        for name, dataset in (("features", features), ("labels", labels)):
            if not _same_grid(sample, dataset):
                raise RasterValidationError(f"{name} raster does not match sample grid")
        if labels.count != 1:
            raise RasterValidationError("labels raster must be single-band")
        if sample.count != 1:
            raise RasterValidationError("sample/submission reference must be single-band")
        if features.count < 1:
            raise RasterValidationError("features raster has no bands")

        valid_sample = sample.read_masks(1) > 0
        label_valid = labels.read_masks(1) > 0
        if not valid_sample.any():
            raise RasterValidationError("sample grid has no valid pixels")
        if np.any(label_valid & ~valid_sample):
            raise RasterValidationError("labels contain valid pixels outside the sample footprint")

        labels_array = labels.read(1)
        label_values = labels_array[label_valid]
        if label_values.size == 0:
            raise RasterValidationError("labels raster contains no valid pixels")
        if not np.isfinite(label_values).all():
            raise RasterValidationError("labels contain NaN/Inf in cells marked valid")
        if not np.isin(label_values, (0, 1)).all():
            raise RasterValidationError("labels must be binary 0/1 inside their valid mask")
        positives = int(np.count_nonzero(label_values == 1))
        if positives == 0:
            raise RasterValidationError("labels contain no positive fault pixels")

        report = {
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "status": "pass",
            "grid": grid_signature(sample_path).to_dict(),
            "features": {
                "path": str(features_path),
                "sha256": sha256_file(features_path),
                "count": features.count,
                "dtypes": list(features.dtypes),
                "nodata": _json_safe_nodata(features.nodata),
            },
            "labels": {
                "path": str(labels_path),
                "sha256": sha256_file(labels_path),
                "count": labels.count,
                "dtype": labels.dtypes[0],
                "nodata": _json_safe_nodata(labels.nodata),
                "valid_pixels": int(label_valid.sum()),
                "positive_pixels": positives,
            },
            "sample": {
                "path": str(sample_path),
                "sha256": sha256_file(sample_path),
                "valid_pixels": int(valid_sample.sum()),
                "nodata": _json_safe_nodata(sample.nodata),
            },
        }
    return report


def compare_rasters(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Assert all rasters share a grid and return their signatures."""
    paths = [Path(path) for path in paths]
    if len(paths) < 2:
        raise ValueError("at least two rasters are required for a grid comparison")
    with rasterio.open(paths[0]) as reference:
        require_competition_grid(reference)
        signatures = {str(paths[0]): grid_signature(paths[0]).to_dict()}
        for path in paths[1:]:
            with rasterio.open(path) as dataset:
                if not _same_grid(reference, dataset):
                    raise RasterValidationError(f"grid mismatch: {path} vs {paths[0]}")
                signatures[str(path)] = grid_signature(path).to_dict()
    return {"status": "pass", "rasters": signatures}


def validate_submission_tif(
    submission_path: str | Path,
    sample_path: str | Path,
) -> dict[str, Any]:
    """Validate single-band float32 output, exact grid, range, and NaN outside.

    The sample raster supplies the authoritative valid-footprint mask. All
    valid-footprint values must be finite and in [0, 1]. Outside the footprint,
    the stored values must be IEEE NaN, not a negative nodata sentinel.
    """
    submission_path = Path(submission_path)
    sample_path = Path(sample_path)
    if not submission_path.is_file() or not sample_path.is_file():
        raise RasterValidationError("submission and sample files must both exist")

    with rasterio.open(sample_path) as sample, rasterio.open(submission_path) as output:
        require_competition_grid(sample)
        if sample.count != 1:
            raise RasterValidationError("sample/reference raster must have exactly one band")
        if not _same_grid(sample, output):
            raise RasterValidationError("submission grid/bounds/transform do not match sample")
        if output.count != 1:
            raise RasterValidationError("submission must have exactly one band")
        if output.dtypes[0] != "float32":
            raise RasterValidationError("submission band dtype must be float32")

        valid = sample.read_masks(1) > 0
        values = output.read(1)
        inside = values[valid]
        outside = values[~valid]
        if inside.size == 0:
            raise RasterValidationError("sample valid footprint is empty")
        if not np.isfinite(inside).all():
            raise RasterValidationError("submission has NaN/Inf inside the valid footprint")
        if np.any((inside < 0.0) | (inside > 1.0)):
            minimum = float(np.min(inside))
            maximum = float(np.max(inside))
            raise RasterValidationError(
                f"valid-footprint values outside [0, 1] (min={minimum}, max={maximum})"
            )
        if outside.size and not np.isnan(outside).all():
            raise RasterValidationError("values outside the valid footprint must be NaN")
        if output.nodata is None or not (
            isinstance(output.nodata, float) and math.isnan(output.nodata)
        ):
            raise RasterValidationError("GeoTIFF nodata metadata must be IEEE NaN")

        return {
            "status": "pass",
            "submission": str(submission_path),
            "sha256": sha256_file(submission_path),
            "grid": grid_signature(submission_path).to_dict(),
            "valid_pixels": int(valid.sum()),
            "outside_pixels": int((~valid).sum()),
            "minimum_inside": float(np.min(inside)),
            "maximum_inside": float(np.max(inside)),
            "finite_inside": bool(np.isfinite(inside).all()),
            "all_outside_nan": bool(np.isnan(outside).all()) if outside.size else True,
            "dtype": output.dtypes[0],
            "count": output.count,
        }


def write_submission_tif(
    predictions_path: str | Path,
    sample_path: str | Path,
    output_path: str | Path,
    *,
    candidate_id: str,
    validation_report_sha256: str,
) -> dict[str, Any]:
    """Package an aligned score raster only after external validation gating.

    This low-level function performs format checks but does not decide whether
    a model passed holdout; the CLI enforces the holdout report gate.
    """
    predictions_path = Path(predictions_path)
    sample_path = Path(sample_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(sample_path) as sample, rasterio.open(predictions_path) as predictions:
        require_competition_grid(sample)
        if sample.count != 1:
            raise RasterValidationError("sample/reference raster must have exactly one band")
        if not _same_grid(sample, predictions):
            raise RasterValidationError("prediction raster does not match sample grid")
        if predictions.count != 1:
            raise RasterValidationError("candidate prediction raster must be single-band")

        valid = sample.read_masks(1) > 0
        candidate = predictions.read(1, masked=False).astype(np.float64, copy=False)
        inside = candidate[valid]
        if not np.isfinite(inside).all():
            raise RasterValidationError("candidate predictions contain NaN/Inf inside footprint")
        if np.any((inside < 0.0) | (inside > 1.0)):
            raise RasterValidationError("candidate predictions must be in [0, 1] inside footprint")

        output = np.full((sample.height, sample.width), np.nan, dtype=np.float32)
        output[valid] = inside.astype(np.float32)
        profile = sample.profile.copy()
        # GeoTIFF tile dimensions must be multiples of 16, including when the
        # raster itself is smaller than a tile. Preserve valid source blocks;
        # otherwise use a conventional 256 x 256 tile.
        blockxsize = int(profile.get("blockxsize", 256))
        blockysize = int(profile.get("blockysize", 256))
        if blockxsize < 16 or blockxsize % 16:
            blockxsize = 256
        if blockysize < 16 or blockysize % 16:
            blockysize = 256
        profile.update(
            driver="GTiff",
            count=1,
            dtype="float32",
            nodata=np.nan,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=blockxsize,
            blockysize=blockysize,
        )
        tags = {
            "candidate_id": candidate_id,
            "validation_report_sha256": validation_report_sha256,
            "generated_utc": datetime.now(UTC).isoformat(),
            "prediction_source_sha256": sha256_file(predictions_path),
            "format_note": "Single-band float32; NaN outside sample valid footprint",
        }
        with rasterio.open(output_path, "w", **profile) as destination:
            destination.write(output, 1)
            destination.update_tags(**tags)

    # Reopen the written bytes and validate the actual file, not only its source array.
    report = validate_submission_tif(output_path, sample_path)
    report["tags"] = tags
    return report
