# H47 — candidate hypotheses for the GEMS Prize (registered before implementation)

**Session:** 2026-10-06 · **Repository:** GEMSDOE46 · **Target:** DrivenData #306 (DOE GEMS Prize)
**Rule applied here (from `PROMPT.md` §5):** every candidate names its layers, its physical
signature, why it should catch a fault *missing from* the USGS/INGENIOUS catalogue, and how it
differs from everything already implemented in this repository **and from the arms already
implemented in the wider GEMSDOE family history that this session could inspect**. Candidates that
need data this sandbox cannot obtain are marked BLOCKED with the exact source named and its
obtainability checked, not assumed.

Evidence classes: **[OFFICIAL]** organizer text, **[MEASURED]** computed here from hash-pinned
bytes, **[OWNER-REPORT]** the group's own unverified ledger, **[BLOCKED]** unobtainable here.

---

## What is already taken (checked, so nothing below is a relabelling)

| already implemented | where | why it constrains the candidates |
|---|---|---|
| Hand-built edge/curvature/ridge fields with corroboration across physics | GEMSDOE46 `H46-2`; family `h19-4/h19-5`, `h27-4`, `H28` | a new arm may not be "Sobel/Laplacian × agreement" again |
| DFA scaling-exponent / crossover fields on magnetic + gravity transects | GEMSDOE46 `H46-1`, `R10` | DFA is spent here; R10 failed its gate |
| Multi-physics Hessian line response × orientation order parameter | family `H33-A` (GEMSDOE32) | an "agreement of orientations" arm is not new |
| Drainage-valley-chain collinearity; en-echelon lidar scarplet chains | family `H33-B`, `H33-C` | valley/scarp chaining is spent |
| Conductive/basement straight boundary; Euler depth clusters | family `H33-D`, `H40/H45`, `h8-euler-lineament-depthcluster` | subsurface-boundary arms are spent |
| Fault-tip / relay-ramp corridors | family `H33-5` (detector-field tips) and `H18-3a` (catalogue-tip density) | tip-based priors are spent — see H47-2 below, which is a *different* tip question and is falsified here |
| Thinning a dot set / pruning the catalogue flank | family `d2.8`, `H33-2-B2` (B=1→2), scored 0.2600→0.2708→0.2778 | emission-budget arms must beat a live-validated mechanism, not re-derive it |
| Catalogue-supervised models | family `GEMSDOE32/src/gems32/detector.py` (HGB/logistic harness), `GEMSDOE36` (stress-regularised U-Net, best family artefact 0.2750) | "train a model" is not a new idea; the *feature stack + screening* must be the claim |

---

## Outcome (measured, end of session 2026-10-06)

| # | candidate | status | measured result |
|---|---|---|---|
| H47-1 | catalogue-supervised multi-scale lineament detector + metric-algebraic dashed emission | **IMPLEMENTED, SCREEN FAILED → HOLD_DO_NOT_SUBMIT** | shipped full field at matched mass (37,654 dots): stratified-SGMC DTI 0.053242 vs incumbent 0.088516 (delta −0.035274), paired over 127 blocks t = −5.48, ranking AUC over the incumbent's own dots 0.497, emission hit fraction 6.3% vs 10.5%. The out-of-fold mixture is +0.005093 but t = 0.64 (not significant). Details in `docs/research/h47-review.md`, receipt `registry/h47.json → screen`. |
| H47-2 | along-strike continuation of catalogue fault tips | **FALSIFIED** | 4,898 tip endpoints projected along local PCA strike land within 300 m of an off-catalogue SGMC fault 12–16% of the time (L = 5…40 px) against a 30.5% unconditional base rate. Also anticipated by family arms H18-3a / H33-5. |
| H47-3 | explicit 1 m lidar scarp channels / 3DEP–GeoDAWN tiles | **BLOCKED, source named** | competition data tab is login-walled; `www.sciencebase.gov`, `data.usgs.gov`, `storage.googleapis.com` return HTTP 000 from this sandbox. Not attempted, not faked. |
| H47-4 | cross-physics rank product (no supervision) | not run | superseded by the H47-1 failure: hand-built multi-physics products are already taken by the family (`H33-A`, `H46-2`, `h19-*`, `h27-4`). |
| H47-5 | collar/budget engineering on the incumbent geometry | not run | the collar (200 m) is already live-validated by H33-2-B2; the remaining budget question is dead-dot identification, which H47-1 measured at chance (AUC 0.497). |

**What the failure taught (feeds the next registration):** catalogue supervision cannot find
catalogue omissions — the model's ranking of the incumbent's own dots is at chance (AUC 0.497), and
its emission hit-rate is flat from 5k to 120k dots. The next registered hypothesis must bring a new
label source (or a verified hand-labelling protocol), not a new architecture.

## H47-1 — Catalogue-supervised multi-scale oriented-lineament detector with metric-algebraic dashed emission  *(rank 1, implemented this session)*

1. **Layers [OFFICIAL band names read from `training_features.tif` band descriptions]:** 1 `mag_anom`,
   2 `rtp`, 14 `tmi` (magnetic); 13 `iso_grav_anom` (gravity); 6 `tc` tilt angle/total curvature;
   12 `det_elev` (topography); 17 `cond_surf` and 15 `depth_to_base_surf` (subsurface/alteration);
   3 `tmi_hg`, 18 `iso_grav_anom_hg` (derivative products); 5 `iso_grav_anom_slope`, 10 `deq_n100a15`,
   16 `ieq_n100a15` as context. 55 features total: for each of the eight principal bands, |∇| at
   σ = 1, 2, 4 px, |Laplacian| at σ = 2 px, structure-tensor coherence at σ = 2 px (inner σ = 1,
   outer σ = 3), and a 4-px high-pass; plus raw + |∇₂| for the two horizontal-gradient bands.
2. **Physical signature:** a *learned* multi-scale oriented-lineament response. A fault produces a
   step/lineament in magnetics, a gradient in gravity, and a curvature/tilt anomaly; the model is
   asked to separate that joint signature from single-physics texture (geology contacts, playa
   edges, radiometric patchiness). The emission layer then applies the metric's own marginal rule
   (`src/gems46/metric.py`: a dot pays only if its kernel credit exceeds `0.2·DTI`), with a
   minimum separation so dots cannot shadow each other under the metric's max operation.
3. **Why it should catch a fault the catalogue lacks:** the published catalogue is a compilation of
   *surface-mappable* faults (USGS Quaternary fault maps + INGENIOUS), so its omissions are
   biased toward structures that are weakly expressed in any single dataset. A joint multi-scale
   descriptor that can only fire when several physics agree is the standard field criterion for
   accepting a fault with no clean surface trace, and it is exactly the class a single-dataset
   compilation under-records. **[OFFICIAL]** The competition's own staff confirm that the scored
   truth is "any fault pixel not already captured by USGS/INGENIOUS", including newly mapped
   geometry of existing systems (community thread 11536), and that known-fault pixels are masked
   from the penalty terms in both rounds (thread 11516).
4. **How it differs from this repository:** GEMSDOE46's own arms are hand-weighted transforms
   (`H46-1` DFA, `H46-2` geometric-mean corroboration, `R8` conformal spacing) that use the
   catalogue only as an exclusion mask; none trains on it. This arm (a) learns the joint
   descriptor from the catalogue under spatial blocking, (b) emits with an anti-shadowing greedy
   rule derived from the metric algebra rather than from a fixed spacing sweep, and (c) is screened
   against **both** an incumbent-matched instrument and the live-anchored ordering of three
   live-scored files. It also differs from the family's supervised arms: `GEMSDOE32`'s detector was
   described as harness-only; `GEMSDOE36`'s CNN used 8–16 input channels of regional/line context
   with a stress-orientation loss. The claim here is narrower and checkable — *placement precision
   at matched mass*.
5. **Expected DTI:** measured, not asserted: see `registry/h47.json` (`comparison` block). The
   screen is a *relative* instrument result; no leaderboard forecast is made.
6. **Cost / data:** ~15 min CPU, no new data. **Status: implemented; results in the receipt.**

## H47-2 — Along-strike continuation of catalogue fault tips  *(rank 2, FALSIFIED this session)*

1. **Layers:** any lineament field + the published catalogue geometry (`labels.tif`).
2. **Signature:** skeletonise the catalogue, take its endpoints, estimate the local strike by PCA
   of nearby catalogue pixels, and project the trace 0.5–4 km beyond the tip; emit there only where
   lineament evidence persists.
3. **Why it should catch a missing fault:** **[OFFICIAL]** newly mapped geometry of an existing
   fault system counts as a "new fault" (thread 11536), and expert mappers routinely extend a
   mapped trace beyond its previous end.
4. **Difference from this repository:** `H18-3a`/`H33-5` (family) emitted a *smoothed density* of
   tips and junctions; this candidate asks the sharper question — *is the along-strike projection
   itself preferentially near off-catalogue faults?*
5. **MEASURED VERDICT — FALSIFIED:** 4,898 catalogue endpoints; projecting along local strike and
   keeping only projections >500 m from any catalogue pixel, the fraction landing within 500 m of
   an off-catalogue SGMC fault falls from **0.152** (L = 0.5 km) to **0.118** (L = 4 km), while the
   *unconditional* random-placement base rate on the same mask is **0.305**. Tip projections are
   therefore worse than random placement at finding off-catalogue faults, and the live evidence is
   consistent: the one live-measured change to this family's best file was *deleting* dots within
   200 m of the catalogue, which raised the reported score 0.2708 → 0.2778.
6. **Cost:** low (3 min). **Do not spend a slot.**

## H47-3 — 1 m LiDAR scarp-chain detection on the GeoDAWN/3DEP DEM  *(rank 3, BLOCKED)*

1. **Layers:** the competition's `1m_DEM_links.csv` targets (USGS 3DEP/GeoDAWN lidar), reduced to
   scarp-height/`step_max`-style rasters, then chained as in the family's `H33-C`.
2. **Signature:** sub-100 m scarp segmentation, which the 100 m competition grid cannot express.
3. **Why it should catch a missing fault:** a <1 m throw produces no 100 m-averaged signal, yet it
   is exactly what lidar-based expert mapping adds to a catalogue built from coarser sources.
4. **Difference:** `H33-C` consumed a *pre-processed* lidar scarp product that is no longer in this
   checkout; this candidate would compute the scarp products directly from the DEM.
5. **BLOCKED — source named and checked:** `1m_DEM_links.csv` is inside the login-walled data tab
   (<https://www.drivendata.org/competitions/306/competition-doe-gems/data/>), and every host that
   would serve the tiles (dropbox.com, usgs.gov, s3.amazonaws.com, raw.githubusercontent.com) returns
   HTTP 000 from this sandbox (verified 2026-10-06, `registry/irregularities.json` IR-46-06). The
   free official source is **USGS 3DEP / GeoDAWN**
   (<https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7>); obtainability **not**
   verified here. Not proposed as viable until a machine with unrestricted egress fetches it.

## H47-4 — Cross-physics rank-product corroboration  *(rank 4, cheap ablation)*

1. **Layers:** magnetic group (1, 2, 14, 3), gravity group (13, 18, 5), curvature/topography (6, 12).
2. **Signature:** rank each candidate location by the *product of percentile ranks* of the
   lineament response in the magnetic and the gravity groups, i.e. demand that both physics rank a
   location highly; then feed the aggregate into the same dot emitter.
3. **Why it should catch a missing fault:** agreement of independent physics is the strongest
   available proxy for a structure with no surface expression, which is what a surface compilation
   omits.
4. **Difference:** `H33-A` required agreement of *orientation* from hand transforms; this is a
   distribution-free *rank aggregation* that never uses an orientation estimate.
5. **Expected DTI / cost:** low gain, low cost (~10 min). Run only if H47-1's screen leaves budget.

## H47-5 — Emission geometry: collar width and budget under the marginal rule  *(rank 5, engineering, not geology)*

1. **Layers:** none (post-processing of any belief field).
2. **Signature:** the metric's own algebra — a dot pays only if its expected kernel credit exceeds
   `0.2·DTI`; dots closer than the 300 m kernel shadow each other and pay the 0.2 false-positive
   tax for nothing.
3. **Why it should improve the score:** it does not find new faults; it stops paying for mass that
   cannot earn credit. The family measured one live step of exactly this kind (flank prune B=1→2).
4. **Difference from this repository:** GEMSDOE46 has never shipped a dot emitter; its arms emit
   the DFA/corroboration fields as continuous surfaces.
5. **Cost:** minutes; parameterised by the collar width (0–5 px) and the budget curve, and screened
   on the instrument ladder. **Risk:** this is the family's live-validated mechanism, so it is
   reported as an engineering setting, not as a new hypothesis.

---

## Ranked summary

| rank | hypothesis | expected DTI | cost | validation status |
|---|---|---|---|---|
| 1 | **H47-1** catalogue-supervised multi-scale lineament detector + metric-algebraic dashed emission | screened on two instruments, matched mass | ~15 min CPU | implemented, see `registry/h47.json` |
| 2 | H47-2 along-strike tip continuation | negative | 3 min | **FALSIFIED** (below random on the off-catalogue proxy) |
| 3 | H47-3 1 m lidar scarp chains | unknown | days + external data | **BLOCKED** (source named; egress verified unavailable) |
| 4 | H47-4 cross-physics rank product | low | 10 min | not run (no evidence it beats H47-1's joint model) |
| 5 | H47-5 collar/budget geometry under the marginal rule | multiplicative on any field | minutes | screened; family-precedented, not new |

## Instrument audit performed before any of this was believed

A proxy instrument is only usable if it ranks *known* live results correctly. The three live-scored
files owned by the family were re-scored under both instruments (`registry/h47.json` → `ladder`):

* **Un-stratified off-catalogue SGMC** (`d0 = 0`): 0.2600 → **0.1311**, 0.2708 → **0.1091**,
  0.2778 → **0.0929** — **inverted** against the live board.
* **Catalogue-block holdout** (truth = one block's catalogue, rest masked): mean 0.0634 / 0.0200 /
  0.0028 — **inverted**. This reproduces, on independent code, the family's own IR-46-04 finding.
* **Stratified off-catalogue SGMC** (truth = SGMC pixels > 500 m from any catalogue pixel):
  0.0864 < 0.0877 < 0.0885 — **monotone with the live board**, and monotone at d0 = 3, 10, 20 px as
  well.

Only the stratified instrument is therefore used for relative screening in this session, and even
that is described as a screen with a known bias (its truth is 56,822 px, far denser than the
estimated ~13,000-px hidden truth), never as a score forecast.
