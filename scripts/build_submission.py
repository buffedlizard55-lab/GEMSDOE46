#!/usr/bin/env python3
"""Build THE submission: binary dots on the validated credit ridge, in legal GeoTIFF form.

Design (all justified in docs/method.md):
  * The metric is linear within a dot: a unit of mass at x adds TP by k(x) and FP by 0.2,
    so mass is all-or-nothing at unit value and should be emitted where the expected kernel
    credit k_hat exceeds 0.2*DTI.  Hence binary dots, never partial values.
  * Kernels are kept non-overlapping (Chebyshev spacing >= 4 px) because two dots covering
    the same truth pixel waste one unit of mass: the max() in TP_w only counts it once while
    FP_w charges both.
  * Placement follows S(x), the kernel-smoothed credit direction r = sum_k beta_k z_k, whose
    coverage-weighted mean is a leave-one-anchor-out-validated predictor of the real headline
    score (deduped LOO Spearman +0.826 on 43 scored anchors).
  * Pixels within 3 px of the visible catalogue are excluded: the official rules mask known
    fault pixels from evaluation, so mass there earns no TP and still pays FP.

Options let the user reproduce every variant and re-run the whole thing unattended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path("/home/user/GEMSDOE46")
sys.path.insert(0, str(ROOT / "src"))
from gems46 import anchors as A  # noqa: E402
from gems46 import metric as M  # noqa: E402
from gems46 import rasters as R  # noqa: E402

DATA = Path("/tmp/gems46/data")
GRID = ROOT / "data" / "raw" / "grid"


def nms_select(S: np.ndarray, candidates: np.ndarray, n_max: int, half: int,
               verbose: bool = True):
    """Greedy non-maximum suppression; returns (flat_idx, S_value) in selection order."""
    order = candidates[np.argsort(-S.ravel()[candidates], kind="stable")]
    H, W = S.shape
    blocked = np.zeros((H, W), bool)
    sv = S.ravel()
    picked = np.zeros(n_max, np.int64)
    vals = np.zeros(n_max, np.float32)
    n = 0
    for f in order:
        y, x = divmod(int(f), W)
        if blocked[y, x]:
            continue
        picked[n] = f
        vals[n] = sv[f]
        n += 1
        y0, y1 = max(0, y - half), min(H, y + half + 1)
        x0, x1 = max(0, x - half), min(W, x + half + 1)
        blocked[y0:y1, x0:x1] = True
        if n >= n_max:
            break
    if verbose:
        print(f"  nms: picked {n} dots (requested {n_max}, half-width {half})")
    return picked[:n], vals[:n]


def predict_score(mean_S: float, n_dots: int, dcat_med: float, model: dict) -> float:
    x = np.array([mean_S, np.log(max(n_dots, 1)), dcat_med], float)
    z = (x - np.array(model["x_mean"])) / np.array(model["x_sd"])
    return float(model["intercept"] + z @ np.array(model["coef"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-dots", type=int, default=35000)
    ap.add_argument("--n-max", type=int, default=60000)
    ap.add_argument("--half", type=int, default=3)
    ap.add_argument("--catalogue-buffer", type=int, default=3,
                    help="px around the visible catalogue excluded as unwinnable")
    ap.add_argument("--out", default=str(ROOT / "deliverables" / "gems46"))
    ap.add_argument("--tag", default="ridge")
    args = ap.parse_args()

    t0 = time.time()
    S = np.load(DATA / "credit_S.npy")
    fp = np.load(DATA / "credit_model.npz", allow_pickle=True)["footprint"]
    with rasterio.open(GRID / "labels.tif") as ds:
        lab = ds.read(1) > 0
        transform, crs = ds.transform, ds.crs
    from scipy.ndimage import distance_transform_edt
    dcat = distance_transform_edt(~lab)
    cand = fp & (dcat > max(args.catalogue_buffer, 0))
    print(f"candidates {int(cand.sum()):,} of footprint {int(fp.sum()):,} "
          f"({time.time()-t0:.0f}s)")

    picked, vals = nms_select(S, np.flatnonzero(cand.ravel()), args.n_max, args.half)
    np.save(DATA / f"emission_{args.tag}_nms.npy", picked)

    model = json.loads((ROOT / "data" / "emission_model.json").read_text())
    H, W = S.shape
    dcat_med = float(np.median(dcat.ravel()[picked]))

    print(f"\n{'N':>7s} {'mean_S':>8s} {'pred':>7s}   (candidate prefixes)")
    best = None
    for n in (10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 60000):
        if n > len(picked):
            continue
        mS = float(vals[:n].mean())
        p = predict_score(mS, n, dcat_med, model)
        print(f"{n:7d} {mS:8.4f} {p:7.4f}")
        if n == args.n_dots:
            best = (n, mS, p)
    if best is None:
        n = min(args.n_dots, len(picked))
        best = (n, float(vals[:n].mean()), predict_score(float(vals[:n].mean()), n, dcat_med, model))

    n, mS, pred = best
    rows, cols = np.divmod(picked[:n], W)
    print(f"\nchosen N={n} mean_S={mS:.4f} predicted={pred:.4f} "
          f"median dist to catalogue {dcat_med:.1f} px")

    arr = np.zeros((H, W), np.float32)
    arr[rows, cols] = 1.0
    out = Path(args.out) / f"gems46-{args.tag}-{n//1000}k-{args.tag}.tif"
    info = R.write_submission(out, arr, transform=transform, crs=crs)
    info["sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    info["mean_S"] = mS
    info["predicted_score"] = pred
    info["catalogue_buffer_px"] = args.catalogue_buffer
    info["nms_half_width_px"] = args.half
    print(json.dumps(info, indent=1))

    # uniqueness vs every fetched anchor
    print("\nuniqueness vs the 43 scored anchor rasters:")
    mine = np.zeros(H * W, bool)
    mine[picked[:n]] = True
    worst = []
    for p in sorted((ROOT / "data" / "raw" / "anchors").glob("p*.tif")):
        d = A.load_dots(p, p.stem)
        flat = np.sort(d.row.astype(np.int64) * W + d.col)
        flat = flat[d.val > 0]
        inter = np.intersect1d(flat, picked[:n], assume_unique=True).size
        union = flat.size + n - inter
        worst.append((inter / union if union else 0.0, p.stem, flat.size, inter))
    worst.sort(reverse=True)
    for jac, aid, na, inter in worst[:5]:
        print(f"  {aid}: jaccard {jac:.4f}  shared {inter} px (anchor {na} dots)")
    info["max_jaccard_vs_anchors"] = float(worst[0][0])
    info["closest_anchor"] = worst[0][1]
    (Path(args.out) / f"gems46-{args.tag}.json").write_text(json.dumps(info, indent=1) + "\n")
    print(f"\nwrote {out}  ({info['bytes']:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
