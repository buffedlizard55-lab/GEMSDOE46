from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from gemsdoe46.raster import validate_submission_tif

ROOT = Path(__file__).resolve().parents[1]


def write_raster(path: Path, values: np.ndarray, *, nodata=None) -> None:
    values = np.asarray(values)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype=values.dtype,
        crs="EPSG:32611",
        transform=Affine(100, 0, 500000, 0, -100, 4500000),
        nodata=nodata,
    ) as dataset:
        dataset.write(values, 1)


def valid_report(path: Path, candidate_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pass",
                "candidate_id": candidate_id,
                "baseline_id": "current-holdout-best-v1",
                "validation_id": "synthetic-test-only",
                "delta_dti": 0.01,
                "prediction_mass_delta_fraction": 0.0,
                "mass_tolerance": 0.01,
                "fold_wins": 3,
                "fold_count": 4,
                "folds": [
                    {"fold_id": fold_id, "candidate_wins": fold_id != 0} for fold_id in range(4)
                ],
                "metric": {"alpha": 0.2, "beta": 0.8, "radius_m": 300.0},
                "inputs": {
                    name: {"sha256": "a" * 64}
                    for name in ("candidate", "baseline", "labels", "sample", "manifest")
                },
                "gates": {
                    "candidate_beats_baseline_global": True,
                    "candidate_wins_at_least_three_folds": True,
                    "prediction_mass_within_tolerance": True,
                    "provenance_manifest_valid": True,
                },
            }
        ),
        encoding="utf-8",
    )


def run_builder(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_submission.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_build_requires_pass_and_emits_valid_fingerprinted_tif(tmp_path) -> None:
    candidate_id = "test-candidate-v1"
    sample = tmp_path / "sample.tif"
    prediction = tmp_path / "prediction.tif"
    report = tmp_path / "holdout.json"
    output_dir = tmp_path / "submissions"
    write_raster(sample, np.zeros((8, 8), dtype=np.float32))
    write_raster(prediction, np.full((8, 8), 0.5, dtype=np.float32))
    valid_report(report, candidate_id)

    result = run_builder(
        [
            "--predictions",
            str(prediction),
            "--sample",
            str(sample),
            "--validation-report",
            str(report),
            "--candidate-id",
            candidate_id,
            "--output-dir",
            str(output_dir),
            "--no-prior-submissions",
        ]
    )

    assert result.returncode == 0, result.stderr
    tifs = list(output_dir.glob("*.tif"))
    assert len(tifs) == 1
    assert "test-candidate-v1" in tifs[0].name
    assert validate_submission_tif(tifs[0], sample)["status"] == "pass"
    assert tifs[0].with_suffix(".json").is_file()


def test_build_refuses_out_of_range_values_before_creating_output(tmp_path) -> None:
    candidate_id = "test-candidate-v1"
    sample = tmp_path / "sample.tif"
    prediction = tmp_path / "prediction.tif"
    report = tmp_path / "holdout.json"
    output_dir = tmp_path / "submissions"
    write_raster(sample, np.zeros((8, 8), dtype=np.float32))
    values = np.full((8, 8), 0.5, dtype=np.float32)
    values[3, 3] = 1.001
    write_raster(prediction, values)
    valid_report(report, candidate_id)

    result = run_builder(
        [
            "--predictions",
            str(prediction),
            "--sample",
            str(sample),
            "--validation-report",
            str(report),
            "--candidate-id",
            candidate_id,
            "--output-dir",
            str(output_dir),
            "--no-prior-submissions",
        ]
    )

    assert result.returncode == 2
    assert "values invalid inside sample footprint" in result.stderr
    assert not output_dir.exists() or not list(output_dir.glob("*.tif"))


def test_build_refuses_failed_report_and_duplicate_predictions(tmp_path) -> None:
    candidate_id = "test-candidate-v1"
    sample = tmp_path / "sample.tif"
    prediction = tmp_path / "prediction.tif"
    prior = tmp_path / "prior.tif"
    report = tmp_path / "holdout.json"
    output_dir = tmp_path / "submissions"
    write_raster(sample, np.zeros((8, 8), dtype=np.float32))
    values = np.full((8, 8), 0.5, dtype=np.float32)
    write_raster(prediction, values)
    write_raster(prior, values.copy())
    valid_report(report, candidate_id)

    duplicate = run_builder(
        [
            "--predictions",
            str(prediction),
            "--sample",
            str(sample),
            "--validation-report",
            str(report),
            "--candidate-id",
            candidate_id,
            "--output-dir",
            str(output_dir),
            "--prior-submission",
            str(prior),
        ]
    )
    assert duplicate.returncode == 2
    assert "duplicate known prior TIF" in duplicate.stderr
    assert not output_dir.exists() or not list(output_dir.glob("*.tif"))

    failed_report = json.loads(report.read_text(encoding="utf-8"))
    failed_report["status"] = "fail"
    report.write_text(json.dumps(failed_report), encoding="utf-8")
    blocked = run_builder(
        [
            "--predictions",
            str(prediction),
            "--sample",
            str(sample),
            "--validation-report",
            str(report),
            "--candidate-id",
            candidate_id,
            "--output-dir",
            str(output_dir),
            "--no-prior-submissions",
        ]
    )
    assert blocked.returncode == 2
    assert "status is not 'pass'" in blocked.stderr
