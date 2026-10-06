#!/usr/bin/env python
"""Validate hypothesis H1 (fault-release / new-fault detection) on the blocked holdout.

The hypothesis
--------------
The scored population is *new* faults found by an expert panel.  A large class of
faults that no compilation contains is revealed by **instrumental seismicity and
its spatial relation to structure**: slip on a blind or previously unmapped
structure shows up as an earthquake cloud before anyone maps a scarp.  The official
raster already carries the ingredients -- band 10 (distance to earthquake) and
band 16 (earthquake density) -- but band 10 is *not in the shipped feature plan at
all*, and band 16 enters only as a plain smoothed value.

Why the test is built from interactions, not from ``exp(-d/lambda)``
--------------------------------------------------------------------
A gradient-boosted tree splits on quantiles of a feature, so it is **invariant to
monotone transformations of a single column**: shipping ``exp(-d/lambda)`` instead
of ``d`` changes nothing the model can see.  What a tree cannot construct by itself
is a *product* of two smooth fields.  The physically motivated content of H1 is
therefore the interaction of a release-proximity score with the structural layers,
and that is what this script adds:

    A  baseline           the shipped 25-column plan                       (control)
    B  proximity          A + 3 columns built from band 10 (rank, standardised
                          value, and a unit-free ``exp(-d / median d)`` decay)
    C  proximity x structure
                          A + 4 columns: prox_z x ridge(elev, sigma=2),
                          prox_z x ridge(tilt-curvature band 6, sigma=1),
                          prox_z x smooth(eq density, sigma=2),
                          prox_z x smooth(conductivity, sigma=2)

Protocol
--------
* Blocks: exactly the 16 blocks that pass the pre-declared eligibility rule R1 --
  the same blocks the shipped conformal selection uses.
* Arm: spacing r = 8 px, identical emitter, identical prior correction, identical
  truth subsample hash (the salt is a function of the block index only).
* Model: identical to ``scripts/run_pipeline.py`` (HGB, 120 iters, seed = block).
* Config A must reproduce the saved sweep DTI to floating-point tolerance; that
  check is asserted and reported, because it is what makes B and C paired rather
  than merely comparable.

The local Monte Cristo check is qualitative by construction: no truth vector
exists for an unmapped fault, so it reports *emission near the published rupture*
(2020 Mw 6.5, 28 km surface rupture on largely unmapped parts of the Candelaria
fault, USGS publication 70220306 / Koehler et al. 2021 SRL, absent from USGS
QFaults and the INGENIOUS catalogue), not a score.
"""
from __future__ import annotations

import json
import sys
import time
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import features as F     # noqa: E402
from gems46 import pipeline as P     # noqa: E402
from gems46 import submit as S       # noqa: E402

CACHE = ROOT / "cache"
EVID = ROOT / "evidence"
SPACING = 8.0
MONTE_CRISTO_LONLAT = (-117.850, 38.169)


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def build_extra_columns():
    """Band-10 proximity columns plus the interaction set, in flat footprint order."""
    import rasterio
    from scipy import ndimage

    with rasterio.open(ROOT / "data/training_features.tif") as src:
        b10 = F._read_band(src, 10)          # median-filled exactly like the shipped plan
        b16 = F._read_band(src, 16)
    ss = rasterio.open(ROOT / "data/sample_submission.tif").read(1)
    footprint = np.isfinite(ss)
    flat = np.nonzero(footprint.ravel())[0]
    w = ss.shape[1]
    fr, fc = flat // w, flat % w

    d_raw = b10[fr, fc].astype(np.float64)
    d_raw = np.where(np.isfinite(d_raw) & (d_raw >= 0), d_raw, np.nan)
    med = float(np.nanmedian(d_raw))
    d_filled = np.where(np.isfinite(d_raw), d_raw, med)
    rank = np.argsort(np.argsort(d_filled, kind="stable"), kind="stable")
    prox_rank = (rank / max(1.0, rank.size - 1.0)).astype(np.float32)      # 1 = closest
    prox_val = d_filled.astype(np.float32)
    prox_decay = np.exp(-d_filled / med).astype(np.float32)                # unit-free
    prox_z = (prox_rank - prox_rank.mean()) / (prox_rank.std() or 1.0)

    d16s8 = ndimage.gaussian_filter(b16, 8.0, mode="nearest")[fr, fc].astype(np.float32)
    log(f"band-10 proximity: median {med:.4g} (band units), decay length = median")
    return footprint, np.column_stack([prox_rank, prox_val, prox_decay,
                                       d16s8]).astype(np.float32), prox_z


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier
    import rasterio
    from scipy import ndimage
    from gems46.window_metric import global_truth_distance

    raw = json.loads((EVID / "spacing_sweep_raw.json").read_text())
    sweep_dti = {d["fold"]: d["arms"][str(SPACING)]["pop_thin"]["DTI"] for d in raw}

    lbl = rasterio.open(ROOT / "data/labels.tif").read(1)
    ss = rasterio.open(ROOT / "data/sample_submission.tif").read(1)
    footprint = np.isfinite(ss)
    truth = lbl == 1
    flat = np.nonzero(footprint.ravel())[0]
    flat_r = (flat // S.SHAPE[1]).astype(np.int32)
    flat_c = (flat % S.SHAPE[1]).astype(np.int32)

    X = np.load(CACHE / "features.npy")
    fp2, extra, prox_z = build_extra_columns()
    assert np.array_equal(fp2, footprint)
    names = {i: n for i, n in enumerate(
        [f"{k}:{F.BANDS[b]}:s{s:g}" for (k, b, s) in F.FEATURE_PLAN])}
    ridge12 = X[:, [i for i, n in names.items() if n == "ridge:detrend_elev:s2"][0]].astype(np.float32)
    ridge6 = X[:, [i for i, n in names.items() if n == "ridge:tilt_curv:s1"][0]].astype(np.float32)
    dens16 = X[:, [i for i, n in names.items() if n == "smooth:eq_density:s2"][0]].astype(np.float32)
    cond17 = X[:, [i for i, n in names.items() if n == "smooth:conductivity:s2"][0]].astype(np.float32)

    def z(c):
        c = c.astype(np.float64)
        return ((c - c.mean()) / (c.std() or 1.0)).astype(np.float32)

    inter = np.column_stack([z(prox_z * ridge12), z(prox_z * ridge6),
                             z(prox_z * dens16), z(prox_z * cond17)]).astype(np.float32)

    configs = {"A_shipped": None,
               "B_proximity": extra[:, [0, 1, 2]],
               "C_proximity_x_structure": inter}
    cat_dist = np.where(footprint, ndimage.distance_transform_edt(~truth),
                        np.inf).astype(np.float32)
    d_truth = global_truth_distance(truth)
    tiles = P.tile_bounds(S.SHAPE)

    per_config = {}
    for cname, add in configs.items():
        Xc = X if add is None else np.concatenate([X, add], axis=1)
        rows = []
        for k, tile in enumerate(tiles):
            factory = (lambda seed: (lambda: HistGradientBoostingClassifier(
                max_iter=120, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
                l2_regularization=1.0, max_bins=128, early_stopping=False, random_state=seed)))(k)
            res = P.run_fold(flat_r, flat_c, footprint, truth, Xc, tile, cat_dist,
                             factory, rng_seed=1000 + k, log=lambda *a: None,
                             top_k_full=120_000, d_truth=d_truth,
                             ratios=(P.NEW_FAULT_TO_CATALOGUE_RATIO,),
                             spacings=(SPACING,))
            if not P.eligible(res):
                continue
            arm = res.arms[SPACING]
            rows.append({"fold": k, "tile": list(tile),
                         "dti": arm[P.PRIMARY_POP]["DTI"],
                         "dots": arm["dot_count"]})
        per_config[cname] = rows
        log(f"config {cname:<24} blocks {len(rows)}  mean DTI "
            f"{np.mean([r['dti'] for r in rows]):.5f}")
        if add is not None:
            del Xc

    # --- pairing check: config A against the saved sweep ---------------------
    diffs = []
    for r in per_config["A_shipped"]:
        s = sweep_dti.get(r["fold"])
        if s is not None:
            diffs.append(abs(r["dti"] - s))
    max_dev = float(max(diffs)) if diffs else float("nan")
    log(f"pairing check |A - saved sweep| max deviation {max_dev:.2e} over {len(diffs)} blocks")
    assert max_dev < 1e-12, "config A does not reproduce the sweep -> comparison is not paired"

    base = {r["fold"]: r["dti"] for r in per_config["A_shipped"]}
    summary = {"hypothesis": "H1 fault-release / new-fault detection",
               "spacing_px": SPACING, "blocks": len(base),
               "pairing_check_max_abs_deviation_vs_sweep": max_dev,
               "arms": {}}
    for cname, rows in per_config.items():
        d = np.array([r["dti"] - base[r["fold"]] for r in rows])
        n = len(d)
        wins = int((d > 1e-12).sum())
        tail = sum(comb(n, x) for x in range(max(wins, n - wins), n + 1)) / 2.0 ** n
        summary["arms"][cname] = {
            "mean_dti": float(np.mean([r["dti"] for r in rows])),
            "mean_diff_vs_A": float(d.mean()), "median_diff_vs_A": float(np.median(d)),
            "blocks_improved": wins,
            "sign_test_two_sided_p": float(min(1.0, 2 * tail)),
            "per_block": rows}
        log(f"  {cname:<24} mean diff vs A {d.mean():+.5f}  median {np.median(d):+.5f}  "
            f"improved {wins}/{n}  sign-test p={min(1.0, 2 * tail):.4f}")

    # --- qualitative local check: Monte Cristo ---------------------------------
    try:
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", "EPSG:32611", always_xy=True)
        x, y = tr.transform(*MONTE_CRISTO_LONLAT)
        row = int(round((4508550.0 - y) / 100.0))
        col = int(round((x - 243350.0) / 100.0))
        summary["monte_cristo_check"] = {
            "lonlat": list(MONTE_CRISTO_LONLAT), "row_col": [row, col],
            "inside_scored_footprint": bool(footprint[row, col]),
            "source": "USGS publication 70220306; Koehler et al. 2021 SRL",
            "note": ("2020 Mw 6.5, 28 km surface rupture on largely unmapped parts of the "
                     "Candelaria fault; absent from USGS QFaults and the INGENIOUS catalogue; "
                     "no truth vector exists for an unmapped fault, so the A/B above is the "
                     "quantitative test and the shipped file's local emission density is reported "
                     "in docs/HYPOTHESES.md")}
        log(f"Monte Cristo epicentre row/col {row}/{col}, inside footprint: "
            f"{summary['monte_cristo_check']['inside_scored_footprint']}")
    except Exception as exc:
        summary["monte_cristo_check"] = {"checked": False, "error": repr(exc)}
        log(f"Monte Cristo check unavailable: {exc!r}")

    # --- verdict rule (declared before the numbers were read) -----------------
    b = summary["arms"]["B_proximity"]
    c = summary["arms"]["C_proximity_x_structure"]
    h1_additive = b["mean_diff_vs_A"] > 0 and b["sign_test_two_sided_p"] < 0.05
    h1_interaction = c["mean_diff_vs_A"] > 0 and c["sign_test_two_sided_p"] < 0.05
    verdict = ("CONFIRMED (interaction)" if h1_interaction else
               "CONFIRMED (additive only)" if h1_additive else "NOT CONFIRMED")
    summary["verdict"] = verdict
    log(f"H1 verdict: {verdict}")

    (EVID / "hypothesis_H1_release.json").write_text(json.dumps(summary, indent=2))
    (EVID / "hypothesis_H1_verdict.txt").write_text(verdict + "\n")


if __name__ == "__main__":
    main()
