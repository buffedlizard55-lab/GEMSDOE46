#!/usr/bin/env python
"""End-to-end GEMSDOE46 pipeline.

    python scripts/run_pipeline.py --stage all

``--stage`` selects how much work to redo:

    all    (default) verify the official data, run the 24-block sweep, then select
    post   reuse ``evidence/spacing_sweep_raw.json`` and only re-run selection --
           this is the cheap path after a change to the selection rules
    verify only re-hash the official data

Everything is cached under ``cache/`` (git-ignored) so stages can be re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import conformal as C                         # noqa: E402
from gems46 import features as F                          # noqa: E402
from gems46 import pipeline as P                          # noqa: E402
from gems46 import submit as S                            # noqa: E402
from gems46.window_metric import window_terms             # noqa: E402

CACHE = ROOT / "cache"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"

EXPECTED_SHA = {
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
}


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_verify():
    log("verify: hashing official data")
    out = {}
    for name, want in EXPECTED_SHA.items():
        got = sha256(ROOT / "data" / name)
        out[name] = {"sha256": got, "expected": want, "ok": got == want}
        log(f"  {name}: {'OK' if got == want else 'MISMATCH'}")
    (EVID / "data_provenance.json").write_text(json.dumps(out, indent=2))
    if not all(v["ok"] for v in out.values()):
        raise SystemExit("official data hash mismatch")
    return out


def load_grid():
    import rasterio
    lbl = rasterio.open(ROOT / "data/labels.tif").read(1)
    ss = rasterio.open(ROOT / "data/sample_submission.tif").read(1)
    footprint = np.isfinite(ss)
    truth = lbl == 1
    assert footprint.shape == S.SHAPE and footprint.sum() == 5_167_373
    assert truth.sum() == 60_988
    return footprint, truth


def stage_features(fresh=False):
    fp = CACHE / "features.npy"
    mp = CACHE / "features_meta.json"
    if fp.exists() and mp.exists() and not fresh:
        log("features: cached")
        return np.load(fp), json.loads(mp.read_text())
    footprint, _ = load_grid()
    log("features: building stack (this reads the 419 MB official raster)")
    X, names = F.build_feature_stack(str(ROOT / "data/training_features.tif"), footprint,
                                     progress=lambda *a: None)
    log(f"  built {X.shape}")
    np.save(fp, X)
    meta = {"names": names, "shape": list(X.shape),
            "footprint_pixels": int(footprint.sum())}
    (CACHE / "features_meta.json").write_text(json.dumps(meta, indent=2))
    return X, meta


def _catalogue_distance(truth, footprint):
    """Distance (px) to the nearest catalogue pixel, restricted to the footprint;
    inf outside.  Used ONLY for the emission exclusion gate, never as a feature."""
    from scipy import ndimage
    d = ndimage.distance_transform_edt(~truth)
    out = np.where(footprint, d, np.inf).astype(np.float32)
    out[truth] = 0.0
    return out


def stage_sweep(n_folds=None, model_kind="hgb"):
    from sklearn.ensemble import HistGradientBoostingClassifier
    footprint, truth = load_grid()
    X, meta = stage_features()
    star_w = ROOT / "data/sample_submission.tif"  # noqa: F841
    import rasterio
    with rasterio.open(ROOT / "data/sample_submission.tif") as s:
        _ = s.shape
    flat = np.nonzero(footprint.ravel())[0]
    flat_r = (flat // S.SHAPE[1]).astype(np.int32)
    flat_c = (flat % S.SHAPE[1]).astype(np.int32)

    tiles = P.tile_bounds(S.SHAPE)
    if n_folds:
        tiles = tiles[:n_folds]
    cat_dist = _catalogue_distance(truth, footprint)
    from gems46.window_metric import global_truth_distance
    d_truth = global_truth_distance(truth)

    def factory(seed=0):
        return HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.08, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, max_bins=128,
            early_stopping=False, random_state=seed,
        )

    results = []
    for k, tile in enumerate(tiles):
        t0 = time.time()
        res = P.run_fold(flat_r, flat_c, footprint, truth, X, tile, cat_dist,
                         model_factory=lambda: factory(seed=k), rng_seed=1000 + k,
                         log=log, top_k_full=120_000, d_truth=d_truth)
        results.append(res)
        log(f"  fold wall {time.time()-t0:.1f}s")
    return results


def results_to_json(results):
    return [
        {"fold": r.fold, "tile": r.tile, "selection": r.selection,
         "n_train_pos": r.n_train_pos, "n_train_neg": r.n_train_neg,
         "arms": {str(s): v for s, v in r.arms.items()}}
        for r in results
    ]


def stage_analytic():
    from gems46.analytic import max_possible_index, max_dots_for_target, credit_needed
    g_decl = 7905.0
    leaders = [0.3345, 0.3262, 0.3222, 0.3218, 0.3195]
    rows = []
    for n in (20_000, 30_000, 44_090, 60_069, 80_000, 100_000, 121_131, 178_000):
        rows.append({"n_dots": n, "ceiling_at_G7905": max_possible_index(n, g_decl)})
    return {
        "declared_G_px": g_decl,
        "declared_G_source": "GEMSDOE32 H28 inference (owner-reported model), "
                             "|G| ~ 12,691 px overall; 7,905 px implied by the 0.2600 cross-check",
        "max_dots_for_target": {str(t): max_dots_for_target(t, g_decl) for t in leaders},
        "ceiling_table": rows,
        "credit_needed_for_0.3345_at_44090": credit_needed(44_090, g_decl, 0.3345),
        "sensitivity_G": {
            str(g): {"max_dots_for_0.3345": max_dots_for_target(0.3345, g),
                     "ceiling_at_44090": max_possible_index(44_090, g)}
            for g in (3950.0, 7905.0, 15_810.0)
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all")
    ap.add_argument("--alpha", type=float, default=0.0769,
                    help="kept for the population-sensitivity screens only; the shipped "
                         "alpha is 1/(n_cal+1) inside gems46.conformal")
    ap.add_argument("--folds", type=int, default=0)
    ap.add_argument("--fresh-features", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(exist_ok=True)
    EVID.mkdir(exist_ok=True)

    if args.stage == "post":
        raw = json.loads((EVID / "spacing_sweep_raw.json").read_text())
        log(f"post: reusing {len(raw)} saved blocks from evidence/spacing_sweep_raw.json")
    else:
        stage_verify()
        if args.stage == "verify":
            return
        results = stage_sweep(n_folds=args.folds or None)
        raw = results_to_json(results)
        (EVID / "spacing_sweep_raw.json").write_text(json.dumps(raw, indent=2))

    # One authoritative selection path: gems46.conformal applies the pre-declared
    # rules R1-R4 (eligibility, checkerboard split, density admissibility, then the
    # split-conformal floor at the smallest alpha the calibration half supports).
    conf = C.select_from_raw(raw)
    (EVID / "conformal_selection.json").write_text(json.dumps(conf, indent=2))
    (EVID / "population_sensitivity.json").write_text(
        json.dumps(conf["population_sensitivity"], indent=2))
    sens = conf["population_sensitivity"]
    chosen = conf["ship"]["spacing_px"]
    table = {float(k): v for k, v in conf["pop_thin"]["table"].items()}
    ana = stage_analytic()
    (EVID / "analytic_screen.json").write_text(json.dumps(ana, indent=2))
    log("analytic screen: declared |G| = 7905 px")
    for t, n in ana["max_dots_for_target"].items():
        log(f"  target {t}: max dots for the ceiling to reach it = {n:,.0f}")
    for row in ana["ceiling_table"]:
        log(f"  N={row['n_dots']:>7,} ceiling {row['ceiling_at_G7905']:.4f}")
    log("population sensitivity (R3+R4 choice under each declared population): " + " ".join(
        f"{k}->r{v['rule_R3R4_choice']:g}" for k, v in sens.items()))
    log(f"conformal: SHIP spacing {chosen:g} px, alpha={conf['alpha']:.4f} "
        f"(confidence {100*conf['confidence']:.1f}%, n_cal={conf['n_calibration']})")
    for s, row in sorted(table.items(), key=lambda kv: -kv[1]["certified_floor"]):
        log(f"  r={s:<4} sel={row['selection_mean']:.4f} cal={row['calibration_mean']:.4f} "
            f"q={row['conformal_quantile']:.4f} floor={row['certified_floor']:.4f} "
            f"dots_full~{row['median_dots_full_footprint']:.0f}")


if __name__ == "__main__":
    main()
