#!/usr/bin/env python3
"""Regenerate the README status block from registry/r12.json.

AGENTS.md §4: numbers published by this project come from a script reading ``registry/*.json``,
never typed by hand.  The block between the BEGIN/END markers in README.md is machine-written;
CI re-runs this script and fails if the committed README drifts from the receipt.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- R12 STATUS:BEGIN -->"
END = "<!-- R12 STATUS:END -->"


def strat_table() -> str:
    st = json.loads((ROOT / "registry/r12.json").read_text())["stratified_instrument"]
    return "\n".join(
        f"| {k} | {st['scores'][k]['tp']:,.0f} | {st['scores'][k]['dti']:.5f} "
        f"| {100 * st['hit_fraction'][k]:.2f} % |"
        for k in sorted(st["scores"], key=lambda k: -st["scores"][k]["dti"]))


def block() -> str:
    R = json.loads((ROOT / "registry/r12.json").read_text())
    a, cfg = R["audit"], R["frozen_configuration"]
    means, pooled = R["mean_locked_dti"], R["pooled_locked_dti"]
    rob = R["robustness_all_locked_blocks"]["means"]
    best = R["best_comparator"]
    ci = R["paired_bootstrap_95"]
    cov = R["coverage"]
    gate = "cleared for a weekly submission slot" if R["gate_passed"] else "HOLD — do not submit"
    table = "\n".join(
        f"| {k} | {v:.5f} | {pooled[k]:.5f} | {rob[k]:.5f} |"
        for k, v in sorted(means.items(), key=lambda kv: -kv[1]))
    return f"""{BEGIN}
## Download the submission TIF

**[Download `{R["file"]}`](docs/r12/{R["file"]})**

**Status: {gate}** under the preregistered rule (R12 beat every comparator on locked spatial blocks
with a bootstrap interval excluding zero). It carries **no leaderboard score**: nothing in this
repository submits to the competition, and a proxy measurement is not a score forecast.

- [Executive summary / exact submission steps](https://buffedlizard55-lab.github.io/GEMSDOE46/docs/executive-summary.html)
- [Active site](https://buffedlizard55-lab.github.io/GEMSDOE46/) · [machine-readable receipt](docs/r12/receipt.json)
- [Scientific review and next steps](docs/research/r12-review.md)
- [Five hypotheses preregistered before implementation](docs/research/session-r12-plan.md)

**Submission name:** `GEMSDOE46-R12-SCARP-RAD-CONCORDANCE-{a["pixel_sha256"][:12].upper()}`
**Short note for the form:** `{R["note"]}`

### What was measured (locked blocks, never used for tuning)

| Field, re-emitted by the same rule | Mean DTI | Pooled DTI | All locked blocks, full budget |
|---|---:|---:|---:|
{table}

Paired difference vs the best comparator (`{best}`): **{R["paired_delta_vs_best"]:+.5f}**, seeded
block-bootstrap 95 % interval **[{ci[0]:+.5f}, {ci[1]:+.5f}]** over {len(R["locked_folds"])} evaluable
locked blocks; {len(R["locked_skipped"])} further locked blocks were dropped where a gapped comparator
could emit nothing, which is conservative for R12. Under R10's stricter rule (no dropped blocks
allowed) the gate reads **{"pass" if R["gate_strict_r10_style"] else "fail"}**; both readings are
published in the receipt.

### The instrument that reproduces the known live ordering (decisive check)

A sibling session's ladder showed the un-stratified off-catalogue SGMC proxy *inverts* the ordering of
the three live-scored family files, while truth stratified at ≥3 px from the catalogue reproduces it
(IR-46-21). R12 was therefore re-measured on that instrument, under a rule amended **before** the
measurement (`session-r12-plan.md` §7.1). Stratified truth {R["stratified_instrument"]["truth_px"]:,} px —
identical to the d0 = 5 px row of that ladder, so it is the same instrument.

| Field, re-emitted at the same mass | Covered truth T | DTI | Dots within 300 m |
|---|---:|---:|---:|
{strat_table()}

Δ vs the incumbent **{R["stratified_instrument"]["delta_vs_incumbent"]:+.5f}**
({R["stratified_instrument"]["scores"]["R12"]["dti"] / R["stratified_instrument"]["scores"]["GEMSDOE32-owner-reported-02778"]["dti"]:.2f}×),
uniform random at matched mass T = {R["stratified_instrument"]["uniform_random_at_matched_mass"]["tp"]:,.0f}.
Both preregistered readings agree, so the status is **{R["status"]}**. The same instrument puts the
incumbent at {R["stratified_instrument"]["scores"]["GEMSDOE32-owner-reported-02778"]["dti"]:.5f} where the
live board says 0.2778 — absolute proxy values are not scores and the ratio is not a promised multiplier.

These are **not leaderboard scores**. The instrument is the reused, imperfect off-catalogue USGS SGMC
proxy at matched emitted mass. The official board snapshot retrieved 2026-10-06 is **0.3774**
(xiaofanhu), not the 0.3195 quoted in the standing prompt — that is the #7 value on the same date.
File-to-score attribution for every historical score remains owner-reported.

### Redundancy check required by the standing prompt

| Compared with | Emitted-pixel / raw-field correlation | Jaccard | Smoothed-field Spearman |
|---|---:|---:|---:|
| GEMSDOE32 file (owner-reported 0.2778) | {R["comparisons"]["GEMSDOE32-owner-reported-02778"]["candidate_pearson"]["pearson"]:+.4f} | {R["comparisons"]["GEMSDOE32-owner-reported-02778"]["jaccard"]:.4f} | {R["comparisons"]["GEMSDOE32-owner-reported-02778"]["field_vs_smoothed_submission"]["spearman"]:+.4f} |
| R10 DFA crossover file | {R["comparisons"]["R10-DFA-crossover"]["candidate_pearson"]["pearson"]:+.4f} | {R["comparisons"]["R10-DFA-crossover"]["jaccard"]:.4f} | {R["comparisons"]["R10-DFA-crossover"]["field_vs_smoothed_submission"]["spearman"]:+.4f} |
| RTP magnetic gradient field (classic arm) | {R["comparisons"]["REF_rtp_gradient"]["field_raw"]["pearson"]:+.4f} | — | {R["comparisons"]["REF_rtp_gradient"]["field_smoothed"]["spearman"]:+.4f} |
| LiDAR morphology alone (own component) | {R["comparisons"]["PART_lidar_only"]["field_raw"]["pearson"]:+.4f} | — | {R["comparisons"]["PART_lidar_only"]["field_smoothed"]["spearman"]:+.4f} |

Emitted pixels are almost disjoint from both shipped files, so this is not a renamed prediction, and
the correlation with gradient/curvature evidence is low. The honest caveat: the *smoothed* field still
correlates {R["comparisons"]["GEMSDOE32-owner-reported-02778"]["field_vs_smoothed_submission"]["spearman"]:+.3f}
with the GEMSDOE32 file at coarse scales, so R12 is **not** spatially independent of the family's best
field (IR-46-18).

### Artefact audit (re-read from disk after writing)

Single band, float32, {a["crs"]}, {a["shape"][0]}×{a["shape"][1]}, 100 m, transform equal to the
template, every value finite and in [{a["min"]}, {a["max"]}], no nodata tag, {a["positive"]:,} positive
pixels, zero elsewhere. SHA-256 `{a["sha256"]}`. Frozen configuration: concordance weight
{cfg["w"]}, radiometric fallback quantile {cfg["fallback_quantile"]}, thinning {cfg["thin"]}.
LiDAR covers {cov["lidar_share_of_domain"]:.2%} of the emittable domain; the rest is carried by the
radiometric fallback. Portal acceptance has not been tested — no organiser receipt exists.

### What failed, and is published anyway

* A **strong** two-sensor concordance gate was falsified on the selection blocks (w = 1 scores below
  morphology alone); only a mild reweighting survived.
* **Ridge-axis thinning (H46-R12-B)** cost 0.010–0.029 DTI in all fifteen configurations tried.
* The previous session's **DFA crossover (R10)** remains `HOLD_DO_NOT_SUBMIT`; it is still downloadable
  in `docs/r10/` for audit.
{END}"""


def main() -> int:
    p = ROOT / "README.md"
    text = p.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit("README.md is missing the R12 STATUS markers")
    head, rest = text.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    p.write_text(head + block() + tail)
    print("README status block regenerated from registry/r12.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
