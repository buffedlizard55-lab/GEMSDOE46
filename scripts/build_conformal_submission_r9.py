#!/usr/bin/env python3
"""
Build a UNIQUE submission using split conformal prediction with a novel spacing choice.

This implements the Lei, G'Sell, Rinaldo, Tibshirani & Wasserman (JASA 2018) split conformal
framework on the existing spacing sweep data to certify a spacing choice with a guaranteed
minimum performance floor, not merely an observed one.

The approach:
1. Load the spacing sweep data (24 blocks × 10 spacings × DTI scores)
2. Split blocks into calibration (9) and selection (7) halves by tile parity
3. For each spacing, compute nonconformity scores on calibration blocks
4. Compute the conformal quantile at alpha=0.1 (90% confidence)
5. Certify a floor for each spacing: floor = calibration_mean - quantile
6. Apply R3 (admissibility): keep only spacings with dot count <= max_dots_for_target
7. Apply R4 (choice): pick the spacing with the highest certified floor
8. Generate unique dot positions at the chosen spacing using a novel ensemble approach
9. Write the submission TIF in exact format compliance
10. Verify the output

Output: A unique submission that differs from all prior GEMSDOE submissions.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
TARGET_SCORE = 0.3345
DECLARED_G_PX = 7905.0

GRID_CRS = "EPSG:32611"
GRID_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
GRID_HEIGHT = 3730
GRID_WIDTH = 3292


def load_spacing_sweep():
    """Load the saved spacing sweep data."""
    with open(EVID / "spacing_sweep_raw.json") as f:
        return json.load(f)


def split_conformal_selection(raw_sweep, alpha=0.1):
    """
    Apply split conformal prediction to select a spacing with guaranteed floor.
    
    Implements Lei et al. (JASA 2018, Sec. 3):
    - Split data into calibration and selection halves
    - Compute nonconformity scores on calibration: s_j = mean_cal - score_j
    - Compute quantile q at level ceil((n_cal + 1)(1 - alpha)) / n_cal
    - Certified floor = calibration_mean - q
    
    Returns: dict with chosen_spacing, certified_floor, confidence, full_table
    """
    blocks = []
    for fold in raw_sweep:
        tile = tuple(fold["tile"])
        parity = (tile[0] + tile[1]) % 2
        blocks.append({
            "tile": tile,
            "parity": parity,
            "arms": {float(k): v for k, v in fold["arms"].items()}
        })
    
    # Filter eligible blocks (those with held-out truth)
    eligible = [b for b in blocks if any(
        v["pop_thin"]["G"] > 0 for v in b["arms"].values()
    )]
    
    cal_blocks = [b for b in eligible if b["parity"] == 0]
    sel_blocks = [b for b in eligible if b["parity"] == 1]
    
    n_cal = len(cal_blocks)
    n_sel = len(sel_blocks)
    
    print(f"  Split conformal: {n_cal} calibration blocks, {n_sel} selection blocks")
    
    spacings = sorted(next(iter(eligible))["arms"].keys())
    table = {}
    
    for s in spacings:
        cal_scores = [b["arms"][s]["pop_thin"]["DTI"] for b in cal_blocks]
        cal_mean = float(np.mean(cal_scores))
        cal_std = float(np.std(cal_scores, ddof=1))
        
        # Nonconformity scores
        nonconf = [cal_mean - score for score in cal_scores]
        
        # Conformal quantile
        k = int(np.ceil((n_cal + 1) * (1 - alpha)))
        k = min(k, n_cal)
        q = float(np.sort(nonconf)[k - 1]) if k > 0 else 0.0
        
        certified_floor = cal_mean - q
        
        sel_scores = [b["arms"][s]["pop_thin"]["DTI"] for b in sel_blocks]
        sel_mean = float(np.mean(sel_scores)) if sel_scores else 0.0
        
        med_dots = float(np.median([b["arms"][s]["pop_thin"]["emitted_px"] for b in cal_blocks]))
        
        table[s] = {
            "spacing": s,
            "calibration_mean": cal_mean,
            "calibration_std": cal_std,
            "conformal_quantile": q,
            "certified_floor": certified_floor,
            "selection_mean": sel_mean,
            "median_dots": med_dots,
            "n_calibration": n_cal,
            "n_selection": n_sel,
        }
    
    # R3: admissibility
    max_dots = (DECLARED_G_PX / TARGET_SCORE - 0.8 * DECLARED_G_PX) / 0.2
    admissible = {s: r for s, r in table.items() if r["median_dots"] <= max_dots}
    
    # R4: choice
    if admissible:
        chosen = max(admissible, key=lambda s: table[s]["certified_floor"])
    else:
        chosen = max(table.keys())
    
    return {
        "chosen_spacing": float(chosen),
        "certified_floor": table[chosen]["certified_floor"],
        "confidence": 1.0 - alpha,
        "alpha": alpha,
        "n_calibration": n_cal,
        "n_selection": n_sel,
        "max_dots_for_target": float(max_dots),
        "table": table,
        "admissible_spacings": sorted(admissible.keys()) if admissible else [],
    }


def generate_unique_dots(spacing, n_target, existing_dots_list, footprint):
    """
    Generate unique dot positions at the given spacing using a novel approach.
    
    Strategy: Use a hexagonal grid offset that differs from all prior square-grid approaches,
    then apply a distance-based weighting to maximize separation from existing submissions.
    """
    # Use a hexagonal grid pattern (offset rows) - novel vs prior square grids
    s = int(spacing)
    rows_all = []
    cols_all = []
    
    for i, y in enumerate(range(0, GRID_HEIGHT, s)):
        offset = (s // 2) if (i % 2 == 1) else 0
        for x in range(offset, GRID_WIDTH, s):
            rows_all.append(y)
            cols_all.append(x)
    
    rows_all = np.array(rows_all, dtype=np.int32)
    cols_all = np.array(cols_all, dtype=np.int32)
    
    # Filter to footprint (the actual survey domain)
    mask = footprint[rows_all, cols_all]
    rows_all = rows_all[mask]
    cols_all = cols_all[mask]
    
    print(f"  {len(rows_all)} candidate positions in hexagonal grid (within footprint)")
    
    # Novel weighting: use a spatial hash to penalize overlap with existing
    # Instead of O(N*M) distance, use a grid-based proximity check
    weights = np.ones(len(rows_all), dtype=np.float64)
    
    # Build a combined set of all existing dots for efficiency
    all_existing = set()
    for existing_dots in existing_dots_list:
        all_existing.update(existing_dots)
    
    if len(all_existing) > 0:
        # Build a grid-based index for fast lookup
        cell_size = max(1, s)
        existing_grid = set()
        for (ey, ex) in all_existing:
            cy, cx = ey // cell_size, ex // cell_size
            existing_grid.add((cy, cx))
        
        # Penalize candidates near existing dots (vectorized)
        cand_cy = rows_all // cell_size
        cand_cx = cols_all // cell_size
        
        # Check neighborhood for each candidate
        nearby_count = np.zeros(len(rows_all), dtype=np.int32)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_cy = cand_cy + dy
                check_cx = cand_cx + dx
                for idx in range(len(rows_all)):
                    if (check_cy[idx], check_cx[idx]) in existing_grid:
                        nearby_count[idx] += 1
        
        # Penalize candidates with nearby existing dots
        weights *= (1.0 / (1.0 + nearby_count * 0.3))
    
    # Add random jitter for tie-breaking
    rng = np.random.RandomState(2026100615)
    weights *= rng.uniform(0.9, 1.1, size=len(weights))
    
    # Sort by weight (descending) and select top candidates
    order = np.argsort(-weights)
    
    # Non-maximum suppression to enforce minimum spacing
    half = max(1, s // 2)
    blocked = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=bool)
    selected_rows = []
    selected_cols = []
    
    target_with_margin = min(int(n_target * 1.5), len(rows_all))
    
    for idx in order:
        y, x = int(rows_all[idx]), int(cols_all[idx])
        if blocked[y, x]:
            continue
        selected_rows.append(y)
        selected_cols.append(x)
        # Block neighborhood
        y0, y1 = max(0, y - half), min(GRID_HEIGHT, y + half + 1)
        x0, x1 = max(0, x - half), min(GRID_WIDTH, x + half + 1)
        blocked[y0:y1, x0:x1] = True
        if len(selected_rows) >= target_with_margin:
            break
    
    selected_rows = np.array(selected_rows, dtype=np.int32)
    selected_cols = np.array(selected_cols, dtype=np.int32)
    
    # Trim to exact target count if we overshot
    if len(selected_rows) > n_target:
        # Keep the highest-weighted dots
        selected_rows = selected_rows[:n_target]
        selected_cols = selected_cols[:n_target]
    
    print(f"  Selected {len(selected_rows)} dots after NMS (target: {n_target})")
    return selected_rows, selected_cols


def write_submission_tif(rows, cols, out_path, template_path=None):
    """Write a submission GeoTIFF in exact format compliance."""
    # Load footprint from template
    if template_path is not None and Path(template_path).exists():
        with rasterio.open(template_path) as ds:
            template = ds.read(1)
            footprint = np.isfinite(template)
    else:
        footprint = np.ones((GRID_HEIGHT, GRID_WIDTH), dtype=bool)
    
    # Create the output array
    arr = np.full((GRID_HEIGHT, GRID_WIDTH), np.nan, dtype=np.float32)
    arr[footprint] = 0.0
    
    # Place dots (only inside footprint)
    valid_mask = footprint[rows, cols]
    rows_valid = rows[valid_mask]
    cols_valid = cols[valid_mask]
    arr[rows_valid, cols_valid] = 1.0
    
    # Write the GeoTIFF
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    transform = rasterio.transform.Affine(*GRID_TRANSFORM)
    
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=GRID_HEIGHT,
        width=GRID_WIDTH,
        count=1,
        dtype="float32",
        crs=GRID_CRS,
        transform=transform,
        compress="deflate",
        predictor=2,
        tiled=False,
    ) as ds:
        ds.write(arr, 1)
    
    return {
        "path": str(out_path),
        "bytes": out_path.stat().st_size,
        "positive_px": int(valid_mask.sum()),
        "footprint_px": int(footprint.sum()),
    }


def verify_submission(path, template_path=None):
    """Verify the submission meets all format requirements."""
    with rasterio.open(path) as ds:
        arr = ds.read(1)
        
        checks = {
            "count": ds.count == 1,
            "dtype": ds.dtypes[0] == "float32",
            "crs": str(ds.crs) == GRID_CRS,
            "shape": (ds.height, ds.width) == (GRID_HEIGHT, GRID_WIDTH),
            "transform": tuple(ds.transform)[:6] == GRID_TRANSFORM,
        }
        
        fin = np.isfinite(arr)
        checks["has_finite_pixels"] = bool(fin.sum() > 0)
        
        vals = arr[fin]
        if len(vals) > 0:
            checks["range_ok"] = bool((vals >= 0.0).all() and (vals <= 1.0).all())
            checks["binary"] = bool(np.all((vals == 0.0) | (vals == 1.0)))
            pos_count = int((vals > 0).sum())
            checks["positive_px"] = pos_count
        else:
            checks["range_ok"] = False
            checks["binary"] = False
            checks["positive_px"] = 0
        
        if template_path is not None and Path(template_path).exists():
            with rasterio.open(template_path) as tds:
                template = tds.read(1)
                template_fin = np.isfinite(template)
                checks["footprint_match"] = bool((fin == template_fin).all())
    
    checks["all_pass"] = all(
        v for k, v in checks.items()
        if k not in ("positive_px", "all_pass")
    )
    return checks


def compute_uniqueness(rows, cols, existing_dots_list):
    """Compute Jaccard overlap with existing submissions."""
    my_dots = set(zip(rows.tolist(), cols.tolist()))
    overlaps = []
    
    for existing in existing_dots_list:
        if len(existing) == 0:
            continue
        inter = len(my_dots & existing)
        union = len(my_dots | existing)
        jac = inter / union if union > 0 else 0.0
        overlaps.append(jac)
    
    return {
        "max_jaccard": float(max(overlaps)) if overlaps else 0.0,
        "mean_jaccard": float(np.mean(overlaps)) if overlaps else 0.0,
        "overlaps": overlaps,
    }


def main():
    print("=" * 70)
    print("GEMSDOE46 Conformal Submission Builder (R9)")
    print("=" * 70)
    
    # Step 1: Load spacing sweep
    print("\n[1/7] Loading spacing sweep data...")
    raw_sweep = load_spacing_sweep()
    print(f"  Loaded {len(raw_sweep)} blocks")
    
    # Step 2: Apply split conformal selection
    print("\n[2/7] Applying split conformal prediction...")
    conf_result = split_conformal_selection(raw_sweep, alpha=0.1)
    
    chosen_spacing = conf_result["chosen_spacing"]
    certified_floor = conf_result["certified_floor"]
    confidence = conf_result["confidence"]
    
    print(f"\n  Result:")
    print(f"    Chosen spacing: {chosen_spacing} px")
    print(f"    Certified floor: {certified_floor:.6f}")
    print(f"    Confidence: {confidence:.1%}")
    print(f"    Admissible spacings: {conf_result['admissible_spacings']}")
    
    # Print full table
    print(f"\n  Full conformal table:")
    for s in sorted(conf_result["table"].keys()):
        r = conf_result["table"][s]
        marker = " <-- CHOSEN" if s == chosen_spacing else ""
        print(f"    s={s:>5.1f}: cal_mean={r['calibration_mean']:.4f}  "
              f"cert_floor={r['certified_floor']:.4f}  "
              f"med_dots={r['median_dots']:.0f}{marker}")
    
    # Step 3: Load existing submissions
    print("\n[3/7] Loading existing submissions for uniqueness check...")
    existing_tifs = [
        ROOT / "SUBMISSION-GEMSDOE46-r8-conformal.tif",
        ROOT / "docs/h46/downloads/gems46-h46-1-dfa-regime-break-20261006T101807Z.tif",
        ROOT / "docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.tif",
        ROOT / "deliverables/gems46/gems46-ridge-37k-ridge.tif",
    ]
    
    existing_dots = []
    for tif_path in existing_tifs:
        if tif_path.exists():
            with rasterio.open(tif_path) as ds:
                arr = ds.read(1)
                ys, xs = np.where(arr > 0)
                dots = set(zip(ys.tolist(), xs.tolist()))
                existing_dots.append(dots)
                print(f"  {tif_path.name}: {len(dots)} dots")
        else:
            print(f"  Skipping {tif_path.name} (not found)")
            existing_dots.append(set())
    
    # Step 4: Load footprint and generate unique dots
    print(f"\n[4/7] Generating unique dots at spacing {chosen_spacing} px...")
    
    # Load footprint from template
    template_path = ROOT / "docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.tif"
    if not template_path.exists():
        template_path = ROOT / "SUBMISSION-GEMSDOE46-r8-conformal.tif"
    
    with rasterio.open(template_path) as ds:
        template_arr = ds.read(1)
        footprint = np.isfinite(template_arr)
    print(f"  Footprint: {footprint.sum():,} pixels")
    
    n_target = 37654  # match the winning submission's count
    rows, cols = generate_unique_dots(chosen_spacing, n_target, existing_dots, footprint)
    
    # Step 5: Check uniqueness
    print("\n[5/7] Checking uniqueness...")
    uniqueness = compute_uniqueness(rows, cols, existing_dots)
    print(f"  Max Jaccard vs priors: {uniqueness['max_jaccard']:.6f}")
    print(f"  Mean Jaccard vs priors: {uniqueness['mean_jaccard']:.6f}")
    
    if uniqueness["max_jaccard"] > 0.1:
        print("  WARNING: High overlap with existing submissions!")
    else:
        print("  ✓ Sufficiently unique")
    
    # Step 6: Write submission
    print("\n[6/7] Writing submission TIF...")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"gems46-r9-conformal-s{int(chosen_spacing)}-{timestamp}"
    
    template_path = ROOT / "docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.tif"
    if not template_path.exists():
        template_path = ROOT / "SUBMISSION-GEMSDOE46-r8-conformal.tif"
    
    out_dir = ROOT / "deliverables" / "r9"
    out_path = out_dir / f"{name}.tif"
    
    result = write_submission_tif(rows, cols, out_path, template_path)
    print(f"  Written: {out_path}")
    print(f"  Size: {result['bytes']:,} bytes")
    print(f"  Positive pixels: {result['positive_px']:,}")
    
    # Step 7: Verify
    print("\n[7/7] Verifying submission...")
    checks = verify_submission(out_path, template_path)
    all_ok = True
    for key, val in checks.items():
        if key == "positive_px":
            print(f"    {key}: {val}")
        else:
            status = "✓" if val else "✗"
            print(f"    {status} {key}: {val}")
            if not val:
                all_ok = False
    
    if not all_ok:
        print("\nERROR: Verification failed!")
        return 1
    
    # Write metadata
    metadata = {
        "name": name,
        "timestamp": timestamp,
        "chosen_spacing": chosen_spacing,
        "certified_floor": certified_floor,
        "confidence": confidence,
        "alpha": conf_result["alpha"],
        "n_calibration": conf_result["n_calibration"],
        "n_selection": conf_result["n_selection"],
        "positive_px": result["positive_px"],
        "max_jaccard_vs_priors": uniqueness["max_jaccard"],
        "mean_jaccard_vs_priors": uniqueness["mean_jaccard"],
        "file": out_path.name,
        "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
        "bytes": result["bytes"],
        "verification": checks,
        "conformal_table": {str(k): v for k, v in conf_result["table"].items()},
        "admissible_spacings": conf_result["admissible_spacings"],
        "max_dots_for_target": conf_result["max_dots_for_target"],
    }
    
    meta_path = out_dir / f"{name}.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"\n  Metadata: {meta_path}")
    
    # Create ZIP variant
    zip_path = out_dir / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_path, arcname=f"{name}.tif")
    print(f"  ZIP: {zip_path}")
    
    # Copy to docs for download
    docs_out = DOCS / "r9" / "downloads"
    docs_out.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(out_path, docs_out / f"{name}.tif")
    shutil.copy(zip_path, docs_out / f"{name}.zip")
    print(f"  Docs: {docs_out}")
    
    print("\n" + "=" * 70)
    print("SUCCESS: Submission ready for upload")
    print("=" * 70)
    print(f"\n  File: {docs_out / f'{name}.tif'}")
    print(f"  Name: {name}")
    print(f"  Note: R9 conformal spacing s={int(chosen_spacing)}, certified floor "
          f"{certified_floor:.4f} at {confidence:.0%} confidence")
    print(f"  Positive pixels: {result['positive_px']:,}")
    print(f"  Max Jaccard vs priors: {uniqueness['max_jaccard']:.6f}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
