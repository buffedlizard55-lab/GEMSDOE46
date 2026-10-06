# GEMSDOE46 — DFA scaling-regime breaks on the magnetic and gravity grids (DOE GEMS Prize, DrivenData #306)

**Read [`PROMPT.md`](PROMPT.md) first, every session.** It is the standing brief (mission, hard
constraints, the hypothesis this repository exists to test, the site requirements and the site-history
table we must not duplicate). This README is the live state of the work; `PROMPT.md` is the objective.

**Site (GitHub Pages):** `docs/index.html` — it opens with the download and the three submission steps.
**Download:** `docs/downloads/gems46-h46-2-dfa-corroborated-<stamp>.tif` (recommended) and
`docs/downloads/gems46-h46-1-dfa-regime-break-<stamp>.tif` (the new hypothesis).

| | |
|---|---|
| Shipped files | single-band `float32` GeoTIFF, `EPSG:32611`, 100 m, 3730 × 3292, geotransform and finite-mask identical to the official template, every finite value exactly 0.0 or 1.0, NaN outside the footprint (a `-zeros` variant is provided too) |
| Emitted mass | 37,654 pixels each — the measured mass of the highest-scoring prior file, and inside the optimum implied by the metric's own algebra for this credit curve |
| Validation | H46-2 **0.1016** vs **0.0991** for the two best prior files re-emitted at the same mass with the same exclusion rules, on the off-catalogue USGS SGMC proxy; H46-1 **0.0809** (measured *weaker* — reported as a negative result) |
| New-hypothesis test | H46-1 correlation with all three prior submissions is −0.012 / −0.009 / −0.012 and with every gradient/curvature transform of the same bands \|r\| ≤ 0.04; Jaccard overlap with the incumbent emission 0.0037 |
| Target | public leaderboard #1 = **0.3345** on 2026-10-06 (the 0.3195 in the brief is stale) |
| Honest expectation | ~0.27–0.29 for H46-2. Nothing in this session produced the +20–29 % field improvement that 0.3345 requires, and we will not claim otherwise |

---

## Answer to the standing question: why did 0.2778 win, and can we beat 0.3345?

Reproduce with `python3 scripts/analyse_live_family.py`. Two identities follow directly from the
published metric (both verified against an independent O(N²) transcription in `tests/test_metric.py`):
`FNw = |G| − TPw`, and `DTI = TPw / (0.2(TPw + S − M) + 0.8|G|)`; the exact marginal rule is
`ΔDTI > 0 ⟺ k(0.2·FP + 0.8|G|) > 0.2·DTI·D·(1−C)`, which reduces to `k > 0.2·DTI` when the truth set
is much larger than the covered part.

Solving the metric algebra on the two closest members of the winning family
(`0.2600` at 44,090 px and `0.2778` at 37,654 px, masses measured from the restored files):

```
G  = 14,089 hidden truth pixels  (≈ 1,409 km of fault trace at 100 m)
TPw(D2.8) = 5,223 px of credit   → 0.1185 realised credit per emitted pixel
break-even bar at 0.2600 = 0.0520
```

The thinned, catalogue-buffered member wins **because every removal step deleted mass whose realised
credit was below the metric's own break-even bar** — not because "smaller is better":

| step | removed | mean realised credit | bar | verdict |
|---|---:|---:|---:|---|
| solid 121,131 px → dotted 60,069 px | 61,062 | 0.0173 | 0.0384 | remove |
| dotted 60,069 px → 44,090 px | 15,979 | 0.0341 | 0.0495 | remove |
| 44,090 px → 37,654 px (200 m catalogue buffer) | 6,436 | 0.0000 | 0.0520 | remove |

The last row is the decisive one, and it rests on an **official clarification**: DrivenData staff state
(forum thread 11516) that known USGS/INGENIOUS fault pixels are masked out of evaluation **in both
rounds**. Mass within the kernel of a mapped fault therefore pays part of the false-positive tax while
being unable to earn credit, so the catalogue is an exclusion zone, not a training target.

**Can we beat 0.3345?** Only with a better field. At matched mass, reaching 0.3345 from the best prior
file requires **+20.4 % credit** (6,289 px vs 5,223 px); at ~44,000 px it requires a mean realised
credit of 0.1524 against 0.1185 today, i.e. **+29 %**. No amount of thinning, dotting, thresholding or
buffering can close that gap, because those moves travel along the same credit curve, and the prior
family is already at its optimum. That is a detector problem — which is what H46-1/H46-2 attack, and
what `registry/hypotheses.json` ranks the remaining candidates against.

⚠️ Attribution warning: 0.2778 appears on the public board attached to participant `extradr19` with no
file link, and the GEMSDOE32 site labels its own B=2 artifact UNSCORED. See
`registry/irregularities.json` (IR-46-01) before quoting that number as this family's score.

## How to submit (full walkthrough in `docs/executive-summary.html`)

1. Sign in → <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/> → **New submission**.
2. **File to submit:** `docs/downloads/gems46-h46-2-dfa-corroborated-<stamp>.tif` (or its `.zip`; the
   `-zeros.tif` is the fallback if the form rejects NaN outside the footprint).
3. **Note (optional):** paste the note printed on the site's overview page and inside the file's
   receipt JSON — it names the method, the emitted mass and the buffer rule.
4. Submit; keep that file selected, because one selection is scored in **both** rounds (initial round
   against a fixed private set of expert-labelled new faults; final round against an expanded label
   set after expert review).

## Repository map

```
src/gems46/        metric.py (official DTI, exact + O(N) binary path)      dfa.py (DFA estimator)
                   grid.py (format contract)  detector.py (H46 fields)     emission.py (budget/dots)
                   holdout.py (instruments)   submission.py (writer)       fields via detector.BAND_INDEX
scripts/           download_competition_data.sh  fetch_earthquake_catalog.sh  build_dfa_field.py
                   validate_candidates.py  build_submission.py  analyse_live_family.py
                   build_site.py  verify_all.py
tests/             27 tests: metric vs published example + O(N²) brute force, DFA vs textbook
                   calibration (white 0.50, fGn H, random walk 1.5), emission algebra, format contract
registry/          data_manifest · sources · hypotheses · irregularities · prior_results.csv
                   emission_model.json (live calibration) · submissions.json · validation.json
docs/              the GitHub Pages site + downloads/ (the shippable artifacts)
data/              raw/ (restored competition files, not committed) · external/ · derived/ (gitignored)
```

## Reproduce

```bash
bash scripts/download_competition_data.sh     # restores the 3 mirror files and verifies sha256
python3 scripts/build_dfa_field.py            # 13 band/variant DFA fields, ~4 min, 2 CPU cores
python3 scripts/build_submission.py           # calibrates, emits, writes + audits both TIFs, ~1 min
python3 scripts/validate_candidates.py        # instruments, distinctness, hedge sweep, ~13 min
python3 scripts/build_site.py                 # regenerates docs/ from registry/
python3 scripts/verify_all.py                 # every check; exit 0 == all pass
```

Hardware: 2 CPU cores, 3 GB RAM, no GPU. Training a neural network is **not** part of this pipeline;
both artifacts are deterministic functions of the official bands plus the emission rules recorded in
`registry/submissions.json`.

## Limitations, stated plainly

- The private/public test labels are not available here, so **no score can be predicted from this
  repository**. The proxy instrument is a different fault population and tracks the live board only
  weakly (owner-group measurement: Spearman +0.31 over 11 files).
- The spatially blocked catalogue holdout is **rejected as an instrument** (IR-46-04): it ranks the
  0.2600 file above the 0.2778 file, the opposite of the live board.
- DFA is adapted from a temporal method to a spatial grid; the published pre-rupture result is a *time
  lag* crossover, not a spatial regime change (IR-46-05). The measured background exponents of this
  dataset are 1.00–1.95, not 0.5, so the detector tests breaks relative to the local background.
- Sandbox egress allowed only github.com and pypi.org (IR-46-06), so no new external dataset could be
  added; the one external raster used is a hash-pinned mirror of USGS SGMC traces.

## Next steps, in priority order

1. **H46-3** (strongest untested idea, one command on an unrestricted machine):
   `bash scripts/fetch_earthquake_catalog.sh` → hypocentre-lineament detector → same matched-mass protocol.
2. **H46-4**: windowed Euler deconvolution (SI = 1) on gravity + RTP magnetics, requiring along-strike
   depth consistency across two independent potential fields (no new data needed).
3. **H46-5**: invert the sign of the measured-geochemistry arm and use it as a **pruning** prior.
4. Re-run `scripts/validate_candidates.py` and require a candidate to beat the current best proxy at
   matched mass **before** giving it the scored slot.

## Evidence policy

Every number on the site is regenerated from `registry/*.json`; every claim about an official source
carries a link in `registry/sources.json` with what was taken from it; every unresolved or contested
issue is listed in `registry/irregularities.json` rather than being silently repeated. Scores marked
*owner-reported* are not organiser receipts.
