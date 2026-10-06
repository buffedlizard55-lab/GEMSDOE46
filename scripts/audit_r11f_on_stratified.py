#!/usr/bin/env python3
"""Pass 3 audit: re-score the R11F candidate on the instrument that reproduces the live order.

The R11F gate (`scripts/run_r11f.py`) used the *un-stratified* off-catalogue SGMC truth.  The H47
session measured (`registry/h47.json -> ladder`) that this instrument INVERTS the three known live
orderings (0.2600 / 0.2708 / 0.2778) and that only the *stratified* version - truth = SGMC fault
pixels more than ``d0`` pixels from every published catalogue pixel, with the catalogue masked -
reproduces all three.  A gate pass on an instrument that inverts the live board is not evidence.

This script therefore re-asks the R11F question on the stratified instrument:

* incumbent file (37,654 dots, owner-reported live 0.2778)
* the shipped R11F candidate (44,090 dots)
* the R11F fused field re-emitted at the matched mass 37,654 with the same emitter as the shipment
* a uniform-random control at the same mass (the instrument's dynamic range reference)

and reports, per instrument (d0 = 3 px and d0 = 5 px): the published-metric DTI under the masking
rule, covered truth credit T, per-dot hit fraction, the ranking AUC of the R11F field over the
incumbent's own dots (the H47 test), and a spatially paired block t-statistic for R11F vs incumbent.

Not a score forecast: the stratified SGMC truth is a compilation 4x denser than the inferred hidden
truth and it is not the competition's label set.  See docs/research/r11f-review.md.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import evidence as EV  # noqa: E402
from gems46 import grid as G  # noqa: E402
from gems46 import metric as M  # noqa: E402
from gems46 import optemit  # noqa: E402
from gems47 import proxy as P  # noqa: E402
import rasterio  # noqa: E402

LABELS = ROOT / "data/raw/labels.tif"
TEMPLATE = ROOT / "data/raw/sample_submission.tif"
FEATURES = ROOT / "data/raw/training_features.tif"
SGMC = ROOT / "data/external/sgmc_faults_100m_u8.tif"
INCUMBENT = ROOT / "data/derived/incumbent_02778.tif"
R11F = ROOT / "docs/r11f/gems46-r11f-scarp-radiometric-fusion-00e049b51218-zeros.tif"
CACHE = ROOT / "data/derived/r11"
OUT = ROOT / "evidence/r11f-stratified-audit.json"
MASS_MATCHED = 37_654
MASS_SHIPPED = 44_090


def read_bool(path: Path) -> np.ndarray:
    with rasterio.open(path) as s:
        return s.read(1) > 0


def main() -> None:
    t0 = time.time()
    labels = read_bool(LABELS)
    fp = G.footprint(TEMPLATE, FEATURES)
    sgmc = read_bool(SGMC)
    d_cat = ndi.distance_transform_edt(~labels)

    incumbent = read_bool(INCUMBENT)
    shipped = read_bool(R11F)
    print(f"incumbent {incumbent.sum():,} dots | R11F shipped {shipped.sum():,} dots", flush=True)

    # Same field as the shipment, re-emitted at the matched mass.
    parts = [
        (np.load(CACHE / "lidar.npy"), 1.0),
        (np.load(CACHE / "topo.npy"), 0.8),
        (np.load(CACHE / "rad.npy"), 0.6),
        (np.load(CACHE / "pot.npy"), 0.3),
    ]
    fused = EV.fuse(parts, fp.shape)
    del parts

    rng = np.random.default_rng(4611)
    report: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "mass_matched": MASS_MATCHED, "mass_shipped": MASS_SHIPPED,
                    "instruments": {}}

    for d0 in (3.0, 5.0):
        truth, known, domain = P.instrument_sgmc_stratified(sgmc, labels, fp, d_cat, d0=d0)
        q = EV.to_probability(fused, domain, target_mass=10_000.0)
        res = optemit.emit(q, domain, budget=MASS_MATCHED, break_even_dti=None)
        reemitted = res.mask
        random_dots = np.zeros_like(domain)
        flat = np.flatnonzero(domain.ravel())
        pick = rng.choice(flat, size=MASS_MATCHED, replace=False)
        random_dots.ravel()[pick] = True
        del flat, pick

        emissions = {
            "incumbent-0.2778": incumbent,
            "r11-shipped-44090": shipped,
            "r11-fused-reemitted-37654": reemitted,
            f"uniform-random-{MASS_MATCHED}": random_dots,
        }

        ids = P.block_ids(fp.shape, 16, 16)
        truth_blocks = [int(b) for b in np.unique(ids[truth]) if b >= 0]
        rows = {}
        for name, emit in emissions.items():
            comp = M.components_binary(emit & domain, truth, valid=domain, known=known)
            d = comp.as_dict()
            dots = emit & domain
            cred = P.masked_credit_to_truth(dots, truth)
            hit = float((cred > 0).mean()) if dots.any() else 0.0
            rows[name] = {
                "dti": float(comp.dti),
                "T_credit": float(d.get("tp", cred.sum())),
                "emitted_px": int(dots.sum()),
                "hit_fraction": hit,
                "mean_credit_per_dot": float(cred.mean()) if dots.any() else 0.0,
            }
            print(f"  d0={d0} {name:28s} dti={rows[name]['dti']:.6f} "
                  f"T={rows[name]['T_credit']:9.2f} hit={hit:.3f}", flush=True)

        # H47 test: can the R11F field rank the incumbent's own dots?
        dots_idx = incumbent & domain
        truth_at_dots = truth[dots_idx]
        score_at_dots = q[dots_idx]
        n_pos = int(truth_at_dots.sum())
        if 0 < n_pos < truth_at_dots.size:
            auc = float(stats.mannwhitneyu(score_at_dots[truth_at_dots],
                                           score_at_dots[~truth_at_dots]).statistic
                        / (n_pos * (truth_at_dots.size - n_pos)))
        else:
            auc = None

        # paired block t for R11-reemitted and shipped vs the incumbent.
        paired = {}
        for name in ("r11-fused-reemitted-37654", "r11-shipped-44090"):
            deltas = []
            h, w = fp.shape
            er = np.linspace(0, h, 17).astype(int)
            ec = np.linspace(0, w, 17).astype(int)
            for b in truth_blocks:
                i, j = divmod(b, 16)
                sl = np.s_[er[i]:er[i + 1], ec[j]:ec[j + 1]]
                d_r = M.components_binary(emissions[name][sl] & domain[sl], truth[sl],
                                          valid=domain[sl], known=known[sl]).dti
                d_i = M.components_binary(incumbent[sl] & domain[sl], truth[sl],
                                          valid=domain[sl], known=known[sl]).dti
                deltas.append(d_r - d_i)
            t, p = stats.ttest_rel(np.array(deltas), np.zeros(len(deltas))) if len(deltas) > 1 else (0.0, 1.0)
            paired[name] = {"blocks": len(deltas), "mean_delta": float(np.mean(deltas)) if deltas else 0.0,
                            "t": float(t), "p": float(p)}
            print(f"  d0={d0} {name:28s} paired vs incumbent: "
                  f"mean {paired[name]['mean_delta']:+.6f} t={t:+.2f} ({len(deltas)} blocks)", flush=True)

        report["instruments"][f"sgmc_stratified_d0_{d0:g}"] = {
            "truth_px": int(truth.sum()), "domain_px": int(domain.sum()),
            "truth_blocks": len(truth_blocks), "emissions": rows,
            "auc_over_incumbent_dots": auc, "paired_vs_incumbent": paired,
        }
        del truth, known, domain, q, res, reemitted, random_dots
        del emissions, ids, truth_blocks, rows

    report["seconds"] = round(time.time() - t0, 1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} in {report['seconds']}s")


if __name__ == "__main__":
    main()
