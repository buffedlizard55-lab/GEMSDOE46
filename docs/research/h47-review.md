# H47 review — why the family plateaued at 0.2778, and what the H47-1 screen measured

Session: 2026-10-06 (GEMSDOE46 workspace, branch `arena/415e48b4-gemsdoe46`).
Everything below is measured in this checkout from hash-pinned inputs; the machine-readable copy is
`registry/h47.json` (`ladder`, `cv`, `calibration`, `comparison`, `screen`, `emission`).
Scores 0.2600 / 0.2708 / 0.2778 are **owner-reported** live results for three family files; the live
board attributes scores to participants, not files (see `registry/irregularities.json`).

## 1. The arithmetic of the plateau (this is the answer to "why 0.2778")

The three live-scored dot files are not three hypotheses. They are **one** dot set:

| file | dots | of which ≤200 m (2 px) from the published catalogue | live score |
|---|---|---|---|
| `gems25-dotted-h19-5-d2-8` (GEMSDOE25) | 44,090 | 6,436 (14.6%) | 0.2600 |
| `gemsdoe31-h27-4-solo-d28` (GEMSDOE31) | 40,199 | 2,545 (6.3%) | 0.2708 |
| `gemsdoe32-h33-h33-2-b2` (GEMSDOE32) | 37,654 | 0 | 0.2778 |

Measured here: `C ⊂ B ⊂ A` as pixel sets (Jaccard A–B 0.9117, A–C 0.8540, B–C 0.9367), and the
`d_cat > 2 px` part of all three files is **exactly the same 37,654 pixels**. The only difference
between the three scores is how many dots sit within 200 m of the catalogue — i.e. inside the band
the organizer's "known faults are masked" rule leaves ambiguous.

Fitting the published metric `DTI = T / (T + 0.2·FP + 0.8·FN)` with one core dot set:

* C's denominator `D_C ≈ 18,800` and numerator `T_C ≈ 5,223` reproduce both other live scores:
  removing/adding 2,545 dots predicts 0.2705 (measured live 0.2708) and 6,436 predicts 0.2600
  (measured live 0.2600).
* Each **dead** dot (no truth within 300 m) removes `0.2·T/D² ≈ 3.0e-6` of score; each **hit** dot
  adds about `(1−DTI)/D ≈ 3.8e-5`. The break-even hit probability is
  `0.2·DTI/(1−DTI) ≈ 7.7%`.
* At ~10.5% hit rate the incumbent's mass sits just *above* break-even, which is why the family's
  five independent 0.26–0.28 files cluster instead of separating.

So the plateau is not a feature-engineering problem, it is a **penalty problem**: roughly 32,000 of
C's 37,654 dots deliver no kernel credit and each pays 0.2. Removing the ~6,400 near-catalogue dead
dots is the only pruning the family actually performed, and it was worth +0.0069 and +0.0108 of the
score. If the remaining dead dots could be identified without the hidden truth, `D` would fall from
≈18,800 to ≈12,300 and the same numerator would be worth ≈0.42 — above today's leader (0.3774).
That gap is the whole game, and it is a *detection* problem: which dots are on new faults?

## 2. Instrument audit (which proxy is allowed to decide anything)

`registry/h47.json → ladder`, three live-scored files, two instruments, six stratification distances:

| instrument | 0.2600 | 0.2708 | 0.2778 | ordering |
|---|---|---|---|---|
| catalogue-in-block holdout (mean of 16 blocks) | 0.063394 | 0.020003 | 0.002791 | **inverted** |
| SGMC off-catalogue, d0 = 0 px (79,615 truth px) | 0.1311 | 0.1091 | 0.0929 | **inverted** |
| SGMC off-catalogue, d0 = 3 px (62,122) | 0.094174 | 0.095295 | 0.095386 | correct |
| SGMC off-catalogue, d0 = 5 px (56,822) | 0.0864 | 0.0877 | 0.0885 | correct |
| SGMC off-catalogue, d0 = 10 px (48,393) | 0.0807 | 0.0820 | 0.0829 | correct |

Only the **stratified** SGMC instrument (truth > 500 m from every catalogue pixel, catalogue masked)
reproduces all three known live orderings. Caveats that belong with any number from it:

* a uniform-random dot set of the same size scores `T = 4,140 ± 70` (3 trials), i.e. the instrument's
  dynamic range over "plausible geology" is roughly ±20% of a random baseline;
* for the same mass, the incumbent C covers `T = 4,737`, the out-of-fold H47 field `T = 5,015`, the
  shipped full-field H47 emission `T = 2,838`;
* the instrument's truth (1:50k–1:1M compilation lines at 100 m) is ~4× denser than the inferred
  hidden truth and is not the competition's label set.

## 3. H47-1: what was built, what it measured, and why it is HOLD

Built (55 features over the 19 official bands: multi-scale |∇|, Laplacian, structure-tensor
coherence, high-pass, plus the raw and local-context bands; LightGBM detector; dot emission with a
300 m separation rule and a 200 m catalogue collar). Trained leave-one-quadrant-out (4 folds, 240k
negatives each), then on the full raster.

Measured failures:

1. **Blocked detection is weak.** Out-of-fold AUC on held-out catalogue pixels = **0.5685**
   (20k positives vs 20k negatives per sample).
2. **Ranking does not concentrate.** Emission hit-rate (fraction of dots within 300 m of the
   stratified truth) is flat: 12.1% for the top 5,000 dots, 11.6% for 10,000, 10.4% for 37,654,
   9.4% for 120,000. A detector whose top 5,000 are barely better than its top 120,000 cannot place
   mass.
3. **Matched-mass screen (the pre-registered test) — FAIL.**
   * shipped full field: `DTI 0.053242` vs incumbent C `0.088516`, **delta −0.035274**, spatially
     paired over 127 truth-bearing blocks **t = −5.48**, ranking AUC over the incumbent's own dots
     **0.497** (chance), hit fraction 6.3% vs 10.5%.
   * out-of-fold mixture: `DTI 0.093609` vs 0.088516, delta **+0.005093**, but paired **t = 0.64**
     and AUC **0.5645** — not significant, and not the field that would ship.
4. Verdict written to `registry/h47.json → screen.verdict`: **HOLD_DO_NOT_SUBMIT**. Pre-registered
   pass condition: matched-mass delta > 0 **and** paired t ≥ 2 **and** AUC over the incumbent's dots
   ≥ 0.55 on the shipped field.

The file itself is format-perfect (`emission.zeros.audit`: single-band float32, template CRS/shape/
transform, 0 out-of-range pixels, 0 NaN in the zeros twin, 37,654 dots, pass=True) and unique
(Jaccard vs C 0.0151; vs R10 0.0025). Uniqueness and format were never the blocker — placement is.

## 4. Cross-checks done this session that close old questions

* **R10 ↔ C overlap (was blocking):** 260 shared pixels, Jaccard 0.0035. The identical 37,654-pixel
  counts are a coincidence, not a copy. R10 remains `HOLD_DO_NOT_SUBMIT` on its own proxy gate.
* **Nesting of the family files** (section 1) also removes the earlier multi-arm confusion
  (`GEMSDOE32/src/gems32/probes.py` H33-1/2/3 are three cuts of one dot set, all re-expressed as
  `solo d2-*`).
* The full field scoring *worse* than the out-of-fold mixture is itself a result: as an in-sample
  model it overfits catalogue-like structure, and the metric's payoff is on faults the catalogue
  does not contain.

## 5. Ranked next moves (with the measurement that justifies each)

1. **New supervision, not new features.** Every catalogue-supervised arm tested (family and this
   session) lands at 0.05–0.09 on the stratified instrument and ~10% hit rate — near break-even.
   The payoff is in faults the catalogue lacks. Candidates: the lidar/scarp product (blocked by the
   login-walled data tab here), USGS 3DEP/GeoDAWN tiles (blocked by sandbox egress), or labels built
   under the organizer's hand-labelling allowance (thread 11543), which must be saved and offered.
2. **Dead-dot identification without truth.** One measured test rules out the obvious version (the
   H47 field ranks the incumbent's hits at AUC 0.497). Remaining testable rules, all cheap on the
   existing pipeline: isolated dots without coherent linear support; dots whose local evidence in
   *all 19* bands is below the noise floor; dot pairs closer than the 300 m kernel. Each must clear
   the same matched-mass + paired-t screen before a slot.
3. **Do not re-run**: the catalogue-tip strike extension (measured below random: 12–16% hit rate vs
   a 30.5% unconditional base rate, 4,898 endpoints), tip/relay-ramp corridor priors (already shipped
   as GEMSDOE32 H33-5, predecessor H18-3a), and any learnt detector without a new label source
   (GEMSDOE36's U-Net plus H33-A…E cover it).

## 6. Limitations of this document

* The live-anchored fit (`T ≈ 5,223`, `D ≈ 18,800`) assumes each dead dot costs exactly 0.2 and each
  hit dot earns its kernel credit; it is a two-point fit to two score deltas, not a measurement of
  the hidden labels. The *nesting* result (identical 37,654-pixel core) is exact and independent of
  that fit.
* The instruments are proxies, as stated. A single proxy cannot settle a 0.01-scale question; the
  HOLD verdict rests on three independent signals (matched mass, paired blocks, ranking AUC) plus
  the flat hit-rate curve.
* No organizer receipt exists for any file→score pair in this repository, and none is claimed.
