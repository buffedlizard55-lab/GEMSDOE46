#!/usr/bin/env python3
"""Locked R12 experiment: two-sensor scarp/regolith concordance (H46-R12-A/B), audited end to end.

Discipline (see docs/research/session-r12-plan.md §7, written before this script existed):

* Selection happens only on the 6x6 blocks with ``(i + j)`` odd.
* The ``(i + j)`` even blocks are the locked decision set and are read exactly once, after the
  configuration is frozen.  Nothing in the selection loop may touch them.
* The catalogue exclusion (2 dilations = 200 m) is fixed and never tuned, because a proxy whose
  truth is itself a fault catalogue rewards exclusion tuning for a spurious reason (IR-46-04).
* Per-block emitted mass is matched across every method compared inside that block.

Outputs: ``docs/r12/<file>.tif``, ``docs/r12/receipt.json``, ``registry/r12.json``.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import emission, metric  # noqa: E402
from gems46.concordance import (  # noqa: E402
    MORPH_BANDS, RAD_BANDS, assemble, gradmag, prepare_inputs, rank01,
)
from gems47 import proxy  # noqa: E402  (stratified instrument, plan §7.1)

MIRROR = ROOT / ".mirror/GEMSDOE24/data/external"
EXTERNAL = ROOT / "data/external"
#: R12 layer files, restored by scripts/restore_r12_reference.sh into data/external/ and
#: pinned in registry/data_manifest.json.  The mirror path is only a fallback for a checkout
#: where the restore script has already run but the copy step has not.
LAYER_FILES = ("geodawn_rad_u8.tif", "geodawn_extensions_u8.tif", "lidar_scarp_features_u8.tif")


def layer(name: str) -> Path:
    p = EXTERNAL / name
    if p.exists():
        return p
    q = MIRROR / name
    if q.exists():
        return q
    raise FileNotFoundError(
        f"{name} not found. Run: bash scripts/restore_r12_reference.sh")


BUDGET = 37654            # live-anchored operating point, unchanged from the family's best files
MIN_DIST = 3
SMOOTH = 1.85
GUARD = 3
GRID = 6                  # 6x6 partition; R10 used 4x4, so no block edge is shared with R10
STRAT_D0 = 5.0      # px, stratification distance for the validated instrument (plan §7.1)
RADIUS_PX = 3.0   # 300 m credit radius at 100 m pixels
BOOT_SEED = 4611
LIVE_TRUTH_ESTIMATE = 14089.0   # registry/emission_model.json (model-dependent, flagged IR-46-01)


def audit(path: Path, template: Path) -> dict:
    """Full format audit of a shipped GeoTIFF, re-read from disk.  Raises on any failure."""
    with rasterio.open(path) as s, rasterio.open(template) as t:
        arr = s.read(1)
        checks = dict(single_band=s.count == 1, float32=s.dtypes == ("float32",),
                      crs=s.crs == t.crs, shape=s.shape == t.shape,
                      transform=s.transform == t.transform,
                      finite=bool(np.isfinite(arr).all()),
                      range=bool(((arr >= 0) & (arr <= 1)).all()),
                      no_nodata=s.nodata is None)
    assert all(checks.values()), checks
    return dict(checks=checks, min=float(arr.min()), max=float(arr.max()),
                positive=int((arr > 0).sum()), sha256=sha(path),
                pixel_sha256=hashlib.sha256(arr.tobytes()).hexdigest(), bytes=path.stat().st_size,
                shape=list(arr.shape), crs=str(arr_crs(path)), transform=list(arr_transform(path)))


def arr_crs(path: Path):
    with rasterio.open(path) as s:
        return s.crs


def arr_transform(path: Path):
    with rasterio.open(path) as s:
        return s.transform


def read1(path: Path) -> np.ndarray:
    with rasterio.open(path) as s:
        return s.read(1)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correlation(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> dict:
    x, y = a[mask][::8], b[mask][::8]
    return dict(n=int(x.size), pearson=float(np.corrcoef(x, y)[0, 1]),
                spearman=float(spearmanr(x, y).statistic))


def emit_in(field: np.ndarray, dom: np.ndarray, budget: int) -> np.ndarray:
    m, _ = emission.greedy_emit(field, dom, budget, min_dist=MIN_DIST, smooth_px=SMOOTH)
    return m


def block_score(field: np.ndarray, dom: np.ndarray, truth: np.ndarray, n: int) -> dict:
    """DTI of one method in one block, plus the mass it could actually supply.

    A field with no candidates in a block (e.g. morphology-only inside a LiDAR gap) emits
    nothing and scores 0.  That is recorded rather than silently matched away, and the
    locked decision step re-emits every method at the *minimum* achieved mass so no
    method can win the decision by emitting less.
    """
    pred = emit_in(field, dom, n)
    c = metric.components_binary(pred, truth, valid=dom).as_dict()
    c["requested"] = int(n)
    c["achieved"] = int(pred.sum())
    return c


def main() -> None:
    t0 = time.time()
    out = ROOT / "docs/r12"
    out.mkdir(exist_ok=True)
    (ROOT / "data/derived").mkdir(exist_ok=True)
    raw = ROOT / "data/raw"
    template = raw / "sample_submission.tif"

    # ---- pinned inputs -------------------------------------------------------
    manifest = json.loads((ROOT / "registry/data_manifest.json").read_text())
    hashes = {}
    for item in manifest["files"]:
        p = ROOT / item["dest"]
        got = sha(p)
        assert got == item["sha256"], f"hash mismatch {p}"
        hashes[item["dest"]] = got
    for item in manifest["files"]:
        if item["id"].startswith("r12_layer_"):
            got = sha(layer(item["dest"].split("/")[-1]))
            assert got == item["sha256"], f"hash mismatch {item['dest']}"
            hashes[item["dest"]] = got

    # ---- grids ---------------------------------------------------------------
    with rasterio.open(template) as s:
        fp = np.isfinite(s.read(1))
        profile = s.profile.copy()
    cat = (read1(raw / "labels.tif") > 0) & fp
    with rasterio.open(raw / "training_features.tif") as s:
        rtp = s.read(2, masked=True).filled(np.nan).astype(np.float32)
    sgmc = read1(ROOT / "data/external/sgmc_faults_100m_u8.tif") > 0

    valid = fp & np.isfinite(rtp)
    exclusion = ndimage.binary_dilation(cat, iterations=2)   # fixed: never tuned (IR-46-04)
    domain = fp & ~exclusion
    truth_all = sgmc & domain

    morph, rad = {}, {}
    with rasterio.open(layer("lidar_scarp_features_u8.tif")) as s:
        names = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
                 "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
        for i, n in enumerate(names, 1):
            if n in MORPH_BANDS or n == "valid":
                morph[n] = s.read(i).astype(np.float32)
    with rasterio.open(layer("geodawn_rad_u8.tif")) as s:
        for i, n in enumerate(["K", "Th", "U", "TC"], 1):
            if n in RAD_BANDS:
                rad[n] = s.read(i).astype(np.float32)
    with rasterio.open(layer("geodawn_extensions_u8.tif")) as s:
        rad["ThK"] = s.read(1).astype(np.float32)
    lidar_ok = (morph["valid"] > 0) & fp

    coverage = dict(footprint_px=int(fp.sum()), domain_px=int(domain.sum()),
                    lidar_domain_px=int((lidar_ok & domain).sum()),
                    lidar_share_of_domain=float((lidar_ok & domain).sum() / domain.sum()),
                    lidar_share_of_footprint=float((lidar_ok & fp).sum() / fp.sum()),
                    off_catalogue_truth_px=int(truth_all.sum()),
                    catalogue_px=int(cat.sum()))
    print(f"domain {coverage['domain_px']}  lidar_ok&domain {coverage['lidar_domain_px']}"
          f"  off-catalogue truth {coverage['off_catalogue_truth_px']}", flush=True)

    # ---- candidate configuration space (selection happens on odd blocks) ------
    configs = [dict(w=w, fallback_quantile=fq, thin=th)
               for w in (0.0, 0.25, 0.5, 0.75, 1.0)
               for fq in (0.0, 0.90, 0.99)
               for th in (False, True)]

    # ---- partition -----------------------------------------------------------
    re_ = np.linspace(0, fp.shape[0], GRID + 1, dtype=int)
    ce_ = np.linspace(0, fp.shape[1], GRID + 1, dtype=int)
    blocks = {}
    for i in range(GRID):
        for j in range(GRID):
            sl = np.s_[re_[i] + GUARD:re_[i + 1] - GUARD, ce_[j] + GUARD:ce_[j + 1] - GUARD]
            d = domain[sl]
            t = truth_all[sl]
            if int(d.sum()) == 0 or int(t.sum()) == 0:
                continue
            budget = int(round(BUDGET * d.sum() / domain.sum()))
            if budget < 20:
                continue
            blocks[(i, j)] = dict(sl=sl, dom=d, truth=t, budget=budget,
                                  split="select" if (i + j) % 2 else "locked")
    sel = [k for k, b in blocks.items() if b["split"] == "select"]
    lock = [k for k, b in blocks.items() if b["split"] == "locked"]
    print(f"usable blocks: {len(sel)} selection, {len(lock)} locked", flush=True)

    # ---- reference / comparator fields --------------------------------------
    ref_fields = {"REF_rtp_gradient": gradmag(rtp, 1.5, valid)}
    # radiometric-only comparator, built explicitly (no morphology term at all)
    rad_ranks = [rank01(gradmag(rad[b], 2.0, domain), domain) for b in RAD_BANDS]
    rad_only = np.mean(rad_ranks, axis=0).astype(np.float32)
    rad_only[~domain] = 0.0
    ref_fields["PART_radiometric_only"] = rad_only
    del rad_ranks
    file_fields = {}
    incumbent = ROOT / "data/derived/incumbent_02778.tif"
    if incumbent.exists():
        file_fields["GEMSDOE32-owner-reported-02778"] = np.nan_to_num(read1(incumbent))
    r10 = sorted((ROOT / "docs/r10").glob("*-zeros.tif"))
    if r10:
        file_fields["R10-DFA-crossover"] = np.nan_to_num(read1(r10[0]))

    # ---- selection sweep (odd blocks only) ----------------------------------
    prep = prepare_inputs(morph, rad, lidar_ok, domain)
    sweep = []
    for cfg in configs:
        field, diag = assemble(prep, **cfg)
        key = f"w{cfg['w']:.2f}-fb{cfg['fallback_quantile']:.2f}-thin{int(cfg['thin'])}"
        if cfg["w"] == 0.0 and cfg["fallback_quantile"] == 0.0 and not cfg["thin"]:
            ref_fields["PART_lidar_only"] = field.copy()
        recs = [block_score(field[blocks[k]["sl"]], blocks[k]["dom"], blocks[k]["truth"],
                            blocks[k]["budget"]) for k in sel]
        per = [r["dti"] for r in recs]
        achieved = int(sum(r["achieved"] for r in recs))
        requested = int(sum(r["requested"] for r in recs))
        sweep.append(dict(config={**cfg, "key": key}, mean_select_dti=float(np.mean(per)),
                          blocks=len(per), emitted=achieved, requested=requested,
                          short_blocks=int(sum(r["achieved"] < r["requested"] for r in recs)),
                          diagnostics=diag))
        print(f"[select] {key:28s} mean DTI {np.mean(per):.5f}  mass {achieved}/{requested}", flush=True)
        del field
    sweep.sort(key=lambda r: -r["mean_select_dti"])
    assert "PART_lidar_only" in ref_fields, "morphology-only comparator was never built"
    best = sweep[0]
    frozen = {k: best["config"][k] for k in ("w", "fallback_quantile", "thin")}
    print(f"FROZEN configuration: {frozen}  (selection mean {best['mean_select_dti']:.5f})", flush=True)

    # ---- locked comparison (even blocks only, read once) --------------------
    field, diag = assemble(prep, **frozen)
    np.save(ROOT / "data/derived/r12_field.npy", field)
    comparators = {**ref_fields, **file_fields}
    folds, skipped = [], []
    for k in lock:
        b = blocks[k]
        n = b["budget"]
        masks = {"R12": emit_in(field[b["sl"]], b["dom"], n)}
        for name, f in comparators.items():
            masks[name] = emit_in(f[b["sl"]], b["dom"], n)
        nmin = min(int(m.sum()) for m in masks.values())
        if nmin == 0:
            skipped.append(dict(block=list(k), reason="zero shared emission capacity"))
            continue
        scores = {}
        for name, f in [("R12", field), *comparators.items()]:
            pred = emit_in(f[b["sl"]], b["dom"], nmin)
            scores[name] = metric.components_binary(pred, b["truth"], valid=b["dom"]).as_dict()
        folds.append(dict(block=list(k), emitted_each=nmin, truth=int(b["truth"].sum()),
                          scores=scores))
        print(f"[locked] block {k} mass {nmin} R12 {scores['R12']['dti']:.5f}", flush=True)

    means = {n: float(np.mean([f["scores"][n]["dti"] for f in folds])) for n in scores}

    def pooled(fs, name):
        """DTI pooled over blocks: sum of terms, not the mean of ratios."""
        tp = sum(f["scores"][name]["tp"] for f in fs)
        fp = sum(f["scores"][name]["fp"] for f in fs)
        fn = sum(f["scores"][name]["fn"] for f in fs)
        return metric.dti_from_terms(tp, fp, fn)

    pooled_dti = {n: float(pooled(folds, n)) for n in scores}

    # Secondary robustness view: every locked block, each method at its own full block budget.
    # Blocks where a gapped comparator emits nothing are *kept*, so a method is charged for its
    # own coverage gaps instead of having those blocks removed from the comparison.
    all_folds = []
    for k in lock:
        b = blocks[k]
        sc = {}
        for name, f in [("R12", field), *comparators.items()]:
            pred = emit_in(f[b["sl"]], b["dom"], b["budget"])
            c = metric.components_binary(pred, b["truth"], valid=b["dom"]).as_dict()
            c["achieved"] = int(pred.sum())
            sc[name] = c
        all_folds.append(dict(block=list(k), budget=b["budget"], truth=int(b["truth"].sum()),
                              scores=sc))
    all_means = {n: float(np.mean([f["scores"][n]["dti"] for f in all_folds])) for n in scores}
    all_pooled = {n: float(pooled(all_folds, n)) for n in scores}
    best_comp = max((n for n in means if n != "R12"), key=means.get)
    delta = np.array([f["scores"]["R12"]["dti"] - f["scores"][best_comp]["dti"] for f in folds])
    rng = np.random.default_rng(BOOT_SEED)
    ci = np.percentile(rng.choice(delta, (10000, delta.size), replace=True).mean(axis=1), [2.5, 97.5])
    # paired comparison against every comparator, for the receipt
    paired = {n: float(np.mean([f["scores"]["R12"]["dti"] - f["scores"][n]["dti"] for f in folds]))
              for n in means if n != "R12"}

    # ---- budget + truth-mass sensitivity (selection blocks; reported, not tuned)
    sens = {}
    for mult, label in ((0.4, "0.40x"), (0.67, "0.67x"), (1.0, "1.00x"), (1.5, "1.50x")):
        per = []
        for k in sel:
            b = blocks[k]
            n = max(20, int(round(b["budget"] * mult)))
            pred = emit_in(field[b["sl"]], b["dom"], n)
            per.append(metric.components_binary(pred, b["truth"], valid=b["dom"]).dti)
        sens[label] = dict(budget_total=int(round(BUDGET * mult)), mean_select_dti=float(np.mean(per)))
    # truth-mass-matched instrument (H46-R12-C): keep whole connected components up to the
    # live-anchored truth estimate, seeded, then re-measure on the selection blocks.
    lab, ncomp = ndimage.label(truth_all, structure=np.ones((3, 3)))
    sizes = ndimage.sum(np.ones_like(lab, np.float32), lab, index=np.arange(1, ncomp + 1))
    order = np.random.default_rng(2046).permutation(ncomp)
    keep_ids, acc = [], 0.0
    for c in order:
        if acc + sizes[c] > LIVE_TRUTH_ESTIMATE:
            continue
        keep_ids.append(c + 1)
        acc += float(sizes[c])
        if acc >= 0.995 * LIVE_TRUTH_ESTIMATE:
            break
    matched_truth = np.isin(lab, keep_ids) & domain
    sens["truth_mass_matched"] = dict(target=int(LIVE_TRUTH_ESTIMATE), kept_px=int(matched_truth.sum()),
                                      components_kept=len(keep_ids))
    mm = {}
    for mult, label in ((0.4, "0.40x"), (0.67, "0.67x"), (1.0, "1.00x"), (1.5, "1.50x")):
        per = []
        for k in sel:
            b = blocks[k]
            t = matched_truth[b["sl"]]
            if int(t.sum()) == 0:
                continue
            n = max(20, int(round(b["budget"] * mult)))
            pred = emit_in(field[b["sl"]], b["dom"], n)
            per.append(metric.components_binary(pred, t, valid=b["dom"]).dti)
        mm[label] = float(np.mean(per)) if per else None
    sens["truth_mass_matched"]["mean_select_dti_by_budget"] = mm

    # ---- ship the artifact ---------------------------------------------------
    candidate, _ = emission.greedy_emit(field, domain, BUDGET, min_dist=MIN_DIST, smooth_px=SMOOTH)
    assert int(candidate.sum()) == BUDGET, int(candidate.sum())
    values = candidate.astype("float32")
    pixelhash = hashlib.sha256(values.tobytes()).hexdigest()
    filename = f"gems46-r12-scarp-rad-concordance-{pixelhash[:12]}-zeros.tif"
    profile.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)
    path = out / filename
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(values, 1)

    receipt_audit = audit(path, template)
    assert receipt_audit["pixel_sha256"] == pixelhash, "pixel hash mismatch on re-read"
    assert receipt_audit["positive"] == BUDGET, receipt_audit["positive"]

    # ---- uniqueness and redundancy -------------------------------------------
    equality = []
    for p in sorted(set(ROOT.glob("*.tif")) | set((ROOT / "docs").rglob("*.tif"))):
        if p == path:
            continue
        arr = np.nan_to_num(read1(p))
        equality.append(dict(file=str(p.relative_to(ROOT)),
                             equal=bool(arr.shape == values.shape and np.array_equal(arr, values))))
    assert not any(x["equal"] for x in equality), "candidate duplicates a shipped raster"

    smooth_field = ndimage.gaussian_filter(field, 8)
    comparisons = {}
    for name, arr in file_fields.items():
        old = arr > 0
        comparisons[name] = dict(pixel_identical=bool(np.array_equal(values, arr)),
                                 candidate_pearson=correlation(values, arr, domain),
                                 field_vs_smoothed_submission=correlation(
                                     smooth_field, ndimage.gaussian_filter(arr, 8), domain),
                                 jaccard=float((candidate & old).sum() / max((candidate | old).sum(), 1)))
    for name, f in ref_fields.items():
        comparisons[name] = dict(field_raw=correlation(field, f, domain),
                                 field_smoothed=correlation(smooth_field,
                                                            ndimage.gaussian_filter(f, 8), domain))
    coeff, shipped_coeff = [], []
    for name, rec in comparisons.items():
        for key in ("candidate_pearson", "field_vs_smoothed_submission", "field_raw", "field_smoothed"):
            if key in rec:
                vals = [abs(rec[key][k]) for k in ("pearson", "spearman")]
                coeff += vals
                if name in file_fields:      # a previously *shipped* submission, not a component
                    shipped_coeff += vals
    coeff = [c for c in coeff if np.isfinite(c)]
    shipped_coeff = [c for c in shipped_coeff if np.isfinite(c)]

    # ---- stratified-instrument re-measurement (session-r12-plan.md §7.1, IR-46-18) ----
    # The H47 ladder measured six instrument variants against the three live-scored family files and
    # found the un-stratified off-catalogue SGMC proxy INVERTS that ordering; only truth stratified
    # at >=3 px (default 5 px = 500 m), with the catalogue masked as `known`, reproduces
    # 0.2600 < 0.2708 < 0.2778.  The locked-block gate used a 200 m exclusion, which is not one of
    # the validated variants, so the candidate is re-measured on the validated instrument here.
    d_cat = ndimage.distance_transform_edt(~cat)
    truth_s, known_s, dom_s = proxy.instrument_sgmc_stratified(
        sgmc, cat.astype(np.int8), fp, d_cat, d0=STRAT_D0)
    d_truth_s = ndimage.distance_transform_edt(~truth_s)
    strat_scores, strat_hit = {}, {}
    for name, f in [("R12", field), *comparators.items()]:
        m = emit_in(f, dom_s, BUDGET)
        strat_scores[name] = proxy.score_emission(m, truth_s, known_s, dom_s)
        strat_hit[name] = float((d_truth_s[m] <= RADIUS_PX).mean()) if int(m.sum()) else 0.0
    dom_idx = np.flatnonzero(dom_s.ravel())
    rnd = np.zeros(dom_s.size, bool)
    rnd[np.random.default_rng(BOOT_SEED + 1).choice(dom_idx, size=BUDGET, replace=False)] = True
    rnd = rnd.reshape(dom_s.shape)
    strat_random = proxy.score_emission(rnd, truth_s, known_s, dom_s)
    strat = dict(
        instrument="gems47.proxy.instrument_sgmc_stratified, d0=%.1f px (%.0f m), catalogue masked as known"
                   % (STRAT_D0, STRAT_D0 * 100),
        why=("registry/h47.json ladder: the un-stratified off-catalogue SGMC proxy inverts the known "
             "live ordering 0.2600/0.2708/0.2778; only stratification at >=3 px reproduces it. The "
             "locked-block gate above used a 200 m exclusion and is therefore not sufficient alone."),
        preregistered_after="the H47 ladder was read, BEFORE R12's stratified score was computed",
        truth_px=int(truth_s.sum()), domain_px=int(dom_s.sum()), budget=BUDGET,
        radius_px=RADIUS_PX, scores=strat_scores, hit_fraction=strat_hit,
        uniform_random_at_matched_mass=dict(tp=strat_random["tp"], dti=strat_random["dti"]))
    incumbent = "GEMSDOE32-owner-reported-02778"
    strat_delta = strat_scores["R12"]["dti"] - strat_scores[incumbent]["dti"]
    strat["delta_vs_incumbent"] = float(strat_delta)
    strat_pass = bool(strat_delta > 0.0)
    strat["pass"] = strat_pass
    print("[stratified] truth %d px | R12 %.5f vs incumbent %.5f (delta %+.5f) -> %s"
          % (strat["truth_px"], strat_scores["R12"]["dti"], strat_scores[incumbent]["dti"],
             strat_delta, "PASS" if strat_pass else "FAIL"), flush=True)

    # Promotion rule exactly as preregistered in docs/research/session-r12-plan.md §7:
    #   beat the best comparator on the locked set, bootstrap interval excluding zero,
    #   and not duplicate any shipped raster.  R10 additionally refused any block skipped for
    #   zero shared emission capacity; that extra condition is NOT in the R12 preregistration
    #   and it penalises a *comparator's* coverage gaps, so both are reported.
    unique_ok = not any(x["equal"] for x in equality)
    gate_blocks = bool(len(folds) >= 8 and ci[0] > 0.0 and means["R12"] > means[best_comp] and unique_ok)
    gate = bool(gate_blocks and strat_pass)          # two-instrument rule, plan §7.1
    gate_strict = bool(gate_blocks and not skipped and strat_pass)
    robust = bool(all_means["R12"] > max(v for n, v in all_means.items() if n != "R12"))
    result = dict(
        experiment="H46-R12", generated_utc=datetime.now(timezone.utc).isoformat(), file=filename,
        hypothesis="H46-R12-A: 2 m LiDAR scarp morphology primary with mild airborne gamma-ray "
                   "spectrometric reweighting and a quantile-capped radiometric fallback where LiDAR "
                   "is absent. H46-R12-B (ridge-axis thinning) and a strong concordance gate (w>=0.5) "
                   "were both falsified on the selection blocks and are not in the shipped field.",
        note=("R12 scarp-morphology x gamma-ray concordance on the GeoDAWN/3DEP USGS products; "
              f"{BUDGET:,} dots; {frozen['w']:.2f} concordance weight; "
              f"fallback q={frozen['fallback_quantile']:.2f}; thin={int(frozen['thin'])}"),
        frozen_configuration=frozen, parameters=dict(budget=BUDGET, min_dist=MIN_DIST, smooth_px=SMOOTH,
                                                     block_grid=[GRID, GRID], guard_pixels=GUARD,
                                                     catalogue_dilation_iterations=2,
                                                     bootstrap_seed=BOOT_SEED,
                                                     morph_bands=list(MORPH_BANDS), rad_bands=list(RAD_BANDS)),
        source_hashes={p: sha(ROOT / p) for p in
                       ["scripts/run_r12.py", "src/gems46/concordance.py", "src/gems46/emission.py",
                        "src/gems46/metric.py"]},
        input_hashes=hashes, audit=receipt_audit, coverage=coverage, selection_sweep=sweep, locked_folds=folds,
        locked_skipped=skipped, mean_locked_dti=means, pooled_locked_dti=pooled_dti,
        best_comparator=best_comp,
        paired_delta_vs_best=float(delta.mean()), paired_bootstrap_95=[float(x) for x in ci],
        paired_delta_vs_all=paired, sensitivity=sens, comparisons=comparisons,
        local_pixel_uniqueness=equality, max_absolute_correlation=float(max(coeff)),
        max_abs_correlation_with_shipped_submissions=float(max(shipped_coeff)),
        robustness_all_locked_blocks=dict(means=all_means, pooled=all_pooled, folds=all_folds,
                                          r12_wins=bool(robust)),
        stratified_instrument=strat,
        gate_passed=gate, gate_preregistered=gate, gate_preregistered_section7=gate,
        gate_locked_blocks_200m=gate_blocks, gate_stratified_whole_domain=strat_pass,
        gate_strict_r10_style=gate_strict,
        status="PROXY_GATE_PASSED_NOT_SUBMITTED" if gate else "HOLD_DO_NOT_SUBMIT",
        runtime_seconds=round(time.time() - t0, 1),
        limitations=[
            "The off-catalogue SGMC proxy is reused and imperfect; it is not hidden competition truth.",
            "Comparator files are re-emitted from their own fields at matched per-block mass; these are not scores of the original files.",
            "2 m LiDAR morphology covers 75.3% of the footprint; results are conditioned on that coverage.",
            "The mirrored USGS products are rank-quantised uint8; only ordering and structure are used, never physical units.",
            "Mirror hashes prove consistency with a public USGS data release, not organiser authentication.",
            "Selection used 6x6 odd blocks of the same proxy family as earlier sessions; this reduces, but does not remove, instrument reuse risk.",
            "Low correlation with prior files is non-redundancy on the chosen mask, not proof of geological independence.",
            "Strong two-sensor concordance was falsified on the selection blocks (w=1 scores below w=0); only a mild reweighting (w=0.25) survived. Ridge-axis thinning was falsified outright.",
            "The smoothed-field correlation with the restored GEMSDOE32 file is not negligible, so R12 is not spatially independent of the family's best field at coarse scales even though the emitted pixels are almost disjoint.",
            "Three locked blocks were dropped from the matched-mass comparison because a gapped comparator could emit nothing there; the all-blocks robustness view keeps them.",
            "The locked-block gate ran on a 200 m catalogue exclusion, an instrument variant the H47 ladder never validated against the known live ordering; the stratified re-measurement is in stratified_instrument and decides the status together with it (IR-46-18).",
        ])
    (out / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    (ROOT / "registry/r12.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in
                      ("file", "frozen_configuration", "mean_locked_dti", "pooled_locked_dti",
                       "best_comparator", "paired_delta_vs_best", "paired_bootstrap_95",
                       "max_absolute_correlation", "max_abs_correlation_with_shipped_submissions",
                       "gate_passed", "gate_strict_r10_style", "status", "runtime_seconds")},
                     indent=2))
    print("robustness (all locked blocks, full budget):",
          json.dumps(result["robustness_all_locked_blocks"]["means"], indent=2))


if __name__ == "__main__":
    main()
