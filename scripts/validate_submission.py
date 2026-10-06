#!/usr/bin/env python3
"""Independently validate a submission GeoTIFF against the official sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make ``src/`` importable when the script is run directly from a checkout, so the
# command line works without an editable install (``pip install -e .``).  Added during
# the merge with the submission layer so that the documented commands are copy-pasteable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gemsdoe46.raster import RasterValidationError, validate_submission_tif


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", required=True, help="candidate single-band GeoTIFF")
    parser.add_argument("--sample", required=True, help="official sample/reference GeoTIFF")
    parser.add_argument("--output", help="optional JSON validation receipt path")
    args = parser.parse_args()

    try:
        report = validate_submission_tif(args.submission, args.sample)
    except (RasterValidationError, OSError, ValueError) as exc:
        print(f"SUBMISSION VALIDATION FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, allow_nan=False)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
