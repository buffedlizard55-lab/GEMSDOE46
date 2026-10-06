# GEMSDOE46 — DOE GEMS fault-mapping research

> **Project state (2026-10-06): research and validation infrastructure only.** The checkout contains no authorized competition rasters/labels, no validated candidate, and no submission GeoTIFF. The submission-download control on the site is therefore intentionally gated; this project will not publish a dummy raster or claim an unmeasured score.

## Standing project charter — Maximize P(Win) · Own the Outcome

This README preserves the user's project brief as the operating charter for future sessions.

### Mission

Develop a scientifically defensible, original approach for the DOE Geothermal Energy from Multiple Sources of Empirical Data (GEMS) competition's fault-mapping task. Seek a public leaderboard result above **0.3195**, but optimize for measured generalization rather than a lucky single score. Store research, sources, assumptions, model versions, holdout results, and submission hashes durably in this repository so later sessions can continue without losing context.

### Core values

- **Maximize P(Win)**: prefer candidate work that has the highest defensible chance of improving the competition result; do not confuse novelty, visual appeal, a proxy score, or public leaderboard rank with evidence of improvement.
- **Own the Outcome**: verify every important claim against authoritative sources, preserve decisions and failures, identify blockers early, and make any final artifact independently reproducible and format-valid.
- Work autonomously where access permits; surface irregularities, uncertainty, and external dependencies instead of silently filling gaps or asking for avoidable manual work.
- Use free, official, legally shareable external data where it provides a distinct geological signal. Document data versions, licenses, attribution, spatial/temporal coverage, and every transformation.
- Disclose generative-AI use and its extent in the competition narrative, as required by the official rules.

### Non-negotiable submission gates

1. **Do not build or submit a geological candidate until authorized competition inputs are present.** The official data page requires an enrolled/logged-in participant; this environment has not obtained it. Do not bypass authentication.
2. Before implementation, preregister **3–5 untried hypotheses** with the physical signal, relevant layers, why the signal could reveal an unlisted fault, novelty against prior work, external-data availability, estimated DTI upside, and implementation cost. The current register is [`docs/research/hypotheses.md`](docs/research/hypotheses.md).
3. Validate the best candidate against the current holdout best on the same **spatially blocked** holdout and matching prediction-mass budget. Do not spend a weekly submission slot unless the candidate beats that holdout best under the preregistered promotion rule. The public leaderboard score is not a substitute for a holdout baseline.
4. A genuine submission must be a new, reproducible, **single-band float32 GeoTIFF**, in the competition's EPSG:32611 / 100 m grid and matching extent, with predictions in **[0, 1]** inside the valid footprint and null/NaN outside it. Independently validate it before upload; reject nodata sentinels, infinities, out-of-range values, grid mismatches, and accidental multiband output. Never copy a previous submission or publish a placeholder.
5. Put a valid, genuinely validated submission download first on the project site. Include an executive-summary guide with the unique submission name, exact upload steps, and a short DrivenData note. If no validated file exists, explain the gate in place of a download link.
6. Run and document three review passes before declaring a deliverable finished. Report remaining limitations and next actions. Create a pull request from the fixed Arena branch and merge it to `main` only if repository access and checks permit.

### Official competition facts to retain

- The task is to map faults; the public description specifies a distance-weighted Tversky metric with a triangular 300 m support, `alpha=0.2`, `beta=0.8`. False negatives receive the larger weight, but that alone does not explain the score of any particular submission.
- The required prediction grid is EPSG:32611 at 100 m, matching the supplied bounds/grid; the submission is one float32 prediction layer with values in [0,1] and null/NaN outside the grid footprint.
- The homepage listed the competition end as **2026-12-03 23:59 UTC** when checked on 2026-10-06. The rules PDF has a different time wording; see the dated irregularities note before relying on the deadline.
- The rules permit up to three feedback submissions per week and require one final submission; the selected final file is used in both prize rounds. Confirm the live rules before an upload.
- The official board is at <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>. Do not scrape, poll, mirror, or schedule a copy of it: DrivenData's Terms of Use prohibit automated monitoring/copying and manual monitoring/copying without prior written consent. A live link is the only feed implemented here unless written permission or an authorized API is obtained.

## Current verified status

- **Competition data:** not available in this checkout. The unauthenticated official data page redirects to login. No training labels, feature raster, official grid/sample, or competition TIFF is present.
- **Candidate model:** none. No holdout score has been produced in this checkout.
- **Submission:** none. No TIF download is linked or implied.
- **Score attribution:** the reported `H33/H33-2-B2 = 0.2778` is unverified. The official public board's `0.2778` entry belongs to `extradr19`; the inspected owner-maintained GEMSDOE32 page calls the H33 artifact **UNSCORED** and labels `0.2747` a model projection, not an organizer score. There is no evidence linking H33 to `extradr19`.
- **Leaderboard comparison (point-in-time, reviewed 2026-10-06):** the current public leader was **0.3345**, above the earlier cited **0.3195** (then fifth); the board also showed `extradr19` at **0.2778** (then thirteenth). These are dated observations, not a cached or automatically refreshed feed. See [`docs/research/score-analysis.md`](docs/research/score-analysis.md) and the official live link above.
- **Deadline irregularity:** official homepage says Dec. 3, 2026 at 23:59 UTC; the rules PDF says 5:00 p.m. ET on Dec. 3. Treat the earlier time as safer and seek clarification from the organizer.
- **Data-source precheck:** a new candidate register is documented, and official catalogue queries confirm relevant public data records in parts of the broad study-area rectangle. Catalogue metadata is not the same as downloaded/quality-checked data or successful model validation.

## Durable project map

- [`docs/index.html`](docs/index.html) — project home and readiness status.
- [`docs/guide.html`](docs/guide.html) — executive summary and exact submission procedure (currently states that no file is ready).
- [`docs/hypotheses.html`](docs/hypotheses.html) — readable hypothesis ranking.
- [`docs/analysis.html`](docs/analysis.html) — H33 score-attribution analysis and dated leaderboard comparison.
- [`docs/sources.html`](docs/sources.html) — official sources, provenance, availability checks, and limitations.
- [`docs/research/hypotheses.md`](docs/research/hypotheses.md) — preregistered candidate hypotheses and validation plan.
- [`docs/research/score-analysis.md`](docs/research/score-analysis.md) — exact score evidence and caveats.
- [`docs/research/source-register.md`](docs/research/source-register.md) — authoritative sources, query dates, attribution, licensing, and limits.
- [`docs/research/validation-plan.md`](docs/research/validation-plan.md) — locked four-block / 300 m spatial holdout protocol and promotion gate.
- [`docs/research/review-log.md`](docs/research/review-log.md) — three-pass review record and outstanding work.
- `data/raw/` — local competition inputs only after lawful download; ignored by Git. See [`data/README.md`](data/README.md).
- `data/processed/` — local manifests and intermediate products; ignored by Git.
- `submissions/` — generated outputs only after passing every gate; ignored by Git unless a final, real submission is deliberately added.

## Continuing from here

1. Enroll/sign in at the official competition page and download the files through its authorized interface.
2. Place the official archive in `data/inbox/` and run `bash scripts/download_competition_data.sh`; that script only imports a locally obtained archive and does not contact DrivenData.
3. Set up `python -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`, identify the archive's real filenames, and run `.venv/bin/python scripts/validate_inputs.py --features … --labels … --sample …`. Then obtain the current holdout-best raster/score and documented split. Do not assume a leaderboard score is a holdout baseline.
4. Resolve the first-ranked InSAR hypothesis' exact raster coverage and variable/quality layers; compare against the same holdout best. If it fails the gate, do not consume a weekly slot.
5. Only then implement a candidate, validate its score and geospatial encoding, generate its uniquely named TIF, update the site, and review the complete evidence trail.

## Environment and test status

- Python: 3.11.2. The base environment initially lacked the project dependencies; they were installed into the ignored local `.venv` for this review: NumPy 2.4.6, SciPy 1.17.1, Rasterio 1.4.4, pytest 8.4.2. Ruff 0.16.10 was installed locally for lint/format review but is not a runtime dependency.
- Verified commands: `.venv/bin/pytest -q` (**26 passed**), `.venv/bin/ruff check src scripts tests`, `.venv/bin/ruff format --check src scripts tests`, `bash -n scripts/download_competition_data.sh`, and `pip check` (all passed). The only automated tests use synthetic fixtures; they do not validate competition data or demonstrate geological performance.
- Fresh setup: `python -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`. `.venv/` is ignored by Git. No competition data, labels, current holdout best, model, or submission file was downloaded/generated by this review.
