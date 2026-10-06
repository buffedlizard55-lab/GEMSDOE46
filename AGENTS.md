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

## R11F session handoff (2026-10-06) — the active candidate

Read `registry/r11f.json`, `docs/research/r11f-review.md` and `docs/research/session-r11f-plan.md`
before touching an artifact.

* **Active site builder:** `scripts/build_r11f_site.py` (writes `index.html`, `docs/index.html`,
  `docs/executive-summary.html` from `registry/r11f.json`; CI runs it and diffs the three pages).
  `build_r11_site.py`, `build_h47_site.py`, `build_r10_site.py` and `build_site.py` are historical —
  they write the same three pages from older receipts and would overwrite the active site.
  `scripts/build_irregularities_page.py` renders `docs/irregularities.html` from
  `registry/irregularities.json`; it is diffed by CI too.
* **R11F status: `PROXY_GATE_PASSED_NOT_SUBMITTED`.** On the stratified-SGMC instrument that
  reproduces the three known live orderings (d0 = 5 px, 127 truth-bearing blocks) the candidate
  scores 0.16619 against the live-scored 0.2778 file's 0.08852, random control 0.06835; paired
  +0.06476, t = +6.77 (matched-mass re-emission +0.03837, t = +4.31). **No slot used; submission is
  the user's decision.**
* **The win is placement, not pruning.** The R11F field's AUC over the incumbent's own dots is
  0.507 — chance. Do not re-run thinning experiments: the metric's algebra (`DTI = T/(0.2N + 0.8G)`)
  says a dot is worth emitting exactly when its marginal kernel credit beats `0.2·DTI`, and that is
  what `src/gems46/optemit.py` implements (brute-force checked in `tests/test_optemit.py`).
* **New information is the lever.** Two families absent from the official stack matter: 1 m lidar
  terrain descriptors (mirrored) and the GeoDAWN K/Th/U/ratio grids (DOI 10.5066/P93LGLVQ). Official
  band 6 is the radiometric *total count* despite its label (IR-46-14).
* **Four DFA implementations have failed** (R10, H46-1, R11-A, R11F re-localised). Treat the DFA
  regime-break idea as falsified unless a genuinely new statistic and a new instrument appear.
* **Never merge main's R11 arms into R11F's names or vice versa:** `registry/r11.json` (A/C/D) and
  `registry/r11f.json` (fusion) are different experiments with different instruments.

## R11 (arms A/C/D) session handoff (2026-10-06) — historical, superseded by the R11F handoff above

Read `registry/r11.json`, `docs/research/r11-review.md` and `docs/research/session-r11-plan.md`
before touching an artifact.

* **Active site builder:** `scripts/build_r11_site.py` (writes `index.html`, `docs/index.html`,
  `docs/executive-summary.html` from `registry/r11.json`; CI runs it and diffs the three pages).
  `scripts/build_h47_site.py`, `scripts/build_r10_site.py` and `scripts/build_site.py` are historical
  — they write the same three pages from older receipts and would overwrite the active site.
  `scripts/build_irregularities_page.py` renders `docs/irregularities.html` from
  `registry/irregularities.json`; it is also diffed by CI.
* **R11 candidate status: `PROXY_GATE_PASSED_NOT_SUBMITTED`** (`registry/r11.json → status`). It is
  unique, format-audited (all-finite, min 0, max 1, zeros outside the footprint) and, on the
  stratified-SGMC instrument that reproduces the three known live orderings, it beats the
  live-scored 0.2778 file 0.16619 vs 0.08852 with the random control at 0.06835 (paired +0.06476,
  t = +6.77, 127 blocks). **No slot has been used; submission is the user's decision.**
* **Do not describe any proxy number as a score forecast.** The stratified instrument's truth is a
  1:50k–1:1M compilation ~4× denser than the inferred hidden set and is not the competition's label
  set. The preregistered gate (un-stratified SGMC) is published beside the Pass 3 instrument, not
  replaced by it; the un-stratified version *inverts* the live order.
* **What actually moved the needle:** new evidence families (mirrored 1 m lidar terrain descriptors
  and the GeoDAWN K/Th/U/ratio grids — the official stack has only the radiometric total count,
  IR-46-14) plus an emitter whose accept rule is the metric's own marginal break-even
  (`src/gems46/optemit.py`). Pruning the incumbent's dots does not work: the R11 field's AUC over
  the incumbent's own dots is 0.507.
* **Negative results stay published:** the brief's DFA regime-break arm (R11/H46-R11-3) and the
  earlier R10 crossover both fail their gates; H47-1 (catalogue-supervised lineament detector) is
  `HOLD_DO_NOT_SUBMIT` on the same instrument R11 passes.

## H47 session handoff (2026-10-06) — historical, superseded by the R11 handoff above

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
