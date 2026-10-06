# Candidate geological hypotheses, ranked — and what happened when the top one was tested

The brief requires 3–5 candidates that **have not been tried**, each naming (i) the specific
layer(s), (ii) the physical signature and transform, (iii) why it should catch a fault *missing from*
USGS QFaults / the INGENIOUS catalogue rather than one already in it, (iv) how it differs from
anything already in this repository, ranked by expected DTI gain against implementation cost, with the
top candidate validated on the spatially blocked holdout **before** a submission slot is spent.

The validation result is at the bottom: **H1 was tested this session and did not beat the shipped
arm**, so no submission slot was spent on it. The shipped file therefore remains the baseline
25-feature arm at the conformally selected spacing.

---

> **Register map (added 2026-10-06).** Three hypothesis registers exist and their identifiers
> overlap numerically. *This* file numbers the brief's in-repo feature hypotheses **H1–H5** (band
> combinations already inside `training_features.tif`). `docs/research/hypotheses.md` numbers
> external-data hypotheses **H46-1–H46-4** (OPERA InSAR, groundwater heads, ASTER, Landsat).
> `registry/hypotheses.json` is the machine register for shipped/blocked structural arms **H46-N**
> plus this session's **H46-R11-N**. Quote the file name with any identifier; a bare "H46-1" is
> ambiguous (IR-46-14).

## The ranking

| rank | hypothesis | layers | expected DTI gain | cost | status |
| --- | --- | --- | --- | --- | --- |
| 1 | **H1** release-controlled new-fault detection (seismicity × structure) | 10, 16 (+ 6, 12, 2, 17) | medium–high | low | **tested → not confirmed** (§result) |
| 2 | **H2** curvature-restoration residual (multi-scale structure tensor) | 6, 2, 12, 19 | medium | medium | queued, harness ready |
| 3 | **H3** lineament-network topology (skeleton graph, missing links, step-overs) | 12, 19, 6, 2 + 15 | medium | high | queued |
| 4 | **H4** conductive-clay / cover-thickness coincidence at depocentre margins | 17, 5, 11, 13, 18, 15 | low–medium | low–medium | queued |
| 5 | **H5** residual analytic-signal window anomaly (multi-scale 1VD/HGM) | 1, 2, 3, 9, 14 | low | low | queued |

No hypothesis in this table requires any **new external download** to be tested: every layer named is
already inside the official `training_features.tif`. Where an *extension* would need data, the free
official source is named and its reachability is flagged (the sandbox cannot reach most hosts; see
`docs/IRREGULARITIES.md`). That is the answer to the brief's "if a candidate can't be validated
without new external data, name the source and check it's obtainable": for H1–H5 the answer is that
the data is already in hand.

---

## H1 — Release-controlled new-fault detection *(rank 1)*

* **Layers.** 10 `distance-to-earthquake`, 16 `earthquake density`; interacting with 12 `detrended
  elevation`, 6 `tilt angle / total curvature`, 2 `RTP magnetic`, 17 `conductivity surface`.
* **Physical signature / transform.** Instrumental seismicity is a *release* field, not a *structure*
  field: its influence should decay like `exp(−d/λ)` from the release points, so the feature is a
  unit-free proximity score (global rank of band 10, and `exp(−d / median(d))`) **multiplied by the
  structural layers** — a ridge/curvature response that is *co-located with a seismicity cloud*.
  A gradient-boosted tree cannot construct such a product by itself, which is why the interaction, not
  the raw band, is the hypothesis. (A monotone transform of band 10 alone would add nothing: tree
  splits are invariant to monotone transforms of a single column.)
* **Why it should catch a *missing* fault.** A fault already in the compilation is already drawn;
  what a surface compilation structurally cannot contain is a structure that has ruptured or is
  creeping without a mapped surface expression — a blind fault, or a fault whose scarp is buried. The
  2020 Mw 6.5 Monte Cristo Range earthquake is the concrete example inside the scored footprint: a
  **28 km surface-rupture zone on largely unmapped parts of the Candelaria fault**, incoherent with the
  QFaults compilation (USGS publication 70220306; Koehler et al. 2021, SRL). Its epicentre
  (38.169 °N, 117.850 °W) maps to row/col **2836/1822**, which is **inside** the scored footprint (this
  was verified programmatically, `evidence/hypothesis_H1_release.json`).
* **How it differs from this repository's prior work.** Band 10 is **not in the shipped 25-feature
  plan at all**; band 16 enters only as a plain smoothed value. Nothing in the shipped stack uses
  seismicity as a *release* field, and nothing anywhere in this repository uses proximity to the
  *catalogue* (that is the documented, deliberate exclusion in `src/gems46/features.py`).
* **Cost.** Low: both bands are in the official raster; four new columns and one A/B run over the 16
  eligible blocks (≈ 7 minutes on this CPU-only box).
* **Sources.** USGS/ANSS ComCat <https://earthquake.usgs.gov/data/comcat/> (the free official
  catalogue behind bands 10/16); USGS <https://pubs.usgs.gov/publication/70220306>;
  <https://data.nbmg.unr.edu/public/OpenData/EQ/docs/Koehler_et_al_2021_SRL.pdf>.

### Result of the holdout test (this session)

Protocol: the 16 blocks that pass rule R1; the shipped arm (r = 8 px); identical emitter, prior
correction, truth subsample hash and model seed as the sweep; three feature sets — A = the shipped 25
columns (control), B = A + 3 proximity columns, C = A + 4 proximity × structure interaction columns.
The control **reproduced the saved sweep DTI exactly** (max |Δ| = 0.0 over all 16 blocks), so B and C
are paired against A rather than merely comparable.

| arm | mean DTI | mean Δ vs A | median Δ | blocks improved | sign test (2-sided) |
| --- | --- | --- | --- | --- | --- |
| A control (shipped) | 0.03846 | — | — | — | — |
| B proximity | 0.03863 | **+0.00017** | −0.00150 | 5 / 16 | p = 0.21 |
| C proximity × structure | 0.03898 | **+0.00051** | +0.000003 | 8 / 16 | p = 1.00 |

**Verdict: NOT CONFIRMED.** The interaction arm is +0.0005 DTI on the density-matched population —
about 1.3 % relative — with a median difference of essentially zero and a sign test that is exactly
consistent with chance (8/16 blocks improved). The additive arm is worse by the median. Recorded in
`evidence/hypothesis_H1_release.json`, verdict string in
`evidence/hypothesis_H1_verdict.txt`.

**Per the brief's rule, no submission slot was spent on H1.** The shipped file is unchanged.

**Descriptive follow-up (not a validation).** The shipped file emits 373 dots within 10 km of the
Monte Cristo epicentre (0.93 % of that 100 × 100 km box) against a global footprint density of
0.32 % — i.e. ~2.9× the average local density — and 2,618 dots within 30 km (0.73 %). Without a truth
vector for an unmapped fault this is not a score and is not treated as one; it says only that the
shipped field is not blind to that area.

---

## H2 — Curvature-restoration residual *(rank 2)*

* **Layers.** 6 `tilt angle / total curvature`, 2 `RTP magnetic`, 12 `detrended elevation`,
  19 `detrended elevation slope`.
* **Signature / transform.** A **structure tensor** over a 5–15 px window (eigenvalues λ₁ ≥ λ₂ give
  coherence `(λ₁−λ₂)/(λ₁+λ₂)` and orientation), plus a *restoration residual*: the difference between
  the field and a locally fitted plane/quadratic. This is a different geometric object from the
  shipped single-scale Hessian ridge: coherence is orientation-*consistency*, and the residual removes
  the regional tilt that dominates raw curvature.
* **Why it should catch a missing fault.** Compilations follow mapped scarps; a residual curvature
  field responds to subdued lineaments under alluvium and is invariant to regional tilt, i.e. it
  targets exactly the lineaments that mapping campaigns miss. It also suppresses the "everything
  looks like a lineament" failure mode of raw curvature on a tilted regional field.
* **Differs from prior work.** The shipped plan computes `L_nn` ridges and gradient magnitudes at
  σ ∈ {1, 1.5, 2, 4} and a scale-space Laplacian; it has **no** structure tensor, no coherence, no
  orientation and no local-plane residual.
* **Cost.** Medium (new feature code + one A/B run using `scripts/hypothesis_release.py`'s harness).
* **Source.** Lindeberg 1998 IJCV 30(2):117–154 (scale-space ridge/edge theory, already the basis of
  the shipped transform).

## H3 — Lineament-network topology *(rank 3)*

* **Layers.** Lineament masks derived from H2's residual/coherence on 12, 19, 6, 2, plus 15
  `depth-to-basement` for through-going structure.
* **Signature / transform.** Skeletonise the lineament mask and build a graph; per-pixel features are
  (a) distance to the nearest skeleton **endpoint**, (b) orientation agreement between segments across
  a gap ("would this segment continue?"), (c) step-over distance between parallel segments, (d)
  junction density.
* **Why it should catch a missing fault.** The scored population plausibly contains faults that
  *complete a network* — the link between two mapped segments, or a structure inside a step-over —
  which is where the BRIDGE final report places the highest permeability, and which compilations
  typically omit because they stop at basin fill.
* **Differs from prior work.** Every shipped feature is pixel-local; this is topological and
  non-local.
* **Cost.** High: skeletonisation of the raster, graph construction, and a longer compute wall on a
  4 GB box.
* **Source.** <https://gdr.openei.org/files/1682/BRIDGE_Final_Report_SAND2025-01826.pdf>
  (step-over / fault-intersection targets; HGM and 1VD derivatives).

## H4 — Conductive-clay / cover-thickness coincidence *(rank 4)*

* **Layers.** 17 `conductivity surface`, 5/11/13/18 (isostatic gravity slope/vertical/horizontal
  gradients), 15 `depth-to-basement`.
* **Signature / transform.** A coincidence score: conductivity high **and** gravity-gradient /
  depocentre margin **and** thick cover — a "hidden fault" indicator, since a fault under cover has no
  surface expression but its damage zone alters clays.
* **Why it should catch a missing fault.** Basin-margin faults beneath cover are exactly what a
  surface mapping programme under-represents; the conductivity layer responds to alteration, not to
  topography.
* **Differs from prior work.** The shipped plan uses band 17 as a plain smoothed column; no
  multi-layer coincidence is computed.
* **Cost.** Low–medium.
* **Source.** BRIDGE report (basin-fill resistivity as cover proxy); Granite Mountain temperature
  study, <https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Adams.pdf> ("most Great Basin
  resources are blind, with no surface manifestation").

## H5 — Residual analytic-signal window anomaly *(rank 5)*

* **Layers.** 1 `magnetic anomaly`, 2 `RTP`, 3 `TMI horizontal gradient`, 9 `TMI vertical gradient`,
  14 `TMI`.
* **Signature / transform.** Analytic-signal amplitude and its residual after removing a
  large-window median, taken at 5–15 px windows — short-wavelength lineaments that survive the
  regional field.
* **Why it should catch a missing fault.** Magnetic lineaments mark buried contacts/intrusions
  independently of topography, so they can outline structures with no surface expression.
* **Differs from prior work.** The shipped plan has TMI/RTP ridges and gradients but no analytic
  signal and no windowed residual.
* **Cost.** Low. Expected gain modest: the magnetic family is already represented and is noisy in this
  survey.
* **Source.** BRIDGE report (1VD/HGM/RTP processing chain).

---

## What would have to be true for H1 to be revisited

The negative result is about *this* feature construction on *this* proxy, not about the physics. It
would be worth revisiting if any of the following becomes available: a seismicity catalogue with
relocated hypocentres and focal mechanisms (USGS ComCat, free and public — the sandbox cannot reach
it, so a mechanism-aware proximity field has **not** been tested); an independent, non-catalogue fault
map to score against (i.e. exactly what the private test labels are); or a deep model that can use the
release field and the structural stack jointly rather than through hand-built products. Until then the
honest statement is the one above: +0.0005 DTI, p = 1.00, not shipped.

---

## R11 — what this session tested instead (2026-10-06)

The brief's DFA hypothesis and three further candidates were preregistered in
`docs/research/session-r11-plan.md` **before** any field was computed, and executed as
`scripts/run_r11.py` (Pass 1) plus `scripts/refine_r11_mass.py` (Pass 2, which corrected two defects
in Pass 1's own mass rule and gate — see `docs/research/r11-review.md`).

| id | candidate | verdict |
| --- | --- | --- |
| H46-R11-1 | GeoDAWN radiometric compositional contrast (K, Th/K, U/K, U/Th — absent from the official 19 bands) | part of the **shipped R11 primary**; fused proxy gate passed; not ablated separately |
| H46-R11-2 | 1 m lidar scarp matched detector (12 channels, coherence-weighted) | part of the **shipped R11 primary**; not ablated separately |
| H46-R11-3 | local DFA scaling-regime break, re-localised (the brief's hypothesis) | **NOT CONFIRMED**: 0.08973 mean blocked proxy DTI at matched mass vs 0.09130 for the incumbent file and 0.17061 for the primary; artefact published anyway (max |r| 0.1406 with prior files) |
| H46-R11-4 | dual-physics strike agreement | **not run**: shares its evidence with the potential-field family already inside the primary; recorded rather than dropped silently |

Two facts about the official data were measured here and are worth carrying forward: the official
19-band stack contains **no magnetic curvature band at all** (band 6, labelled "tilt angle or total
curvature", correlates +0.997 with the GeoDAWN radiometric total count — IR-46-13), and the K/Th/U
and ratio grids are therefore genuinely new information (DOI 10.5066/P93LGLVQ). Any hypothesis in
the H2–H5 table above that names band 6 as a curvature layer should be re-specified before it is run.
