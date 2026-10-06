#!/usr/bin/env python3
"""Evaluate a preregistered 4-fold spatial out-of-fold comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gemsdoe46.raster import RasterValidationError
from gemsdoe46.validation import evaluate_oof_rasters


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate", required=True, help="candidate out-of-fold prediction GeoTIFF"
    )
    parser.add_argument(
        "--baseline", required=True, help="current-best out-of-fold prediction GeoTIFF"
    )
    parser.add_argument("--labels", required=True, help="official label GeoTIFF")
    parser.add_argument("--sample", required=True, help="official sample/reference GeoTIFF")
    parser.add_argument(
        "--manifest", required=True, help="provenance JSON asserting fold/embargo construction"
    )
    parser.add_argument(
        "--mass-tolerance",
        type=float,
        default=0.01,
        help="maximum relative candidate-vs-baseline prediction-mass difference (default: 1%%)",
    )
    parser.add_argument(
        "--output",
        default="data/processed/holdout-report.json",
        help="JSON report path (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        report = evaluate_oof_rasters(
            candidate_path=args.candidate,
            baseline_path=args.baseline,
            labels_path=args.labels,
            sample_path=args.sample,
            manifest_path=args.manifest,
            mass_tolerance=args.mass_tolerance,
        )
    except (FileNotFoundError, RasterValidationError, ValueError, json.JSONDecodeError) as exc:
        print(f"HOLDOUT EVALUATION FAILED: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    if report["status"] != "pass":
        print(
            "Candidate did not pass the preregistered promotion gate; do not use a submission slot.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
