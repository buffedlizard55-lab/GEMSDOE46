# R12 session plan — preregistered hypotheses (2026-10-06)

**Read with:** [`AGENTS.md`](../../AGENTS.md) (session protocol), [`r10-review.md`](r10-review.md)
(previous session's negative result and next-step list), [`registry/irregularities.json`](../../registry/irregularities.json).

This plan is written **before** the R12 detector is implemented. The exploratory layer screen
(`scripts/screen_r12_layers.py`, receipt `evidence/r12_layer_screen.json`) was run first and is
labelled *exploratory* everywhere below; it motivates the ranking but it is **not** the decision
instrument. The decision instrument is defined in §7 and is a set of spatial blocks that no
selection step in this session is allowed to look at.

---

## 1. What the previous session established (do not repeat)

| Prior finding | Consequence for R12 |
|---|---|
| R10 DFA crossover failed the blocked proxy gate (0.0617 vs 0.1033 best comparator) | Do not re-tune R10 parameters on the same blocks. R10 stays `HOLD_DO_NOT_SUBMIT`. |
| The 4×4 blocked grid used by R10 has been looked at | R12 must select on a **different** partition and decide on blocks never used for selection (§7). |
| `DTI = T / [0.2(T+S−M) + 0.8G]` exactly | Coverage `T` is the only numerator. At `S = 37,654`, `G ≈ 14,089` the denominator is ≈18,802, so live 0.2778 ⇒ `T ≈ 5,224` and live 0.3774 (leader, retrieved 2026-10-06) ⇒ `T ≈ 7,094`: **+36 % coverage at the same emitted mass**. |
| IR-46-04: the catalogue-truth holdout is an inverted instrument | Never tune the catalogue exclusion buffer on a proxy whose truth is a fault catalogue. R12 keeps the family's live-validated 200 m exclusion and does not tune it. |
| IR-46-05: absolute DFA thresholds do not transfer | No absolute-threshold detector in R12. |
| Geodetic bands 4/7/8, gravity slope, depth-to-basement show no relationship to realised score (univariate `p` = 0.37–0.96, `data/feature_signal.json`) | Do not build an R12 arm on strain-rate or cover-thickness layers. |

## 2. Data newly available to this repository (verified this session)

Restored from the group's public mirror of **USGS ScienceBase item 657e1d85d34e23d3533209f7**
(GeoDAWN, DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ)); the mirror records the source
archive MD5/SHA-256 for every member file. None of these layers is in `training_features.tif`, and a
grep of `registry/` and `docs/` in this repository shows **no arm has used them**:

| Product | Bands | Coverage of scored footprint | Note |
|---|---|---|---|
| `geodawn_rad_u8.tif` | K, Th, U, TC | 100 % | airborne gamma-ray spectrometry, rank-quantised uint8 |
| `geodawn_extensions_u8.tif` | Th/K, U/K, U/Th, TMI up-continued 150 m | 100 % (TMI_up150 99.9 %) | contractor ratio/derivative grids, rank-quantised |
| `lidar_scarp_features_u8.tif` | 12 channels of 2 m LiDAR scarp morphology (`step_max`, `downface_max`, `upface_max`, `lapneg_max`, `lappos_max`, `cross_max`, `ex_max`, `coh100`, `strike`, `valid`, …) | 75.3 % | derived from 1 m 3DEP LiDAR flown with the survey |

Two properties were measured, not assumed: the products are **rank-quantised** ("uint8 1..255 over
per-channel 1st..99th pct", per the mirror's own receipts), so only monotone/structural information
is meaningful; and the scored footprint (5,167,373 finite template pixels) coincides with the survey
area (band 2 has 5,165,852 valid pixels), which explains why 53.8 % of 64-px blocks of the official
rasters are constant — they are outside the footprint, not a data defect.

## 3. Exploratory screen (motivating evidence, not a decision)

`scripts/screen_r12_layers.py`: off-catalogue SGMC proxy truth, catalogue exclusion (2 dilations),
matched mass 37,654, `min_dist 3`, smoothing 1.85 px, exact DTI. Whole domain, no block split.

| Field | Proxy DTI | dots within 300 m of a proxy trace |
|---|---:|---:|
| LiDAR `downface_max` | 0.14448 | 15.0 % |
| LiDAR `step_max` | 0.14436 | 15.0 % |
| Gamma-ray Th/K gradient (σ = 2 px) | 0.11215 | 11.8 % |
| Gamma-ray TC gradient | 0.11152 | 11.6 % |
| Reference: RTP gradient σ = 1.5 (the classic arm) | 0.07908 | 8.9 % |
| Reference: isostatic-gravity gradient σ = 2 | 0.04615 | 5.2 % |
| Naive rank-geometric-mean composites | 0.090–0.108 | — |

Read honestly: (i) the 2 m LiDAR morphology bands and (ii) the gamma-ray channels both beat every
reference field this repository has used, and (iii) a naive symmetric composite is **worse** than
either part — so corroboration has to be asymmetric or it destroys the stronger signal.

## 4. Candidate hypotheses (PROMPT.md §5 attributes, ranked)

### H46-R12-A — *rank 1*: scarp-morphology primary with gamma-ray corroboration, radiometric fallback where LiDAR is absent

* **Layers:** LiDAR-derived `downface_max`, `upface_max`, `step_max`, `lappos_max` (2 m DEM
  morphology); GeoDAWN gamma-ray `Th/K`, `TC`, `Th` gradients; `valid` band as the coverage mask.
* **Physical signature:** a normal fault scarp is an *oriented* slope break — the band-passed
  gradient measured down the regional slope (`downface_max`) and against it (`upface_max`) are
  asymmetric across the trace — while the same structure disrupts the top 0.3–0.5 m sampled by
  gamma-ray spectrometry, producing a linear break in total count and in the Th/K ratio
  (gouge, breccia, clay alteration, moisture contrast). Neither is an amplitude or curvature maximum
  of a potential field.
* **Why off-catalogue:** the published catalogue is a Quaternary-fault compilation mapped from
  surface expression. A trace that is morphologically subtle but has a strong regolith contrast, or
  one buried by alluvium, is under-recorded; the conjunction of two independent sensors (topography
  and near-surface radiochemistry) is specific to a *structure* rather than to a landform, and the
  200 m catalogue exclusion removes the already-mapped population by construction.
* **Differs from everything in this repository:** gamma-ray spectrometry has never been used by any
  arm here (verified by grep across `registry/`, `docs/`, `src/`); the LiDAR morphology product is
  not used by any arm here either; and no shipped arm used an *asymmetric* corroboration gate with a
  coverage-aware fallback. A sibling site (7GEMSDOE, `lidarscarp-ridge-top2pct`, owner-reported
  0.1461) used a LiDAR ridge alone, so a LiDAR-only arm would **not** be a new hypothesis — which is
  exactly why R12 requires the second sensor and is validated against LiDAR-alone as a comparator.
* **Expected DTI:** unknown; the parts measure 0.1445 and 0.1122 exploratorily. Falsified if the
  concordance does not beat the better part on the locked blocks.
* **Cost:** low (CPU, minutes). **External data:** already restored, hash-pinned.

### H46-R12-B — *rank 2*: ridge-axis thinning before emission (operator, not field)

* **Layers:** same field; changes only how the field is converted into dots.
* **Physical signature:** structure-tensor orientation → non-maximum suppression perpendicular to
  strike collapses a 3–5 px wide response band onto a one-pixel axis.
* **Why off-catalogue:** instrument-level, not geological. Justification is metric algebra: at fixed
  `S`, `DTI` rises only through `T`, and a dot on the trace axis earns `k = 1` for its nearest truth
  pixel while a dot on the response flank earns `k ≈ 0.67`; spreading dots also stops two dots from
  competing for the same truth pixel (the metric takes a max, the second dot pays the 0.2 FP tax).
* **Differs from repo:** every arm here uses `emission.greedy_emit` on a smoothed field; no
  axis-thinning operator exists in `src/`.
* **Expected DTI:** modest positive; falsified if it does not beat the unthinned field at matched mass.
* **Cost:** low.

### H46-R12-C — *rank 3*: truth-mass-matched instrument and budget re-derivation (methodological)

* **Layers:** none new; changes the validation instrument.
* **Signature:** the off-catalogue proxy contains 66,277 truth pixels while the live-anchored hidden
  truth estimate is ≈14,089 (`registry/emission_model.json`, itself model-dependent). The optimal
  emitted mass depends on `G`, so a proxy with 4.7× the truth mass systematically favours larger
  budgets. Re-deriving the budget on a truth-mass-matched instrument (whole connected components
  retained, seeded) tests whether the family's 37,654 operating point is even optimal.
* **Why off-catalogue:** n/a — instrument, not detector.
* **Differs from repo:** all prior proxy work used unmatched truth mass.
* **Expected:** possibly large (the family ledger shows Spearman −0.907 between emitted mass and
  live score, IR-46-07). Reported as a *sensitivity*, never as a licence to change the shipped mass
  without a live receipt.
* **Cost:** low.

### H46-R12-D — *rank 4*: strike-continuity gap closure from the LiDAR `strike`/`coh100` bands

* **Layers:** LiDAR `strike` (0–180°, linear quantisation) and `coh100`.
* **Physical signature:** lineaments interrupted by alluvial cover keep a coherent orientation; the
  gap is filled by extending detected segments along their own strike.
* **Why off-catalogue:** gaps are exactly where a mapper could not see the trace.
* **Differs from repo:** the derived strike band is unused here; a sibling site tried topographic
  gap closure (GEMSDOE27, owner-reported 0.2449), so this is *partially* explored elsewhere and is
  ranked below A–C for that reason.
* **Cost:** medium. Deferred unless A/B succeed and time remains.

### H46-R12-E — *rank 5, BLOCKED*: hypocentre lineaments from the USGS ANSS catalogue

* **Layers:** USGS FDSN event service, M ≥ 1.5, 1900–present, inside the footprint
  (−120.04…−116.14 E, 37.33…40.73 N — Walker Lane).
* **Physical signature:** alignment of precisely located hypocentres into strike-parallel
  lineaments — a fault-*activity* signature, independent of rock properties and topography.
* **Why off-catalogue:** an active fault with no Quaternary surface trace still produces
  microseismicity; the competition's seismic bands are smoothed at 100 km and cannot express it.
* **Obtainability check performed this session:** `https://earthquake.usgs.gov/fdsnws/event/1/query`
  returns **HTTP 000 from the sandbox shell** (re-measured 2026-10-06, no route), so
  `scripts/fetch_earthquake_catalog.sh` cannot run here. The agent's own web tool *does* reach the
  service (a malformed query returned the service's HTTP 400 usage page, proving reachability), but
  transferring ~10⁴ CSV rows through that tool into the repository is impractical and would not be
  reproducible by CI. **Therefore: not viable this session, named source recorded, no slot spent.**

## 5. Ranking rule

Expected DTI improvement first (evidence-weighted by the exploratory screen and by the metric
algebra), then implementation cost, then whether the idea needs data this environment cannot obtain.
A: strongest measured components and a genuinely new sensor. B: cheap, algebra-justified, applies to
any field. C: cheap, addresses the largest known instrument bias. D: partially explored elsewhere.
E: blocked.

## 6. What R12 will *not* claim

* That a proxy DTI is a leaderboard score, or that beating the proxy implies beating 0.3774.
* That low correlation with prior files proves geological independence (it proves non-redundancy on
  the chosen mask only).
* That the mirrored USGS products are organiser-authenticated. They are hash-pinned copies of a
  public USGS data release; the pins prove mirror consistency.
* That rank-quantised uint8 channels carry physical units. Only ordering and structure are used.

## 7. Decision instrument (locked before implementation)

* Partition: **6×6 = 36 blocks**, three-pixel interior guard, catalogue exclusion 2 dilations
  (fixed, not tuned), per-block matched emitted mass proportional to block domain area.
* **Selection set:** blocks with `(i + j)` odd. Used for every design choice (concordance weight,
  thinning on/off, fallback share, smoothing, spacing).
* **Locked decision set:** blocks with `(i + j)` even. Never inspected during selection. One
  comparison only, after the configuration is frozen.
* Comparators re-emitted from their own fields at the same per-block mass: LiDAR-alone, gamma-ray
  alone, RTP-gradient reference, restored GEMSDOE32 file, shipped R10 file.
* Promotion rule: R12 must beat the **best** comparator on the locked set with a seeded paired
  block-bootstrap 95 % interval excluding zero, and must not duplicate any shipped raster.
  Otherwise the artifact is published as `HOLD_DO_NOT_SUBMIT`, exactly as R10 was.

### 7.1 Amendment (added 2026-10-06, *before* the stratified measurement was computed)

Merging `origin/main` into this branch surfaced the H47 instrument ladder
(`registry/h47.json → ladder`, `docs/research/h47-review.md` §2). It measured the three live-scored
family files (0.2600 / 0.2708 / 0.2778) on six instrument variants and found that

* the catalogue-in-block holdout **inverts** the live ordering,
* the un-stratified off-catalogue SGMC truth (0 px exclusion) **inverts** it,
* only SGMC truth stratified at **≥3 px** from the catalogue (module default 5 px = 500 m), with the
  catalogue masked as `known` exactly as the organiser confirmed for the live scorer, reproduces
  0.2600 < 0.2708 < 0.2778.

§7 above fixed the exclusion at 2 dilations (200 m) — a variant that has never been checked against
the live ordering. A gate that passes on an instrument which can invert the known ranking is not
evidence of improvement, so §7 alone is not sufficient. The following rule is added **before** R12's
stratified score is computed (IR-46-18):

> **Two-instrument promotion rule.** R12 is `PROXY_GATE_PASSED_NOT_SUBMITTED` only if **both**
> readings agree:
> 1. §7 unchanged — beat the best comparator on the locked 6×6 even blocks at matched per-block mass,
>    with a seeded paired block-bootstrap 95 % interval excluding zero, and duplicate no shipped
>    raster; **and**
> 2. on `gems47.proxy.instrument_sgmc_stratified` with `d0 = 5 px` (500 m), the catalogue masked as
>    `known`, over the whole footprint at matched mass 37,654, R12's DTI **exceeds** the restored
>    GEMSDOE32 incumbent file's DTI at the same mass.
>
> If either reading fails, the artifact is published as `HOLD_DO_NOT_SUBMIT`. Both readings are
> written to `registry/r12.json` (`gate_locked_blocks_200m`, `gate_stratified_whole_domain`) and
> neither may be quoted without naming its instrument.

No configuration, block or comparator is changed by this amendment; only the decision rule is
tightened. This is recorded as an amendment rather than folded into §7 so that the original rule and
the reason it was insufficient both stay on the record.
