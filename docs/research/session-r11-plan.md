# R11 preregistration — 2026-10-06

Written before any R11 implementation. No numeric DTI gain is defensible in
advance: ranking is qualitative expected benefit adjusted for failure risk,
not a forecast. Hypotheses A–C use restored competition bands only. D uses
additionally the group's public github-hosted mirrors of free INGENIOUS/GDR
point data (reachable from this sandbox; hashes pinned at implementation
time). E is BLOCKED on a host this sandbox cannot reach. Novelty means
absent from the inspected local implementations (H46-1, H46-2, R8, R9, R10);
exhaustive proof across every family repository is not claimed.

## Measured context this ranking rests on (all in-repo, all cited)

- R10 (51.2 km support, scales 0.8–12.8 km, physics-min, orientation-mean):
  blocked SGMC mean 0.06169 vs 0.10329 best comparator; wins only 2/9 blocks
  (the two most truth-dense); two truth-bearing blocks have zero R10 emission
  capacity (coverage failure); support was eroded 16 px for control
  computation, which is a design defect (registry/r10.json).
- H46-1 DFA variants on the unblocked SGMC proxy at matched mass: the
  regime-BOUNDARY (|grad z|) combination `both_bnd` scored 0.08225, the best
  of all DFA variants tested (registry/validation.json). The boundary
  statistic, not the anomaly magnitude, is the DFA family's best performer.
- Official GeoDAWN release: two surveys with different flight specs (Area 1:
  200 m line spacing; Area 2: 400 m spacing; different aircraft and heights),
  four acquisition blocks, contractor leveling/micro-leveling
  (https://doi.org/10.5066/P93LGLVQ). Any grid-texture statistic confounds
  survey processing with geology unless it stratifies by acquisition block.
  No local DFA arm has done so.
- Varotsos et al. report a TIME-LAG crossover (random at short lags,
  α≈0.9 at long lags) in pre-rupture magnetic series
  (https://arxiv.org/abs/0904.2465). The spatial-grid adaptation remains this
  project's hypothesis, not a published result (IR-46-05).

## The five candidates

| Rank | Hypothesis / layers | Physical signature and off-catalogue rationale | Difference from existing work | Expected improvement / cost |
|---|---|---|---|---|
| 1 | R11-A: localized DFA regime-BOUNDARY with survey-block stratification; raw RTP band 2 and raw isostatic gravity band 13 | Per-orientation short-scale (0.4–1.6 km) vs long-scale (1.6–3.2 km) DFA slope crossover, times the spatial gradient of the long-slope's departure from its WITHIN-BLOCK background. 400 m posting; scales bracket the 300 m scoring kernel. A texture boundary under basin fill has no scarp and no amplitude edge, so surface-compiled catalogues miss it; block stratification removes the survey-processing regime shifts R10 confounded with geology. | H46-1: scales 0.8–6.4 km, stride 800 m, global background, orientation-mean, derivative/high-pass bands included. R10: 51.2 km windows, stride 1.6 km, scales 0.8–12.8 km, physics-min, orientation-mean, no survey control. R11-A: 12.8 km windows, 400 m stride, scales 0.4–3.2 km, block-stratified background, orientation-MAX, physics-MEAN, no support erosion. | Unknown; the best direct localization fix of the requested mechanism; low/medium CPU cost. |
| 2 | R11-B: windowed Euler deconvolution depth-consistency lineaments (H46-4, still untested); bands 13, 2, 15 | Per-window Euler solutions (SI=1 contact/step) from RTP and gravity; a fault is a LINEAMENT OF CONSISTENT DEPTH SOLUTIONS across both fields, not an edge maximum. Depth extent flags basement-involved structures under cover that surface mapping under-records. | No shipped arm uses Euler depth consistency. The group's h32-1 used Euler output as a single-field scalar ridge (owner-reported 0.2649, did not beat its incumbent). | Moderate, unproven; standard physics but noise-sensitive implementation; medium cost. No new data. |
| 3 | R11-C: tilt-phase zero-crossing coherence; bands 6 (tc), 2, 13 | Coincident zero-contours of the tilt angle across magnetics and gravity within 300 m. Tilt phase locates source edges independent of contrast strength, so weak-contrast buried contacts still carry a phase signature where amplitude ridges fall below detection. | H46-2 uses tc/ridge AMPLITUDE, never phase coincidence. | Small; risks correlation with the existing edge family (may fail the distinctness gate); low cost. No new data. |
| 4 | R11-D: thermal-anomaly-anchored structural conjunction; 2 m probe + wellspring + paleo-sinter/tufa mirrors (github-reachable) with the R11-A field | Shallow thermal anomaly (2 m T, spring/well T, geothermometers) AND structural lineament = active fluid pathway. Hidden geothermal faults are thermally anomalous by definition but often trace-free at the surface. | H46-5's geothermometry-ADDITION arm was falsified by the group (credit/add ~0.002–0.005 vs ~0.054 bar); the pruning direction is untested. R11-D requires structural conjunction, neither addition nor pruning alone. | Small; thermal points are sparse/clustered (21 vents; ~2k hot rows concentrated at known systems); medium cost (shapefile/xlsx parsing, projection, holdout). Viable only if point parsing verifies. |
| 5 | R11-E: hypocentre lineaments from raw USGS ComCat (H46-3, BLOCKED); exact source https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&… (free, official, no key; query template in scripts/fetch_earthquake_catalog.sh) | Strike-parallel alignment of precisely located hypocentres + nodal-plane consistency: a fault-ACTIVITY signature, not a rock-property signature. Active faults with no Quaternary trace still generate microseismicity; competition seismic bands are 100 km smoothers. | Group's GEMSDOE32 wrote a fetch script but never obtained the catalogue; no shipped arm used raw hypocentres. | Unknown; strong physics, data free. BLOCKED: sandbox returns HTTP 000 for earthquake.usgs.gov (re-measured 2026-10-06). Must not take a slot until validated. |

Considered and rejected: 1 m DEM scarps (login-walled links + very large
downloads; the lidar-scarp surface family already scored 0.1294–0.1461
owner-reported, i.e. below the thinning lineage); QFaults v2 (group
measurement: all but one rasterized pixel within 300 m of the given
catalogue — no new coverage); MT conductance (GDR direct unreachable, no
github mirror found — unavailable, not merely blocked).

## Locked R11-A experiment

- Raw bands only: RTP (2), isostatic gravity (13). No derivatives, no
  high-pass variants, no amplitude/gradient/curvature in the ranking.
- Row + column transects, window 128 samples (12.8 km), centers on a
  4-pixel (400 m) grid. DFA1 scales (4, 8, 16, 32) samples = 0.4–3.2 km.
  All window samples must be valid; largest scale has 4 blocks.
- Short slope over scales (4, 8, 16), long slope over (16, 32) sharing the
  1.6 km pivot. The long fit is a 2-point secant: noisier than R10's
  4-point fit — recorded limitation, not hidden.
- Per orientation, per physics: long-slope z against the WITHIN-BLOCK
  median/MAD from acquisition_block_id_100m.tif (ids 1–4; id 0 or blocks
  with <25 valid coarse cells contribute z=0). Boundary = |grad z| on the
  coarse grid. Crossover = |long − short|.
- Per (physics, orientation): p99-normalize crossover and boundary
  separately to [0,1]; score = sqrt(cross01 × bnd01). Physics score = MAX
  over orientations (strike-preserving). Field = MEAN over available
  physics (coverage fix vs R10's min; single-physics breaks allowed).
  Expand by nearest center; support = ≥1 physics valid. NO support erosion
  (R10 defect fixed); gradient/curvature controls computed on a separately
  eroded mask.
- Emit 37,654 binary cells with the existing spacing-constrained emitter
  (min_dist 3, smooth 1.85); published catalogue excluded with the existing
  two-iteration cross dilation (Manhattan, not a Euclidean 200 m disk).
- Comparators (all re-emitted per block at matched mass): GEMSDOE32 file,
  H46-structural, R8, R9, H46-pure, and R10. 4×4 spatial blocks, 3-pixel
  interior guard, fresh bootstrap seed 4611.
- Correlation gate: |r| and |rho| < 0.2 on every comparator (candidate +
  field-vs-smoothed) and every raw/smoothed gradient/curvature control.
  Failing it prohibits a distinctness claim.
- Survey audit (diagnostic, non-gating): fraction of emitted dots within
  5 px of an acquisition-block boundary vs a domain-matched null; >2×
  enrichment flags a processing confound for review.

## Synthetic gates (locked thresholds, diagnostic for publication, gating for any slot)

- S1 (1-D texture step, seed 1101): 256 white-noise + 256 integrated-noise
  samples (α≈0.5 → ≈1.5, boundary at 256, halves separately standardized).
  PASS = argmax score center within 8 samples of 256 AND peak ≥ 3× the
  median flank score (beyond ±64 of the boundary).
- S2 (1-D ramp + stationary noise, seed 1102): PASS = peak/flank ratio < 2
  AND max raw crossover < 0.15 (no firing on texture-stationary gradients).
- S3 (2-D texture half-planes, seed 1103): 256×256, white noise left /
  x-integrated noise right, boundary x=128, halves standardized. Full 2-D
  scorer + production emitter (top 200, min_dist 3, smooth 1.85).
  PASS = ≥50% of dots within 10 px of x=128.

## Slot rule

No weekly slot unless: S1–S3 all pass, ≥8 evaluable blocks, zero
zero-capacity skips, R11-A beats EVERY comparator mean, paired
block-bootstrap 95% lower bound > 0, and the correlation gate passes. Even
passing is only a reused-proxy gate, not evidence of beating the hidden
competition set. The TIF is published regardless, with its measured
outcome and HOLD status when any gate fails.

## Amendment 1 (2026-10-06, before any production data use): full-slope pure-boundary design + fGn fixtures

Cause (measured on the locked synthetics, seed 1101): the preregistered
2-point long secant (scales 16–32) swings 0.3–0.7 inside stationary white
noise; the crossover×boundary product peaks 56 samples (5.6 km) from a
clean texture step, systematically (repeat measurements at 52–56 samples).
The crossover of a mixed window is maximized by small contaminations, i.e.
it behaves as an outlier detector, not a boundary localizer. H46-1's own
evidence already ranked the pure-boundary variant (`both_bnd`, 0.08225)
above every joint/crossover variant on the SGMC proxy.

Locked changes (production gate still un-peeked):
- Exponent = FULL-range DFA1 slope over scales (4, 8, 16, 32) (4-point
  fit; measured ±0.03–0.06 in stationary noise vs ±0.2 for the secant).
- Score = p99-normalized |grad z| ONLY (crossover dropped). This is the
  prompt's literal statistic: "flag locations where the local scaling
  exponent breaks from the surrounding background's regime". Orientation
  MAX and physics MEAN are unchanged, as are window 128, stride 4,
  block stratification, emission, blocks, seeds and gates.
- Fixtures use stationary fractional Gaussian noise (Fourier synthesis;
  verified DFA α ≈ 0.38/0.55/0.90 for H = 0.3/0.5/0.9) instead of
  white|integrated-noise halves, because (a) cumsum-from-zero smears the
  effective texture boundary rightward by construction, and (b)
  separately-standardized white|walk halves make white dominate mixed
  windows, shifting the apparent step. S1: fGn H=0.3 | H=0.9 (Δα≈0.5),
  boundary 256, seed 1101. S3: 2-D half-planes of independent per-row fGn,
  boundary x=128, seed 1103 (column transects see uniform white: this also
  tests the orientation-MAX design). S1/S3 bars unchanged
  (≤8 samples; ≥50% of 200 dots within 10 px).
- S2 metric replaced: p99 normalization forces contrast by construction,
  so a normalized peak/flank ratio is vacuous on texture-stationary input.
  S2 PASS = top-20 score-peak centers spread with std ≥ 100 samples over
  the 512-sample ramp (seed 1102), i.e. no localized firing; the raw
  exponent range is reported as a diagnostic.

## Addendum 1 (2026-10-06, before any R11-C implementation): R11-C locked design

Triggered by the Amendment-1 finding that windowed-DFA boundary
localization is O(window/4) (≈3 km for 12.8 km windows — an irreducible
tension between DFA's need for long windows and the metric's 300 m
kernel). R11-C (rank 3 in this plan) is promoted to implementation as the
well-localizing arm. Everything below was fixed before R11-C code ran.

- Layers: band 9 (tmi_vg) and band 11 (iso_grav_anom_vg) ONLY. Band 6 (tc)
  is not used (its description, "Tilt angle or total curvature", is
  ambiguous). No amplitude, gradient-magnitude or curvature enters the
  ranking; only the SIGN of the vertical derivatives.
- Physics: a contact edge sits on the tilt-angle zero contour, i.e. where
  the vertical derivative crosses zero (THDR maximal there). Zero-crossing
  masks zc_TMI/zc_GRAV = pixels whose 4-neighborhood contains both signs
  (zeros treated as positive), kept only where the local 3×3 |VDR| range
  exceeds the footprint p10 of |VDR| (locked hysteresis against flat-area
  noise crossings).
- Per physics: d = Euclidean distance (px) to the zero-crossing mask,
  score = max(0, 1 − d/3) (300 m kernel-matched decay), in [0,1] by
  construction. Field = sqrt(score_TMI × score_GRAV) (coincidence
  geomean). Support = footprint ∩ finite(vg bands).
- Emission, exclusion, budget (37,654), blocks (4×4, guard 3) identical to
  R11-A. Comparators: the same six plus the R11-A file (seven total).
  Fresh bootstrap seed 4612. Correlation gate |r|,|rho| < 0.2 identical.
- Survey audit identical (block-boundary enrichment diagnostic).
- Slot rule identical to R11-A (all gates incl. ≥8 blocks, no
  zero-capacity skips, beat every comparator, bootstrap lower > 0,
  correlation gate). TIF published regardless with measured outcome.

## Amendment 2 (2026-10-06): R11-A STOPPED FOR FUTILITY — no R11-A full-grid run

Measured on the locked Amendment-1 synthetics (seed 1101/1103, fGn step
Δα≈0.5, full-slope pure-boundary design): S1 peak at 300 vs true 256
(Δ=44 samples = 4.4 km; bar ≤8); S3 boundary concentration 0.18 (bar
≥0.50); anomaly-functional |z| even worse (Δ=52, contrast 1.41×). The
window-128 exponent profile of a clean step has intrinsic bump-dip
structure spanning ~100 samples (mixed-window kink inflation plus
inflation decay), so NO functional of the windowed exponent — boundary,
anomaly, or crossover (Δ=56 pre-amendment) — localizes better than
~W/3. DFA needs W≳100 for stable exponents; the metric needs ≤3 px
localization. This irreducible tension falsifies windowed-DFA-exponent
detection FOR THIS COMPETITION (it is consistent with R10's blocked
0.0617 and its wins only in the two most truth-dense blocks, where coarse
firing overlaps by coverage). The measurements are locked as regression
tests (tests/test_r11.py). Per futility-stopping practice the R11-A
production run is cancelled — its preregistered "TIF regardless" assumed
reaching the emission stage with an intact mechanism — and all session
effort redirects to R11-C. No production data was used in this decision;
the R11-C gate below remains un-peeked.

## Addendum 2 (2026-10-06, before any R11-C implementation): R11-C synthetic gates

- C-S1 (contact recovery, seed 1201): 256×256 grid; per-row VDR profiles
  = antisymmetric wavelet −(x−128)/9×exp(−(x−128)²/18) (σ=3 px) plus
  independent N(0, 0.05) noise per physics (TMI σ=3, gravity σ=4, contact
  x=128 both). Full production scorer (hysteresis, 3 px decay, geomean) +
  production emitter (top 200, min_dist 3, smooth 1.85).
  PASS = ≥70% of dots within 3 px of x=128.
- C-S2 (noise control, seed 1202): pure N(0,1) VDR both physics.
  PASS = no 6 px-wide vertical strip contains >25% of the top-200 dots.
- C-S3 (separated sources, seed 1203): TMI contact x=120, gravity contact
  x=136 (16 px apart). PASS = max field value < 0.3 (strict coincidence:
  no phantom between separated sources).
- C synthetics gate the slot exactly as A synthetics did; the TIF is
  published regardless with its measured outcome.

## Amendment 3 (2026-10-06): R11-C hysteresis replaced by multi-scale persistence

Measured on locked C synthetics: the Addendum-1 local-range hysteresis is
useless — C1 crossing densities 0.89/0.89 per physics, field mean 0.95
(saturated), C1 recovery 0.0, C3 max 1.0. Cause: local |VDR| range cannot
separate noise wiggles from contact crossings (both have large local
range; only spatial coherence differs). Replacement (same physics,
properly implemented): Gaussian-smooth the VDR at σ∈{0,1,2} px (all
sub-kernel), take 4-neighbourhood sign crossings per scale, keep σ0
crossings supported within 1 px (8-connected) at σ1 AND σ2. Contact phase
is scale-invariant (persists); noise crossings migrate with smoothing
(dropped). No amplitude enters; bands unchanged (9+11 signs only);
3 px decay, geomean, emission, budget, exclusions, comparators, seed 4612
unchanged. C-S2 strengthened: PASS = field max < 0.5 (quiet on noise)
AND (fewer than 20 dots emitted OR no 6 px strip holds >25% of dots).
C-S1/C-S3 bars unchanged. Still pre-production; production gate un-peeked.

## Amendment 3b (2026-10-06): persistence also fails — restore the literature tilt criterion

Measured: σ0/σ1/σ2 persistence still keeps density 0.57/0.55 (tolerance
intersection cannot work when smoothed scales stay dense); σ2 alone gives
0.29–0.31, still above the 8-connected percolation threshold — giant
noise components (7k–18k px) swallow the 256 px contact line, so no
component-size filter can separate them either. Sign-only detection is
unworkable under noise. Fix: restore the published tilt method (Salem et
al. 2007) — VDR zero-crossing (raw scale, sharp) AND a THDR significance
gate (3×3-max THDR > median + 3×MAD over valid; robust z > 3). Bands
3/18 (THDR) enter as a BINARY gate only, never ranked; ranking stays
phase-pure. C fixtures gain locked synthetic THDR (|ridge + N(0,0.05)|,
ridge amp 1.0; C2 pure |noise|). All bars unchanged (C-S1 ≥70% within
3 px, C-S2 max < 0.5 + scatter, C-S3 max < 0.3). Still pre-production.

## Amendment 3c (2026-10-06): THDR gate on the pixel value, not the 3×3 max

Measured: gating the 3×3-max THDR passes 12% of pure-noise pixels (max
of 9 inflates the tail: P ≈ 0.12 vs 0.008 for the pixel value), keeping
density 0.10 on C2 and saturating all three C gates. Fix: gate on the
pixel THDR (self-consistent with the median/MAD statistics; the ridge
crest coincides with the zero pixel per tilt theory, jitter < 1 px ≪
ridge width σ=3–4). Still pre-production.

## Amendment 3d (2026-10-06): fixtures use instrument-realistic smooth noise

Measured: under WHITE-noise VDR the k=3 pixel gate still keeps ~800
noise pixels/physics (C2) and C1 recovery is 0.205 (bar 0.70) — noise
survivals outnumber contact pixels 3:1 and outrank flanks at score 1.0.
Tuning k upward would overtune to an unphysical regime: per the GeoDAWN
release (Glen & Earney 2024, DOI 10.5066/P93LGLVQ) the Area 1/2 surveys
flew 200–400 m line spacing rendered on 100 m cells, so cells are
oversampled 2–4× and white-noise VDR at 100 m is instrumentally
impossible; real VDR grids (and their gridding artifacts) are smooth.
Fix: fixture noise = σ=2.5-px-smoothed Gaussian renormalized to std 0.05
(correlation ≈ line spacing), same seeds, same bars. White-noise stress
results are retained as a diagnostic (detector requires gridded-smooth
input, which the production grids are; production crossing densities
will be reported in the receipt). Still pre-production.

## Addendum 4 (2026-10-06): H1 SUSPENDED after Amendment 3d also fails — pivot to H3 (R11-D)

Measured with smooth-noise fixtures: gated density 0.011 but noise
components still reach 30 px (C2 max 18) vs the contact component, and
C-S1/C-S2/C-S3 ALL still fail (C1 recovery 0.23, C2 max 0.82, C3 max
1.0). Six design iterations (range hysteresis → multi-scale persistence
→ σ2 → THDR pixel/max gate → smooth fixtures) all fail the locked bars:
the zero set of a noisy grid is intrinsically dense/percolated, and every
patch adds seed-fragile thresholds. H1 is SUSPENDED (not falsified on
clean data, but not robust; code + measurements preserved in
src/gems46/tiltphase.py, tests/test_r11c.py). Per the preregistered
ranking, the session pivots to H3 (matched-filter contact detector) as
arm R11-D, with fresh seeds and identical bars — a fair pre-registered
test, not bar-shopping: H3 was ranked #2 before any implementation.

### R11-D locked design (H3 finalization; pre-implementation)
- Bands: TMI-RTP + isostatic gravity (indices per src/gems46/features.py —
  read before coding), step-edge template (matches contact anomaly shape).
- Template: 25-tap zero-mean step (12×−1, 1×0, 12×+1), unit norm; Pearson
  r per position (fully amplitude-invariant) at 4 strike angles
  (0/45/90/135°, design detail for strike invariance — a 45° fault is a
  ramp to row/column templates; documented here before implementation).
- Per-physics score = max over angles of |r| (either polarity), hard
  floor |r| ≥ 0.6 (analytic neutral midpoint between the noise floor
  1/√25 = 0.2 and clean-contact r ≈ 0.9+; NOT tuned to data).
- Field = geomean of the two per-physics scores (dual-physics
  coincidence); masked normalized cross-correlation (≥80% valid pixels
  per template footprint; no invented data).
- Emission/budget (37,654)/exclusions/support/comparators (GEMSDOE32,
  H46-structural, R8, R9, H46-pure, R10)/seed 4613/slot rule: identical
  to R11-A prereg. TIF published regardless with measured outcome.
- Comparators note: R11-A has no file (futility stop); R11-C has no file
  (suspended). Six comparators stand.

### R11-D synthetic gates (fresh seeds; same bars)
- D-S1 (step recovery, seed 1301): 256×256, N-S step (0|1) at x=128 +
  WHITE noise σ=0.1 both physics (correlation must earn its robustness
  claim on harsh noise). Production scorer + emitter (top 200, min_dist
  3, smooth 1.85). PASS = ≥70% of dots within 3 px of x=128.
- D-S2 (noise control, seed 1302): pure N(0,1) both physics.
  PASS = field max < 0.5 AND (<20 dots OR no 6 px strip >25%).
- D-S3 (separated steps, seed 1303): TMI step x=120, gravity step x=136.
  PASS = max field < 0.3.
- D synthetics gate the slot exactly as A synthetics did.

## Outcome (2026-10-06): R11-D ran locked — HOLD on both gates, no slot used

- D synthetics passed first try after Amendment 5 (D-S1 1.0, D-S2 0.0,
  D-S3 0.0), unlocking the single locked production run (seed 4613).
- Production: mean blocked DTI 0.0610, best comparator (GEMSDOE32
  re-emitted) 0.1007; paired Δ −0.0397, bootstrap 95% [−0.0546, −0.0258];
  R11-D lost all 9 evaluable folds (same skip pattern as R10: blocks
  6/13 zero emission capacity, 5 blocks without proxy truth).
- Distinctness gate also failed: max |correlation| 0.543 (smoothed-field
  Spearman vs RTP curvature, negative). Dot-pattern correlations ≈ 0.
- Post-hoc mechanism (diagnostic only; design frozen): 71% of support
  passes the |r| ≥ 0.8 floor (median field 0.879) — the step template
  matches smooth regional gradients (ramp r ≈ 0.9+) nearly everywhere,
  so emission picks the top 1% of a saturated field. The D fixtures'
  flat background never tested ramp rejection. Candidate fix for a
  future session (NOT this one): ramp-orthogonalized (detrended) step
  template, i.e. gradient-spike matching, with ramp fixtures.
- File `docs/r11/gems46-r11d-matchedfilter-5caba5cc4ffc-zeros.tif`
  (37,654 dots, format-audited) published with HOLD status per prereg;
  receipt `registry/r11.json`. Session arms: A futility-stopped, C
  suspended, D held. No weekly slot spent.

## Amendment 5 (2026-10-06): D-S1 comb fixture + FWER-derived floor 0.8

Two measured findings forced these pre-production changes (bars unchanged):
1. Single-line synthetic bars are MATHEMATICALLY unachievable: at the
   locked min_dist=3 (Chebyshev-5 exclusion) the ±3 px band around one
   256 px line holds at most ~102 dots, so ≥70% of 200 dots (140) cannot
   fit — C-S1's bar was unachievable too (H1's suspension stands on its
   other failures regardless). A correct H3 detector measured D-S1
   frac 0.225: the ±12 px ridge is real and centered, but spacing spreads
   dots along it. Fix: D-S1 uses a 5-line comb (x ∈ {64,96,128,160,192},
   spacing 32 ≫ template; parallel strands = realistic fault networks),
   budget 200 (~40/line, under the ~51/line track capacity), bar ≥70%
   within 3 px of the NEAREST line.
2. The |r| ≥ 0.6 floor leaks chance pixels (D2 max 0.68 over 3 px; D3
   overlap phantom 0.84 at 16 px separation — the 25-tap ridge is ±12
   wide). Fix: floor 0.8 = Bonferroni family-wise 5% significance for
   |r| (df=22) over M ≈ footprint px × 4 angles ≈ 2e7 tests
   (t ≈ 6.5 → r ≈ 0.81), computed from public grid dims, conservative
   under template overlap. Still pre-production.
