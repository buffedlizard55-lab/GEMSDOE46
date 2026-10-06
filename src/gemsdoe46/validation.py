"""Spatially blocked out-of-fold evaluation utilities."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from .metric import dti_components
from .raster import RasterValidationError, _same_grid, require_competition_grid, sha256_file


class ValidationProtocolError(ValueError):
    """Raised when validation inputs/provenance do not satisfy the protocol."""


def four_spatial_folds(valid_mask: np.ndarray) -> np.ndarray:
    """Assign valid cells to four contiguous quadrants (IDs 0–3; -1 outside)."""
    valid = np.asarray(valid_mask, dtype=bool)
    if valid.ndim != 2:
        raise ValueError("valid_mask must be two-dimensional")
    height, width = valid.shape
    row_split = height // 2
    col_split = width // 2
    if row_split == 0 or col_split == 0:
        raise ValueError("grid is too small for a 2-by-2 spatial split")

    fold = np.full(valid.shape, -1, dtype=np.int8)
    fold[:row_split, :col_split] = 0
    fold[:row_split, col_split:] = 1
    fold[row_split:, :col_split] = 2
    fold[row_split:, col_split:] = 3
    fold[~valid] = -1
    return fold


def _validate_oof_manifest(manifest: dict[str, Any]) -> list[str]:
    required_true = (
        "candidate_oof",
        "baseline_oof",
        "candidate_label_leakage_checked",
        "baseline_label_leakage_checked",
    )
    errors: list[str] = []
    for key in ("validation_id", "candidate_id", "baseline_id"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"manifest is missing a valid {key}")
    if manifest.get("folds") != 4:
        errors.append("manifest must declare folds=4")
    if manifest.get("fold_method") != "2x2 contiguous grid quadrants":
        errors.append("manifest fold_method must be '2x2 contiguous grid quadrants'")
    if manifest.get("buffer_meters") != 300:
        errors.append("manifest must declare a 300 m label embargo")
    for key in required_true:
        if manifest.get(key) is not True:
            errors.append(f"manifest must assert {key}=true")
    return errors


def _read_aligned_band(
    path: str | Path,
    reference: rasterio.io.DatasetReader,
    *,
    name: str,
    valid_mask: np.ndarray,
) -> np.ndarray:
    with rasterio.open(path) as dataset:
        if not _same_grid(reference, dataset):
            raise RasterValidationError(f"{name} raster does not match the official sample grid")
        if dataset.count != 1:
            raise RasterValidationError(f"{name} raster must contain one band")
        values = dataset.read(1).astype(np.float64, copy=False)
        if not np.isfinite(values[valid_mask]).all():
            raise RasterValidationError(f"{name} has non-finite values inside valid footprint")
        if np.any((values[valid_mask] < 0.0) | (values[valid_mask] > 1.0)):
            raise RasterValidationError(f"{name} values must be in [0, 1]")
        return values


def evaluate_oof_rasters(
    *,
    candidate_path: str | Path,
    baseline_path: str | Path,
    labels_path: str | Path,
    sample_path: str | Path,
    manifest_path: str | Path,
    mass_tolerance: float = 0.01,
) -> dict[str, Any]:
    """Score candidate/baseline OOF rasters on identical four-block folds.

    Fold score masks partition the scoring contributions, while each fold's
    local credit calculation sees the full valid truth/prediction context. This
    avoids an artificial 300 m truncation at quadrant boundaries. The caller
    must provide genuinely out-of-fold prediction rasters; the provenance
    assertions in the JSON manifest are required but cannot be independently
    proven from raster bytes alone.
    """
    if not np.isfinite(mass_tolerance) or mass_tolerance < 0.0:
        raise ValueError("mass_tolerance must be a finite, nonnegative fraction")

    candidate_path = Path(candidate_path)
    baseline_path = Path(baseline_path)
    labels_path = Path(labels_path)
    sample_path = Path(sample_path)
    manifest_path = Path(manifest_path)
    for path in (candidate_path, baseline_path, labels_path, sample_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict):
        raise ValidationProtocolError("validation manifest must be a JSON object")
    provenance_errors = _validate_oof_manifest(manifest)

    with rasterio.open(sample_path) as sample, rasterio.open(labels_path) as labels:
        require_competition_grid(sample)
        if not _same_grid(sample, labels):
            raise RasterValidationError("labels raster does not match official sample grid")
        if labels.count != 1:
            raise RasterValidationError("labels raster must be single-band")
        valid = sample.read_masks(1) > 0
        label_valid = labels.read_masks(1) > 0
        if np.any(valid & ~label_valid):
            raise RasterValidationError(
                "labels are missing from sample-valid cells; confirm official label semantics before scoring"
            )
        label_array = labels.read(1)
        if not np.isfinite(label_array[valid]).all():
            raise RasterValidationError("labels contain non-finite values inside sample footprint")
        if not np.isin(label_array[valid], (0, 1)).all():
            raise RasterValidationError("labels must be binary 0/1 inside sample footprint")
        truth = label_array == 1
        truth_count = int(np.count_nonzero(truth & valid))
        if truth_count == 0:
            raise RasterValidationError("no positive fault labels inside sample footprint")

        candidate = _read_aligned_band(
            candidate_path, sample, name="candidate OOF prediction", valid_mask=valid
        )
        baseline = _read_aligned_band(
            baseline_path, sample, name="baseline OOF prediction", valid_mask=valid
        )

        folds = four_spatial_folds(valid)
        fold_results: list[dict[str, Any]] = []
        for fold_id in range(4):
            score_mask = folds == fold_id
            positives = int(np.count_nonzero(truth & score_mask))
            if positives == 0:
                raise ValidationProtocolError(
                    f"spatial fold {fold_id} has no positive labels; do not silently score an empty fold"
                )
            candidate_parts = dti_components(
                candidate,
                label_array,
                valid_mask=valid,
                score_mask=score_mask,
            )
            baseline_parts = dti_components(
                baseline,
                label_array,
                valid_mask=valid,
                score_mask=score_mask,
            )
            fold_results.append(
                {
                    "fold_id": fold_id,
                    "valid_pixels": int(score_mask.sum()),
                    "truth_pixels": positives,
                    "candidate": candidate_parts.to_dict(),
                    "baseline": baseline_parts.to_dict(),
                    "delta_dti": candidate_parts.score - baseline_parts.score,
                    "candidate_wins": candidate_parts.score > baseline_parts.score,
                }
            )

        candidate_total = dti_components(candidate, label_array, valid_mask=valid)
        baseline_total = dti_components(baseline, label_array, valid_mask=valid)

    baseline_mass = baseline_total.prediction_mass
    mass_delta_fraction = (
        abs(candidate_total.prediction_mass - baseline_mass) / baseline_mass
        if baseline_mass > 0.0
        else (0.0 if candidate_total.prediction_mass == 0.0 else None)
    )
    fold_wins = sum(bool(row["candidate_wins"]) for row in fold_results)
    score_delta = candidate_total.score - baseline_total.score
    mass_matched = mass_delta_fraction is not None and mass_delta_fraction <= mass_tolerance

    gates = {
        "candidate_beats_baseline_global": score_delta > 1e-12,
        "candidate_wins_at_least_three_folds": fold_wins >= 3,
        "prediction_mass_within_tolerance": mass_matched,
        "provenance_manifest_valid": not provenance_errors,
    }
    status = "pass" if all(gates.values()) else "fail"
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "candidate_id": manifest.get("candidate_id"),
        "baseline_id": manifest.get("baseline_id"),
        "validation_id": manifest.get("validation_id"),
        "metric": {
            "name": "published distance-weighted Tversky (local implementation)",
            "alpha": 0.2,
            "beta": 0.8,
            "radius_m": 300.0,
            "cell_size_m": 100.0,
        },
        "inputs": {
            "candidate": {"path": str(candidate_path), "sha256": sha256_file(candidate_path)},
            "baseline": {"path": str(baseline_path), "sha256": sha256_file(baseline_path)},
            "labels": {"path": str(labels_path), "sha256": sha256_file(labels_path)},
            "sample": {"path": str(sample_path), "sha256": sha256_file(sample_path)},
            "manifest": {"path": str(manifest_path), "sha256": sha256_file(manifest_path)},
        },
        "candidate": candidate_total.to_dict(),
        "baseline": baseline_total.to_dict(),
        "delta_dti": score_delta,
        "fold_wins": fold_wins,
        "fold_count": 4,
        "prediction_mass_delta_fraction": mass_delta_fraction,
        "mass_tolerance": mass_tolerance,
        "gates": gates,
        "provenance_errors": provenance_errors,
        "provenance_note": (
            "OOF/leakage assertions come from the supplied manifest and upstream pipeline; "
            "this scorer cannot prove how prediction rasters were trained."
        ),
        "folds": fold_results,
    }
