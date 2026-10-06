#!/usr/bin/env python3
"""Preflight official feature, label, and sample rasters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gemsdoe46.raster import RasterValidationError, preflight_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True, help="official multiband feature GeoTIFF")
    parser.add_argument("--labels", required=True, help="official binary fault-label GeoTIFF")
    parser.add_argument("--sample", required=True, help="official sample/reference GeoTIFF")
    parser.add_argument(
        "--output",
        default="data/processed/input-preflight.json",
        help="JSON path for the preflight receipt (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        report = preflight_inputs(args.features, args.labels, args.sample)
    except (RasterValidationError, OSError, ValueError) as exc:
        print(f"PREFLIGHT FAILED: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
