#!/usr/bin/env python
"""Train on all data, apply the pre-declared decision rules, write + audit the GeoTIFF.

Decision rules (fixed in advance; see ``src/gems46/conformal.py`` for the full text)

  R1  eligibility    blocks with no held-out truth are excluded            (in conformal.py)
  R2  split          selection / calibration = tile parity                 (in conformal.py)
  R3  admissibility  an arm may ship only if its emitted dot count N leaves room
                     for the target score under the data-free ceiling
                     ``DTI <= |G| / (0.2 N + 0.8 |G|)``
  R4  choice         among admissible arms, the largest certified split-conformal
                     floor (Lei et al. 2018) from the calibration blocks

R3 is applied here to the **measured** full-grid dot count of each candidate arm,
not to the per-block extrapolation in the sweep evidence.  The extrapolation
``median(per-block dots) x 24`` is biased upward for two measured reasons: the
median block emits more than the mean block, and tile-edge blocking differs between
a block and the global grid.  At r = 8 px the extrapolation says 67,836 dots, the
pooled per-tile density says 41,579, and the measured full-grid count is 39,108.
Both numbers are recorded for every arm so the reader can see the gap.

Usage
-----
    PYTHONPATH=src python scripts/make_submission.py            # rules pick the arm
    PYTHONPATH=src python scripts/make_submission.py --spacing 8 --tag my-tag
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import pipeline as P            # noqa: E402
from gems46 import submit as S              # noqa: E402
from gems46.analytic import max_dots_for_target, max_possible_index  # noqa: E402
from gems46.emitter import emit_positions, expected_credit  # noqa: E402
from gems46.window_metric import window_terms  # noqa: E402

CACHE = ROOT / "cache"
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
TARGET_SCORE = 0.3345


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spacing", type=float, default=None,
                    help="override the rule-chosen arm; the override is asserted against R3")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--g-mass", type=float, default=7905.0)
    ap.add_argument("--reuse-belief", action="store_true")
    ap.add_argument("--max-dots", type=int, default=3_000_000)
    args = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier
    import rasterio
    from scipy import ndimage

    conf = json.loads((EVID / "conformal_selection.json").read_text())
    table = {float(k): v for k, v in conf["pop_thin"]["table"].items()}
    spacings = sorted(table)
    max_dots_r3 = max_dots_for_target(TARGET_SCORE, args.g_mass)

    lbl = rasterio.open(ROOT / "data/labels.tif").read(1)
    ss = rasterio.open(ROOT / "data/sample_submission.tif").read(1)
    footprint = np.isfinite(ss)
    truth = lbl == 1
    X = np.load(CACHE / "features.npy")
    flat = np.nonzero(footprint.ravel())[0]
    flat_r = (flat // S.SHAPE[1]).astype(np.int32)
    flat_c = (flat % S.SHAPE[1]).astype(np.int32)
    cat_dist = np.where(footprint, ndimage.distance_transform_edt(~truth),
                        np.inf).astype(np.float32)
    allow = footprint & (cat_dist > P.CATALOGUE_EXCLUSION_PX)

    belief_path = CACHE / "belief_final.npy"
    if args.reuse_belief and belief_path.exists():
        belief = np.load(belief_path).astype(np.float32)
        log(f"belief reloaded from {belief_path}")
        shift = float("nan")
    else:
        pos = np.nonzero(truth[flat_r, flat_c])[0]
        neg_pool = np.nonzero(~truth[flat_r, flat_c])[0]
        rng = np.random.default_rng(20261006)
        n_neg = min(3 * len(pos), len(neg_pool))
        neg = rng.choice(neg_pool, size=n_neg, replace=False)
        idx = np.concatenate([pos, neg])
        log(f"final model: {len(pos)} positives + {n_neg} negatives = {len(idx)} rows")
        model = HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
            l2_regularization=1.0, max_bins=128, early_stopping=False, random_state=0)
        model.fit(X[idx], np.concatenate([np.ones(len(pos), np.int8),
                                          np.zeros(n_neg, np.int8)]))
        del idx, pos, neg_pool

        p_train = 0.25                       # 1 positive : 3 negatives by construction
        p_pop = float(truth[flat_r, flat_c].mean())
        shift = float(np.log(p_train / (1 - p_train)) - np.log(p_pop / (1 - p_pop)))
        log(f"prior shift = {shift:.4f} (train prev {p_train:.4f} -> population {p_pop:.5f})")

        belief = np.zeros(S.SHAPE, dtype=np.float32)
        for a in range(0, len(flat), 250_000):
            b = min(a + 250_000, len(flat))
            pr = model.predict_proba(X[a:b])[:, 1].astype(np.float32)
            pr = np.clip(pr, 1e-9, 1 - 1e-9)
            pr = (1.0 / (1.0 + np.exp(-(np.log(pr / (1 - pr)) - shift)))).astype(np.float32)
            belief[flat_r[a:b], flat_c[a:b]] = pr
        np.save(belief_path, belief)
    log(f"belief field: max {belief.max():.5f} mean {belief[footprint].mean():.6f} "
        f"p99 {float(np.quantile(belief[footprint], 0.99)):.6f}")

    sc = expected_credit(allow, belief, P.R_PIXELS)[allow]
    bar = 0.2 * P.INDEX_FLOOR
    log(f"emitter bar 0.2*{P.INDEX_FLOOR} = {bar:.4f}; fraction of allowed cells above it "
        f"{float((sc > bar).mean()):.4f} (mean credit {sc.mean():.4f})")
    del sc

    # ---- R3 with measured counts -------------------------------------------
    measured, emitted = {}, {}
    for s in spacings:
        rr, cc = emit_positions(belief, allow, s, index_floor=P.INDEX_FLOOR,
                                max_dots=args.max_dots)
        measured[s] = int(len(rr))
        emitted[s] = (rr.copy(), cc.copy())
        log(f"  measured arm r={s:<5g} -> {measured[s]:>8,} dots "
            f"(sweep extrapolation {table[s]['median_dots_full_footprint']:>8,.0f})")

    admissible = [s for s in spacings if measured[s] <= max_dots_r3]
    log(f"[R3] target {TARGET_SCORE} at declared |G|={args.g_mass:.0f} px -> max dots "
        f"{max_dots_r3:,.0f}; admissible measured arms: {admissible}")
    if not admissible:
        raise SystemExit("no arm is admissible: every measured arm is denser than the ceiling allows")
    best = max(admissible, key=lambda s: table[s]["certified_floor"])
    log(f"[R4] argmax certified floor among admissible arms: r={best:g} px "
        f"(floor {table[best]['certified_floor']:.4f} at "
        f"{100 * conf['confidence']:.1f}% confidence, n_cal={conf['n_calibration']})")
    if args.spacing is not None and abs(args.spacing - best) > 1e-9:
        raise SystemExit(f"--spacing {args.spacing:g} contradicts the pre-declared rules "
                         f"(R3+R4 give r={best:g}); refusing to ship an off-rule arm")
    spacing = best
    tag = args.tag or f"gemsdoe46-h46a-r{spacing:g}-conformal"

    rr, cc = emitted[spacing]
    dots = np.stack([rr, cc], axis=1).astype(np.int32)
    log(f"ship arm r={spacing:g} px -> {len(dots):,} dots "
        f"({100 * len(dots) / footprint.sum():.3f}% of the {footprint.sum():,}-px footprint)")

    # ---- audit against the official metric on the catalogue proxy -----------
    d_truth = np.asarray(ndimage.distance_transform_edt(~truth), dtype=np.float64)
    terms = window_terms(dots, truth, P.R_PIXELS, origin=(0, 0), d_truth_global=d_truth)
    ceiling = max_possible_index(len(dots), args.g_mass)

    out_all = DOCS / "downloads" / f"{tag}-allfinite.tif"
    out_nan = DOCS / "downloads" / f"{tag}-nan.tif"
    S.write_submission(dots, footprint, out_all, mode="allfinite")
    S.write_submission(dots, footprint, out_nan, mode="nan")
    a_all = S.audit(out_all, len(dots), footprint=footprint, mode="allfinite")
    a_nan = S.audit(out_nan, len(dots), footprint=footprint, mode="nan")
    for a in (a_all, a_nan):
        assert a["all_checks_passed"], a
        assert a["positives"] == len(dots), (a["positives"], len(dots))
    log(f"  allfinite {a_all['sha256'][:16]} {a_all['bytes']:,} B  "
        f"nan {a_nan['sha256'][:16]} {a_nan['bytes']:,} B")

    note = (f"GEMSDOE46 {tag} | split-conformal spacing r={spacing:g} px "
            f"({int(spacing * 100)} m minimum separation), certified floor "
            f"{table[spacing]['certified_floor']:.4f} at {100 * conf['confidence']:.1f}% confidence "
            f"(alpha={conf['alpha']:.4f}; n_cal={conf['n_calibration']} exchangeable spatial blocks; "
            f"Lei et al. 2018 split conformal) | {len(dots):,} dots | "
            f"declared |G|={int(args.g_mass)} px -> analytic ceiling {ceiling:.4f} | "
            f"DTI on the catalogue proxy {terms['DTI']:.4f} | "
            f"geology: multi-scale L2 curvature + official tilt-angle edge layer; "
            f"no feature uses distance to any known fault")

    ev = {"tag": tag, "spacing_px": spacing,
          "chosen_by": "pre-declared rules R3 (density admissibility) then R4 "
                       "(argmax certified split-conformal floor)",
          "candidate_arms": {str(s): {
              "measured_dots_full_footprint": measured[s],
              "sweep_extrapolated_dots_full_footprint": table[s]["median_dots_full_footprint"],
              "admissible_at_declared_G": s in admissible,
              "selection_mean": table[s]["selection_mean"],
              "calibration_mean": table[s]["calibration_mean"],
              "conformal_quantile": table[s]["conformal_quantile"],
              "certified_floor": table[s]["certified_floor"]} for s in spacings},
          "dots": int(len(dots)),
          "footprint_px": int(footprint.sum()),
          "footprint_fraction": float(len(dots) / footprint.sum()),
          "catalogue_proxy": terms,
          "declared_G_px": args.g_mass,
          "analytic_ceiling_at_declared_G": ceiling,
          "dots_allowed_for_target_at_declared_G": max_dots_r3,
          "prior_shift": shift,
          "conformal": {"alpha": conf["alpha"], "confidence": conf["confidence"],
                        "n_calibration": conf["n_calibration"],
                        "n_selection": conf["n_selection"],
                        "certified_floor": table[spacing]["certified_floor"],
                        "certified_floor_at_chosen": conf["pop_thin"]["certified_floor_at_chosen"],
                        "split_scheme": conf["split_scheme"],
                        "eligibility_rule": conf["eligibility_rule"],
                        "excluded_tiles": conf["excluded_tiles"]},
          "submission_note": note,
          "files": {"allfinite": a_all, "nan": a_nan}}
    (EVID / f"submission_{tag}.json").write_text(json.dumps(ev, indent=2))
    (DOCS / "downloads" / f"checks-{tag}-allfinite.json").write_text(json.dumps(a_all, indent=2))
    (DOCS / "downloads" / f"checks-{tag}-nan.json").write_text(json.dumps(a_nan, indent=2))
    (DOCS / "downloads" / f"NOTE-{tag}.txt").write_text(note + "\n")
    log("NOTE (paste into the DrivenData 'Note' field):")
    log("  " + note)


if __name__ == "__main__":
    main()
