# GEMSDOE46 — auditable fault-discovery experiments

<!-- R12 STATUS:BEGIN -->
## Download the submission TIF

**[Download `gems46-r12-scarp-rad-concordance-23e807e2de9f-zeros.tif`](docs/r12/gems46-r12-scarp-rad-concordance-23e807e2de9f-zeros.tif)**

**Status: cleared for a weekly submission slot** under the preregistered rule (R12 beat every comparator on locked spatial blocks
with a bootstrap interval excluding zero). It carries **no leaderboard score**: nothing in this
repository submits to the competition, and a proxy measurement is not a score forecast.

- [Executive summary / exact submission steps](https://buffedlizard55-lab.github.io/GEMSDOE46/docs/executive-summary.html)
- [Active site](https://buffedlizard55-lab.github.io/GEMSDOE46/) · [machine-readable receipt](docs/r12/receipt.json)
- [Scientific review and next steps](docs/research/r12-review.md)
- [Five hypotheses preregistered before implementation](docs/research/session-r12-plan.md)

**Submission name:** `GEMSDOE46-R12-SCARP-RAD-CONCORDANCE-23E807E2DE9F`
**Short note for the form:** `R12 scarp-morphology x gamma-ray concordance on the GeoDAWN/3DEP USGS products; 37,654 dots; 0.25 concordance weight; fallback q=0.90; thin=0`

### What was measured (locked blocks, never used for tuning)

| Field, re-emitted by the same rule | Mean DTI | Pooled DTI | All locked blocks, full budget |
|---|---:|---:|---:|
| R12 | 0.10420 | 0.13912 | 0.15586 |
| PART_lidar_only | 0.09368 | 0.12467 | 0.12413 |
| PART_radiometric_only | 0.07309 | 0.09611 | 0.10775 |
| GEMSDOE32-owner-reported-02778 | 0.06781 | 0.08870 | 0.09967 |
| R10-DFA-crossover | 0.05294 | 0.07777 | 0.04072 |
| REF_rtp_gradient | 0.05228 | 0.06926 | 0.08732 |

Paired difference vs the best comparator (`PART_lidar_only`): **+0.01052**, seeded
block-bootstrap 95 % interval **[+0.00140, +0.02121]** over 10 evaluable
locked blocks; 3 further locked blocks were dropped where a gapped comparator
could emit nothing, which is conservative for R12. Under R10's stricter rule (no dropped blocks
allowed) the gate reads **fail**; both readings are
published in the receipt.

### The instrument that reproduces the known live ordering (decisive check)

A sibling session's ladder showed the un-stratified off-catalogue SGMC proxy *inverts* the ordering of
the three live-scored family files, while truth stratified at ≥3 px from the catalogue reproduces it
(IR-46-18). R12 was therefore re-measured on that instrument, under a rule amended **before** the
measurement (`session-r12-plan.md` §7.1). Stratified truth 56,822 px —
identical to the d0 = 5 px row of that ladder, so it is the same instrument.

| Field, re-emitted at the same mass | Covered truth T | DTI | Dots within 300 m |
|---|---:|---:|---:|
| R12 | 9,003 | 0.16622 | 16.42 % |
| PART_lidar_only | 8,386 | 0.15506 | 15.80 % |
| PART_radiometric_only | 5,170 | 0.09638 | 10.52 % |
| GEMSDOE32-owner-reported-02778 | 5,081 | 0.09474 | 10.50 % |
| REF_rtp_gradient | 4,022 | 0.07519 | 8.32 % |
| R10-DFA-crossover | 3,628 | 0.06787 | 6.88 % |

Δ vs the incumbent **+0.07148**
(1.75×),
uniform random at matched mass T = 3,695.
Both preregistered readings agree, so the status is **PROXY_GATE_PASSED_NOT_SUBMITTED**. The same instrument puts the
incumbent at 0.09474 where the
live board says 0.2778 — absolute proxy values are not scores and the ratio is not a promised multiplier.

These are **not leaderboard scores**. The instrument is the reused, imperfect off-catalogue USGS SGMC
proxy at matched emitted mass. The official board snapshot retrieved 2026-10-06 is **0.3774**
(xiaofanhu), not the 0.3195 quoted in the standing prompt — that is the #7 value on the same date.
File-to-score attribution for every historical score remains owner-reported.

### Redundancy check required by the standing prompt

| Compared with | Emitted-pixel / raw-field correlation | Jaccard | Smoothed-field Spearman |
|---|---:|---:|---:|
| GEMSDOE32 file (owner-reported 0.2778) | +0.0054 | 0.0051 | +0.5325 |
| R10 DFA crossover file | +0.0004 | 0.0037 | -0.1018 |
| RTP magnetic gradient field (classic arm) | +0.1150 | — | +0.2448 |
| LiDAR morphology alone (own component) | +0.7350 | — | +0.7130 |

Emitted pixels are almost disjoint from both shipped files, so this is not a renamed prediction, and
the correlation with gradient/curvature evidence is low. The honest caveat: the *smoothed* field still
correlates +0.532
with the GEMSDOE32 file at coarse scales, so R12 is **not** spatially independent of the family's best
field (IR-46-15).

### Artefact audit (re-read from disk after writing)

Single band, float32, EPSG:32611, 3730×3292, 100 m, transform equal to the
template, every value finite and in [0.0, 1.0], no nodata tag, 37,654 positive
pixels, zero elsewhere. SHA-256 `73fd1d8340e32d0175ca7ddb084c50f561a04a2b6bd58f80426d7934cef157c7`. Frozen configuration: concordance weight
0.25, radiometric fallback quantile 0.9, thinning False.
LiDAR covers 75.13% of the emittable domain; the rest is carried by the
radiometric fallback. Portal acceptance has not been tested — no organiser receipt exists.

### What failed, and is published anyway

* A **strong** two-sensor concordance gate was falsified on the selection blocks (w = 1 scores below
  morphology alone); only a mild reweighting survived.
* **Ridge-axis thinning (H46-R12-B)** cost 0.010–0.029 DTI in all fifteen configurations tried.
* The previous session's **DFA crossover (R10)** remains `HOLD_DO_NOT_SUBMIT`; it is still downloadable
  in `docs/r10/` for audit.
<!-- R12 STATUS:END -->

## Reproduce on CPU

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/restore_competition_data.sh     # organiser rasters + SGMC proxy, hash-verified
bash scripts/restore_r10_reference.sh        # GEMSDOE32 / R10 comparator files, hash-verified
bash scripts/restore_r12_reference.sh        # USGS GeoDAWN gamma-ray + LiDAR layers, hash-verified
.venv/bin/python scripts/run_h47.py            # H47 ladder, cv, calibration, screen, emission
.venv/bin/python scripts/screen_r12_layers.py   # R12 exploratory layer screen
.venv/bin/python scripts/run_r12.py             # R12 locked experiment + audited GeoTIFF
.venv/bin/python scripts/build_readme_status.py # this status block
.venv/bin/python scripts/build_r12_site.py      # active site + executive summary
.venv/bin/python -m pytest
.venv/bin/python scripts/verify_all.py
```

Inputs are hash-pinned public mirrors; the pins prove mirror consistency, not organiser
authentication. Raw rasters and derived arrays stay git-ignored. `lightgbm` and `scikit-learn` are
pinned in `requirements.txt` (the sklearn wrapper of LightGBM needs it; both are CPU-only). The site
serves precomputed audited files — no scientific computation happens in a browser. No authenticated
organiser access and no private labels are available, so this pipeline can prepare and validate a file
but cannot submit one. The leaderboard snapshot is dated and linked, never presented as a live feed.

**Instrument discipline (from the H47 ladder, `registry/h47.json`):** the catalogue-in-block holdout
and the un-stratified SGMC truth both *invert* the known live ordering; only SGMC truth stratified at
≥3 px from the catalogue reproduces 0.2600 < 0.2708 < 0.2778. Any gate decision must state which
instrument produced it.

`scripts/build_site.py --legacy-h46` regenerates the archived H46 pages. It used to need
`data/derived/dfa_stats.json` (produced by `scripts/build_dfa_field.py`, git-ignored) and therefore
crashed in a clean checkout; that table is now optional, so the archive rebuilds everywhere.

## Corrections, limitations and priorities

Fixed in the R12 session, with tests: the rank transform returned an arbitrary tie-broken ramp for a
constant channel (`tests/test_concordance.py`); a block-slicing bug passed a whole-grid field to a
block domain; the promotion gate silently inherited R10's stricter "no dropped blocks" condition,
which is not in the R12 preregistration, so both readings are reported; and `build_site.py
--legacy-h46` crashed on a git-ignored derived file so the archived sources/irregularities pages could
not be regenerated. One claim written early in that session — that two builders were writing the same
live pages — was **false**, and it is recorded together with its retraction as IR-46-17.

**Instrument conflict found while merging (IR-46-18, measured and closed).** R12's gate used a 200 m
catalogue exclusion (66,277 truth px), which is not one of the variants the H47 ladder showed to
preserve the live ordering. R12 was re-measured on the stratified instrument (d0 = 5 px, catalogue
masked as `known`) under a rule amended *before* the measurement: R12 DTI **0.16622** / hit rate
**16.42 %** against the incumbent's **0.09474** / **10.50 %** (Δ +0.07148), with uniform random at
matched mass at DTI 0.06912. Both readings are in `registry/r12.json` and the promotion rule now
requires both. The absolute proxy value is still not a score — the same instrument scores the
incumbent 0.09474 where the live board says 0.2778.

Earlier corrections stand: the former README treated model-dependent hidden-label counts as measured
facts, called low Pearson correlation proof of physical independence, and guaranteed a scoring route
that had not been demonstrated; those claims are withdrawn. The legacy DFA half-window index bug and
the empty-prediction boundary bug in the binary metric are fixed and regression-tested. The exact
denominator is `0.2(T+S−M)+0.8G`; replacing it with `0.2S+0.8G` requires `M=T`. The H47 session fixed
a `KeyError` in the artifact audit and two test-side errors. The
[archived README](docs/research/readme-pre-r10.md) is preserved for audit, not recommendations.

Next, in order: (1) **settle the instrument** — re-measure R12 on the stratified proxy and downgrade it
to HOLD if it does not clear the same threshold there; (2) obtain one organiser receipt by submitting
the best surviving candidate, recording score + file hash + note together; (3) improve the radiometric
fallback, which carries 24.87 % of the emittable domain at a locked DTI of 0.073; (4) one measured
dead-dot rule (the field-based one is already ruled out at AUC 0.497); (5) test strike-continuity gap
closure (H46-R12-D) with the unused LiDAR `strike`/`coh100` bands. Never re-tune R12 on the blocks that
decided it, and do not spend a slot on an unscreened file.

## Core values

**Maximize P(Win):** the two parts of the hypothesis that failed are published next to the part that
worked, the stricter gate is reported beside the preregistered one, and a slot is recommended only
because a rule written in advance was met. **Own the Outcome:** our own defects are fixed in the open
with tests, receipts are preserved, negative results are labelled negative, and hypothesis is never
reported as evidence.

## Standing operating prompt — read at every session

The consolidated brief below preserves the project's requirements and supplied historical score ledger. Historical targets and hypotheses are not current facts. `PROMPT.md`, `registry/irregularities.json` and the R10 receipt govern interpretation.

<details>
<summary>Expand the project prompt and history</summary>

# The operating prompt for this project

> **Read this file at the start of every session.** It is the standing brief for GEMSDOE46. It is
> consolidated here (not a verbatim transcript) so that the objective, the constraints and
> the evidence rules cannot drift between sessions. Then read [`README.md`](README.md) for the current
> state, [`registry/hypotheses.json`](registry/hypotheses.json) for what is already tried, and
> [`registry/irregularities.json`](registry/irregularities.json) before repeating any claim.

---

## 1. The mission

We need to create a project that can compete and place top of the leaderboard in the DrivenData
competition **The Geologic Enhanced Mapping System (GEMS) Prize Challenge**
(<https://www.drivendata.org/competitions/306/competition-doe-gems/>). We need to understand the
problem, collect all the data and organise it into a clean, easily auditable table with official
verified links for manual verification.

- Get familiar with the problem through the overview and problem description
  (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>). Additional
  resources are on the about page
  (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/>).
- Download the data from the data tab
  (<https://www.drivendata.org/competitions/306/competition-doe-gems/data/>).
- Create and train your own model. The reference solution
  (<https://github.com/drivendataorg/gems-prize-reference-solution>) implements a simple approach.
- Use your model to generate predictions that match the submission format.
- Tell me what your limitations are and what you need access to during this project. We will need to
  find free publicly available sources and data from official and verified sources if we are to use
  third-party or external data.
- The submission rules are also outlined in the competition PDF
  (<https://docs.nlr.gov/docs/fy26osti/96647.pdf>).

**The goal of this project is to place top of the leaderboard.** We need to do our own research, deep
research and scientific literature research, and organise that knowledge so we can think critically
about the problem and generate a solution from scientific and free publicly available information.
This must be done autonomously and must be constantly reviewed and improved upon.

## 2. Hard constraints on the work

- Work line by line, verifying from official, trusted sources, and provide links for manual review.
- There should be no manual input: work on your own to complete the tasks.
- **Flag any irregularities for review. No hallucinations. Verify no hallucinations.**
- The goal of this project is to get a full list that follows our requirements. No hallucinations.
  Verify line by line. Run the task through multiple passes (implement and verify; review for bugs,
  missing requirements, incorrect assumptions and edge cases; re-check the whole implementation
  against the request).
- Store all information and knowledge gathered from official verified sources. This will serve as a
  starting point for other projects as well.
- Think outside the box but stay grounded in proper scientific research: we are ultimately aiming for
  a top prize that many others are competing for, so it is important to be contrarian but smart.
- Find sources of data that others overlook, and areas of the project connected to geothermal vents.
  Do deep research and critical thinking, and come up with new hypotheses to test.

## 3. Submission requirements (highest urgency, must be followed)

- **MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.** Do not copy a previous submission
  except for learning and education, but we must generate a unique TIF submission. The submission
  must be different from the collection of GEMSDOE sites listed below.
- There must be an easy-to-download submission TIF file as described by the prompt. Read the entire
  prompt.
- The site must be able to generate a TIF file that is required for submission. It should be as easy
  as: download, click, submit. This needs to be in the executive summary or the very beginning of the
  site, and it should be obvious when you visit the site.
- A previous download produced the submission-form error **"Predicted values must be in range
  [0, 1]"**, so range compliance has to be verified, not assumed.
- Each submission needs a unique name and a short note to tell submissions apart later
  (e.g. "clustering with k=25").
- The submission form reads: *"You can submit a single-band GeoTIFF (.tif) file, or a .zip file
  containing a single GeoTIFF, with your predictions. It must match the submission format's CRS,
  shape, and geotransform. You may wish to review the competition rules first."*
- Create an executive-summary subpage that explains exactly how to make a submission into the
  contest.

## 4. The specific hypothesis requested for GEMSDOE46

Test for a breakdown in long-range scaling behaviour along the magnetic and gravity grids, not just a
local edge or amplitude feature. This is a different kind of signal than anything tried so far:
Peng and colleagues' detrended fluctuation analysis (Physical Review E, 1994) measures whether a
signal's fluctuations scale consistently across window sizes, and a documented application to the
magnetic and electric field variations preceding physical rupture found the scaling exponent itself
shifts — from uncorrelated (~0.5) to strongly long-range correlated (~0.9–1.0) — right at the
transition associated with the rupture process, a genuinely different signature than an edge or a
curvature break. Run DFA along transects of the magnetic and gravity layers and flag locations where
the local scaling exponent breaks from the surrounding background's regime, rather than where the
amplitude or gradient spikes — this should catch structural discontinuities that are statistically
distinct from the surrounding geology even where they produce no sharp local edge. Normalize to
[0,1], write to the required format, and confirm this candidate's correlation with our prior
gradient/curvature-based submissions is low before calling it a new hypothesis rather than a
relabeled one.

## 5. Method requirements for proposing new work

Before implementing, generate 3–5 candidate geological hypotheses we have not tried yet, each naming:

1. the specific layer(s) involved,
2. the physical signature being targeted (e.g. an edge-detection or curvature transform),
3. why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it,
4. how it differs from anything already implemented in this repository.

Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our
spatially blocked holdout set before touching a weekly submission slot — do not spend a submission
slot on an idea that has not beaten the current holdout best. If a candidate cannot be validated
without new external data, name the specific free, official source needed and check it is obtainable
before proposing the idea as viable.

## 6. Site requirements

Create a GitHub Page for this repository that has a clean UI, is user friendly, simple and easy to
use, organised and clean. It should include all relevant information in an easy to read format, with
official verified links as sources for review. Work line by line, verify everything, no
hallucinations.

## 7. Standing question to answer

> Why and how did the highest-scoring submission (`h33-h33-2-b2`, 0.2778) get the highest score, and
> are we able to generate a submission that scores higher than the leader?

Answer with PhD-level judgement, then use the answer to generate a unique TIF submission. Verify no
hallucinations, work line by line, and flag irregularities.

## 8. Core values to apply while building, researching, suggesting upgrades and implementing

**Maximize P(Win)** — "Maximize the Probability of Winning" is our decision-making framework. In
every decision we weigh tradeoffs, assess risk, and choose the path that maximizes the probability
that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win).
"Maximize P(Win)" frees us from constraints and clarifies that we must put Arena first.

**Own the Outcome** — We own results end to end, not just our individual slice of the work. When
problems arise and we have the means to act, we do so without waiting for permission or assignment.
We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the
final outcome.

## 9. The GEMSDOE site history this work must not duplicate

Starting points that already generated TIF submissions (scores as recorded in the session brief;
provenance is owner-reported — see `registry/irregularities.json`):

| site | submission(s) | recorded score |
|---|---|---|
| GEMSDOE | gems-submission-20260925T001403Z-7f00890a | 0.1563 |
| 6GEMSDOE | gems6_hgb88-topk03_33cec71ff0 | 0.0286 |
| GEMSDOE3 | pindrop-v4 nodes / discovery / ridge | 0.1193 / 0.0830 / 0.1152 |
| GEMSDOE2 | gemsdoe2-dual-family-union | 0.1560 |
| GEMSDOE4 | gems-submission-20260926T163915Z | 0.0343 |
| 5GEMSDOE | gems-submission-20260926T175114Z | 0.1563 |
| 7GEMSDOE | lidarscarp-ridge-top2pct | 0.1461 |
| 8GEMSDOE | Hedge-v2_submission | 0.1563 |
| GEMSDOE9 | 2314b599 | 0.0107 |
| 11GEMSDOE | gems-structural-area06-v1 | 0.0202 |
| 12GEMSDOE | r7-nms3-dem10-scarp | 0.1294 |
| 15GEMSDOE | gems-tso1-…-conj_alteration_mag | 0.0782 |
| 14GEMSDOE | r5-geom-horse-ensemble | 0.0020 |
| 17GEMSDOE | F-ensemble-2pct | 0.0187 |
| 18GEMSDOE | H19-C | 0.0297 |
| 19GEMSDOE | h19-4 / h19-5 | 0.1894 / 0.1922 |
| GEMSDOE10 | h16-continuation / h20-dem10-scarp-thin / H25-ctx-ridge / h28-dotted-ridge | 0.0461 / 0.0921 / 0.1280 / 0.1839 |
| 13GEMSDOE | r13-lattice-s5_v2 | 0.0904 |
| 16GEMSDOE | h16-1 / h18-3a / h18-4 | 0.1855 / 0.0976 / 0.0360 |
| GEMSDOE21 | h19-4-reference | 0.1894 |
| 20GEMSDOE | h20-1 / h20-5 | 0.1890 / 0.1859 |
| GEMSDOE22 | h23-a / h23-b | 0.1002 / 0.0748 |
| GEMSDOE23 | h30-arrangement-matched-habitat | 0.1352 |
| GEMSDOE24 | h25-1-dotted-h19-5-d1-5 | 0.2477 |
| GEMSDOE25 | dotted-h19-5-d2-8 | 0.2600 |
| GEMSDOE26 | dilcond-oof-v1 | 0.1223 |
| GEMSDOE27 | topo-gap-closure-t-v2 | 0.2449 |
| GEMSDOE28 | h27-4-r1-solo-d2-8 / h32-1 / h36-1 / h38-1 | 0.2708 / 0.2649 / 0.2710 / not reported |
| GEMSDOE29 | efd28-repro / repo-c0-habitat / sgmc-off-catalogue / wormrank / wormsurv / xfit-* | 0.2600 / 0.0041 / 0.0512 / not reported |
| GEMSDOE30 | d28-poisson300m-offcat-44090 | 0.2600 |
| GEMSDOE31 | h27-4-solo-d28 | 0.2708 |
| GEMSDOE32 | h33-h33-2-b2 | 0.2778 (attribution contested) |
| GEMSDOE33 | h33d-analog-tip-stepover-r30 | 0.2632 |
| GEMSDOE34 | h34-scatter-q50-arr-matched | 0.0778 |
| GEMSDOE35 | h35-06 | 0.0418 |
| GEMSDOE36 | anderson-geothermal-pinn-38854 | 0.2750 |
| GEMSDOE37 | h6-physics-dotted-80k | 0.1193 |
| GEMSDOE38 | D-step-3p0-07pct-tipProt | 0.0763 |
| GEMSDOE39–47, 48GEMSDOE, 49GEMSDOE | listed research sites and candidates | not reported |

The supplied family history attributes its highest score, 0.2778, to GEMSDOE32; this is owner-reported. The prompt cites 0.3195 as the leader, while this session observed 0.3774 on the official board. These are dated observations, not a continuous feed. A relabelled version of a prior prediction does not count.


## 10. Data and access requirements

The task includes autonomously completing data restoration and preparation, not asking the owner to place files manually. Restore the hash-pinned public mirrors already recorded in `registry/data_manifest.json`; if they are unavailable, the prompt supplies these alternative user-provided links (not official provenance authentication):

- Rules: https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&dl=1
- Template: https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&dl=1
- Catalogue: https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&dl=1
- Features: https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&dl=1
- DEM links: https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&dl=1
- Official external-data starting point: https://gdr.openei.org/submissions/1391

The previous-session assertion that data placement is the sole blocker, and a GPU is necessary, must be verified rather than repeated. Disclose unavailable private labels, competition authentication, data licensing and proxy-validation limitations. No secrets should be requested or stored. Any future neural-training pipeline needs its own verified execution; generating a CPU detector is not evidence of having trained a neural model.

## 11. Current session additions (2026-10-06)

- Review all previous work first, preserve the highest-priority unique-TIF requirement, and never present a renamed prediction as a new hypothesis.
- Complete three passes: implement/test; review and fix; recheck original requirements.
- Open a pull request from the session branch and merge it to main after checks. Do not automatically use a competition submission slot.
- Maintain a prominent download and an executive-summary submission guide, unique name, short note, all-finite [0,1] validation, official sources, clearly recorded limitations, and next-session priorities.
- The full user history now extends through GEMSDOE47, 48GEMSDOE and 49GEMSDOE (the latter entries have no scores supplied). Empty scores are unknown, not zero.
- The stated 0.3195 leader is historical; link to the live official board and label cached observations with their retrieval date.

</details>
