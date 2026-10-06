#!/usr/bin/env python3
"""Create a format-valid submission only after the holdout gate passes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make ``src/`` importable when the script is run directly from a checkout, so the
# command line works without an editable install (``pip install -e .``).  Added during
# the merge with the submission layer so that the documented commands are copy-pasteable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import rasterio

from gemsdoe46.raster import (
    RasterValidationError,
    _same_grid,
    sha256_file,
    validate_submission_tif,
    write_submission_tif,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REQUIRED_GATES = (
    "candidate_beats_baseline_global",
    "candidate_wins_at_least_three_folds",
    "prediction_mass_within_tolerance",
    "provenance_manifest_valid",
)
_REQUIRED_INPUTS = ("candidate", "baseline", "labels", "sample", "manifest")


def _prediction_fingerprint(path: Path, sample_path: Path) -> str:
    """Hash grid identity plus float32 values inside the sample footprint."""
    digest = hashlib.sha256()
    with rasterio.open(sample_path) as sample, rasterio.open(path) as dataset:
        if not _same_grid(sample, dataset):
            raise RasterValidationError(f"prior/candidate grid does not match sample: {path}")
        if dataset.count != 1:
            raise RasterValidationError(f"prior/candidate must be single-band: {path}")
        valid = sample.read_masks(1) > 0
        values = dataset.read(1).astype(np.float64, copy=False)
        inside = values[valid]
        if not np.isfinite(inside).all() or np.any((inside < 0.0) | (inside > 1.0)):
            raise RasterValidationError(
                f"prior/candidate values invalid inside sample footprint: {path}"
            )
        digest.update(
            f"{sample.width}x{sample.height}|EPSG:{sample.crs.to_epsg()}|".encode("ascii")
        )
        digest.update(np.asarray(sample.transform[:6], dtype="<f8").tobytes())
        digest.update(np.packbits(valid, bitorder="little").tobytes())
        digest.update(inside.astype("<f4", copy=False).tobytes())
    return digest.hexdigest()


def _check_validation_report(path: Path, candidate_id: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as stream:
        report = json.load(stream)
    if not isinstance(report, dict):
        raise TypeError("validation report must be a JSON object")
    if report.get("schema_version") != 1:
        raise ValueError("validation report schema_version must be 1")
    if report.get("status") != "pass":
        raise ValueError("holdout report status is not 'pass'; no TIF will be built")
    if report.get("candidate_id") != candidate_id:
        raise ValueError("candidate_id does not match the passing holdout report")
    for field in ("baseline_id", "validation_id"):
        if not isinstance(report.get(field), str) or not report[field].strip():
            raise ValueError(f"validation report is missing a valid {field}")

    gates = report.get("gates")
    if not isinstance(gates, dict) or any(gates.get(key) is not True for key in _REQUIRED_GATES):
        raise ValueError("not all required holdout promotion gates are explicitly true")

    inputs = report.get("inputs")
    if not isinstance(inputs, dict):
        raise TypeError("validation report is missing hashed input provenance")
    for name in _REQUIRED_INPUTS:
        row = inputs.get(name)
        if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
            raise TypeError(f"validation report is missing the {name} input hash")
        if _SHA256.fullmatch(row["sha256"]) is None:
            raise ValueError(f"validation report has an invalid {name} SHA-256")

    metric = report.get("metric")
    if not isinstance(metric, dict) or any(
        metric.get(key) != value
        for key, value in (("alpha", 0.2), ("beta", 0.8), ("radius_m", 300.0))
    ):
        raise ValueError("validation report metric does not match the registered DTI definition")

    try:
        delta_dti = float(report["delta_dti"])
        mass_delta = float(report["prediction_mass_delta_fraction"])
        mass_tolerance = float(report["mass_tolerance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "validation report is missing numeric improvement/mass diagnostics"
        ) from exc
    if not math.isfinite(delta_dti) or delta_dti <= 0.0:
        raise ValueError("holdout report does not show a finite positive DTI improvement")
    if (
        not math.isfinite(mass_delta)
        or not math.isfinite(mass_tolerance)
        or mass_delta < 0.0
        or mass_tolerance < 0.0
        or mass_delta > mass_tolerance
    ):
        raise ValueError("holdout report does not show comparable prediction mass")

    fold_wins = report.get("fold_wins")
    fold_count = report.get("fold_count")
    fold_rows = report.get("folds")
    if type(fold_wins) is not int or type(fold_count) is not int or fold_count != 4:
        raise ValueError("holdout report must contain integer 3-of-4 fold diagnostics")
    if not isinstance(fold_rows, list) or len(fold_rows) != 4:
        raise ValueError("holdout report must include all four fold results")
    observed_wins = sum(
        isinstance(row, dict) and row.get("candidate_wins") is True for row in fold_rows
    )
    if fold_wins != observed_wins or fold_wins < 3:
        raise ValueError("holdout report does not show the required 3-of-4 fold improvement")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions", required=True, help="aligned single-band probability GeoTIFF"
    )
    parser.add_argument("--sample", required=True, help="official sample/reference GeoTIFF")
    parser.add_argument(
        "--validation-report", required=True, help="passing spatial holdout JSON report"
    )
    parser.add_argument(
        "--candidate-id", required=True, help="unique lowercase model/hypothesis ID"
    )
    parser.add_argument(
        "--output-dir", default="submissions", help="output directory (default: %(default)s)"
    )
    parser.add_argument(
        "--prior-submission",
        action="append",
        default=[],
        help="path to each known prior submission TIF (repeat the flag as needed)",
    )
    parser.add_argument(
        "--no-prior-submissions",
        action="store_true",
        help="explicitly attest that no previous submission TIFs exist",
    )
    args = parser.parse_args()

    candidate_id = args.candidate_id
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", candidate_id):
        parser.error("--candidate-id must be 3–64 lowercase letters/digits/dot/underscore/hyphen")
    if args.no_prior_submissions and args.prior_submission:
        parser.error("do not combine --no-prior-submissions with --prior-submission")
    if not args.no_prior_submissions and not args.prior_submission:
        parser.error(
            "supply every known --prior-submission TIF, or explicitly attest --no-prior-submissions"
        )

    prediction_path = Path(args.predictions)
    sample_path = Path(args.sample)
    report_path = Path(args.validation_report)
    output_path: Path | None = None
    receipt_path: Path | None = None
    created_output = False
    try:
        holdout = _check_validation_report(report_path, candidate_id)
        fingerprint = _prediction_fingerprint(prediction_path, sample_path)
        prior_paths = [Path(path) for path in args.prior_submission]
        for prior_path in prior_paths:
            if not prior_path.is_file():
                raise FileNotFoundError(prior_path)
            if _prediction_fingerprint(prior_path, sample_path) == fingerprint:
                raise ValueError(f"candidate predictions duplicate known prior TIF: {prior_path}")

        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        filename = f"gemsdoe46-{candidate_id}-{timestamp}-{fingerprint[:10]}.tif"
        output_path = Path(args.output_dir) / filename
        receipt_path = output_path.with_suffix(".json")
        if output_path.exists() or receipt_path.exists():
            raise FileExistsError(output_path if output_path.exists() else receipt_path)
        created_output = True

        validation_sha = sha256_file(report_path)
        raster_report = write_submission_tif(
            prediction_path,
            sample_path,
            output_path,
            candidate_id=candidate_id,
            validation_report_sha256=validation_sha,
        )
        # A final byte-level and grid check is performed after writing.
        final_report = validate_submission_tif(output_path, sample_path)
        if final_report["sha256"] != raster_report["sha256"]:
            raise RasterValidationError("post-write checksum changed unexpectedly")

        receipt_path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "candidate_id": candidate_id,
                    "submission_file": output_path.name,
                    "submission_sha256": final_report["sha256"],
                    "prediction_fingerprint": fingerprint,
                    "holdout_report_sha256": validation_sha,
                    "holdout_delta_dti": holdout["delta_dti"],
                    "holdout_fold_wins": holdout["fold_wins"],
                    "prior_tifs_checked": [str(path) for path in prior_paths],
                    "no_prior_submissions_attested": bool(args.no_prior_submissions),
                    "format_validation": final_report,
                },
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except (
        FileNotFoundError,
        RasterValidationError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        if created_output:
            if output_path is not None:
                output_path.unlink(missing_ok=True)
            if receipt_path is not None:
                receipt_path.unlink(missing_ok=True)
        print(f"SUBMISSION BUILD BLOCKED: {exc}", file=sys.stderr)
        return 2

    print(f"PASS: {output_path}")
    print(f"SHA-256: {final_report['sha256']}")
    print("The file was compared with all supplied prior TIFs and passed format validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
