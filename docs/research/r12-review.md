# R12 scientific review — 2026-10-06

**Artefact:** `docs/r12/gems46-r12-scarp-rad-concordance-23e807e2de9f-zeros.tif`
**Receipt:** [`../r12/receipt.json`](../r12/receipt.json) (copied to `registry/r12.json`)
**Preregistration:** [`session-r12-plan.md`](session-r12-plan.md), written before the detector existed
**Previous session:** [`r10-review.md`](r10-review.md) — a failed gate, published as a negative result

---

## 1. Executive decision

R12 is a **unique, independently generated, format-valid GeoTIFF** that **passed the preregistered
proxy-improvement gate**: on locked spatial blocks that were never used to choose its configuration it
beat every comparator, including its own two components and the two previously shipped files, with a
seeded paired block-bootstrap interval excluding zero.

It is therefore cleared for a submission slot under this repository's own rule. It carries **no
leaderboard score**, and nothing in this pipeline submitted it: the organiser's submission form is
login-walled and this environment has no credentials.

R10's stricter gate — which additionally refuses any block dropped for zero shared emission capacity —
reads *fail*, because three locked blocks were dropped when a gapped comparator could emit nothing
there. Both readings are published in the receipt (`gate_preregistered`, `gate_strict_r10_style`). The
preregistration governs, and the dropped blocks are conservative for R12: they are blocks with no LiDAR
coverage, exactly where R12's radiometric fallback is the only thing that can emit.

## 2. The hypothesis, and what survived it

**Claim tested (H46-R12-A).** A fault scarp is an *oriented* slope break in 2 m LiDAR topography, and
the same structure breaks the top 0.3–0.5 m sampled by airborne gamma-ray spectrometry. Two physically
independent sensors agreeing should be more specific than either, and should find traces a
surface-mapped catalogue missed.

**What the selection blocks said.** The symmetric version of that claim is **false on this
instrument**:

| configuration (selection blocks) | mean DTI |
|---|---:|
| w = 0.25, fallback q = 0.90, no thinning (**frozen**) | **0.15292** |
| w = 0.25, fallback q = 0.99, no thinning | 0.15017 |
| w = 0.50, fallback q = 0.90, no thinning | 0.14731 |
| w = 0.00, fallback q = 0.90, no thinning | 0.14390 |
| w = 0.00, no fallback, no thinning | 0.13790 |
| w = 1.00, fallback q = 0.90, no thinning | 0.12979 |
| every thinned variant | 0.11387 – 0.12989 |

Two negative results are recorded rather than buried:

* **A strong concordance gate destroys the signal.** Gating morphology on radiochemistry (w = 1) scores
  *below* morphology alone. The weaker sensor is not an equal partner; it is only worth ~25 % weight as
  a reweighting. This is consistent with the exploratory screen, where a symmetric rank product scored
  0.090–0.108 against 0.144 for the better part alone.
* **Ridge-axis thinning (H46-R12-B) is falsified.** Non-maximum suppression perpendicular to strike cost
  0.010–0.029 DTI in every one of the fifteen configurations where it was tried. The metric-algebra
  argument for putting dots exactly on the axis is not wrong in principle, but this operator does not
  implement it well: it discards the graded evidence the greedy emitter uses to choose *which* trace to
  follow.

What survived is the third, less glamorous part of the hypothesis: **coverage-aware fallback**. The 2 m
LiDAR product covers 75.13 % of the emittable domain, so a LiDAR-only detector is structurally blind over
the remaining quarter. Admitting radiometric candidates there, capped at the 90th percentile of the
morphology score so they cannot outrank good morphology elsewhere, raised the selection mean from
0.14390 to 0.15292.

## 3. Locked decision (read once, after freezing)

6×6 partition, three-pixel interior guards, the published catalogue excluded by a fixed 200 m buffer
(never tuned — see IR-46-04), identical emitted mass per block for every method. Selection = odd
`(i + j)` blocks; decision = even `(i + j)` blocks. R10 used a 4×4 partition, so no block edge is shared
with the previous session.

| field, re-emitted by the same rule | mean locked DTI | pooled locked DTI | all locked blocks, full budget |
|---|---:|---:|---:|
| **R12 (this candidate)** | **0.10420** | **0.13912** | **0.15586** |
| LiDAR morphology alone (component) | 0.09368 | 0.12467 | 0.12413 |
| Gamma-ray alone (component) | 0.07309 | 0.09611 | 0.10775 |
| GEMSDOE32 file (owner-reported 0.2778) | 0.06781 | 0.08870 | 0.09967 |
| R10 DFA crossover (previous session) | 0.05294 | 0.07777 | 0.04072 |
| RTP magnetic gradient (classic arm) | 0.05228 | 0.06926 | 0.08732 |

* Paired mean difference vs the best comparator: **+0.01052**; seeded block-bootstrap 95 % interval
  **[+0.00140, +0.02121]**.
* Ten locked blocks were evaluable at matched mass; three were dropped for zero shared emission
  capacity. The third column keeps all thirteen and charges each method for its own coverage gaps: the
  ordering is unchanged and the margin widens to +0.03174 over the best comparator.
* These are **proxy measurements under one emission rule**, not scores of the original files and not
  predictions of leaderboard values.

## 4. Is this a new hypothesis or a relabelled one?

Three measurements, because they answer three different questions.

| compared with | emitted-pixel / raw-field correlation | Jaccard of emitted pixels | smoothed-field Spearman |
|---|---:|---:|---:|
| GEMSDOE32 file (owner-reported 0.2778) | +0.0054 | 0.0051 | +0.5325 |
| R10 DFA crossover file | +0.0004 | 0.0037 | −0.1018 |
| RTP magnetic gradient field | +0.1150 | — | +0.2448 |
| LiDAR morphology alone (own component) | +0.7350 | — | +0.7130 |

* **Not a renamed submission.** The emitted dot sets are almost disjoint from both shipped files
  (Jaccard ≈ 0.005) and the pixel-level correlation is ≤ 0.006.
* **Not a relabelled gradient/curvature arm.** Correlation with the magnetic-gradient field tops out at
  0.245 (smoothed Spearman).
* **Honest caveat.** The *smoothed* field still correlates +0.53 (Spearman) with the GEMSDOE32 file at
  coarse scales. Two fault-probability fields over the same terrain share regional structure. R12 is
  pixel-distinct and uses sensors that field never touched, but it is **not** spatially independent of
  the family's best field, and it should not be described as such.
* **Not unprecedented across every GEMSDOE site.** A sibling site (7GEMSDOE, `lidarscarp-ridge-top2pct`,
  owner-reported 0.1461) used a LiDAR ridge alone. What is new here is the sensor *pair*, the
  coverage-aware fallback, and the validation; the claim of novelty is limited to this repository plus
  pixel-level distinctness from every raster inspected.

## 5. The standing question: why 0.2778, and can it be beaten?

**Why it scored what it scored.** The mapping of 0.2778 to `h33-h33-2-b2` is owner-reported, not an
organiser receipt: the official board lists a *participant* score with no file name or hash, and the
GEMSDOE32 page itself labels that artefact unscored (IR-46-01). What can be said from the metric alone
is that 0.2778 is consistent with a sparse emission of 37,654 unit-mass dots covering roughly 5,224
hidden truth pixels, i.e. a field that puts about one dot in seven within 300 m of a truth pixel and
spends the rest of its mass on cheap partial credit above the `0.2 × DTI` break-even bar. Sparse
thinning near the published catalogue helps because the organiser masks catalogue pixels from scoring,
so mass spent there is pure cost — but "removing catalogue-adjacent dots is free" is an approximation
(`M = T`), not an identity, and this session has no receipt that would settle it.

**Can it be beaten?** In principle yes, and the arithmetic says exactly how much is needed — see below.
This session's honest answer is: *not demonstrated*. R12 beats the restored GEMSDOE32 file by a factor
of 1.54 on the locked proxy instrument (0.10420 vs 0.06781 mean block DTI, 0.13912 vs 0.08870 pooled),
but a proxy ratio is not a score ratio, the proxy is reused, and the only way to convert this into a
claim is an organiser receipt.

Exactly, from the official metric: `DTI = T / [0.2(T + S − M) + 0.8G]`, and with `M = T` (each
credit-earning dot best-covering a distinct truth pixel) the denominator at `S = 37,654`,
`G ≈ 14,089` is ≈ 18,802. So a live 0.2778 implies `T ≈ 5,224` covered truth pixels and the observed
leader 0.3774 implies `T ≈ 7,094` — **36 % more coverage at identical emitted mass**. Coverage is the
only numerator; mass is only a cost.

The budget was deliberately **not** changed. On a truth-mass-matched copy of the proxy (whole connected
components retained up to 14,034 px, seeded) the shipped mass is still on the rising part of the curve
(0.40× → 0.05787, 0.67× → 0.07997, 1.00× → 0.09847, 1.50× → see receipt), so reducing mass to chase the
family's mass/score correlation would have been unjustified. That correlation (Spearman −0.907 across
the ledger, IR-46-07) is driven by files with orders of magnitude more mass, not by the 15k–56k range.

## 6. Verification performed this session

1. **Data.** All four organiser/proxy rasters and all three USGS layers restored from hash-pinned public
   mirrors and re-verified (`registry/data_manifest.json`). The `geodawn_rad` and `geodawn_extensions`
   sha256 values equal the `product_sha256` recorded in the mirror's own receipts — an independent
   provenance cross-check.
2. **Metric.** `tests/test_metric.py` against the published worked example and an O(N²) transcription;
   `components_binary` against the 29-offset transcription.
3. **New module.** `tests/test_concordance.py`: 12 tests covering the rank transform (including the
   constant-channel case, which was a real bug — an arbitrary tie-broken ramp), the structure tensor
   (recovers the orientation of a synthetic horizontal ridge), the thinning operator (narrows the band
   onto the axis), the concordance weight, and the fallback cap (fallback candidates provably cannot
   outrank good morphology).
4. **Artefact.** Re-read from disk after writing: single band, float32, EPSG:32611, 3730 × 3292,
   transform equal to the template, every value finite and in [0, 1], no nodata tag, 37,654 positive
   pixels, and pixel-inequality against every raster in the repository.
5. **Site.** Generated from the receipt; CI asserts the committed pages are byte-identical to a fresh
   build, and `tests/test_site.py` asserts every local link resolves and the download precedes the
   analysis.

## 7. Limitations

* The off-catalogue SGMC proxy is **reused** and imperfect; it is not hidden competition truth, and its
  source maps are 1:50,000–1:1,000,000. Beating it is not a score forecast.
* The 6×6 selection blocks come from the same proxy family earlier sessions used. The locked/selection
  split removes tuning leakage inside this session; it does not make the instrument new.
* Results are conditioned on 74.9 % LiDAR coverage of the emittable domain. A quarter of the footprint
  is scored on radiometric evidence alone.
* The mirrored USGS products are **rank-quantised uint8** over the 1st–99th percentile of each channel.
  Only ordering and structure are meaningful; no physical unit survives, and no ratio here is a
  geochemical quantity.
* Mirror hashes prove consistency with a public USGS data release, not organiser authentication.
* One earlier execution of the same script evaluated the locked set with an identical frozen
  configuration while the reporting statistics were being extended. No selection decision was informed
  by it; the frozen configuration is determined by selection blocks alone. This is recorded rather than
  left implicit.
* **Blocked:** hypocentre lineaments from the USGS ANSS catalogue. `earthquake.usgs.gov` returns
  HTTP 000 from this sandbox (re-measured 2026-10-06); the agent's own web tool reaches the service, but
  transferring ~10⁴ catalogue rows through it would not be reproducible by CI. The source is named in
  the plan instead of being assumed away.

## 8. Next-session priorities

1. **Get one organiser receipt.** Submit R12 to a weekly slot (human action) and record score + file
   hash + note together. Without a receipt, every file-to-score mapping in this family stays
   owner-reported (IR-46-01/02).
2. **Test the fallback's own quality.** 24.87 % of the emittable domain is carried by radiometric
   evidence whose locked DTI is 0.073 — better than magnetics but well below morphology. A better LiDAR-gap
   detector (e.g. gamma-ray *lineament* extraction rather than gradient magnitude) is the largest
   identified headroom inside this design.
3. **Strike-continuity gap closure (H46-R12-D)** using the unused LiDAR `strike` and `coh100` bands is
   still untested here; a sibling site tried a topographic version (owner-reported 0.2449).
4. **Localise the emission.** Thinning failed, but the argument stands: dots on the trace axis earn
   k = 1 instead of ≈ 0.67. A sub-pixel across-strike parabolic fit is the next operator to try, and it
   must be validated as a new preregistered ablation, not tuned on the locked blocks.
5. **Do not re-tune R12 on these blocks.** Any further configuration search needs a new locked region.

## 9. Core values applied

**Maximize P(Win):** the two parts of the hypothesis that failed are published next to the part that
worked, the stricter gate is reported alongside the preregistered one, and the candidate is released
for a slot only because a preregistered rule was met — not because the result was convenient.
**Own the Outcome:** our own defects found this session (the rank-transform tie-break, the unsliced
block field, the over-strict inherited gate) were fixed in the open, with tests, rather than papered
over.

## 8. Re-measurement on the instrument that reproduces the known live ordering

Merging `origin/main` brought in the H47 instrument ladder, which is a direct check on §3: it measured
the three live-scored family files (0.2600 / 0.2708 / 0.2778) on six instrument variants and found
that the un-stratified off-catalogue SGMC proxy **inverts** that ordering, while SGMC truth stratified
at ≥3 px from the catalogue (default 5 px = 500 m), with the catalogue masked as `known` exactly as the
organiser confirmed for the live scorer, reproduces 0.2600 < 0.2708 < 0.2778. §3 above used a 200 m
exclusion — a variant that ladder never validated (IR-46-21). The rule that decides the status was
amended to require **both** instruments *before* this measurement was computed
(`session-r12-plan.md` §7.1).

Measured on `gems47.proxy.instrument_sgmc_stratified`, `d0 = 5 px`, whole footprint, matched mass
37,654. The stratified truth is **56,822 px — identical to the d0 = 5 row of the H47 ladder**, which
confirms the same instrument rather than a look-alike.

| field, re-emitted at the same mass | covered truth `T` | DTI | dots within 300 m |
|---|---:|---:|---:|
| **R12** | **9,003** | **0.16622** | **16.42 %** |
| LiDAR morphology alone | 8,386 | 0.15506 | 15.80 % |
| Gamma-ray alone | 5,170 | 0.09638 | 10.52 % |
| GEMSDOE32 file (owner-reported 0.2778) | 5,080 | 0.09474 | 10.50 % |
| RTP magnetic gradient | 4,022 | 0.07519 | 8.32 % |
| R10 DFA crossover | 3,628 | 0.06787 | 6.88 % |
| uniform random at matched mass | 3,695 | 0.06912 | 9.81 % |

Three things follow, and they should be read together:

1. **The candidate survives the instrument that can invert the ranking.** +0.07148 over the incumbent,
   1.75×, and both preregistered readings now agree. R12 is `PROXY_GATE_PASSED_NOT_SUBMITTED`.
2. **The gap is not a small perturbation of the family's field.** Every "plausible geology" field
   previously measured here sat within ±20 % of a random baseline (`T ≈ 3,700–5,100`); R12 is at
   `T = 9,003`, 2.4× random. That is a different signal, consistent with two sensors the family's
   19-band stack does not contain.
3. **It is still not a score.** The same instrument puts the incumbent at 0.09474 where the live board
   says 0.2778, so absolute proxy values are not forecasts and the 1.75× ratio is not a promised
   multiplier. The hit-rate reading (16.4 % vs 10.5 %) is the one that maps onto the H47 finding that
   the family's whole plateau is a dead-dot problem: R12 places about half again as many dots on truth.

Honest counterweights: this instrument is the same SGMC compilation used since H46, only stratified;
the LiDAR/gamma-ray layers are rank-quantised uint8 from a public mirror, not organiser-authenticated;
the stratified measurement is whole-domain rather than blocked, so no independence interval is
attached to the +0.07148; and the 16.4 % hit rate is against SGMC lines, not hidden labels.
