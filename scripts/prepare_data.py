#!/usr/bin/env python
"""Place and verify the three official competition rasters in ``data/``.

The competition data tab requires a signed-in DrivenData session, so this script never
downloads anything by itself.  It does three things:

1. **Verifies** whatever is already in ``data/`` against the sha256 pins recorded when
   the files were first obtained from the competition data tab (the same pins are
   re-checked by ``scripts/run_pipeline.py`` on every run).
2. **Moves files into place** from a directory you point it at with ``--from-dir``
   (or the ``GEMS46_RAW_DIR`` environment variable), so a download made in a browser
   can be dropped in without renaming by hand.
3. **Checks the geometry** that the submission format depends on: EPSG:32611, 100 m,
   shape (3730, 3292), and that ``labels.tif`` has exactly one positive class.

Usage
-----
    python scripts/prepare_data.py                      # verify only
    python scripts/prepare_data.py --from-dir ~/Downloads
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Pins recorded when the files were downloaded from the competition data tab.
PINS = {
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
}
EXPECTED_SHAPE = (3730, 3292)
EXPECTED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", default=os.environ.get("GEMS46_RAW_DIR"),
                    help="directory holding freshly downloaded copies of the three files")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    if args.from_dir:
        src = Path(args.from_dir).expanduser()
        for name in PINS:
            candidate = src / name
            if candidate.exists():
                shutil.copy2(candidate, DATA / name)
                print(f"copied {candidate} -> {DATA / name}")

    missing, bad = [], []
    for name, want in PINS.items():
        p = DATA / name
        if not p.exists():
            missing.append(name)
            continue
        got = sha256(p)
        ok = got == want
        print(f"{name}: {'OK' if ok else 'MISMATCH'} {got[:16]}… {p.stat().st_size:,} B")
        if not ok:
            bad.append(name)

    if missing or bad:
        print("\nCannot continue.", file=sys.stderr)
        if missing:
            print("missing: " + ", ".join(missing), file=sys.stderr)
        if bad:
            print("hash mismatch: " + ", ".join(bad), file=sys.stderr)
        print("\nObtain the files from the competition data tab while signed in:\n"
              "  https://www.drivendata.org/competitions/306/competition-doe-gems/data/\n"
              f"then re-run:  python {Path(__file__).name} --from-dir <download dir>",
              file=sys.stderr)
        return 1

    import numpy as np
    import rasterio

    print("\ngeometry checks")
    for name in ("labels.tif", "sample_submission.tif", "training_features.tif"):
        with rasterio.open(DATA / name) as s:
            transform_ok = tuple(s.transform)[:6] == EXPECTED_TRANSFORM
            shape_ok = (s.height, s.width) == EXPECTED_SHAPE
            print(f"  {name}: {s.count} band(s), {s.dtypes[0]}, {s.crs}, "
                  f"shape {s.height}x{s.width} {'OK' if shape_ok else 'WRONG'}, "
                  f"transform {'OK' if transform_ok else 'WRONG'}")
            if not (shape_ok and transform_ok and str(s.crs).upper() == "EPSG:32611"):
                return 1

    with rasterio.open(DATA / "labels.tif") as s:
        labels = s.read(1)
    with rasterio.open(DATA / "sample_submission.tif") as s:
        footprint = np.isfinite(s.read(1))
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    n_out = int((labels == -1).sum())
    print(f"\nlabels convention: 1 = catalogue fault ({n_pos:,} cells), "
          f"0 = no catalogue fault ({n_neg:,}), -1 = outside the surveyed area ({n_out:,})")
    ok = (n_pos == 60_988
          and n_pos + n_neg == int(footprint.sum())
          and n_out == int((~footprint).sum())
          and not set(np.unique(labels).tolist()) - {-1, 0, 1})
    if not ok:
        print("labels.tif does not match the recorded catalogue mask / footprint convention",
              file=sys.stderr)
        return 1
    print(f"  cross-check: positives+negatives = {n_pos + n_neg:,} = finite sample_submission "
          f"cells; -1 cells = {n_out:,} = NaN cells  ->  OK")
    print("\nAll three official rasters are in place and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
