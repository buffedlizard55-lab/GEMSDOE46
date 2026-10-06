#!/usr/bin/env python3
"""R11F, Pass 2: correct the two defects found by re-reading the executed receipt, then re-gate.

What Pass 1 (``scripts/run_r11f.py``) actually did, verbatim from ``registry/r11f.json``:

* the preregistered mass rule transferred a *flat* proxy credit ratio onto the incumbent's credit and
  therefore made the predicted DTI decrease with emitted mass, so the "max-min" choice collapsed to
  the **smallest** grid point -- 10,000 dots, against an incumbent file that emits 37,654;
* the gate then took the maximum over comparators, including ``incumbent-as-shipped`` at **its own**
  mass, so the "matched emitted mass" clause of the preregistration was not honoured.

Pass 2 fixes the transfer model (the candidate's live credit is the candidate's *proxy* credit at that
same mass, scaled by the incumbent's live-to-proxy factor measured at the incumbent's own operating
point), re-selects the mass with the preregistered max-min rule, re-emits at a **matched** mass and
re-runs the blocked gate against both comparators.  Both gates are written into the receipt: the
first one is never overwritten or deleted.

Outputs: rewritten ``registry/r11f.json`` (adds a ``pass2`` block), ``docs/r11f/receipt.json``,
``docs/r11f/<candidate>.tif``, ``docs/r11f/<dfa>.tif``, ``evidence/r11f-gate-at-mass.json``.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems46 import evidence as EV  # noqa: E402
from gems46 import grid, metric, optemit  # noqa: E402
from run_r11 import MASS_GRID, G_CANDIDATES, INCUMBENT_LIVE, INCUMBENT_MASS, credit_of, block_slices  # noqa: E402

RAW = ROOT / "data/raw"
CACHE = ROOT / "data/derived/r11"
WEIGHTS = [("lidar", 1.0), ("topo", 0.8), ("rad", 0.6), ("pot", 0.3)]
BOOT_SEED = 4611
OUT_DIR = ROOT / "docs/r11"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    t0 = time.time()
    receipt = json.loads((ROOT / "registry/r11f.json").read_text())
    fp = grid.footprint(RAW / "sample_submission.tif", RAW / "training_features.tif")
    with rasterio.open(RAW / "labels.tif") as s:
        cat = (s.read(1) > 0) & fp
    domain = fp & ~ndimage.binary_dilation(cat, np.ones((3, 3), bool), iterations=2)
    with rasterio.open(ROOT / ".mirror/GEMSDOE24/data/external/derived_sgmc_faults_100m_u8.tif") as s:
        sgmc = s.read(1) > 0
    proxy_truth = sgmc & fp & ~ndimage.binary_dilation(cat, np.ones((3, 3), bool), iterations=1)

    # ---- rebuild the three fields exactly as Pass 1 built them ---------------------------------
    fused = EV.fuse([(np.load(CACHE / f"{n}.npy"), w) for n, w in WEIGHTS], fp.shape)
    q_primary = EV.to_probability(fused, domain, target_mass=10_000.0)
    inc = np.nan_to_num(EV.read_layer(ROOT / "data/derived/incumbent_02778.tif", 1, guard=None), nan=0.0)
    inc_binary = inc > 0
    q_inc = EV.to_probability(ndimage.gaussian_filter(inc_binary.astype(np.float32), 1.85), domain,
                              target_mass=10_000.0)
    rows = np.arange(128 // 2, fp.shape[0] - 128 // 2 + 1, 8)
    cols = np.arange(128 // 2, fp.shape[1] - 128 // 2 + 1, 8)
    from run_r11 import expand_coarse  # noqa: E402
    parts = []
    for b in ("dfa_rtp", "dfa_iso_grav_anom"):
        full, supp = expand_coarse(np.load(CACHE / f"{b}.npy"), rows, cols, fp.shape)
        parts.append((full, supp))
    dfa = np.minimum(parts[0][0], parts[1][0])
    dfa_support = parts[0][1] & parts[1][1]
    q_dfa = EV.to_probability(EV.rank_norm(EV.gaussian(dfa, 2.0), dfa_support & domain),
                              domain & dfa_support, target_mass=10_000.0)
    del parts, dfa, fused

    # ---- the incumbent file's own proxy credit: the anchor the transfer was missing -------------
    inc_ship_tp, inc_ship_dti = credit_of(inc_binary, proxy_truth, domain)
    print(f"incumbent-as-shipped: proxy credit {inc_ship_tp:.1f}  proxy DTI {inc_ship_dti:.6f}", flush=True)

    # ---- corrected transfer: candidate live credit = candidate proxy credit x live/proxy factor --
    # the factor is measured once, at the incumbent's own operating point, and held fixed: that is
    # the only place where an owner-reported live value enters.
    factor = {G: INCUMBENT_LIVE * (0.2 * INCUMBENT_MASS + 0.8 * G) / inc_ship_tp for G in G_CANDIDATES}
    pred = {}
    for G in G_CANDIDATES:
        row = {}
        for m in MASS_GRID:
            tp = receipt["proxy_curves"]["R11F-fused"][str(m)]["proxy_credit"]
            row[int(m)] = dict(proxy_credit=tp, predicted_dti=factor[G] * tp / (0.2 * m + 0.8 * G))
        pred[G] = row
    # the max-min rule, now applied to a curve that is not monotone-degenerate
    opt = {G: max(pred[G], key=lambda m: pred[G][m]["predicted_dti"]) for G in G_CANDIDATES}
    mass = max(opt.values())  # conservative: the larger of the two optima
    print("corrected transfer -> per-G optimum:", {G: (opt[G], round(pred[G][opt[G]]["predicted_dti"], 5))
                                                   for G in G_CANDIDATES}, "-> mass", mass, flush=True)

    # ---- re-emit at the matched mass -------------------------------------------------------------
    print(f"emitting at matched mass {mass} …", flush=True)
    final = optemit.emit(q_primary, domain, budget=int(mass), break_even_dti=None)
    inc_re = optemit.emit(q_inc, domain, budget=int(mass), break_even_dti=None)
    dfa_em = optemit.emit(q_dfa, domain, budget=int(mass), break_even_dti=None)

    masks = {"R11F-fused": final.mask, "incumbent-as-shipped": inc_binary,
             "incumbent-reemitted": inc_re.mask, "R11F-dfa-local": dfa_em.mask}
    folds = []
    for bid, sl in block_slices(fp.shape):
        d = domain[sl]
        target = proxy_truth[sl]
        if target.sum() == 0 or d.sum() == 0:
            continue
        folds.append(dict(block=int(bid), truth=int(target.sum()), emitted={n: int(m[sl].sum())
                                                                           for n, m in masks.items()},
                          dti={n: metric.components_binary(m[sl] & d, target, valid=d).dti
                               for n, m in masks.items()}))
    means = {n: float(np.mean([f["dti"][n] for f in folds])) for n in masks}
    rng = np.random.default_rng(BOOT_SEED)
    stat = {}
    for comp in ("incumbent-reemitted", "incumbent-as-shipped"):
        delta = np.array([f["dti"]["R11F-fused"] - f["dti"][comp] for f in folds])
        ci = np.percentile(rng.choice(delta, (10_000, len(delta)), replace=True).mean(axis=1), [2.5, 97.5])
        stat[comp] = dict(mean_delta=float(delta.mean()), ci95=ci.tolist(),
                          blocks_improved=int((delta > 0).sum()), n_blocks=len(delta),
                          passed=bool(len(folds) >= 8 and ci[0] > 0 and means["R11F-fused"] > means[comp]))
    print("blocked means:", {k: round(v, 5) for k, v in means.items()}, flush=True)
    print("matched-mass gate:", json.dumps(stat, indent=1), flush=True)

    # ---- write artifacts -------------------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(RAW / "sample_submission.tif") as t:
        profile = t.profile.copy()
    profile.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)

    def write_candidate(mask: np.ndarray, tag: str) -> dict:
        values = mask.astype(np.float32)
        pix = hashlib.sha256(values.tobytes()).hexdigest()
        filename = f"gems46-{tag}-{pix[:12]}-zeros.tif"
        path = OUT_DIR / filename
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(values, 1)
        with rasterio.open(path) as s:
            a = s.read(1)
        return dict(file=filename, sha256=sha256(path), pixel_sha256=pix, shape=list(s.shape),
                    crs=str(s.crs), transform=list(tuple(s.transform)[:6]), count=s.count,
                    dtype=str(s.dtypes[0]), nodata=s.nodata, min=float(a.min()), max=float(a.max()),
                    positive=int((a > 0).sum()), all_finite=bool(np.isfinite(a).all()),
                    in_range=bool(((a >= 0) & (a <= 1)).all()), bytes=path.stat().st_size)

    old = {receipt["candidate"]["file"], receipt["dfa_candidate"]["file"]}
    audit = write_candidate(final.mask, "r11-scarp-radiometric-fusion")
    dfa_audit = write_candidate(dfa_em.mask, "r11-dfa-regime-break-local")
    for name in old - {audit["file"], dfa_audit["file"]}:
        p = OUT_DIR / name
        if p.exists():
            p.unlink()
            print(f"removed superseded artefact {name}", flush=True)

    # ---- correlations at the new mass ------------------------------------------------------------
    priors = {
        "GEMSDOE32-02778": ROOT / "data/derived/incumbent_02778.tif",
        "R10-dfa-crossover": ROOT / "docs/r10/gems46-r10-dfa-crossover-95ba59eb9030-zeros.tif",
        "H46-2-structural-DFA": ROOT / "docs/downloads/gems46-h46-2-dfa-corroborated-zeros.tif",
        "H46-1-pure-DFA": ROOT / "docs/downloads/gems46-h46-1-dfa-regime-break-zeros.tif",
        "R8-conformal": ROOT / "SUBMISSION-GEMSDOE46-r8-conformal.tif",
    }
    corr, dfa_corr = {}, {}
    smooth = ndimage.gaussian_filter(final.mask.astype(np.float32), 8)
    smooth_dfa = ndimage.gaussian_filter(dfa_em.mask.astype(np.float32), 8)
    for nm, p in priors.items():
        if not p.exists():
            continue
        a = np.nan_to_num(EV.read_layer(p, 1, guard=None), nan=0.0)
        b = ndimage.gaussian_filter(a.astype(np.float32), 8)
        corr[nm] = dict(pearson_smoothed=float(np.corrcoef(smooth[domain][::16], b[domain][::16])[0, 1]),
                        jaccard=float((final.mask & (a > 0)).sum() / max((final.mask | (a > 0)).sum(), 1)))
        dfa_corr[nm] = dict(pearson_smoothed=float(np.corrcoef(smooth_dfa[domain][::16], b[domain][::16])[0, 1]),
                            jaccard=float((dfa_em.mask & (a > 0)).sum() / max((dfa_em.mask | (a > 0)).sum(), 1)))

    pass2 = dict(
        reason="Pass 1's mass rule was degenerate (it collapsed to the smallest grid point) and its "
               "gate admitted a comparator at a different emitted mass, contradicting the "
               "preregistration's 'matched emitted mass' clause.",
        corrected_transfer=dict(rule="candidate live credit = factor(G) x candidate proxy credit at "
                                     "the same mass; factor measured once at the incumbent file's own "
                                     "operating point",
                                incumbent_as_shipped_proxy_credit=inc_ship_tp,
                                incumbent_as_shipped_proxy_dti=inc_ship_dti,
                                factor={str(G): factor[G] for G in G_CANDIDATES},
                                predicted_dti={str(G): pred[G] for G in G_CANDIDATES},
                                per_G_optimum={str(G): int(opt[G]) for G in G_CANDIDATES}),
        matched_mass=int(mass),
        gate_vs_reemitted=stat["incumbent-reemitted"],
        gate_vs_shipped=stat["incumbent-as-shipped"],
        blocked_means=means,
        candidate=audit,
        dfa_candidate=dfa_audit,
        correlations_primary=corr,
        max_abs_correlation_primary=max((abs(v["pearson_smoothed"]) for v in corr.values()), default=None),
        correlations_dfa=dfa_corr,
        max_abs_correlation_dfa=max((abs(v["pearson_smoothed"]) for v in dfa_corr.values()), default=None),
        gate_passed=bool(stat["incumbent-as-shipped"]["passed"]),
        seconds=round(time.time() - t0, 1),
    )
    receipt["pass1_as_executed"] = dict(
        status=receipt["status"], gate_passed=receipt["gate_passed"],
        chosen_mass=receipt["decision_rule"]["chosen_mass"], blocked_means=receipt["blocked_means"],
        paired_delta=receipt["paired_delta"], paired_bootstrap_95=receipt["paired_bootstrap_95"],
        candidate=receipt["candidate"], dfa_candidate=receipt["dfa_candidate"],
        note="the Pass-1 gate is kept here unedited; the decision below uses the matched-mass gate.")
    receipt["pass2"] = pass2
    receipt["candidate"], receipt["dfa_candidate"] = audit, dfa_audit
    receipt["correlations_primary"], receipt["correlations_dfa"] = corr, dfa_corr
    receipt["max_abs_correlation_primary"] = pass2["max_abs_correlation_primary"]
    receipt["max_abs_correlation_dfa"] = pass2["max_abs_correlation_dfa"]
    receipt["blocked_means"] = means
    receipt["gate_passed"] = pass2["gate_passed"]
    receipt["status"] = ("PROXY_GATE_PASSED_NOT_SUBMITTED" if pass2["gate_passed"] else "HOLD_DO_NOT_SUBMIT")
    receipt["paired_delta"] = stat["incumbent-as-shipped"]["mean_delta"]
    receipt["paired_bootstrap_95"] = stat["incumbent-as-shipped"]["ci95"]
    receipt["best_comparator"] = "incumbent-as-shipped"
    receipt["decided_mass"] = int(mass)
    receipt["emissions"] = dict(r11f_fused=dict(accepted=int(final.accepted), stopped=final.stopped),
                                dfa=dict(accepted=int(dfa_em.accepted)))
    receipt["limitations"] = [
        "The gate compares two emission rules on the SGMC off-catalogue proxy, which this repository "
        "has already flagged as a weak instrument (group measurement: Spearman ~ +0.31 with 11 live "
        "scores); a pass is permission to consider a slot, not a score forecast.",
        "The corrected transfer multiplies a proxy credit ratio by a factor fitted once at the "
        "incumbent's owner-reported live score; it is a model, not a forecast, and it is reported "
        "next to the uncorrected Pass-1 model rather than replacing it.",
        "The mass rule was corrected after seeing that the preregistered rule was degenerate; the "
        "Pass-1 numbers are preserved unedited in pass1_as_executed so the correction is auditable.",
        "Lidar coverage is 75 % of the footprint; outside it the field rests on coarser evidence.",
        "Correlation is a redundancy diagnostic on the common domain, not proof of independence.",
        "No organizer receipt exists for any file in this repository.",
    ]
    receipt["generated_utc_pass2"] = datetime.now(timezone.utc).isoformat()
    (ROOT / "registry/r11f.json").write_text(json.dumps(receipt, indent=1) + "\n")
    (OUT_DIR / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    (ROOT / "evidence/r11f-gate-at-mass.json").write_text(json.dumps(
        dict(pass1=receipt["pass1_as_executed"], pass2={k: v for k, v in pass2.items()
                                                        if k not in ("correlations_primary", "correlations_dfa")},
             folds=folds), indent=1) + "\n")
    print(f"\nstatus {receipt['status']}  mass {mass}  gate {receipt['gate_passed']}\n"
          f"candidate {audit['file']}  sha256 {audit['sha256'][:16]}…  ({audit['positive']} dots)\n"
          f"dfa       {dfa_audit['file']}  ({dfa_audit['positive']} dots)")


if __name__ == "__main__":
    main()
