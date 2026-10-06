from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from affine import Affine

from gemsdoe46.validation import evaluate_oof_rasters, four_spatial_folds


def write_tif(path, array, *, nodata=None):
    array = np.asarray(array)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype,
        crs="EPSG:32611",
        transform=Affine(100, 0, 500000, 0, -100, 4500000),
        nodata=nodata,
    ) as dataset:
        dataset.write(array, 1)


def test_invalid_mass_tolerance_is_rejected_before_io(tmp_path) -> None:
    with pytest.raises(ValueError, match="mass_tolerance"):
        evaluate_oof_rasters(
            candidate_path=tmp_path / "candidate.tif",
            baseline_path=tmp_path / "baseline.tif",
            labels_path=tmp_path / "labels.tif",
            sample_path=tmp_path / "sample.tif",
            manifest_path=tmp_path / "manifest.json",
            mass_tolerance=-0.1,
        )


def test_four_spatial_folds_are_contiguous_and_cover_valid_cells() -> None:
    valid = np.ones((8, 10), dtype=bool)
    valid[0, 0] = False

    folds = four_spatial_folds(valid)

    assert set(np.unique(folds)) == {-1, 0, 1, 2, 3}
    assert np.all(folds[valid] >= 0)
    assert np.all(folds[~valid] == -1)
    assert sum(int(np.count_nonzero(folds == fold_id)) for fold_id in range(4)) == int(valid.sum())


def test_oof_gate_passes_only_for_spatially_consistent_improvement(tmp_path) -> None:
    size = 20
    sample = tmp_path / "sample.tif"
    labels = tmp_path / "labels.tif"
    candidate = tmp_path / "candidate-oof.tif"
    baseline = tmp_path / "baseline-oof.tif"
    manifest_path = tmp_path / "manifest.json"

    write_tif(sample, np.zeros((size, size), dtype=np.float32))
    truth = np.zeros((size, size), dtype=np.uint8)
    positive_cells = [(4, 4), (4, 14), (14, 4), (14, 14)]
    for row, col in positive_cells:
        truth[row, col] = 1
    write_tif(labels, truth)

    candidate_values = np.zeros((size, size), dtype=np.float32)
    baseline_values = np.zeros((size, size), dtype=np.float32)
    for row, col in positive_cells:
        candidate_values[row, col] = 0.8
    baseline_values[positive_cells[0]] = 1.0
    false_positive_cells = [(0, 19), (19, 0), (19, 19)]
    for row, col in false_positive_cells:
        baseline_values[row, col] = (3.2 - 1.0) / 3.0
    write_tif(candidate, candidate_values)
    write_tif(baseline, baseline_values)

    manifest = {
        "candidate_id": "h46-1-opera-disp-v1",
        "baseline_id": "current-holdout-best-v1",
        "validation_id": "synthetic-test-only",
        "folds": 4,
        "fold_method": "2x2 contiguous grid quadrants",
        "buffer_meters": 300,
        "candidate_oof": True,
        "baseline_oof": True,
        "candidate_label_leakage_checked": True,
        "baseline_label_leakage_checked": True,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = evaluate_oof_rasters(
        candidate_path=candidate,
        baseline_path=baseline,
        labels_path=labels,
        sample_path=sample,
        manifest_path=manifest_path,
    )

    assert report["status"] == "pass"
    assert report["candidate"]["score"] > report["baseline"]["score"]
    assert report["fold_wins"] == 3
    assert report["gates"]["prediction_mass_within_tolerance"] is True
    assert len(report["folds"]) == 4


def test_oof_manifest_claim_is_required_for_promotion(tmp_path) -> None:
    size = 20
    sample = tmp_path / "sample.tif"
    labels = tmp_path / "labels.tif"
    candidate = tmp_path / "candidate.tif"
    baseline = tmp_path / "baseline.tif"
    manifest_path = tmp_path / "manifest.json"

    write_tif(sample, np.zeros((size, size), dtype=np.float32))
    truth = np.zeros((size, size), dtype=np.uint8)
    for cell in [(4, 4), (4, 14), (14, 4), (14, 14)]:
        truth[cell] = 1
    write_tif(labels, truth)
    candidate_values = truth.astype(np.float32) * 0.8
    baseline_values = truth.astype(np.float32) * 0.7
    write_tif(candidate, candidate_values)
    write_tif(baseline, baseline_values)

    manifest = {
        "candidate_id": "candidate-v1",
        "baseline_id": "baseline-v1",
        "validation_id": "missing-leakage-assertion",
        "folds": 4,
        "fold_method": "2x2 contiguous grid quadrants",
        "buffer_meters": 300,
        "candidate_oof": False,
        "baseline_oof": True,
        "candidate_label_leakage_checked": True,
        "baseline_label_leakage_checked": True,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = evaluate_oof_rasters(
        candidate_path=candidate,
        baseline_path=baseline,
        labels_path=labels,
        sample_path=sample,
        manifest_path=manifest_path,
    )

    assert report["status"] == "fail"
    assert report["gates"]["provenance_manifest_valid"] is False
    assert any("candidate_oof" in error for error in report["provenance_errors"])
