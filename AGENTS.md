# Session protocol for agents working in this repository

1. **Read [`PROMPT.md`](PROMPT.md) first.** It is the objective: a unique TIF submission for the DOE
   GEMS Prize Challenge (DrivenData #306) that beats the leaderboard, plus the hard constraints
   (no hallucinations, line-by-line verification, flag irregularities, free official sources only,
   site with an obvious download and an executive summary explaining exactly how to submit).
2. **Then read state, not history:** `README.md` (current numbers), `registry/hypotheses.json` (what is
   already tried and what was falsified), `registry/irregularities.json` (what is contested),
   `registry/sources.json` (what each official source underwrites).
3. **Never repeat a falsified arm as if it were new.** In particular: the spatially blocked catalogue
   holdout is a rejected instrument (IR-46-04); measured geothermometry as an *addition* arm was
   falsified by the group (H46-5 lists the untested pruning direction); DFA to an absolute 0.5
   threshold is wrong for this dataset (IR-46-05).
4. **Rules for new work**
   - Proposal first: 3–5 hypotheses with layers, physical signature, why off-catalogue, how it differs
     from everything already in the repository, expected DTI, implementation cost (PROMPT.md §5).
   - Validate on the off-catalogue proxy **at matched emitted mass and identical exclusion rules**
     before touching the scored slot.
   - If a hypothesis needs external data, name the exact free official source and check it is reachable
     from *this* environment before calling the idea viable (currently reachable: github.com, pypi.org).
   - Keep `registry/` receipts authoritative: numbers in the site come from `scripts/build_site.py`
     reading `registry/*.json`, never typed by hand.
5. **Verification gates before finishing a session**
   ```
   python3 -m pytest tests -q          # metric vs published example + brute force; DFA calibration
   python3 scripts/verify_all.py       # adds pinned hashes + a full format audit of the shipped TIFs
   python3 scripts/build_h47_site.py   # active site must regenerate byte-identically (CI diffs it)
   ```
6. **Reporting style** — state what was measured, what was assumed, and what is owner-reported.
   Label negative results as negative results; they are the most useful output of this project.

## H47 session handoff (2026-10-06) — supersedes R10 guidance for the active site

Read `registry/h47.json`, `docs/research/h47-review.md` and `docs/research/h47-hypotheses.md` before
touching an artifact.

* **Active site builder:** `scripts/build_h47_site.py` (writes `index.html`, `docs/index.html`,
  `docs/executive-summary.html` from `registry/h47.json`; CI runs it and diffs the three pages).
  `scripts/build_r10_site.py` and `scripts/build_site.py` are historical — running them overwrites
  the active pages.
* **H47-1 status: HOLD_DO_NOT_SUBMIT** (`registry/h47.json → screen.verdict`). The shipped
  full-field emission at matched mass (37,654 dots) scores 0.053242 against the incumbent's 0.088516
  on the stratified instrument (delta −0.035274, paired t −5.48 over 127 blocks, ranking AUC over
  the incumbent's own dots 0.497). The artifact is unique and format-audited and is published for
  inspection only. **Do not spend the weekly slot on it.**
* **Format rule measured from the files that actually have live scores:** the three family files
  (0.2600/0.2708/0.2778) are all-finite single-band float32, min 0, max 1, zeros outside the
  footprint, no nodata sentinel. Ship that shape (the `-zeros` twin); the NaN-outside twin matches
  the template's footprint but NaN fails a naive `0 <= v <= 1` check — that is the historical
  "Predicted values must be in range [0, 1]" portal error. Both twins are audited by
  `scripts/verify_all.py` §5b.
* **The three live-scored family files are ONE dot set** (exact nesting C ⊂ B ⊂ A, identical
  37,654-pixel core beyond 200 m of the catalogue). The whole 0.26→0.28 progression is removal of
  near-catalogue dead mass. Any new arm must win by placement of new dots, not by re-thinning.
* **Instrument rule** (`registry/h47.json → ladder`): the catalogue-in-block holdout and the
  un-stratified SGMC truth **invert** the live order; only SGMC truth stratified at ≥3 px (module
  default 5 px = 500 m) reproduces 0.2600 < 0.2708 < 0.2778. A uniform-random emission at matched
  mass scores T ≈ 4,140 ± 70, so the instrument's useful range is ±20% of chance — screen only.
* **Falsified:** along-strike continuation of catalogue tips (H47-2: 12–16% hit rate vs a 30.5%
  random base rate); catalogue-supervised detection as a route to new faults (H47-1: ranking AUC
  0.497 over the incumbent's dots, flat hit-rate 12.1% → 9.4% from 5k to 120k dots).
* **Blocked, named, not faked:** 1 m lidar/3DEP–GeoDAWN scarps (competition data tab login-walled;
  sciencebase/usgs/s3 hosts return HTTP 000 here) and the raw USGS earthquake catalogue.
* R10 remains HOLD_DO_NOT_SUBMIT. R10↔0.2778 overlap measured: 260 shared pixels, Jaccard 0.0035
  (the equal 37,654 counts are coincidence). The old hidden-truth-count and independence claims stay
  withdrawn. Aggregate leaderboard values are not file receipts.

## R12 session handoff (2026-10-06, later than the R11/H47 arms above)

Read [`registry/r12.json`](registry/r12.json) and [`docs/research/r12-review.md`](docs/research/r12-review.md)
before using any artifact.

* The **active artifact is R12**: `docs/r12/gems46-r12-scarp-rad-concordance-23e807e2de9f-zeros.tif`.
  It is the first arm in this repository to use the **2 m LiDAR scarp morphology** and the **airborne
  gamma-ray spectrometry** layers, and the first to obtain them at all: the H47 session recorded those
  layers as blocked (login-walled data tab, HTTP 000 from the sandbox); R12 restores them from a
  hash-pinned public mirror (`bash scripts/restore_r12_reference.sh`, USGS GeoDAWN DOI
  10.5066/P93LGLVQ). "Blocked" is a statement about one route, not about obtainability.
* **Instrument conflict, measured and closed (IR-46-18).** R12's original gate used SGMC truth >200 m
  from the catalogue (66,277 px), which is *not* one of the variants the H47 ladder showed to preserve
  the live ordering. R12 was therefore re-measured on `gems47.proxy.instrument_sgmc_stratified`
  (d0 = 5 px, catalogue masked as `known`, whole footprint, matched mass) under a rule amended *before*
  the measurement (`docs/research/session-r12-plan.md` §7.1). Stratified truth 56,822 px — identical to
  that ladder's d0 = 5 row. **R12 T = 9,003, DTI 0.16622, hit rate 16.42 %** vs the incumbent's
  **T = 5,081, DTI 0.09474, 10.50 %** (Δ +0.07148, 1.75×); uniform random at matched mass T ≈ 3,695.
  Both preregistered readings pass, so the status is `PROXY_GATE_PASSED_NOT_SUBMITTED`. **Never quote
  the 0.10420 blocked-block figure without naming its instrument**, and never convert a proxy ratio
  into a predicted live score: the same instrument puts the incumbent at 0.09474 where the board says
  0.2778.
* **Two negative results** are part of the record and must not be re-proposed as new: a **strong**
  two-sensor concordance gate (w ≥ 0.5) is worse than morphology alone, and **ridge-axis thinning**
  cost 0.010–0.029 DTI in all fifteen configurations tried.
* **Correlation must be reported in three parts** — emitted-pixel, raw field, smoothed field. A
  single "low correlation" claim hides the +0.53 smoothed-field Spearman against the GEMSDOE32 file
  (IR-46-15).
* **Live pages** (`index.html`, `docs/index.html`, `docs/executive-summary.html`) are owned by
  `scripts/build_r12_site.py` from `registry/r12.json`; `scripts/build_site.py` delegates to it and
  writes only archived `docs/h46/` pages. `scripts/build_readme_status.py` owns the README block
  between the `R12 STATUS` markers. The R11, R10 and H47 artifacts stay on disk with their receipts.
* Restore steps: `restore_competition_data.sh`, `restore_r10_reference.sh` (comparators),
  `restore_r12_reference.sh` (USGS GeoDAWN gamma-ray + LiDAR layers). Every pin is in
  `registry/data_manifest.json`.
* Still blocked: the USGS ANSS hypocentre catalogue. `earthquake.usgs.gov` returns HTTP 000 from this
  sandbox; the free official source is named in the plan rather than assumed away.

### R10 handoff (kept for audit)
`registry/r10.json` describes the DFA-crossover candidate: unique and format-valid but
`HOLD_DO_NOT_SUBMIT` after a failed blocked proxy gate. `registry/submissions.json` describes
historical, pre-index-fix H46 files. The old hidden-truth-count and independence claims are withdrawn.
Do not use aggregate leaderboard values as authenticated file receipts.
