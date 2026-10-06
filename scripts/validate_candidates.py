#!/usr/bin/env python3
"""Validate the H46-1 candidate fields against the incumbent submissions and two instruments.

What this script can and cannot do is stated up front, because the honest answer changes how the
output should be read:

  * It CANNOT measure the competition score.  The private/public test labels (newly identified
    faults not in the USGS/INGENIOUS catalogue) are not available to this repository.
  * It CAN measure (a) distinctness of a candidate from the prior submissions and from the plain
    gradient/curvature transforms of the same bands, and (b) relative performance at matched
    emitted mass on two *proxy* truth sets: the held-out published catalogue (weak instrument: the
    group measured Spearman +0.09 against 11 official scores) and off-catalogue USGS SGMC fault
    traces (Spearman +0.31 on the same 11).

Outputs: registry/validation.json, data/derived/*.npy previews.
(registry/emission_model.json is owned by scripts/build_submission.py - the live-score calibration.)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import detector as D  # noqa: E402
from gems46 import emission as E  # noqa: E402
from gems46 import grid as G  # noqa: E402
from gems46 import holdout as H  # noqa: E402

DATA = ROOT / "data"
DERIVED = DATA / "derived"
REG = ROOT / "registry"
BUDGET_MATCH = 37654          # matched to the highest-scoring prior file (h33-2-b2)
MIN_DIST = 3
SMOOTH_PX = 1.85


def load_npz(path: Path) -> dict:
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def norm01(x: np.ndarray, valid: np.ndarray, hi_pct: float = 99.5) -> np.ndarray:
    v = x[valid & np.isfinite(x)]
    if v.size == 0:
        return np.zeros_like(x, dtype=np.float32)
    hi = float(np.percentile(v, hi_pct))
    out = np.clip(np.nan_to_num(x, nan=0.0) / max(hi, 1e-9), 0.0, 1.0)
    out[~valid] = 0.0
    return out.astype(np.float32)


def smooth_corr(a: np.ndarray, b: np.ndarray, mask: np.ndarray, sigma: float = 8.0) -> dict:
    """Pearson/Spearman between two fields, raw and after 800 m smoothing (spatial correlation)."""
    aa = ndimage.gaussian_filter(np.nan_to_num(a, nan=0.0) * mask, sigma, mode="constant")
    bb = ndimage.gaussian_filter(np.nan_to_num(b, nan=0.0) * mask, sigma, mode="constant")
    m = mask & (aa != 0) & (bb != 0)
    if m.sum() < 100:
        return dict(pearson_smoothed=None, spearman_smoothed=None, n=int(m.sum()))
    x, y = aa[m], bb[m]
    return dict(pearson_smoothed=float(pearsonr(x, y)[0]),
                spearman_smoothed=float(spearmanr(x, y, ).statistic) if hasattr(spearmanr(x, y), "statistic")
                else float(spearmanr(x, y)[0]), n=int(m.sum()))


def binary_overlap(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> dict:
    """Jaccard / precision / recall between two emitted masks inside the footprint."""
    A, B, M = a & mask, b & mask, mask
    inter = int((A & B).sum())
    union = int((A | B).sum())
    return dict(jaccard=float(inter / union) if union else None, intersection=inter,
                union=union, a_px=int(A.sum()), b_px=int(B.sum()),
                frac_of_a_inside_b=float(inter / max(int(A.sum()), 1)),
                frac_of_b_inside_a=float(inter / max(int(B.sum()), 1)))


def main() -> int:
    REG.mkdir(exist_ok=True)
    t_start = time.time()
    feat = DATA / "raw" / "training_features.tif"
    tmpl = DATA / "raw" / "sample_submission.tif"
    labels_p = DATA / "raw" / "labels.tif"
    fp = G.footprint(tmpl, feat)
    with rasterio.open(labels_p) as s:
        labels = s.read(1) > 0
    cat = labels & fp

    # ---- external proxy truth: off-catalogue USGS SGMC traces (restored mirror, pinned locally)
    sgmc_path = DATA / "external" / "sgmc_faults_100m_u8.tif"
    sgmc = None
    if sgmc_path.exists():
        with rasterio.open(sgmc_path) as s:
            a = s.read(1)
            sgmc = (a > 0)
        if sgmc.shape != fp.shape:
            raise SystemExit("SGMC raster shape mismatch")
    print(f"footprint {int(fp.sum())} px; catalogue {int(cat.sum())} px; "
          f"SGMC {int(sgmc.sum()) if sgmc is not None else 'n/a'} px")

    # ---- fields under test -------------------------------------------------------------------
    grp = load_npz(DERIVED / "dfa_groups.npz")
    bases = load_npz(DERIVED / "baselines.npz")
    fields: dict[str, np.ndarray] = {}
    for key in ("mag_abs", "grav_abs", "both_abs", "any_abs", "mag_bnd", "grav_bnd", "both_bnd",
                "any_bnd"):
        if key in grp:
            fields[f"H46-1:{key}"] = norm01(grp[key], fp)
    joint = norm01(np.sqrt(np.clip(grp["both_abs"], 0, None) * np.clip(grp["both_bnd"], 0, None)), fp)
    fields["H46-1:joint"] = joint
    for name in ("tmi", "rtp", "iso_grav_anom", "mag_anom"):
        key = f"dfa_{name}_resid"
        p = DERIVED / f"{key}.npz"
        if p.exists():
            f = load_npz(p)
            fields[f"H46-1res:{name}"] = norm01(f["absz"], fp)

    # ---- prior submissions (restored, owner-reported scores) ---------------------------------
    priors = {
        "prior:d2.8 (0.2600)": DATA / "derived" / "d28_02600.tif",
        "prior:h33-2-b2 (0.2778)": DATA / "derived" / "incumbent_02778.tif",
        "prior:h32d (unscored)": DATA / "derived" / "h32d.tif",
    }
    prior_fields, prior_masks = {}, {}
    for k, p in priors.items():
        if p.exists():
            with rasterio.open(p) as s:
                a = np.nan_to_num(s.read(1), nan=0.0)
            prior_masks[k] = a > 0
            prior_fields[k] = norm01(ndimage.gaussian_filter((a > 0).astype(np.float32), 1.5,
                                                             mode="constant"), fp)

    # ---- gradient/curvature baselines (the "already tried" family) ---------------------------
    base_fields = {k: norm01(v, fp) for k, v in bases.items()}

    # ---- instruments -------------------------------------------------------------------------
    blk, edges = H.blocks(fp.shape, 3, 3)
    instruments = []
    for b in range(9):
        truth, known, domain = H.instrument_cat(cat, fp, blk, b)
        if truth.sum() >= 200:
            instruments.append(dict(name=f"cat-block-{b}", block=b, truth=truth, known=known,
                                    domain=domain))
    if sgmc is not None:
        truth, known, domain = H.instrument_sgmc(sgmc, cat, fp, min_offcat_px=2)
        instruments.append(dict(name="sgmc-offcatalogue", block=None, truth=truth, known=known,
                                domain=domain))

    # ---- emission budget: fit the emission model on the group's 11 (score, size) records ------
    ledger = []
    ledger_path = ROOT / "registry" / "prior_results.csv"
    if ledger_path.exists():
        import csv

        with ledger_path.open() as fh:
            for row in csv.DictReader(fh):
                try:
                    ledger.append((float(row["official_score"]), int(row["emitted_px"]),
                                   row.get("provenance", "owner-reported")))
                except (KeyError, ValueError):
                    continue
    model = dict(n=len(ledger),
                 note="A single-credit fit DTI_i = c*N_i/(0.2*N_i + 0.8*G) over the whole ledger "
                      "DEGENERATES (the optimiser drives G to its lower bound and R^2 < 0): the "
                      "ledger mixes files of different field quality, so emitted mass and credit "
                      "per pixel are confounded and G is not identifiable this way. The identifying "
                      "information is inside one family, and that calibration lives in "
                      "registry/emission_model.json (built by scripts/build_submission.py from the "
                      "0.2600 and 0.2778 members). Provenance of the ledger: owner-reported scores.")
    if len(ledger) >= 4:
        sc = np.array([x[0] for x in ledger])
        n = np.array([x[1] for x in ledger], float)

        def resid(p):
            c, Gv = p
            return c * n / (0.2 * n + 0.8 * Gv) - sc

        from scipy.optimize import least_squares
        fit = least_squares(resid, x0=[0.09, 8000.0], bounds=([1e-4, 100.0], [1.0, 5e5]))
        c_hat, G_hat = float(fit.x[0]), float(fit.x[1])
        pred = c_hat * n / (0.2 * n + 0.8 * G_hat)
        model.update(dict(credit_per_px=c_hat, hidden_truth_px=G_hat,
                          rmse=float(np.sqrt(np.mean((pred - sc) ** 2))),
                          r2=float(1 - np.sum((pred - sc) ** 2) / np.sum((sc - sc.mean()) ** 2)),
                          observations=[dict(official=s, emitted_px=int(m), provenance=pv)
                                        for s, m, pv in ledger]))
    # NOTE: registry/emission_model.json is owned by scripts/build_submission.py (the live-score
    # calibration). This script must not overwrite it, so the degeneracy note stays in
    # registry/validation.json only.

    # ---- evaluate ----------------------------------------------------------------------------
    out = dict(ledger_fit_attempt=model, budget_matched=BUDGET_MATCH, min_dist=MIN_DIST,
               smooth_px=SMOOTH_PX, footprint_px=int(fp.sum()), catalogue_px=int(cat.sum()),
               sgmc_px=int(sgmc.sum()) if sgmc is not None else None,
               fields={}, distinctness={}, instruments={}, seconds=None)

    # reference emission from the incumbent field, mass-matched, for like-for-like comparison
    ref_emit = None
    for tag in ("prior:h33-2-b2 (0.2778)", "prior:d2.8 (0.2600)"):
        if tag in prior_fields:
            dom = fp & ~cat
            e, _ = E.greedy_emit(prior_fields[tag], dom, BUDGET_MATCH, min_dist=MIN_DIST,
                                 smooth_px=SMOOTH_PX)
            scores = {}
            for ins in instruments:
                r = H.evaluate(e, ins["truth"], ins["known"], fp)
                scores[ins["name"]] = dict(dti=r["dti"], tp=r["tp"], fp=r["fp"], fn=r["fn"],
                                           truth_px=r["truth_px"])
            out["instruments"][tag] = scores
            mean_dti = float(np.mean([v["dti"] for v in scores.values()]))
            out["fields"][tag] = dict(matched_emission_mean_dti=mean_dti, emitted_px=int(e.sum()))
            if ref_emit is None:
                ref_emit = e
            print(f"reference {tag}: matched-mass mean instrument DTI {mean_dti:.4f}")

    for name, field in fields.items():
        dom = fp & ~cat
        t0 = time.time()
        emit, trace = E.greedy_emit(field, dom, BUDGET_MATCH, min_dist=MIN_DIST,
                                    smooth_px=SMOOTH_PX)
        scores = {}
        for ins in instruments:
            r = H.evaluate(emit, ins["truth"], ins["known"], fp)
            scores[ins["name"]] = dict(dti=r["dti"], tp=r["tp"], fp=r["fp"], fn=r["fn"],
                                       truth_px=r["truth_px"])
        mean_dti = float(np.mean([v["dti"] for v in scores.values()]))
        entry = dict(matched_emission_mean_dti=mean_dti, emitted_px=int(emit.sum()),
                     seconds=round(time.time() - t0, 1),
                     instrument_detail=scores)
        if ref_emit is not None:
            entry["overlap_vs_incumbent"] = binary_overlap(emit, ref_emit, fp)
        out["fields"][name] = entry
        out["instruments"][name] = scores
        print(f"{name:24s} mean DTI {mean_dti:.4f}  ({time.time() - t0:.0f}s)")

    # ---- distinctness ------------------------------------------------------------------------
    for name, field in fields.items():
        dst = {"vs_prior": {}, "vs_gradient_curvature_baselines": {}}
        for k, pf in prior_fields.items():
            dst["vs_prior"][k] = smooth_corr(field, pf, fp)
            dst["vs_prior"][k].update(binary_overlap(field > 0.5, prior_masks[k], fp))
        for k, bf in base_fields.items():
            dst["vs_gradient_curvature_baselines"][k] = smooth_corr(field, bf, fp)
        out["distinctness"][name] = dst

    out["seconds"] = round(time.time() - t_start, 1)
    (REG / "validation.json").write_text(json.dumps(out, indent=1) + "\n")
    np.save(DERIVED / "candidate_joint.npy", fields.get("H46-1:joint"))
    print("wrote registry/validation.json in %.0fs" % (time.time() - t_start))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
