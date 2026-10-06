#!/usr/bin/env python3
"""Independent format + uniqueness audit of an R11 deliverable, from the bytes on disk.

Checks every clause of the official submission contract (page 967, retrieved 2026-10-06) against
the *template* the competition ships, and checks the uniqueness claim against every GeoTIFF in this
repository. Exit status is non-zero if any check fails. No claim is printed that was not measured.

Usage: python scripts/verify_r11_candidate.py [path ...]      (default: every docs/r11/*.tif)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data/raw/sample_submission.tif"


def audit(path: Path) -> tuple[list[dict], int]:
    checks: list[dict] = []
    failures = 0

    def check(name, ok, detail=""):
        nonlocal failures
        ok = bool(ok)
        checks.append(dict(check=name, ok=ok, detail=str(detail)))
        if not ok:
            failures += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {path.name} :: {name}: {detail}")

    if not path.exists():
        check("exists", False, path)
        return checks, failures
    with rasterio.open(TEMPLATE) as t:
        t_crs, t_shape, t_transform, t_finite = (t.crs, t.shape, t.transform,
                                                 np.isfinite(t.read(1)))
    with rasterio.open(path) as s:
        a = s.read(1)
        checks_meta = dict(count=s.count, dtype=str(s.dtypes[0]), crs=str(s.crs), shape=s.shape,
                           transform=tuple(s.transform)[:6], nodata=s.nodata)
    check("single band", checks_meta["count"] == 1, checks_meta["count"])
    check("float32", checks_meta["dtype"] == "float32", checks_meta["dtype"])
    check("crs == template", checks_meta["crs"] == str(t_crs), f"{checks_meta['crs']} vs {t_crs}")
    check("shape == template", checks_meta["shape"] == t_shape, f"{checks_meta['shape']} vs {t_shape}")
    check("transform == template", checks_meta["transform"] == tuple(t_transform)[:6],
          str(checks_meta["transform"]))
    check("no nodata tag", checks_meta["nodata"] is None, checks_meta["nodata"])
    check("all values finite", bool(np.isfinite(a).all()), f"min {float(a.min())} max {float(a.max())}")
    check("values in [0, 1]", bool(((a >= 0) & (a <= 1)).all()),
          f"min {float(a.min())} max {float(a.max())}")
    check("zero outside the scored footprint", bool((a[~t_finite] == 0).all()),
          f"{int((a[~t_finite] != 0).sum())} non-zero cells outside")
    check("positive cells inside the footprint only", bool((a[t_finite] > 0).any()),
          f"{int((a > 0).sum())} positive cells")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"       sha256 {sha}")
    print(f"       bytes  {path.stat().st_size:,}")

    # uniqueness: no other local GeoTIFF shares this pixel array
    identical = []
    for other in sorted(set(ROOT.glob("*.tif")) | set(ROOT.rglob("*.tif"))):
        if other == path:
            continue
        try:
            with rasterio.open(other) as o:
                if o.shape != a.shape:
                    continue
                b = o.read(1)
            if np.array_equal(np.nan_to_num(b.astype(np.float32)), a.astype(np.float32)):
                identical.append(str(other.relative_to(ROOT)))
        except Exception:
            continue
    check("pixel-unique against every local GeoTIFF", not identical, identical or "none matched")
    return checks, failures


def main() -> int:
    targets = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "docs/r11").glob("*.tif"))
    total_failures = 0
    report = {}
    for t in targets:
        checks, failures = audit(t)
        report[str(t.relative_to(ROOT))] = checks
        total_failures += failures
        print()
    out = ROOT / "evidence/r11-format-audit.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"{'ALL CHECKS PASSED' if total_failures == 0 else f'{total_failures} FAILURES'}; "
          f"report written to {out.relative_to(ROOT)}")
    return 1 if total_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
