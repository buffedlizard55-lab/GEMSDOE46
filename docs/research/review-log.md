# Three-pass implementation and review log

**Review date:** 2026-10-06 UTC
**Branch:** `arena/61460a10-gemsdoe46`
**Disposition:** infrastructure, research notes, and static site are ready for review; no geological candidate, holdout result, or competition submission is ready.

## Pass 1 — raster, metric, validation, and packaging correctness

**Scope:** `src/gemsdoe46/`, `scripts/`, `tests/`, project dependency/install behavior.

- Implemented and exercised the local published-form DTI components, raster/grid preflight, independent submission-TIFF validation, four-quadrant OOF comparison gates, local ZIP importer, and gated TIF builder.
- The first full test run exposed a real packaging bug: Rasterio rejected small tiled GeoTIFFs because the inherited tile width was not a multiple of 16. The writer now uses valid block dimensions; the regression test covers small-raster packaging.
- Hardened the ZIP importer to stream hashes/copies, reject traversal/Windows absolute paths/symlinks/encrypted entries/duplicate destinations, and preflight names before extraction. It remains intentionally offline.
- Hardened the builder to require a complete versioned passing holdout report, finite positive DTI improvement, all required gates, mass/fold diagnostics, hashes, matching candidate ID, valid in-footprint values, and a known-prior-TIF check or explicit no-prior attestation. The prediction fingerprint includes the valid-footprint mask. Failed packaging removes any output it created.
- **Checks passed:** 26 synthetic-fixture pytest tests; Ruff lint and formatting; `bash -n scripts/download_competition_data.sh`; `pip check`; every Python CLI `--help`; static-site internal-link/anchor tests; and a local preview HTTP response check. The offline archive command returned its expected “no local competition ZIP” exit code 2 and stated that it made no network request.
- **Boundary:** these checks prove code-path behavior on synthetic rasters only. They do not prove that the local metric exactly matches the organizer's production scorer, that any upstream predictions are genuinely OOF, or that a geological model improves DTI.

## Pass 2 — geological reasoning, score attribution, sources, and compliance

**Scope:** `docs/research/hypotheses.md`, `score-analysis.md`, `source-register.md`, `validation-plan.md`, and matching static pages.

- Preserved four ranked, qualitative geological hypotheses with relevant layers, physical signatures, reasons a buried fault could be absent from the USGS/INGENIOUS catalogue, novelty boundaries, official data-source/availability notes, expected DTI upside, and implementation effort. H46-1 OPERA DISP-S1 remains the first experiment, not a validated model. H46-3 ASTER remains conditional because a prior `conj_alteration_mag` run may overlap.
- **Irregularity caught and corrected:** an earlier draft claimed matching-repeat Sentinel-1C acquisitions. The documented Copernicus OData query actually returned S1A-only catalog products and did not establish a repeat pair, current S1C/S1D coverage, payload access, or InSAR feasibility. The claim was removed from the research register and site.
- Recorded a separate unresolved catalog discrepancy: NASA's OPERA catalog summary describes a 2016–2025 span while CMR responses contain 2025–2026 acquisition periods. The metadata has not been reconciled; no OPERA payload was downloaded.
- H33/H33-2-B2 = 0.2778 remains **unverified**: the dated public-board row was `extradr19`; the owner-maintained GEMSDOE32 page reports H33 as “UNSCORED” and 0.2747 as a projection. The 2026-10-06 point-in-time board review put 0.3345 first and 0.3195 fifth. That snapshot is carried forward from the single dated review and was not re-polled/re-copied during this implementation review. No causal score explanation is claimed.
- Respected DrivenData's Terms of Use: no crawler, polling, scheduled monitor, or leaderboard mirror. The site contains an attributed, dated snapshot and a link to the official live board. The deadline disagreement (homepage 23:59 UTC vs. rules 5 p.m. ET) is explicitly flagged; plan for the earlier time pending organizer clarification.
- **Boundary:** public catalogue records show only partial-area metadata availability. No competition data, external raster payload, labels, feature grid, sample TIF, current holdout-best artifact, or submission receipt is present. Novelty cannot be exhaustive without auditing prior runs/artifacts.

## Pass 3 — site, accessibility, operational flow, and repository safety

**Scope:** `docs/index.html`, `guide.html`, `hypotheses.html`, `analysis.html`, `sources.html`, `404.html`, `assets/site.css`, data/submission policies, and delivery flow.

- Built a responsive, static, no-JavaScript site with an accessible skip link, keyboard-focus styles, reduced-motion handling, descriptive page titles, semantic sections/tables, responsive overflow, external-link protections, and a consistent desktop/mobile navigation.
- Put the submission-file status gate before the landing hero. It clearly states that no validated TIFF exists; the button is disabled rather than linking to a placeholder. The guide gives a deterministic filename pattern and instructs the portal name to match the generated filename stem exactly.
- Documented authorized portal steps, local data import and preflight, spatial-holdout and submission gates, feedback-slot/final-selection cautions, the DrivenData terms note, source attribution, and limitations.
- Automated page checks found no duplicate IDs or broken local links/anchors. External `target="_blank"` links carry `noopener noreferrer`; no client-side request can poll or mirror the leaderboard. A live local preview is running on port 8080.
- **Boundary:** the live preview is available for a human visual review; this agent did not run a formal browser/assistive-technology audit or organizer-run upload test. No actual validated output exists.

## Remaining work / handoff

1. Enroll/sign in and download the competition archive using the official participant Data page. Do not bypass login or put credentials in Git.
2. Inspect the archive's true band names, masks, label semantics, grid, and licensing. Run `scripts/validate_inputs.py` after setting up `.venv`; adapt assumptions only with documented evidence.
3. Obtain an identifiable current spatial holdout best and its out-of-fold predictions. Freeze four geographic blocks and the 300 m label embargo before viewing candidate performance.
4. Resolve exact OPERA DISP-S1 variables/quality layers, full-grid valid coverage, catalog-period discrepancy, and confounders. Validate H46-1 against the current holdout best; if it does not pass the preregistered gate, do not use a weekly slot.
5. Audit all known prior submission TIFs and the possible ASTER overlap before claiming global uniqueness/novelty. Build and publish a unique TIFF only after the actual holdout gate and independent format validation pass.
6. Confirm the official deadline discrepancy with organizers, use only the live official board for any later score check, and update the site snapshot only through a permitted/manual process.
7. Create the PR from this fixed Arena branch and merge only if repository access and checks permit. No commit, push, PR, or merge has been made at the time this review log was written.

## 2026-10-06 · R11 (this session)

* Restored and hash-verified all four organiser/proxy rasters plus three previously unused USGS
  GeoDAWN layers (gamma-ray K/Th/U/TC, contractor Th-K-U ratios and 150 m up-continued TMI, and 12
  channels of 2 m LiDAR scarp morphology). Verified that no prior arm in this repository used them.
* Preregistered five hypotheses before implementing (`session-r11-plan.md`), with the USGS ANSS
  hypocentre arm marked BLOCKED after re-measuring that `earthquake.usgs.gov` is unreachable here.
* Exploratory whole-domain screen (`evidence/r11_layer_screen.json`): LiDAR morphology 0.141–0.145,
  gamma-ray 0.106–0.112, magnetic gradient 0.079, gravity gradient 0.046, naive composites 0.090–0.108.
* Built `src/gems46/concordance.py` with 12 unit tests; found and fixed a constant-channel tie-break
  bug in the rank transform.
* Locked 6×6 experiment: froze w = 0.25, fallback q = 0.90, no thinning on odd blocks; R11 then beat
  every comparator on even blocks (0.10420 vs 0.09368, bootstrap [+0.00140, +0.02121]).
* Falsified in the open: a strong concordance gate and ridge-axis thinning.
* Fixed a block-slicing bug, the over-strict inherited gate (both readings now reported), and the
  two-builders-one-page conflict (IR-46-12).
