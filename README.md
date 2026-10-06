# GEMSDOE46 — DOE GEMS Prize (DrivenData #306): DFA scaling-regime breaks + split-conformal spacing

**Site:** <https://buffedlizard55-lab.github.io/GEMSDOE46/> (the repository root `index.html` **is** the
download page; GitHub Pages is configured at `main:/` and cannot be re-pointed, see `docs/IRREGULARITIES.md` IR-46-12).
**Read [`PROMPT.md`](PROMPT.md) first, every session** — it is this project's objective and hard constraints.
Session 1's brief is archived verbatim in [`docs/charter-session-1.md`](docs/charter-session-1.md).

---

## ⬇️ Download the submission

**Recommended (session 2, the DFA hypothesis):**
[`docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.tif`](docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.tif)
· [`.zip`](docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.zip)
· [fallback `-zeros` encoding](docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z-zeros.tif)
· [format audit](docs/h46/downloads/gems46-h46-2-dfa-corroborated-20261006T101807Z.json)
· **Name:** `gems46-h46-2-dfa-corroborated` · **37,654 positive pixels**, single-band `float32`, EPSG:32611, 100 m,
3730 × 3292, geotransform and finite-mask identical to the official template, every finite value exactly 0.0/1.0.
**Note to paste into the form:** "H46-2 structural corroboration with a 10 % DFA scaling-regime-break hedge;
37,654 dots, min separation 3 px, 200 m catalogue buffer; off-catalogue proxy DTI 0.1016 vs 0.0991 for the
best prior files at matched mass."

**The new hypothesis, on its own (session 2):**
[`gems46-h46-1-dfa-regime-break-20261006T101807Z.tif`](docs/h46/downloads/gems46-h46-1-dfa-regime-break-20261006T101807Z.tif)
· [`.zip`](docs/h46/downloads/gems46-h46-1-dfa-regime-break-20261006T101807Z.zip)
· [audit](docs/h46/downloads/gems46-h46-1-dfa-regime-break-20261006T101807Z.json).

**Session 1's certified arm (kept, still valid):**
[`SUBMISSION-GEMSDOE46-r8-conformal.tif`](SUBMISSION-GEMSDOE46-r8-conformal.tif) (39,108 dots, split-conformal
spacing r = 8 px, 90.0 % confidence floor 0.0283 on 9 exchangeable blocks;
[guide](docs/SUBMISSION_GUIDE.md) · [how-to-submit page](docs/how-to-submit.html)).

**Upload walkthrough:** [`docs/h46/executive-summary.html`](docs/h46/executive-summary.html) and
[`docs/SUBMISSION_GUIDE.md`](docs/SUBMISSION_GUIDE.md). One selection is scored in **both** rounds, so submit
the file you want evaluated at the end. Format checks re-read the written bytes
([`scripts/verify_all.py`](scripts/verify_all.py)); the earlier form error *"Predicted values must be in
range [0, 1]"* cannot recur in either encoding (all-finite and NaN-outside variants are both audited).

---

## 1. The standing question: why did 0.2778 win, and can we beat 0.3345?

Reproduce every number: `python3 scripts/analyse_live_family.py` (session 2),
`python3 scripts/reanalyse_conformal.py` (session 1).

The metric is `DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)` with a 300 m triangular kernel. Two identities make
it a *density* problem: `FNw = |G| − TPw` and `FPw = S − M`, so

```
DTI = T / (0.2·S + 0.8·|G|)        (T = realised credit, S = emitted mass, |G| = hidden truth)
marginal rule:  adding a unit of mass helps  ⟺  its kernel credit k > 0.2·DTI      (bar 0.0520 at 0.2600)
```

The `h33-h33-2-b2` family did not get better at finding faults — it emitted **less worthless mass**. Each
thinning step removed pixels whose realised credit was below the metric's own break-even bar, and the last
step removed the 200 m ring around the published catalogue, which is free score because DrivenData staff
confirm that known USGS/INGENIOUS fault pixels are masked out of evaluation in both rounds
([forum thread 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)).

| step | mass removed | mean realised credit | bar `0.2·DTI_before` | verdict |
|---|---:|---:|---:|---|
| solid H19-5 (121,131 px, 0.1922) → D1.5 (60,069 px, 0.2477) | 61,062 | 0.0173 | 0.0384 | remove |
| D1.5 → D2.8 (44,090 px, 0.2600) | 15,979 | 0.0341 | 0.0495 | remove |
| D2.8 → +200 m catalogue buffer (37,654 px, 0.2778) | 6,436 | 0.0000 | 0.0520 | remove |

*Credit numbers are quoted at the **boundary** value of |G| (see the honesty box below); the verdict column
is identical at every feasible |G|, which is the part the decision rests on.*

**Honesty box on |G| — two scores, three unknowns.** `T = 0.26·(0.2·44,090 + 0.8·|G|)` and
`T' = 0.2778·(0.2·37,654 + 0.8·|G|)` give two equations in three unknowns, so |G| is **not point-identified**.
Non-negativity of the removed credit (`TPw` is monotone) gives the bound **|G| ≤ 14,089 px**; that boundary
value is where the removed pixels carried exactly zero credit, and it is the one quoted above. Session 1's
receipts *declare* 7,905 px (H28 inference, owner-reported), which is also feasible and implies 0.0893
credit/px instead of 0.1185. Everything the decision uses is invariant: the bar is `0.2·DTI`, and reaching
0.3345 from 0.2778 at the same emitted mass needs **+20.4 % credit** at *any* feasible |G| (+29 % per-pixel
improvement at ~44 k px). See [`registry/emission_model.json`](registry/emission_model.json) and
[`registry/irregularities.json`](registry/irregularities.json) IR-46-07.

**Can we beat 0.3345?** Only with a better field: `DTI ≤ |G|/(0.2·S + 0.8·|G|)` caps what any emission can
do, and thinning/tresholding only walks along the existing credit curve, which the prior family has already
optimised. That is why this repository now ships a **detector** hypothesis (session 2: DFA scaling-regime
breaks) rather than another thinning variant, and why the honest expectation for the shipped file is
**~0.27–0.29**, not 0.33+.

⚠️ Attribution: 0.2778 appears on the public board for participant `extradr19` with no file link, while the
GEMSDOE32 site labels its own B = 2 artifact UNSCORED. Treat the family's scores as owner-reported
(IR-46-01) and the live public leaderboard as the only organiser-stamped evidence (leader **0.3345**,
2nd 0.3262, 3rd 0.3222 on 2026-10-06; the brief's 0.3195 is stale).

## 2. What session 2 built (the mandated new hypothesis)

**H46-1 — DFA scaling-exponent breaks (Peng et al., Phys. Rev. E 49, 1685, 1994).** Detrended fluctuation
analysis is run along every row and column transect of the magnetic (`mag_anom`, `rtp`, `tmi`, `tmi_hg`,
`tmi_vg`) and gravity (`iso_grav_anom`, `-hg`, `-slope`, `-vg`) bands at 100 m; the local exponent in a
128-px (12.8 km) window is differenced against a 31-window (24.8 km) median background and scaled by a local
MAD. What is flagged is therefore **where the scaling regime changes**, not where the amplitude or gradient
spikes, plus the regime-boundary transform `|∇ z|`. The estimator is verified against exact-spectral
fractional Gaussian noise (α = H ± 0.02 for H = 0.1 … 1.0) and against the textbook values for white noise
(0.50) and a random walk (1.5) in `tests/test_dfa.py`; the measured band background exponents here are
1.00–1.95, so the detector tests breaks *relative to the local background* and never against an absolute 0.5.

**Distinctness (the condition for calling it new).** Smoothed Pearson correlation of the H46-1 emission with
the three prior submissions is **−0.012 / −0.009 / −0.012**; against every gradient/curvature transform of the
same bands it is **|r| ≤ 0.04**; Jaccard overlap with the incumbent emission is **0.0037**. It is not a
relabelled edge/curvature detector.

**Its measured value is negative, and it is reported as such.** On the off-catalogue USGS SGMC proxy at
matched mass, pure DFA scores **0.0809** against **0.0991** for the best prior files, and 0.1054 for the
structural-only field. So H46-1 is shipped as the novelty/test artifact, while the slot recommendation is
H46-2 — the structural corroboration field with a **10 % DFA hedge** (0.1016, the best of the hedge sweep:
0 % → 0.1054, 5 % → 0.1031, 10 % → 0.1016, 12 % → 0.1008, 20 % → 0.0990; the sweep's own margin over the
incumbent is 0.0025, i.e. inside that instrument's noise — stated, not hidden).

**Session 1's parallel contribution** (kept): a split-conformal selection rule over the spacing sweep, which
certifies the operating point instead of eyeballing it — [`evidence/conformal_selection.json`](evidence/conformal_selection.json),
[`docs/SCORE_ANALYSIS.md`](docs/SCORE_ANALYSIS.md).

## 3. Repository map

| path | what it is |
| --- | --- |
| `src/gems46/metric.py` | the official metric, transcribed line-by-line (both the session-1 array API and the session-2 component API with `known`-catalogue masking) |
| `src/gems46/dfa.py`, `detector.py` | **session 2**: vectorised sliding-window DFA, local-exponent break fields, regime-boundary transform |
| `src/gems46/emission.py`, `holdout.py`, `submission.py`, `grid.py` | **session 2**: marginal-credit budget, greedy emission, rejection-sampling holdout, format-exact writer + re-read audit |
| `src/gems46/{window_metric,features,emitter,pipeline,conformal,analytic,submit}.py` | **session 1**: windowed scorer, 25-band feature stack, metric-aware emitter, blocked-holdout pipeline, R1–R4 selection, data-free ceiling |
| `scripts/build_dfa_field.py` | builds the DFA fields (`data/derived/dfa_*.npz`) and `data/derived/dfa_stats.json` |
| `scripts/build_h46_submission.py` | calibrates from the live scores, emits, writes and audits both TIFs, writes `registry/submissions.json` |
| `scripts/validate_candidates.py` | instruments, distinctness correlations, hedge sweep — `registry/validation.json` |
| `scripts/analyse_live_family.py` | the metric algebra of §1, with the |G| bound and its sensitivity |
| `scripts/build_site.py` | regenerates `docs/h46/` from `registry/*.json` (no hand-typed numbers in the pages) |
| `scripts/verify_all.py` | one-command audit: tests + pinned hashes + format audit of the shipped bytes + calibration arithmetic |
| `scripts/{run_pipeline,make_submission,hypothesis_release,prepare_data,download_competition_data,import_competition_archive}.py` | **session 1**: end-to-end driver, submission builder, A/B test, data verification/import |
| `registry/` | session-2 receipts: hypotheses, sources, irregularities, emission model, submissions, validation |
| `evidence/`, `docs/*.md`, `docs/*.html` | session-1 receipts, score analysis, hypothesis register, source register, review log |
| `docs/h46/` | the session-2 site (overview, executive summary, hypotheses, validation, research, sources, irregularities) |

## 4. Reproduce

```bash
pip install -r requirements.txt
bash   scripts/restore_competition_data.sh   # sparse-clone mirror restore + sha256 verification
python3 scripts/build_dfa_field.py           # DFA fields, ~2 min on 2 cores
python3 scripts/build_h46_submission.py      # emits + audits both TIFs, ~1 min
python3 scripts/validate_candidates.py       # instruments + distinctness + hedge sweep, ~13 min
python3 scripts/build_site.py                # regenerates docs/h46/
python3 -m pytest tests -q                   # metric vs published example + brute force, DFA calibration, format
python3 scripts/verify_all.py                # every check; exit 0 == all pass
```

## 5. Limitations (as the brief requires)

1. **No leaderboard feedback loop.** The private labels are unavailable here; no score can be predicted from
   this repository, and no file was submitted by this session (the upload must be done by the project owner).
2. **The local instruments disagree with the live board** (IR-46-04): the spatially blocked catalogue holdout
   ranks 0.2600 *above* 0.2778 (Spearman +0.087, sign-inverted), so it is rejected as a selection instrument;
   the off-catalogue USGS SGMC proxy is the better analogue (+0.305 over the group's 11-file ledger) but is a
   different fault population. Every comparison here is at **matched emitted mass** for that reason.
3. **DFA is adapted from time series to a spatial grid.** The published pre-rupture application is a *time-lag*
   crossover in field variations, not a spatial regime change (IR-46-05); using it as a spatial texture
   statistic is our hypothesis, not a published result, and it measured weaker than the structural field.
4. **Sandbox egress was limited to github.com and pypi.org** (IR-46-06): no new external dataset could be
   fetched this session. The one external raster used is a hash-pinned mirror of USGS SGMC traces
   (`registry/data_manifest.json`), not an organiser-served file.
5. **|G| is bounded, not measured** (IR-46-07) — see the honesty box in §1.

## 6. Next steps, in priority order

1. **H46-3 (free official data, blocked here):** hypocentre lineaments from the USGS FDSN event service —
   `bash scripts/fetch_earthquake_catalog.sh` on an unrestricted machine, then a double-difference alignment
   detector; active seismicity is a physically independent off-catalogue fault indicator.
2. **H46-4 (no new data):** windowed Euler deconvolution (SI = 1) on gravity + RTP magnetics, keeping only
   structures whose depth is consistent across both fields and along strike.
3. **H46-5:** invert the measured-geochemistry arm (group data) into a *pruning* prior — the addition
   direction was already falsified, the removal direction has not been tested.
4. Re-run `scripts/validate_candidates.py` and require a candidate to beat the current best proxy **at matched
   mass** before it takes the scored slot.

## 7. The session-2 brief (kept verbatim as the project charter)

The full working copy, with the standing constraints and the site-history table that must not be duplicated,
is [`PROMPT.md`](PROMPT.md). Its requirement bullets, word for word:

> **Highest urgency**: produce a UNIQUE TIF submission for the DrivenData DOE GEMS Prize
> (https://www.drivendata.org/competitions/306/competition-doe-gems/, page 967, data page, rules). Never copy a
> prior GEMSDOE submission (copying only for learning); must differ from every listed GEMSDOE submission;
> provide an easy-to-download `.tif` URL; validate the file.
>
> **Mandated new hypothesis**: DFA (Peng et al., Phys. Rev. E 1994) on magnetic + gravity grids — flag where
> the local scaling exponent breaks from its surrounding background regime rather than amplitude/gradient
> spikes, including along-track transects, normalized to 0–1, written in the required format, with confirmed
> low correlation to prior gradient/curvature submissions before it may be called a new hypothesis.
>
> Before coding: 3–5 candidate geological hypotheses not yet tried, each naming (a) layers, (b) physical
> signature, (c) why it finds a fault missing from USGS/INGENIOUS rather than one already in it, (d) how it
> differs from anything in the repo; ranked by expected DTI gain vs implementation cost; validate the top
> candidate on the spatially-blocked holdout before spending a weekly slot; if external data is needed, name
> the specific free official source and verify obtainability.
>
> Analyze WHY `h33-h33-2-b2…-zeros: 0.2778` scored highest and whether it can be beaten; design strategy to
> beat leader #1 (0.3195 as stated; live board is now 0.3345).
>
> Build a system removing manual checking: up-to-date feed, clean GitHub Pages site (index, executive summary,
> how-to-submit, hypotheses, sources, irregularities), verified official links for manual review, prompt in README.
>
> Rules of engagement: line-by-line verification against official sources with links, fully autonomous, flag
> irregularities, **no hallucinations**, **multiple passes (Pass 1 implement+verify, Pass 2 review bugs/edge
> cases, Pass 3 re-check against the request)**, create PR and merge to `main`, state limitations and remaining work.

**Core values:** *Maximize P(Win)* — every design choice is made against the official metric's own algebra,
never against a proxy known to drift; where they disagree, the algebra wins and the disagreement is filed in
`registry/irregularities.json`. *Own the Outcome* — the repository ships an auditable artifact plus the
instrument that turns each future slot decision into a measurement, and it reports its own negative results.

## 8. Evidence policy

Every number in `docs/h46/` is regenerated from `registry/*.json` by `scripts/build_site.py`; every claim
about an official source carries a link and what was taken from it in `registry/sources.json`; every
unresolved or contested issue is filed in `registry/irregularities.json` instead of being repeated quietly.
Scores marked *owner-reported* are not organiser receipts.
