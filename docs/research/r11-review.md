# R11 review: three arms, three negative results, one published TIF (HOLD)

Date: 2026-10-06. Session plan (preregistration + 5 amendments + 4 addenda):
`session-r11-plan.md`. Receipt: `registry/r11.json`. No weekly slot was used.

## What was tested and what happened

| Arm | Mechanism | Stage reached | Verdict |
|---|---|---|---|
| R11-A (DFA, this prompt's literal statistic) | Windowed DFA exponent boundaries, block-stratified | Synthetic | **Futility stop** (Amendment 2): 4.4 km mislocalization on a clean step; no functional of windowed exponents beats ~W/3. No TIF. |
| R11-C (tilt phase) | VDR zero-crossing coincidence, TMI × gravity | Synthetic (6 iterations) | **Suspended** (Addendum 4): zero sets percolate under grid noise; every patch added fragile thresholds. No TIF. |
| R11-D (matched filter) | Step-template Pearson-r coincidence, RTP × gravity | Full locked production | **HOLD**: blocked DTI 0.0610 vs 0.1007 best; correlation gate failed (0.543). TIF published, not submitted. |

All three outcomes were produced by the preregistered gates, not by
post-hoc judgment. The amendments (documented in the plan with measured
causes) changed designs only before production; nothing was tuned to
production output.

## R11-D in numbers

- File: `docs/r11/gems46-r11d-matchedfilter-5caba5cc4ffc-zeros.tif`
  (37,654 dots, [0,1], EPSG:32611, 3730×3292, 100 m, format-audited).
- 9 evaluable 4×4 spatial blocks; lost all 9. Paired Δ −0.0397,
  descriptive bootstrap 95% [−0.0546, −0.0258] (seed 4613). Zero-capacity
  skips in blocks 6/13 (same as R10) independently fail the coverage gate.
- Dot-pattern correlations to every comparator ≈ 0 (unique placement);
  smoothed-field Spearman vs RTP curvature −0.543 fails distinctness.
- Post-hoc mechanism: 71% of support passes |r| ≥ 0.8 (median 0.879) —
  the step template matches smooth regional gradients (ramps) as well as
  steps, so the emission ranks the top 1% of a saturated field. The
  synthetic fixtures' flat background never tested ramp rejection. A
  future session could test a ramp-orthogonalized (detrended) template
  with ramp fixtures; that design is not validated and was not run here.

## On GEMSDOE32 h33 (owner-reported 0.2778) and beating the leader (0.3774)

- The 0.2778 attribution remains owner-reported and file-unlinked: the
  official board does not map scores to files, and GEMSDOE32's own page
  still labels the file unscored. Treat "h33 scored 0.2778" as a claim
  with provenance, not an authenticated measurement.
- What the claim plus our proxy grids jointly suggest: h33-style sparse
  thinned patterns reduce false-positive tax (0.2 each beyond 300 m)
  while retaining coverage of major structures; the re-emitted GEMSDOE32
  comparator also leads our blocked proxy means (0.101/0.103). Sparse
  precision beats dense recall under this metric — consistent with the
  exact identity DTI = T / [0.2(T+S−M) + 0.8G].
- Old-README causal stories (inferred hidden-label counts guaranteeing
  the score) were not justified and are withdrawn wherever they appear.
- Is >0.3774 achievable? Unknown. Nothing we have run (R8/R9 conformal,
  H46 DFA family, R10 crossover, R11-D matched filter) exceeds ~0.10 on
  the SGMC proxy while the re-emitted incumbent sits at ~0.10 — but the
  proxy is not hidden truth (coarse SGMC source scales, reused labels),
  so proxy headroom does not bound leaderboard headroom. A submission
  beating the leader needs demonstrably better 300 m localization or
  precision on HELD-OUT truth-like labels; no current candidate has
  shown that, so no slot should be spent on one.

## Standing hypotheses (from the prereg; status)

1. H1 tilt-phase coincidence — suspended (robustness failure, 6 tries).
2. H3 matched-filter contacts — held (ramp-saturation failure).
3. H2 Euler deconvolution clustering — untested, next in line.
4. H4 balanced-dilation relief ratio — untested.
5. H5 acquisition-block residual texture — diagnostic only so far
   (R11-D survey audit: field means 0.60–0.65 across all four blocks).

Euler (H2) is the recommended next arm: per-window least-squares depth
solutions degrade gracefully under noise (scatter, not percolation),
but its ~1–2 km solution clustering must still clear a synthetic
localization bar before any production run.

## Irregularities and cautions

- Forum 11527's staff answer on expert-label data sources is
  unrecoverable via page fetch; label provenance stays unverified.
- Direct GDR/ComCat/NLR/DrivenData fetches fail from this environment;
  external-data claims rest on github-mirrored bytes already local.
- Uniqueness is verified against inspected local rasters plus the
  restored GEMSDOE32 file only — not universally.
- Low/failed correlation says nothing about geological independence.
