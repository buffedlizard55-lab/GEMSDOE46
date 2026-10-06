# GEMSDOE46 — split-conformal spacing selection for the DOE GEMS Prize

**Competition:** DOE/NLR *Geologic Enhanced Mapping System (GEMS) Prize*, DrivenData #306
**Task:** predict geological faults indicative of geothermal resources across the GeoDAWN region
(NW Nevada / Walker Lane) as a single-band `float32` GeoTIFF of confidence values in `[0, 1]`.
**Deadline:** Dec 3, 2026 23:59 UTC · **Prize pool:** $300,000 (Initial $50k / Final $250k).
**Site:** <https://buffedlizard55-lab.github.io/GEMSDOE46/>

> ## ⬇️ DOWNLOAD THE SUBMISSION
> **[`SUBMISSION-GEMSDOE46-r8-conformal.tif`](SUBMISSION-GEMSDOE46-r8-conformal.tif)** — single-band
> `float32` GeoTIFF, 250 KB, EPSG:32611, 100 m, **every cell in [0, 1]**, 39,108 positive cells.
> Suggested name: `gemsdoe46-h46a-r8-conformal`. Note to paste into the form's *Note* field:
> [`docs/downloads/NOTE-gemsdoe46-h46a-r8-conformal.txt`](docs/downloads/NOTE-gemsdoe46-h46a-r8-conformal.txt)
> (spacing **r = 8 px**, certified floor **0.0283 at 90.0 % conformal confidence**, α = 0.1000 over
> **9 exchangeable calibration blocks**).
> **Fallback**, same dots with `NaN` outside the survey bounds:
> [`docs/gemsdoe46-h46a-r8-conformal-nan.tif`](docs/gemsdoe46-h46a-r8-conformal-nan.tif).
> **Upload instructions:** [`docs/SUBMISSION_GUIDE.md`](docs/SUBMISSION_GUIDE.md) · site page
> [`docs/how-to-submit.html`](docs/how-to-submit.html). **Format audit of that exact file:**
> [`docs/downloads/checks-gemsdoe46-h46a-r8-conformal-allfinite.json`](docs/downloads/checks-gemsdoe46-h46a-r8-conformal-allfinite.json).

---

## 0. What this repository is, in one paragraph

`GEMSDOE46` builds a competition submission from the **official** competition rasters, and decides
*how many dots to emit and how far apart* not by eyeballing a sweep but by a **split-conformal**
selection rule with a finite-sample confidence level a Phase-2 reviewer can check
([`evidence/conformal_selection.json`](evidence/conformal_selection.json),
[`evidence/analytic_screen.json`](evidence/analytic_screen.json)). It replaces the prior lines'
"we tried a few spacings and this one looked best" with *"this spacing is certified at 90.0 %
confidence with a floor of 0.0283 on 9 exchangeable spatial blocks, and its density is admissible
against the metric's own ceiling."* Everything downstream of the three data files is reproducible:

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
bash   scripts/download_competition_data.sh   # or: python scripts/prepare_data.py --from-dir ~/Downloads
python scripts/run_pipeline.py                # hash-verify data -> 24-block sweep -> R1-R4 selection
python scripts/make_submission.py             # rules pick the arm -> writes + audits the GeoTIFF
python -m pytest tests -q                     # metric transcription + audit checks
```

---

## 1. The brief this repository exists to answer (verbatim, kept as the project charter)

> Review the repo.
>
> THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!
>
> MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION
> UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. The
> submission must be different than the collection of gemsdoe sites below.
>
> There should be an easy to download submission tif file as described by the prompt. Read the
> entire prompt.
>
> Use split conformal prediction on your own spacing sweep to pick an operating point with a
> guaranteed floor, not just an observed one. You already have the calibration data for this
> sitting in your own score history — a sequence of spacing/threshold choices each scored against
> holdout DTI. Lei, G'Sell, Rinaldo, Tibshirani, and Wasserman's split conformal framework (JASA,
> 2018) converts a calibration set like this into a selection rule with a finite-sample coverage
> guarantee under far weaker assumptions than a Bayesian or parametric method needs — rather than
> eyeballing that d2-8 beat d1-5 and picking d2-8, split your existing spacing/DTI results into a
> calibration half and a selection half, and use the calibration half to certify a spacing choice
> with a guaranteed minimum holdout performance, not merely an observed one from a single sweep.
> Normalize to [0,1], write to the required format, and report the conformal guarantee's
> confidence level next to the chosen spacing in the submission notes — a number a Phase 2
> reviewer can check, unlike "we tried a few and this one was best."
>
> WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE
> SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING: GEMSDOE32
> `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778`. Why and how did this get the highest
> score and are we able to generate a submission that scores higher than 0.2778? … 0.3195 is the
> highest score right now so we need to design a new strategy, research, testing, analyzing, and
> generating submission system than the current website. It should be unique, take unique
> approaches to generating a submission that can score higher than 0.3195.
>
> Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each
> naming: the specific layer(s) involved, the physical signature being targeted (e.g., an
> edge-detection or curvature transform), why it should catch a fault missing from the
> USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already
> implemented in this repo. Rank them by expected DTI improvement and implementation cost.
> Validate the top candidate on our spatially-blocked holdout set before touching a weekly
> submission slot — do not spend a submission slot on an idea that hasn't beaten the current
> holdout best. If a candidate can't be validated without new external data, name the specific
> free, official source needed and check it's obtainable before proposing the idea as viable.
>
> Work line by line verifying from official verified trusted sources, provide links for manual
> review. There should be no manual input, work on your own to complete tasks. Flag any
> irregularities for review. No hallucinations. Verify no hallucinations. The goal of this
> project is to get a full list that follow our requirements. No hallucinations. Verify line by
> line.
>
> We need to focus on being able to generate a submission into the competition. The site should
> be able to generate a TIF file that is required for submission. It should be as easy as
> download to click a File to submit into the competition. This needs to be in the executive
> summary or the very beginning of the site. it should be obvious when you visit the site.
>
> I tried to submit the document that i downloaded from the site but it returned this error on the
> submission form: **"Predicted values must be in range [0, 1]"**. Also we need to give it a
> unique name and A short comment to help you or your team tell submissions apart later e.g.,
> clustering with k=25. … Create a executive summary subpage that explains exactly how to make a
> submission into the contest.
>
> Put this prompt into the repo readme and read it everytime we work on the project as a starting
> point… Run this task through multiple passes. Pass 1: implement completely and verify. Pass 2:
> review for bugs, missing requirements, incorrect assumptions, edge cases. Pass 3: re-check the
> entire implementation against the original request. Do not stop after the first pass. … Go ahead
> and create a pull request and then merge the pull request onto the main. Make suggestions for
> what work still needs to be done and any limitations that is in the way of a successful project.

### Core values applied here (Arena)

* **Maximize P(Win).** Every design choice is made against the *official metric's own algebra*, not
  against a proxy known to drift ([`docs/SCORE_ANALYSIS.md`](docs/SCORE_ANALYSIS.md)). Where the proxy
  and the algebra disagree, the algebra wins and the disagreement is reported
  ([`docs/IRREGULARITIES.md`](docs/IRREGULARITIES.md)).
* **Own the outcome.** The repository ships an auditable artefact *and* a slot-ready file, plus the
  instrument (conformal selector + analytic screen) that turns every future slot decision into a
  measurement rather than a preference.

---

## 2. The one-paragraph answer to "why did 0.2778 win, and can we beat it?"

`h33-h33-2-b2` (GEMSDOE32, public LB #13, **0.2778**) is not a better model than its parent; it is the
*same* field emitted with **less mass**. The published index is
`DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)` with a 300 m triangular kernel, which collapses in the sparse
regime to **`DTI = T / (0.2·N + 0.8·|G|)`** — a *budget*. Adding a unit of mass pays iff its kernel
credit `k > 0.2 × DTI`. `h33-2-b2` deleted every dot within 200 m of the catalogue (37,654 dots left),
because the organizer masks USGS/INGENIOUS pixels out of scoring: a dot *on* the catalogue is free but
worthless, and a dot *beside* it is charged while earning nothing. The family's whole sequence — 0.1922
@ 121,131 → 0.2477 @ 60,069 → 0.2600 @ 44,090 → 0.2708 @ 40,199 → 0.2778 @ 37,654 — is monotone in
**mass deleted**, not in model quality. The identity reproduces the 0.2600 row *exactly* from its own
reported dot count and credit (3,937.2 / (0.2·44,090 + 0.8·7,905) = 0.2600), which is why we trust the
algebra as the leaderboard's.

**Can we beat it?** Only by raising the credit `T` at a *lower* `N`. Two hard, data-free bounds say how
far that can go: `DTI ≤ |G| / (0.2·N + 0.8·|G|)`, so at the declared `|G| = 7,905 px`
**no submission with more than 86,541 dots can reach 0.3345 even with perfect placement**, and at the
sibling's own mass the target needs **28.6 % more kernel credit per unit mass**, not more dots. Every
extra dot is a tax; the only lever left is the *field* — see
[`docs/HYPOTHESES.md`](docs/HYPOTHESES.md), where the highest-value candidate (a fault that is provably
real, provably not in the catalogue, and provably inside the footprint: the 2020 Mw 6.5 Monte Cristo
surface rupture) was **tested this session and did not beat the shipped arm**, so no slot was spent on it.

---

## 3. Contents

| path | what it is |
| --- | --- |
| `src/gems46/metric.py` | the official metric, transcribed line-by-line from the problem page |
| `src/gems46/window_metric.py` | exact windowed scorer (global-truth `FPw`, halo-correct `TPw`/`FNw`) |
| `src/gems46/features.py` | 25-band multi-scale curvature / edge / cover feature stack (official 19 bands) |
| `src/gems46/emitter.py` | metric-aware sparse emitter; spacing is the sweep parameter; greedy NMS thinning |
| `src/gems46/pipeline.py` | spatially blocked holdout, 24 tiles, density-matched populations, fold runner |
| `src/gems46/conformal.py` | **the single authoritative selection path** — rules R1–R4 |
| `src/gems46/analytic.py` | the data-free metric ceiling on dots vs. truth mass |
| `src/gems46/submit.py` | writer + independent re-read auditor (both `nan` and `allfinite` encodings) |
| `scripts/run_pipeline.py` | end-to-end driver; `--stage post` re-runs only the selection |
| `scripts/make_submission.py` | fits on all data, applies R3/R4 to **measured** counts, writes + audits |
| `scripts/hypothesis_release.py` | the paired A/B that tested hypothesis H1 on the same 16 blocks |
| `scripts/prepare_data.py` | verifies the three official rasters (hashes, geometry, label convention) |
| `scripts/download_competition_data.sh` | fetch the rasters with your own signed-in session URLs |
| `docs/SCORE_ANALYSIS.md` | why 0.2778 scored; what the metric does and does not reward |
| `docs/HYPOTHESES.md` | the 5 ranked geological hypotheses + the H1 holdout result |
| `docs/SUBMISSION_GUIDE.md` | exactly how to upload (executive-summary subpage, prose version) |
| `docs/SOURCES.md` | every external claim with its official link |
| `docs/IRREGULARITIES.md` | flags, unfixed risks, and the two defects found and fixed in this audit |
| `docs/index.html` | the executive summary site (download button at the very top) |
| `evidence/` | machine-readable results of every stage |

---

## 4. Limitations (stated up front, as the brief requires)

1. **No DrivenData account in this environment.** The three official rasters are the project's own
   copies, re-verified byte-for-byte against hash pins on every run
   ([`evidence/data_provenance.json`](evidence/data_provenance.json)); the private test labels are not
   available anywhere and are never guessed at. The upload itself must be done by the project owner.
2. **The certified floor is a statement about the catalogue-proxy holdout, not about the leaderboard.**
   The scored truth is the new-fault population, which no public data labels. Only the *density* side of
   the metric transfers exactly, and that is where the algebra is used.
3. **No GPU and 4 GB of RAM here.** The detector is a gradient-boosted model on hand-built multi-scale
   features. The deep-model direction is ranked in [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).
4. **The top geological hypothesis did not survive its holdout test.** H1 (release-controlled new-fault
   detection) gained +0.00051 mean DTI with a median difference of zero and a sign test at p = 1.00 on
   the density-matched population — recorded, not shipped.
5. **Scores from sibling sites are owner-reported** except the rows `0.2600` (#20) and `0.2778` (#13),
   which are also visible on the live public leaderboard, which is what licenses treating them as real
   anchors.

## 5. Remaining work, in priority order

1. **Upload the shipped file** ([`SUBMISSION-GEMSDOE46-r8-conformal.tif`](SUBMISSION-GEMSDOE46-r8-conformal.tif))
   and record the leaderboard score in [`docs/IRREGULARITIES.md`](docs/IRREGULARITIES.md) IR-46-02.
2. **Work H2–H5** in [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md) using the paired A/B harness — H2
   (structure-tensor coherence + local-plane residual) is the cheapest with a real geometric idea.
3. **Replace the hand-built emitter with a locally optimal credit allocator** (the exact greedy on
   marginal credit, not first-order), and certify it with the same R1–R4 rules.
4. **Remove the manual step entirely**: a weekly job that re-runs `run_pipeline.py` + `make_submission.py`,
   records every scored arm, and re-certifies the spacing as calibration blocks accumulate — the
   conformal coverage claim strengthens with `n_cal`, so the instrument is worth re-running even when
   the data does not change.
5. **Deep research storage**: a versioned knowledge store of verified geothermal/fault facts with
   source hashes (the `docs/SOURCES.md` convention, machine-readable), so future sessions start from
   verified text rather than re-searching.
