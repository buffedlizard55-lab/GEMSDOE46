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
