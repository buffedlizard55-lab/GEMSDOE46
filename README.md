# GEMSDOE46 — auditable fault-discovery experiments

Four parallel arms live in this repository. **One is the current candidate**: the R11F fusion arm.

## Download the TIF

**[Download `gems46-r11f-scarp-radiometric-fusion-00e049b51218-zeros.tif`](docs/r11f/gems46-r11f-scarp-radiometric-fusion-00e049b51218-zeros.tif)** · [full machine-readable
receipt](docs/r11f/receipt.json) · [step-by-step submission guide](https://buffedlizard55-lab.github.io/GEMSDOE46/docs/executive-summary.html)

**PROXY GATE PASSED — NOT SUBMITTED.** A unique, format-audited, all-finite single-band float32
GeoTIFF: 44,090 unit dots, zero outside the scored footprint, sha256
`57be86502a03a22e…`. It fuses two evidence families the official 19-band stack does not contain
(1 m lidar terrain descriptors as a scarp matched filter; the GeoDAWN K/Th/U compositional-contrast
ratio grids, DOI 10.5066/P93LGLVQ) and emits them with an expected-credit submodular optimiser whose
stop rule is the metric's own break-even. **No competition slot has been used; submitting it is the
user's decision.**

| Measured result (all proxy, not organizer scores) | Value |
|---|---:|
| R11F candidate on the live-order-calibrated stratified-SGMC instrument (d0 = 5 px) | **0.16619** |
| Live-scored 0.2778 incumbent file, same instrument | 0.08852 |
| Uniform-random control, same mass | 0.06835 |
| Paired over 127 truth-bearing blocks | +0.06476 (t = +6.77) |
| Same field re-emitted at the matched mass 37,654 | +0.03837 (t = +4.31) |
| Dots within 300 m of truth (candidate vs incumbent) | 14.3 % vs 10.5 % |

The advantage is **new placement, not pruning**: the R11F field's AUC over the incumbent's *own*
dots is 0.507 — chance — so it wins by putting dots where the incumbent
has none. The candidate is explicitly *not* claimed as a new hypothesis: its maximum |correlation|
with prior shipped files is 0.3779, above the 0.2 ceiling.

- [Active site](https://buffedlizard55-lab.github.io/GEMSDOE46/) ·
  [R11F review, defects found and limitations](docs/research/r11f-review.md) ·
  [preregistration](docs/research/session-r11f-plan.md) ·
  [flagged irregularities](https://buffedlizard55-lab.github.io/GEMSDOE46/docs/irregularities.html)

### The other three arms, kept as published negatives

| arm | what it tested | verdict |
|---|---|---|
| **R11 (A/C/D)** `registry/r11.json` | windowed-DFA boundaries; tilt zero-crossings; matched-filter contacts | A stopped for **futility** at synthetics (4.4 km mislocalization); C **suspended**; D **HOLD** (blocked DTI 0.0610 vs 0.1007 for the best comparator, correlation gate 0.543). [TIF](docs/r11/gems46-r11d-matchedfilter-5caba5cc4ffc-zeros.tif) · [review](docs/research/r11-review.md) |
| **H47-1** `registry/h47.json` | catalogue-supervised lineament detector (LightGBM over 55 features) | **HOLD_DO_NOT_SUBMIT**: 0.053242 vs the incumbent's 0.088516 on the same stratified instrument R11F passes; AUC over the incumbent's dots 0.497. [TIF](docs/downloads/h47/gemsdoe47-h47-1-catalogue-supervised-lineament-37654-20261006T180000Z-h47a-zeros.tif) · [review](docs/research/h47-review.md) |
| **R10** `registry/r10.json` | 51 km DFA slope crossover | **HOLD**: 0.0617 vs 0.1033, paired −0.0416. [TIF](docs/r10/gems46-r10-dfa-crossover-95ba59eb9030-zeros.tif) |

The DFA regime-break detector asked for by the standing brief has now failed in four independent
implementations (R10, H46-1, R11-A, R11F's re-localised variant) — see `docs/HYPOTHESES.md` and
IR-46-16.

## The standing question: why did 0.2778 score highest, and is more reachable?

Measured this session from the three live-scored dot files (owner-reported scores; no organizer file→score receipt exists):

* They are **one** dot set. The 37,654-pixel file (0.2778) is an exact subset of the 40,199-pixel file (0.2708), which is an exact subset of the 44,090-pixel file (0.2600); all three share the **identical 37,654-pixel** core beyond 200 m of the published catalogue. The entire 0.26→0.28 progression is the deletion of near-catalogue dead mass, nothing else.
* The published metric charges 0.2 per dot with no truth within 300 m and 0.8 per uncovered truth pixel. Fitting the two score steps gives `T ≈ 5,223` covered truth pixels and denominator `D ≈ 18,800`; each dead dot costs `0.2·T/D² ≈ 3.0e-6`, each hit dot earns `(1−DTI)/D ≈ 3.8e-5`, so the break-even hit rate is `0.2·DTI/(1−DTI) ≈ 7.7%`. The incumbent hits at ~10.5% — just above break-even. That is the plateau.
* Beating it needs either (i) removing the ~32,000 dead dots without the hidden labels — the test is whether a model can rank the incumbent's own dots, and the H47 detector was at chance (AUC 0.497) — or (ii) placing dots on faults the catalogue lacks. H47 found its own detector could not do (ii) either (flat hit-rate 12.1 % → 9.4 % from 5 k to 120 k dots) and concluded the needed information was "not obtainable in this sandbox". **R11 supersedes that conclusion**: the information was in the mirrored external layers (1 m lidar terrain descriptors, GeoDAWN radiometric ratios), and R11's fusion lifts the instrument hit fraction from 10.5 % to 14.3 % and the instrument DTI from 0.0885 to 0.1662 (paired t +6.77 over 127 blocks). See §5b of `docs/research/r11-review.md`.
* Instrument discipline: the catalogue-in-block holdout and the un-stratified SGMC truth both **invert** the live order; only SGMC truth stratified at ≥3 px from the catalogue reproduces 0.2600 < 0.2708 < 0.2778. `registry/h47.json → ladder` prints all six rows before any delta.

## Reproduce on CPU

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/restore_competition_data.sh
.venv/bin/python scripts/screen_r11.py        # one-channel-at-a-time screen (proxy ranks)
.venv/bin/python scripts/run_r11.py           # Pass 1: families, curves, first gate (~10 min)
.venv/bin/python scripts/refine_r11_mass.py   # Pass 2: measured transfer, matched gate
.venv/bin/python scripts/audit_r11_on_stratified.py  # Pass 3: live-order-calibrated instrument
.venv/bin/python scripts/build_r11_site.py    # active site (CI diffs the three pages)
.venv/bin/python scripts/build_irregularities_page.py
# historical: scripts/run_h47.py + build_h47_site.py (H47, HOLD), run_r10.py + build_r10_site.py (R10, HOLD)
.venv/bin/python -m pytest
.venv/bin/python scripts/verify_all.py
```

`lightgbm` and `scikit-learn` are pinned in `requirements.txt` (the sklearn wrapper of LightGBM needs it; both are CPU-only). The inputs are hash-pinned public-family mirrors; hashes prove consistency, not organizer authentication. Raw data and derived arrays remain ignored. No GPU is needed. The site serves precomputed audited files, not a browser-side scientific pipeline.

## Corrections, limitations and priorities

The former README treated model-dependent hidden-label counts as measured facts, called low Pearson correlation proof of physical independence, and guaranteed a scoring route that had not been demonstrated; those claims are withdrawn. The exact denominator is `0.2(T+S−M)+0.8G`; replacing it with `0.2S+0.8G` requires an extra assumption. Legacy DFA maps carry a half-window index bug (fixed, regression-tested); archived artifacts do not silently inherit the correction. New H47 bugs found and fixed this session: a `KeyError` in the artifact audit and two test-side errors (a 3 px shift is outside the metric's support; the marginal-rule test used per-dot credit as its own penalty weight).

Next session, in order: (1) an organizer file→score receipt for the three family files, or a second independent truth source — a single proxy cannot settle a 0.01-scale question; (2) one measured dead-dot rule (the field-based one is already ruled out at AUC 0.497); (3) the 1 m lidar/3DEP route on a machine with unrestricted egress, which is the only identified upside large enough to matter. Do not spend the weekly slot on an unscreened file, and do not tune repeatedly on the same nine SGMC blocks.

## Core values

**Maximize P(Win):** a failed proxy gate is a reason to protect the weekly slot, not conceal the result. **Own the Outcome:** fix our own defects, preserve receipts, publish negative findings and distinguish hypothesis from evidence.

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
