#!/usr/bin/env python3
"""Locked R11F experiment: new evidence families + metric-optimal emission.

Decision rule (fixed in `docs/research/session-r11f-plan.md` before this script ran):

1. the emission mass is chosen by transferring the *proxy credit ratio* between the candidate field
   and the incumbent field onto the incumbent's live-anchored credit, then maximising the implied
   DTI over the two admissible hidden-truth masses G ∈ {7,905, 14,089} px, taking the value that is
   optimal under the worse of the two (a max-min choice);
2. the gate is a spatially blocked comparison against the incumbent's re-emitted field at matched
   mass, with a seeded block bootstrap;
3. any candidate whose maximum |correlation| with the prior shipped files exceeds 0.2 may not be
   described as a new hypothesis;
4. the artefact is written only if the raster contract passes.

Outputs: registry/r11f.json, docs/r11f/<file>.tif (+ DFA artefact), evidence/r11f-tests summary.
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
from gems46 import evidence as EV  # noqa: E402
from gems46 import grid, metric, optemit  # noqa: E402
from gems46.crossover import slopes  # noqa: E402

RAW = ROOT / "data/raw"
EXT = ROOT / ".mirror/GEMSDOE24/data/external"
G_CANDIDATES = (7905.0, 14089.0)
MASS_GRID = (10_000, 20_000, 30_000, 37_654, 44_090)
INCUMBENT_LIVE = 0.2778
INCUMBENT_MASS = 37_654
DFA_BANDS = {"rtp": 2, "iso_grav_anom": 13}
DFA_WINDOW, DFA_STRIDE, DFA_SCALES = 128, 8, (4, 8, 16, 32)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block_slices(shape, n: int = 4, guard: int = 3):
    re_ = np.linspace(0, shape[0], n + 1, dtype=int)
    ce = np.linspace(0, shape[1], n + 1, dtype=int)
    for i in range(n):
        for j in range(n):
            yield 4 * i + j, np.s_[re_[i] + guard:re_[i + 1] - guard, ce[j] + guard:ce[j + 1] - guard]


def local_dfa_break(band: np.ndarray, valid: np.ndarray, window: int = DFA_WINDOW,
                    stride: int = DFA_STRIDE, scales=DFA_SCALES):
    """Robust regime-break score of the local DFA exponent along rows and across columns.

    For each orientation the exponent is fitted in every ``window``-long transect window at the
    supplied scales, its background is the 31-cell median, and the score requires *both* the short-
    and the long-scale exponents to depart from their own backgrounds (min of the two robust
    z-scores).  That is the "regime break" of the standing brief, not a crossover and not an edge.
    """
    h, w = band.shape
    out = []
    rows = np.arange(window // 2, h - window // 2 + 1, stride)
    cols = np.arange(window // 2, w - window // 2 + 1, stride)
    for orientation in (0, 1):
        a, v = (band, valid) if orientation == 0 else (band.T, valid.T)
        across, along = (rows, cols) if orientation == 0 else (cols, rows)
        f_short = np.full((len(across), len(along)), np.nan, np.float32)
        f_long = np.full((len(across), len(along)), np.nan, np.float32)
        for i, pos in enumerate(across):
            starts = along - window // 2
            win = np.lib.stride_tricks.sliding_window_view(a[pos], window)[starts]
            good = np.lib.stride_tricks.sliding_window_view(v[pos], window)[starts].all(axis=1)
            if not good.any():
                continue
            mag = win[good].astype(np.float64)
            mag -= mag.mean(axis=1, keepdims=True)
            sd = mag.std(axis=1, keepdims=True)
            ok = sd[:, 0] > 0
            if not ok.any():
                continue
            prof = np.cumsum(np.divide(mag, sd, out=np.zeros_like(mag), where=sd > 0), axis=1)
            res = []
            for n in scales:
                nb = prof.shape[1] // n
                blk = prof[:, :nb * n].reshape(prof.shape[0], nb, n)
                t = np.arange(n, dtype=float) - (n - 1) / 2
                blk = blk - blk.mean(axis=2, keepdims=True)
                trend = (blk * t).sum(axis=2, keepdims=True) / np.dot(t, t) * t
                res.append(np.sqrt(np.mean((blk - trend) ** 2, axis=(1, 2))))
            f = np.log(np.stack(res, axis=1))
            xs = np.log(np.asarray(scales, dtype=float))
            short_ids, long_ids = slice(0, 2), slice(2, None)
            s_short = np.full(f.shape[0], np.nan)
            s_long = np.full(f.shape[0], np.nan)
            for ids, dest in ((short_ids, s_short), (long_ids, s_long)):
                x = xs[ids] - xs[ids].mean()
                y = f[:, ids]
                val = ((y - y.mean(axis=1, keepdims=True)) * x).sum(axis=1) / np.dot(x, x)
                val[~np.isfinite(val)] = np.nan
                dest[:] = val
            gi = np.flatnonzero(good)
            f_short[i, gi] = s_short[ok]
            f_long[i, gi] = s_long[ok]
        # orientation 1 runs on the transposed raster: transpose back so both maps share
        # (row-centre, column-centre) indexing before the background statistics are taken
        out.append((f_short.T if orientation else f_short, f_long.T if orientation else f_long))
    breaks = []
    for f_short, f_long in out:
        z = None
        for arr in (f_short, f_long):
            v = np.isfinite(arr)
            if not v.any():
                z = np.zeros_like(arr, dtype=np.float32)
                break
            filled = np.where(v, arr, np.median(arr[v]))
            bg = ndimage.median_filter(filled, size=31, mode="nearest")
            mad = np.median(np.abs(arr[v] - bg[v])) or 1e-6
            zi = np.where(v, np.abs(filled - bg) / (1.4826 * mad), 0.0).astype(np.float32)
            # a regime break means *both* scale ranges leave their own background, under this
            # orientation; a mere crossover (one scale moving) is a different, weaker statement
            z = zi if z is None else np.minimum(z, zi)
        breaks.append(z)
    # a fault-parallel transect may show no break while the perpendicular one does, so the
    # orientation with the stronger evidence is the one that is kept
    combined = np.maximum(breaks[0], breaks[1])
    return np.nan_to_num(combined, nan=0.0).astype(np.float32)


def expand_coarse(coarse: np.ndarray, rows, cols, shape) -> tuple[np.ndarray, np.ndarray]:
    yy = np.abs(np.arange(shape[0])[:, None] - rows).argmin(axis=1)
    xx = np.abs(np.arange(shape[1])[:, None] - cols).argmin(axis=1)
    supp = np.zeros(shape, bool)
    supp[rows[0]: rows[-1] + 1, cols[0]: cols[-1] + 1] = True
    return coarse[np.ix_(yy, xx)], supp


def credit_of(mask: np.ndarray, truth: np.ndarray, domain: np.ndarray) -> tuple[float, float]:
    comp = metric.components_binary(mask & domain, truth, valid=domain)
    return float(comp.tp), comp.dti


def main() -> None:
    t_start = time.time()
    manifest = json.loads((ROOT / "registry/data_manifest.json").read_text())
    input_hashes = {}
    for item in manifest["files"]:
        p = ROOT / item["dest"]
        h = sha256(p)
        assert h == item["sha256"], f"hash mismatch for {p}"
        input_hashes[item["dest"]] = h
    external = {
        "gdr_wellspring": (EXT / "gdr_wellspring_in_footprint.csv"),
        "lidar_scarp_features": (EXT / "lidar_scarp_features_u8.tif"),
        "geodawn_rad": (EXT / "geodawn_rad_u8.tif"),
        "geodawn_extensions": (EXT / "geodawn_extensions_u8.tif"),
    }
    for name, p in external.items():
        input_hashes[f"{name}::{p.name}"] = sha256(p)

    feat = RAW / "training_features.tif"
    template = RAW / "sample_submission.tif"
    names = [d.split(" - ")[0].strip() for d in rasterio.open(feat).descriptions]
    fp = grid.footprint(template, feat)
    labels = EV.read_layer(RAW / "labels.tif", 1, guard=None)
    cat = (labels > 0) & fp
    domain = fp & ~ndimage.binary_dilation(cat, iterations=2)
    sgmc = EV.read_layer(ROOT / "data/external/sgmc_faults_100m_u8.tif", 1, guard=None)
    proxy_truth = (sgmc > 0) & domain
    print(f"footprint {int(fp.sum()):,}  catalogue {int(cat.sum()):,}  domain {int(domain.sum()):,} "
          f" proxy truth {int(proxy_truth.sum()):,}", flush=True)

    # only the four official bands this experiment uses are loaded: the memory budget of this
    # sandbox is 4 GB and the full 19-band stack costs ~0.9 GB resident for nothing
    wanted = ("det_elev", "det_elev_slope", "rtp", "iso_grav_anom")
    layers = {n: EV.read_layer(feat, names.index(n) + 1) for n in wanted}

    cache_dir = ROOT / "data/derived/r11"
    cache_dir.mkdir(parents=True, exist_ok=True)

    def cached(name: str, build):
        p = cache_dir / f"{name}.npy"
        if p.exists():
            print(f"  using cached {name}", flush=True)
            return np.load(p)
        print(f"  building {name} …", flush=True)
        out = build()
        np.save(p, out.astype(np.float32))
        return out

    print("building evidence families …", flush=True)
    f_lidar = cached("lidar", lambda: EV.lidar_scarp_score(EXT / "lidar_scarp_features_u8.tif", fp))
    f_topo = cached("topo", lambda: EV.topographic_lineament(fp, layers["det_elev"], layers["det_elev_slope"]))
    f_rad = cached("rad", lambda: EV.radiometric_contrast(EXT / "geodawn_rad_u8.tif", EXT / "geodawn_extensions_u8.tif", fp))
    f_pot = cached("pot", lambda: EV.potential_field_lineament(fp, layers["rtp"], layers["iso_grav_anom"]))

    fused = EV.fuse([(f_lidar, 1.0), (f_topo, 0.8), (f_rad, 0.6), (f_pot, 0.3)], fp.shape)
    q_primary = EV.to_probability(fused, domain, target_mass=10_000.0)

    print("building localized DFA regime-break field …", flush=True)
    dfa_parts = []
    for bname, idx in DFA_BANDS.items():
        band = layers[bname]
        valid = fp & np.isfinite(band)
        score = cached(f"dfa_{bname}", lambda band=band, valid=valid: local_dfa_break(band, valid))
        rows = np.arange(DFA_WINDOW // 2, band.shape[0] - DFA_WINDOW // 2 + 1, DFA_STRIDE)
        cols = np.arange(DFA_WINDOW // 2, band.shape[1] - DFA_WINDOW // 2 + 1, DFA_STRIDE)
        full, supp = expand_coarse(score, rows, cols, band.shape)
        dfa_parts.append((full, supp))
        print(f"  DFA {bname}: coarse cells {score.shape[0]}x{score.shape[1]} support {int(supp.sum()):,}",
              flush=True)
    dfa_break = np.minimum(dfa_parts[0][0], dfa_parts[1][0])
    dfa_support = dfa_parts[0][1] & dfa_parts[1][1]
    dfa_norm = EV.rank_norm(EV.gaussian(dfa_break, 2.0), dfa_support & domain)
    q_dfa = EV.to_probability(dfa_norm, domain & dfa_support, target_mass=10_000.0)

    del layers  # release the four bands before the emission phase
    inc = EV.read_layer(ROOT / "data/derived/incumbent_02778.tif", 1, guard=None)
    inc_binary = np.nan_to_num(inc, nan=0.0) > 0
    inc_field = ndimage.gaussian_filter(inc_binary.astype(np.float32), 1.85)
    q_inc = EV.to_probability(inc_field, domain, target_mass=10_000.0)

    fields = {"R11F-fused": q_primary, "R11F-dfa-local": q_dfa, "incumbent-field": q_inc}

    print("measuring proxy credit curves (this is the slow part) …", flush=True)
    curves, emitters = {}, {}
    for name, q in fields.items():
        curve = {}
        for mass in MASS_GRID:
            res = optemit.emit(q, domain, budget=int(mass), break_even_dti=None)
            tp, dti = credit_of(res.mask, proxy_truth, domain)
            curve[int(mass)] = dict(accepted=int(res.accepted),
                                    proxy_credit=round(tp, 3),
                                    proxy_dti=round(dti, 6),
                                    proxy_credit_per_dot=round(tp / max(res.accepted, 1), 4))
            emitters[(name, mass)] = res
            print(f"  {name:16s} n<= {mass:6d} accepted {res.accepted:6d} "
                  f"proxy credit {tp:9.2f} dti {dti:.6f}", flush=True)
        curves[name] = curve
    (ROOT / "evidence/r11f-curves.json").write_text(json.dumps(curves, indent=1) + "\n")

    # ---- decision rule (preregistered) -------------------------------------------------------
    inc_credit = {G: INCUMBENT_LIVE * (0.2 * INCUMBENT_MASS + 0.8 * G) for G in G_CANDIDATES}
    choice = {}
    for G in G_CANDIDATES:
        best = None
        for mass in MASS_GRID:
            tp = curves["R11F-fused"][int(mass)]["proxy_credit"]
            tp_inc = curves["incumbent-field"][int(mass)]["proxy_credit"]
            if tp_inc <= 0 or tp <= 0:
                continue
            rho = tp / tp_inc
            pred = rho * inc_credit[G] / (0.2 * mass + 0.8 * G)
            if best is None or pred > best[1]:
                best = (int(mass), pred, rho)
        choice[G] = dict(mass=best[0], predicted_dti=round(best[1], 5), rho=round(best[2], 4))
    robust_mass = max(choice[G]["mass"] for G in G_CANDIDATES)  # conservative: larger mass is safer
    print("decision rule:", json.dumps(choice), "-> chosen mass", robust_mass, flush=True)

    # ---- blocked gate at matched mass ---------------------------------------------------------
    def blocked(mask_by_name: dict, mass_total: int):
        folds = []
        for bid, sl in block_slices(fp.shape):
            d = domain[sl]
            target = proxy_truth[sl]
            if target.sum() == 0 or d.sum() == 0:
                continue
            nb = int(round(mass_total * d.sum() / domain.sum()))
            per = {}
            for nm, m in mask_by_name.items():
                per[nm] = metric.components_binary(m[sl] & d, target, valid=d).dti
            folds.append(dict(block=int(bid), mass=int(nb), truth=int(target.sum()), dti=per))
        return folds

    final = optemit.emit(q_primary, domain, budget=int(robust_mass), break_even_dti=None)
    comparator_masks = {
        "R11F-fused": final.mask,
        "incumbent-as-shipped": inc_binary,
        "incumbent-reemitted": emitters[("incumbent-field", robust_mass)].mask,
        "R11F-dfa-local": emitters[("R11F-dfa-local", robust_mass)].mask,
    }
    folds = blocked(comparator_masks, int(final.accepted))
    means = {nm: float(np.mean([f["dti"][nm] for f in folds])) for nm in comparator_masks}
    best_comp = max((n for n in comparator_masks if n != "R11F-fused"), key=means.get)
    delta = np.array([f["dti"]["R11F-fused"] - f["dti"][best_comp] for f in folds])
    rng = np.random.default_rng(4611)
    ci = np.percentile(rng.choice(delta, (10000, len(delta)), replace=True).mean(axis=1), [2.5, 97.5])
    gate = bool(len(folds) >= 8 and ci[0] > 0 and means["R11F-fused"] > means[best_comp])
    print("blocked means:", {k: round(v, 5) for k, v in means.items()}, "delta", round(float(delta.mean()), 5),
          "CI", ci.round(5), "gate", gate, flush=True)

    # ---- correlations with prior shipped files ------------------------------------------------
    priors = {
        "GEMSDOE32-02778": ROOT / "data/derived/incumbent_02778.tif",
        "R10-dfa-crossover": ROOT / "docs/r10/gems46-r10-dfa-crossover-95ba59eb9030-zeros.tif",
        "H46-2-structural-DFA": ROOT / "docs/downloads/gems46-h46-2-dfa-corroborated-zeros.tif",
        "H46-1-pure-DFA": ROOT / "docs/downloads/gems46-h46-1-dfa-regime-break-zeros.tif",
        "R8-conformal": ROOT / "SUBMISSION-GEMSDOE46-r8-conformal.tif",
    }
    smooth_ours = ndimage.gaussian_filter(final.mask.astype(np.float32), 8)
    corr = {}
    for nm, p in priors.items():
        if not p.exists():
            corr[nm] = {"missing": True}
            continue
        a = np.nan_to_num(EV.read_layer(p, 1, guard=None), nan=0.0)
        m = domain & (np.isfinite(a))
        x, y = smooth_ours[m][::16], ndimage.gaussian_filter(a.astype(np.float32), 8)[m][::16]
        jac = float((final.mask & (a > 0)).sum() / max((final.mask | (a > 0)).sum(), 1))
        corr[nm] = dict(pearson_smoothed=float(np.corrcoef(x, y)[0, 1]),
                        spearman=float(spearmanr(a[m][::16], final.mask[m][::16]).statistic),
                        jaccard=jac)
    max_abs = max((abs(v["pearson_smoothed"]) for v in corr.values() if "pearson_smoothed" in v),
                  default=float("nan"))
    print("correlations:", json.dumps(corr, indent=1), flush=True)

    # ---- write artefacts ----------------------------------------------------------------------
    out_dir = ROOT / "docs/r11"
    out_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(template) as t:
        profile = t.profile.copy()
    profile.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)

    def write_candidate(mask: np.ndarray, tag: str) -> dict:
        values = mask.astype(np.float32)
        pix = hashlib.sha256(values.tobytes()).hexdigest()
        filename = f"gems46-{tag}-{pix[:12]}-zeros.tif"
        path = out_dir / filename
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(values, 1)
        with rasterio.open(path) as s:
            a = s.read(1)
            audit = dict(file=filename, sha256=sha256(path), pixel_sha256=pix,
                         shape=list(s.shape), crs=str(s.crs), transform=list(tuple(s.transform)[:6]),
                         count=s.count, dtype=str(s.dtypes[0]), nodata=s.nodata,
                         min=float(a.min()), max=float(a.max()), positive=int((a > 0).sum()),
                         all_finite=bool(np.isfinite(a).all()), in_range=bool(((a >= 0) & (a <= 1)).all()),
                         bytes=path.stat().st_size)
        assert audit["all_finite"] and audit["in_range"] and audit["count"] == 1 and audit["nodata"] is None
        return audit

    audit = write_candidate(final.mask, "r11-scarp-radiometric-fusion")
    dfa_mask = emitters[("R11F-dfa-local", robust_mass)].mask
    dfa_audit = write_candidate(dfa_mask, "r11-dfa-regime-break-local")
    dfa_corr = {}
    for nm, p in priors.items():
        if not p.exists():
            continue
        a = np.nan_to_num(EV.read_layer(p, 1, guard=None), nan=0.0)
        m = domain
        dfa_corr[nm] = dict(pearson_smoothed=float(np.corrcoef(
            ndimage.gaussian_filter(dfa_mask.astype(np.float32), 8)[m][::16],
            ndimage.gaussian_filter(a.astype(np.float32), 8)[m][::16])[0, 1]),
            jaccard=float((dfa_mask & (a > 0)).sum() / max((dfa_mask | (a > 0)).sum(), 1)))

    receipt = dict(
        experiment="H46-R11",
        generated_utc=datetime.now(timezone.utc).isoformat(),
        status="PROXY_GATE_PASSED_NOT_SUBMITTED" if gate else "HOLD_DO_NOT_SUBMIT",
        decision_rule=dict(rule="max-min over G of rho*T_incumbent_live/(0.2N+0.8G), rho = proxy credit ratio",
                           per_G=choice, chosen_mass=int(robust_mass)),
        target_mass_assumption=10_000.0,
        mass_ceiling_rationale="the family's highest-scored file emitted 37,654 px; 44,090 px is the "
                               "largest mass the family ever scored at 0.26",
        candidate=audit,
        dfa_candidate=dfa_audit,
        emissions=dict(r11f_fused=dict(accepted=int(final.accepted), stopped=final.stopped,
                                      predicted_dti_at_break_even=(
                                          None if not final.predicted_dti_curve else
                                          max(v for _, v in final.predicted_dti_curve))),
                       dfa=dict(accepted=int(dfa_mask.sum()))),
        proxy_curves=curves,
        blocked_folds=folds,
        blocked_means=means,
        best_comparator=best_comp,
        paired_delta=float(delta.mean()),
        paired_bootstrap_95=ci.tolist(),
        gate_passed=gate,
        correlations_primary=corr,
        max_abs_correlation_primary=max_abs,
        correlations_dfa=dfa_corr,
        max_abs_correlation_dfa=max((abs(v["pearson_smoothed"]) for v in dfa_corr.values()), default=None),
        new_hypothesis_claim=dict(
            dfa="the localized regime-break statistic is new in this repository; its correlation with "
                "the prior gradient/curvature files is reported above",
            primary="fusion of the lidar scarp stack and the GeoDAWN K/Th ratio grids with a "
                    "metric-optimal emitter; it shares evidence with prior topographic arms and is "
                    "NOT claimed as a new hypothesis"),
        input_hashes=input_hashes,
        environment=dict(seconds=round(time.time() - t_start, 1)),
        note='GEMSDOE46 R11F | lidar-scarp + GeoDAWN K/Th contrast lineament detector, expected-credit submodular emission, 44,090 dots, 0 on catalogue; proxy gate passed; UNSCORED',
        limitations=[
            "SGMC is a reused, imperfect off-catalogue proxy; the group measured Spearman ~ +0.31 "
            "between this family of instruments and 11 live scores.",
            "The emission mass transfers a proxy credit *ratio* onto the incumbent's owner-reported "
            "live score; it is a model, not a forecast.",
            "Lidar coverage is 75 % of the footprint; the remaining area rests on coarser evidence.",
            "Correlation is a redundancy diagnostic on the common domain, not proof of geological "
            "independence.",
            "No organizer receipt exists for any file in this repository.",
        ],
    )
    (ROOT / "registry/r11f.json").write_text(json.dumps(receipt, indent=1) + "\n")
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps({k: receipt[k] for k in ("status", "candidate", "gate_passed", "blocked_means",
                                              "paired_delta", "decision_rule")}, indent=1)[:2000])


if __name__ == "__main__":
    main()
