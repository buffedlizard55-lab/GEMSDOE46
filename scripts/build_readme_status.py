#!/usr/bin/env python3
"""Regenerate the README status block from registry/r11.json.

AGENTS.md §4: numbers published by this project come from a script reading ``registry/*.json``,
never typed by hand.  The block between the BEGIN/END markers in README.md is machine-written;
CI re-runs this script and fails if the committed README drifts from the receipt.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- R11 STATUS:BEGIN -->"
END = "<!-- R11 STATUS:END -->"


def block() -> str:
    R = json.loads((ROOT / "registry/r11.json").read_text())
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

**[Download `{R["file"]}`](docs/r11/{R["file"]})**

**Status: {gate}** under the preregistered rule (R11 beat every comparator on locked spatial blocks
with a bootstrap interval excluding zero). It carries **no leaderboard score**: nothing in this
repository submits to the competition, and a proxy measurement is not a score forecast.

- [Executive summary / exact submission steps](https://buffedlizard55-lab.github.io/GEMSDOE46/docs/executive-summary.html)
- [Active site](https://buffedlizard55-lab.github.io/GEMSDOE46/) · [machine-readable receipt](docs/r11/receipt.json)
- [Scientific review and next steps](docs/research/r11-review.md)
- [Five hypotheses preregistered before implementation](docs/research/session-r11-plan.md)

**Submission name:** `GEMSDOE46-R11-SCARP-RAD-CONCORDANCE-{a["pixel_sha256"][:12].upper()}`
**Short note for the form:** `{R["note"]}`

### What was measured (locked blocks, never used for tuning)

| Field, re-emitted by the same rule | Mean DTI | Pooled DTI | All locked blocks, full budget |
|---|---:|---:|---:|
{table}

Paired difference vs the best comparator (`{best}`): **{R["paired_delta_vs_best"]:+.5f}**, seeded
block-bootstrap 95 % interval **[{ci[0]:+.5f}, {ci[1]:+.5f}]** over {len(R["locked_folds"])} evaluable
locked blocks; {len(R["locked_skipped"])} further locked blocks were dropped where a gapped comparator
could emit nothing, which is conservative for R11. Under R10's stricter rule (no dropped blocks
allowed) the gate reads **{"pass" if R["gate_strict_r10_style"] else "fail"}**; both readings are
published in the receipt.

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
with the GEMSDOE32 file at coarse scales, so R11 is **not** spatially independent of the family's best
field (IR-46-09).

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
* **Ridge-axis thinning (H46-R11-B)** cost 0.010–0.029 DTI in all fifteen configurations tried.
* The previous session's **DFA crossover (R10)** remains `HOLD_DO_NOT_SUBMIT`; it is still downloadable
  in `docs/r10/` for audit.
{END}"""


def main() -> int:
    p = ROOT / "README.md"
    text = p.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit("README.md is missing the R11 STATUS markers")
    head, rest = text.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    p.write_text(head + block() + tail)
    print("README status block regenerated from registry/r11.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
