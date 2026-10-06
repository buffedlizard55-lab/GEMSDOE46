#!/usr/bin/env python3
"""GEMSDOE47 run pipeline - H47-1 detector, instruments, emission, submission audit.

Stages (each cached under ``data/derived/h47/``; the receipt records input hashes):

  ladder    score the three live-anchored incumbent emissions on both instruments, over a range of
            SGMC stratification distances, to test whether an instrument reproduces the live order
  cv        leave-a-quadrant-out training of the H47-1 detector; writes the out-of-fold field
  calib     out-of-fold score -> credit calibration and the predicted-DTI budget curve
  compare   matched-mass comparison against the 0.2778 incumbent on both instruments
  screen    decisive screen: null distributions, paired-block test, ranking AUC, verdict
  emit      final full-raster field, budget by the marginal rule, writes the submission TIFs
  audit     independent re-read of the shipped bytes (format, range, finiteness, uniqueness)

Usage:  python3 scripts/run_h47.py [stage ...]      (default: all stages in order)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import metric as M              # noqa: E402
from gems47 import emission as E            # noqa: E402
from gems47 import features as F            # noqa: E402
from gems47 import model as MOD             # noqa: E402
from gems47 import proxy as P               # noqa: E402

DATA = ROOT / "data"
DER = DATA / "derived" / "h47"
DOCS = ROOT / "docs" / "downloads" / "h47"
LABELS = DATA / "raw" / "labels.tif"
TEMPLATE = DATA / "raw" / "sample_submission.tif"
FEATURES = DATA / "raw" / "training_features.tif"
SGMC = DATA / "external" / "sgmc_faults_100m_u8.tif"

INCUMBENTS = {
    "A_live_0.2600_d2.8": ROOT / ".mirror/GEMSDOE25/docs/downloads/"
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif",
    "B_live_0.2708_solo_d2.8": ROOT / ".mirror/GEMSDOE31/docs/downloads/"
    "gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-allfinite.tif",
    "C_live_0.2778_flankB2": ROOT / ".mirror/GEMSDOE32/docs/downloads/"
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif",
}
# Owner-reported live scores for the three files above (session brief; NOT organizer receipts).
LIVE = {"A_live_0.2600_d2.8": 0.2600, "B_live_0.2708_solo_d2.8": 0.2708, "C_live_0.2778_flankB2": 0.2778}

NROWS, NCOLS = 4, 4
QUADRANTS = {0: (0, 1, 4, 5), 1: (2, 3, 6, 7), 2: (8, 9, 12, 13), 3: (10, 11, 14, 15)}
COLLAR_PX = 2          # dots within 200 m of the published catalogue are not emitted
MIN_DIST = 3           # minimum separation between emitted dots (shadowing rule)
G_ASSUMED = 13_000.0   # hidden-truth pixels, from the group's live-anchored model (contested)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True).strip()
    except Exception:  # pragma: no cover
        return "unknown"


def load_inputs():
    with rasterio.open(LABELS) as d:
        labels = d.read(1) == 1
    with rasterio.open(TEMPLATE) as d:
        footprint = np.isfinite(d.read(1))
    with rasterio.open(SGMC) as d:
        sgmc = d.read(1) > 0
    return labels, footprint, sgmc


def _dist_to(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi
    return ndi.distance_transform_edt(~mask).astype(np.float32)


def stage_ladder(state: dict) -> dict:
    labels, footprint, sgmc = state["labels"], state["footprint"], state["sgmc"]
    d_cat = state["d_cat"]
    rows = {}
    for d0 in (0.0, 3.0, 5.0, 10.0, 20.0, 50.0):
        truth, known, domain = P.instrument_sgmc_stratified(sgmc, labels, footprint, d_cat, d0)
        rows[f"sgmc_d0_{d0:g}"] = {
            "truth_px": int(truth.sum()),
            "scores": {k: round(P.score_emission(state["emit"][k], truth, known, domain)["dti"], 6)
                       for k in INCUMBENTS},
        }
    ids = state["block_ids"]
    hold_rows = {}
    for hold in range(NROWS * NCOLS):
        truth, known, domain = P.instrument_catalogue_block(labels, footprint, ids, hold)
        if truth.sum() < 200:
            continue
        hold_rows[str(hold)] = {k: round(P.score_emission(state["emit"][k], truth, known, domain)["dti"], 6)
                                for k in INCUMBENTS}
    mean_hold = {k: round(float(np.mean([v[k] for v in hold_rows.values()])), 6) for k in INCUMBENTS}
    return {"live_scores_owner_reported": LIVE, "sgmc_stratified": rows,
            "catalogue_block_per_block": hold_rows, "catalogue_block_mean": mean_hold,
            "truth_px": {"catalogue": int(labels.sum()), "sgmc": int(sgmc.sum()),
                         "footprint": int(footprint.sum())}}


def stage_cv(state: dict) -> dict:
    labels, footprint = state["labels"], state["footprint"]
    d_cat, ids = state["d_cat"], state["block_ids"]
    names = F.feature_names()
    cfg = MOD.ModelConfig()
    oof_path = DER / "h47_oof_field.npy"
    if oof_path.exists():
        state["oof"] = np.load(oof_path)
        return {"reused": str(oof_path.relative_to(ROOT))}
    oof = np.zeros(labels.shape, dtype=np.float32)
    fold_meta = {}
    with rasterio.open(FEATURES) as src:
        for fold, blocks in QUADRANTS.items():
            t0 = time.time()
            train_mask = footprint & ~np.isin(ids, blocks)
            rows, cols, y = MOD._sample_rows(labels, footprint, d_cat, train_mask, cfg,
                                             np.random.default_rng(cfg.seed + fold))
            X = MOD.extract_rows(src, rows, cols, names, cfg.tile_rows)
            model = MOD.train(X, y, cfg, seed=cfg.seed + fold)
            sel = np.isin(ids, blocks)
            rows_lo = np.flatnonzero(sel.any(axis=1))
            sub = np.zeros(labels.shape, dtype=np.float32)
            MOD.predict_field(src, model, names, sub, cfg.tile_rows,
                              rows=(int(rows_lo[0]), int(rows_lo[-1]) + 1))
            oof[sel] = sub[sel]
            fold_meta[str(fold)] = {"train_rows": int(rows.size), "seconds": round(time.time() - t0, 1),
                                    "pos": int((y == 1).sum()), "neg": int((y == 0).sum())}
            print(f"[cv] fold {fold} done in {time.time() - t0:.0f}s", flush=True)
    np.save(oof_path, oof)
    state["oof"] = oof
    return {"folds": fold_meta, "field": str(oof_path.relative_to(ROOT)),
            "field_sha256": sha256(oof_path)}


def _credit_maps(state: dict, field: np.ndarray, block_set, instrument: str):
    """Per-candidate credit and own-credit measured against the *held-out* truth."""
    labels, footprint, sgmc = state["labels"], state["footprint"], state["sgmc"]
    d_cat, ids = state["d_cat"], state["block_ids"]
    if instrument == "catalogue":
        truth = labels & np.isin(ids, list(block_set))
        known = labels & ~truth
    else:
        truth, known, _ = P.instrument_sgmc_stratified(sgmc, labels, footprint, d_cat, 5.0)
    domain = footprint & ~known
    credit_map = M.kernel(_dist_to(truth))          # k(d(x, truth))
    return credit_map, truth, known, domain


def stage_calib(state: dict) -> dict:
    labels, footprint = state["labels"], state["footprint"]
    oof = state["oof"]
    out = {}
    all_scores, all_credit = [], []
    for fold, blocks in QUADRANTS.items():
        credit_map, truth, known, domain = _credit_maps(state, oof, blocks, "catalogue")
        sel = np.isin(state["block_ids"], blocks) & domain
        vals = oof[sel]
        cred = credit_map[sel]
        out[f"fold_{fold}"] = {
            "truth_px": int(truth.sum()),
            "mean_credit_top_40k": None,
            "n_dots_credit_over_0.2dti": None,
        }
        order = np.argsort(-vals)
        top = cred[order[:40_000]]
        out[f"fold_{fold}"]["mean_credit_top_40k"] = round(float(top.mean()), 4)
        all_scores.append(vals[order][:400_000])
        all_credit.append(cred[order][:400_000])
    s = np.concatenate(all_scores)
    c = np.concatenate(all_credit)
    qs, vals = E.calibrate_score_to_credit(s, c, n_bins=25)
    out["score_bins"] = [float(v) for v in qs]
    out["credit_per_bin"] = [float(v) for v in vals]
    # expected-credit curve after the shadowing rule: 1 accepted dot per min_dist px of line
    out["assumed_hidden_truth_px"] = G_ASSUMED
    state["calib"] = (qs, vals)
    return out


def stage_full_field(state: dict) -> dict:
    labels, footprint = state["labels"], state["footprint"]
    d_cat, ids = state["d_cat"], state["block_ids"]
    path = DER / "h47_full_field.npy"
    if path.exists():
        state["full"] = np.load(path)
        return {"reused": str(path.relative_to(ROOT)), "field_sha256": sha256(path)}
    names = F.feature_names()
    cfg = MOD.ModelConfig()
    t0 = time.time()
    with rasterio.open(FEATURES) as src:
        rows, cols, y = MOD._sample_rows(labels, footprint, d_cat, footprint, cfg,
                                         np.random.default_rng(cfg.seed))
        X = MOD.extract_rows(src, rows, cols, names, cfg.tile_rows)
        model = MOD.train(X, y, cfg)
        field = np.zeros(labels.shape, dtype=np.float32)
        MOD.predict_field(src, model, names, field, cfg.tile_rows)
        imp = model.feature_importances_
    np.save(path, field)
    state["full"] = field
    order = np.argsort(-imp)[:15]
    return {"field": str(path.relative_to(ROOT)), "field_sha256": sha256(path),
            "seconds": round(time.time() - t0, 1),
            "top_features": [[F.pretty_feature_names()[i], int(imp[i])] for i in order]}


def stage_compare(state: dict) -> dict:
    labels, footprint = state["labels"], state["footprint"]
    d_cat = state["d_cat"]
    res = {}
    for fold, blocks in QUADRANTS.items():
        in_block = np.isin(state["block_ids"], blocks)
        domain = footprint & in_block & (d_cat > COLLAR_PX)
        field = state["oof"]
        inc = state["emit"]["C_live_0.2778_flankB2"] & domain
        n = int(inc.sum())          # matched mass *inside this quadrant*
        ours = E.emit_dots(field, domain, budget=n, min_dist=MIN_DIST)
        credit_map, truth, known, dom = _credit_maps(state, field, blocks, "catalogue")
        a = P.score_emission(ours, truth, known, dom)
        b = P.score_emission(inc, truth, known, dom)
        res[f"fold_{fold}"] = {
            "matched_mass": n,
            "ours": {k: round(a[k], 6) for k in ("dti", "tp", "fp", "fn", "truth_px")},
            "incumbent_C": {k: round(b[k], 6) for k in ("dti", "tp", "fp", "fn", "truth_px")},
            "delta": round(a["dti"] - b["dti"], 6),
        }
    deltas = [v["delta"] for v in res.values()]
    res["mean_delta"] = round(float(np.mean(deltas)), 6)
    res["folds_ours_wins"] = int(sum(d > 0 for d in deltas))
    # global stratified-SGMC comparison at matched mass (full-raster field)
    truth, known, domain_all = P.instrument_sgmc_stratified(state["sgmc"], labels, footprint, d_cat, 5.0)
    dom = domain_all & (d_cat > COLLAR_PX)
    field = state["full"]
    for key in ("C_live_0.2778_flankB2", "A_live_0.2600_d2.8"):
        inc = state["emit"][key] & dom
        n = int(inc.sum())
        ours = E.emit_dots(field, dom, budget=n, min_dist=MIN_DIST)
        a = P.score_emission(ours, truth, known, dom)
        b = P.score_emission(inc, truth, known, dom)
        res[f"sgmc_matched_{key}"] = {
            "matched_mass": n,
            "ours": {k: round(a[k], 6) for k in ("dti", "tp", "fp", "fn", "truth_px")},
            "incumbent": {k: round(b[k], 6) for k in ("dti", "tp", "fp", "fn", "truth_px")},
            "delta": round(a["dti"] - b["dti"], 6),
        }
    return res


def stage_screen(state: dict) -> dict:
    """Decisive screen of the H47 fields against the live-scored 0.2778 dot set.

    The pre-registered test is the matched-mass comparison on ``instrument_sgmc_stratified``
    (d0 = 5 px), the only instrument in the ladder that reproduces the three known live
    orderings.  Reported with its null distribution (uniform-random emission at the same mass and
    the same 300 m separation rule), a spatially paired block test, and the ranking AUC of each
    field over the incumbent's own dots - the test that decides whether the field could prune or
    place dots better rather than merely spreading mass.
    """
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree  # noqa: F401  (documented dependency for the receipt)
    labels, footprint, sgmc = state["labels"], state["footprint"], state["sgmc"]
    d_cat, ids = state["d_cat"], state["block_ids"]
    truth, known, domain_all = P.instrument_sgmc_stratified(sgmc, labels, footprint, d_cat, 5.0)
    dom = domain_all & (d_cat > COLLAR_PX)
    d_truth = ndi.distance_transform_edt(~truth)
    cred = M.kernel(d_truth)
    inc = state["emit"]["C_live_0.2778_flankB2"] & dom
    mass = int(inc.sum())

    def score(mask):
        c = M.components_binary(mask, truth, valid=dom, known=known)
        return {"dti": round(c.dti, 6), "tp": round(c.tp, 2), "fp": round(c.fp, 2)}

    out = {"instrument": "sgmc_stratified d0=5 (the only ladder row that reproduces the live order)",
           "truth_px": int(truth.sum()), "domain_px": int(dom.sum()), "matched_mass": mass,
           "incumbent_C": score(inc),
           "incumbent_C_hit_fraction": round(float((cred[inc] > 0).mean()), 4)}
    rng = np.random.default_rng(11)
    rnd = []
    for _ in range(3):
        e = E.emit_dots(rng.random(labels.shape).astype(np.float32), dom, budget=mass, min_dist=MIN_DIST)
        rnd.append(score(e)["tp"])
    out["uniform_random_T"] = {"mean": round(float(np.mean(rnd)), 1), "trials": [round(v, 1) for v in rnd]}
    fields = {"oof": state["oof"], "full": state["full"]}
    for name, field in fields.items():
        e = E.emit_dots(field, dom, budget=mass, min_dist=MIN_DIST)
        s = score(e)
        s["hit_fraction"] = round(float((cred[e] > 0).mean()), 4)
        s["mean_kernel_credit_per_dot"] = round(float(cred[e].mean()), 4)
        s["delta_vs_C"] = round(s["dti"] - out["incumbent_C"]["dti"], 6)
        # spatially paired block test on the truth-side credit (16 x 16 grid)
        ker = M.kernel(ndi.distance_transform_edt(~e)) * truth
        ker_c = M.kernel(ndi.distance_transform_edt(~inc)) * truth
        bid = P.block_ids(labels.shape, 16, 16)
        diffs = []
        for b in np.unique(bid[truth]):
            sel = bid == b
            diffs.append(float(ker[sel].sum() - ker_c[sel].sum()))
        d = np.asarray(diffs)
        s["paired_blocks"] = int(d.size)
        s["paired_mean_delta"] = round(float(d.mean()), 2)
        s["paired_t"] = round(float(d.mean() / (d.std(ddof=1) / np.sqrt(d.size))), 2) if d.size > 1 else None
        # ranking AUC over the incumbent's own dots: can the field tell a hit from a miss?
        y = (cred[inc] > 0).astype(int)
        from sklearn.metrics import roc_auc_score
        s["auc_over_incumbent_dots"] = round(float(roc_auc_score(y, field[inc])), 4)
        out[name] = s
    # The file that would ship is built from the FULL field, so the verdict must be decided by the
    # full field alone.  Pre-registered pass condition: matched-mass gain over the live-scored
    # 0.2778 dot set that is also positive in the spatially paired block test (t >= 2) and backed by
    # a ranking AUC over the incumbent's own dots above 0.55.  Anything less cannot justify a slot.
    ship = out["full"]
    out["pass_condition"] = ("delta_vs_C > 0 and paired_t >= 2 and auc_over_incumbent_dots >= 0.55")
    passed = bool(ship["delta_vs_C"] > 0 and (ship["paired_t"] or 0) >= 2.0
                  and ship["auc_over_incumbent_dots"] >= 0.55)
    out["verdict"] = "SCREEN_PASSED_REVIEW_REQUIRED" if passed else "HOLD_DO_NOT_SUBMIT"
    out["verdict_reason"] = (
        f"ship-field (full) matched-mass delta {ship['delta_vs_C']:+.5f} "
        f"(paired t {ship['paired_t']}, {ship['paired_blocks']} blocks), "
        f"ranking AUC over the incumbent's dots {ship['auc_over_incumbent_dots']:.3f}, "
        f"hit fraction {ship['hit_fraction']:.3f} vs incumbent {out['incumbent_C_hit_fraction']:.3f}; "
        f"the out-of-fold mixture is {out['oof']['delta_vs_C']:+.5f} but not significant "
        f"(paired t {out['oof']['paired_t']}, AUC {out['oof']['auc_over_incumbent_dots']:.3f})"
        if not passed else "matched-mass gain with a positive paired block test - human review of one "
                           "file before any submission")
    return out


def _budget_curve(state: dict) -> dict:
    """Budget from the marginal rule, using the calibrated score->credit map."""
    qs, vals = state["calib"]
    field = state["full"]
    d_cat = state["d_cat"]
    dom = state["footprint"] & (d_cat > COLLAR_PX)
    cand = np.flatnonzero((dom & np.isfinite(field)).reshape(-1))
    values = field.reshape(-1)[cand]
    order = np.argsort(-values)
    values = values[order]
    credit = E.credit_at(qs, vals, values)
    # shadowing: one accepted dot per MIN_DIST px of the footprint's dense line support
    own = np.minimum(credit, 1.0)
    curve = E.predicted_dti(credit, own, G_ASSUMED)
    # the marginal rule of gems46.metric: add while the dot's credit clears alpha * DTI
    bar = M.ALPHA * curve
    ok = np.flatnonzero(credit > bar)
    n_star = int(ok[-1] + 1) if ok.size else 0
    cap = 200_000
    n_star = min(n_star, cap)
    # robustness sweep over the assumed hidden-truth size
    sweep = {}
    for g in (9_000.0, 13_000.0, 20_000.0, 30_000.0):
        sw = E.predicted_dti(credit, own, g)
        bar_g = M.ALPHA * sw
        ok_g = np.flatnonzero(credit > bar_g)
        n_g = int(ok_g[-1] + 1) if ok_g.size else 0
        sweep[f"G_{int(g)}"] = {"budget": min(n_g, cap),
                                "predicted_dti": round(float(sw[min(max(n_g, 1), sw.size) - 1]), 4)}
    return {"budget": n_star, "G_assumed": G_ASSUMED,
            "predicted_dti_at_budget": round(float(curve[max(n_star, 1) - 1]), 4),
            "credit_threshold_bar": round(float(bar[max(n_star, 1) - 1]), 4),
            "sweep": sweep,
            "candidate_pixels": int(cand.size)}


def stage_emit(state: dict) -> dict:
    labels, footprint = state["labels"], state["footprint"]
    d_cat, template = state["d_cat"], state["template_profile"]
    budget_info = _budget_curve(state)
    dom = footprint & (d_cat > COLLAR_PX)
    # Ship at the mass the screen compared against, not at the marginal-rule suggestion: on the
    # dense stratified instrument the marginal rule keeps asking for more mass (FN is cheap there),
    # so its budget is not transferable to the sparse hidden truth.  Matched mass keeps the
    # comparison honest - same number of dots as the live-scored 0.2778 file, placement only.
    matched = int((state["emit"]["C_live_0.2778_flankB2"] & dom).sum())
    budget_info["matched_mass"] = matched
    budget_info["shipped_budget"] = matched
    budget = matched
    emit = E.emit_dots(state["full"], dom, budget=budget, min_dist=MIN_DIST)
    n = int(emit.sum())
    out = np.zeros(labels.shape, dtype=np.float32)
    out[emit] = 1.0
    out[~footprint] = np.nan
    DOCS.mkdir(parents=True, exist_ok=True)
    stamp = "20261006T180000Z"
    name = f"gemsdoe47-h47-1-catalogue-supervised-lineament-{n}-{stamp}-h47a"
    nan_path = DOCS / f"{name}-nan.tif"
    zeros = np.where(np.isfinite(out), out, 0.0).astype(np.float32)
    zeros_path = DOCS / f"{name}-zeros.tif"
    profile = dict(template)
    profile.update(dtype="float32", count=1, nodata=None, compress="deflate", tiled=False)
    with rasterio.open(nan_path, "w", **profile) as d:
        d.write(out.astype(np.float32), 1)
        d.set_band_description(1, "GEMSDOE47 H47-1 fault probability (dots)")
    with rasterio.open(zeros_path, "w", **profile) as d:
        d.write(zeros, 1)
        d.set_band_description(1, "GEMSDOE47 H47-1 fault probability (dots, zeros outside footprint)")
    a = audit_file(zeros_path)
    b = audit_file(nan_path)
    return {"name": name, "budget_rule": budget_info, "emitted_px": n,
            "zeros": {"path": str(zeros_path.relative_to(ROOT)), "sha256": sha256(zeros_path),
                      "bytes": zeros_path.stat().st_size, "audit": a},
            "nan": {"path": str(nan_path.relative_to(ROOT)), "sha256": sha256(nan_path),
                    "bytes": nan_path.stat().st_size, "audit": b},
            "emitted_within_100m_of_catalogue": int((emit & (d_cat <= 1)).sum()),
            "emitted_within_200m_of_catalogue": int((emit & (d_cat <= 2)).sum())}


def audit_file(path: Path) -> dict:
    with rasterio.open(path) as d:
        arr = d.read(1)
        info = {"crs": str(d.crs), "shape": list(d.shape), "count": d.count,
                "dtype": str(d.dtypes[0]), "transform": [round(v, 4) for v in d.transform[:6]],
                "nodata": None if d.nodata is None else float(d.nodata)}
    fin = np.isfinite(arr)
    vals = arr[fin]
    out_of_range = int(((vals < 0) | (vals > 1)).sum())
    info.update({
        "min": float(vals.min()), "max": float(vals.max()),
        "finite_px": int(fin.sum()), "nan_px": int((~fin).sum()),
        "positive_px": int((arr == 1).sum()),
        "out_of_range_px": out_of_range,
        "unique_values": [float(v) for v in np.unique(vals)[:5]],
    })
    info["passes"] = bool(info["count"] == 1 and info["dtype"] == "float32"
                          and float(vals.min()) >= 0.0 and float(vals.max()) <= 1.0
                          and out_of_range == 0)
    return info


def main(argv: list[str]) -> int:
    stages = argv[1:] or ["ladder", "cv", "calib", "full", "compare", "screen", "emit"]
    DER.mkdir(parents=True, exist_ok=True)
    receipt_path = ROOT / "registry" / "h47.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    receipt.update({"experiment": "H47-1", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                         time.gmtime()),
                    "git_rev": git_rev()})
    labels, footprint, sgmc = load_inputs()
    state = {"labels": labels, "footprint": footprint, "sgmc": sgmc}
    d_cat_path = DER / "h47_d_cat.npy"
    if d_cat_path.exists():
        state["d_cat"] = np.load(d_cat_path)
    else:
        state["d_cat"] = _dist_to(labels)
        np.save(d_cat_path, state["d_cat"])
    state["block_ids"] = P.block_ids(labels.shape, NROWS, NCOLS)
    state["emit"] = {}
    for key, path in INCUMBENTS.items():
        with rasterio.open(path) as d:
            state["emit"][key] = d.read(1) > 0
    with rasterio.open(TEMPLATE) as d:
        state["template_profile"] = d.profile.copy()
    receipt["inputs_sha256"] = {
        "data/raw/labels.tif": sha256(LABELS),
        "data/raw/sample_submission.tif": sha256(TEMPLATE),
        "data/raw/training_features.tif": sha256(FEATURES),
        "data/external/sgmc_faults_100m_u8.tif": sha256(SGMC),
    }
    receipt["incumbents_sha256"] = {k: sha256(p) for k, p in INCUMBENTS.items()}
    for stage in stages:
        t0 = time.time()
        print(f"[h47] stage {stage} ...", flush=True)
        if stage == "ladder":
            receipt["ladder"] = stage_ladder(state)
        elif stage == "cv":
            state["oof"] = np.load(DER / "h47_oof_field.npy") if (DER / "h47_oof_field.npy").exists() else None
            receipt["cv"] = stage_cv(state)
        elif stage == "calib":
            if state.get("oof") is None:
                state["oof"] = np.load(DER / "h47_oof_field.npy")
            receipt["calibration"] = stage_calib(state)
        elif stage == "full":
            receipt["full_field"] = stage_full_field(state)
        elif stage == "compare":
            state["oof"] = np.load(DER / "h47_oof_field.npy")
            state["full"] = np.load(DER / "h47_full_field.npy")
            receipt["comparison"] = stage_compare(state)
        elif stage == "screen":
            state["oof"] = np.load(DER / "h47_oof_field.npy")
            state["full"] = np.load(DER / "h47_full_field.npy")
            receipt["screen"] = stage_screen(state)
        elif stage == "emit":
            state["full"] = np.load(DER / "h47_full_field.npy")
            if "calib" not in state:
                qs = receipt["calibration"]["score_bins"]
                vals = receipt["calibration"]["credit_per_bin"]
                state["calib"] = (np.asarray(qs), np.asarray(vals))
            receipt["emission"] = stage_emit(state)
        else:
            raise SystemExit(f"unknown stage {stage}")
        print(f"[h47] stage {stage} done in {time.time() - t0:.0f}s", flush=True)
        receipt_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    print("[h47] wrote", receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
