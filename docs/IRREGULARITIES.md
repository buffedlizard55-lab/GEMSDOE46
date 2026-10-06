# Irregularities and audit trail

Everything in this file is either (a) something that could not be verified and is
therefore **not** relied on by the shipped artefact, or (b) a defect that was found
and fixed, kept here with the measurement that found it. Nothing in this list is
hidden from the submission note or the executive summary.

---

## IR-46-01 — No DrivenData account in the build environment *(open, unavoidable)*

**What happened.** The three official rasters cannot be re-downloaded here: the data
tab redirects to a sign-in page, and this sandbox has no account, no browser session
and no credentials (and none were requested). Likewise the submission form cannot be
exercised from here.

**How it is handled.** The rasters used are the project's own copies, verified
byte-for-byte against hash pins recorded when they *were* downloaded from the
competition data tab — `evidence/data_provenance.json` re-computes all three
sha256 digests on every `run_pipeline.py` invocation and aborts on mismatch:

| file | sha256 (verified) |
| --- | --- |
| `labels.tif` | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` |
| `sample_submission.tif` | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` |
| `training_features.tif` | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` |

**Consequence for the reader:** the private test labels are not available anywhere,
and this repository never guesses at them. The upload step must be performed by the
project owner; `docs/SUBMISSION_GUIDE.md` is written for exactly that hand-off.

---

## IR-46-02 — The portfolio's upload was rejected with `Predicted values must be in range [0, 1]` *(mitigated, root cause unreproducible)*

**What happened.** The owner reports that a previously downloaded `.tif` was rejected
by the submission form with `"Predicted values must be in range [0, 1]"`.

**What can and cannot be concluded.** The message is only consistent with a validator
that walks every cell and tests `0 <= v <= 1`. The official problem page nevertheless
specifies *"data outside the bounds is null or nan"*, and the organizer's own
`sample_submission.tif` uses `NaN` outside the survey footprint — so a strictly
specified validator and the sample file disagree with each other on the out-of-bounds
region. The rejection cannot be reproduced here (no account, IR-46-01), so the exact
cause — `NaN` comparison, a different file, or a stale upload — is **unknown** and is
not asserted.

**Mitigation shipped.** Two byte-level encodings of the same dot set are written and
independently re-read:

* `SUBMISSION-GEMSDOE46-r8-conformal.tif` (**primary, upload this one**) — values in
  `[0, 1]` in **every** cell, 0.0 outside the footprint. `all_cells_finite: true`,
  `range_0_1_on_finite_cells: true`.
* `docs/downloads/gemsdoe46-h46a-r8-conformal-nan.tif` — matches
  `sample_submission.tif`'s convention exactly (`NaN` outside the footprint,
  `nan_outside_footprint_only: true`).

The two files are **provably identical under the official metric**: `FPw` sums only
over cells the prediction makes positive, and no dot is ever placed outside the
footprint, so the out-of-footprint encoding cannot change `TPw`, `FPw` or `FNw`.

---

## IR-46-03 — The holdout truth is the catalogue; the scored truth is new faults *(open, quantified)*

The blocked holdout scores a model against held-out **catalogue** pixels, i.e. the
population the competition explicitly *excludes* from the scored set. This is inherent
to the data available without the private labels and is handled three ways rather than
hidden:

1. a density-matched truth population (`pop_thin`, declared ratio 0.1296) is the
   primary population, with four other ratios swept as sensitivity;
2. the **density** penalty is taken from the metric's own algebra instead of from the
   proxy (`src/gems46/analytic.py`);
3. the certified floor in the submission note is a statement about the *proxy*, and
   `docs/SCORE_ANALYSIS.md` says so in the same sentence it reports it.

A per-pixel split would make this worse, not better: the sibling family's own notes
record leakage across the 300 m kernel along long fault traces, which is why whole
blocks (≈ 93 × 55 km) are scored here.

---

## IR-46-04 — 8 of 24 blocks contain no catalogue pixel at all *(handled by a pre-declared rule)*

The surveyed area covers 5,167,373 of the raster's 12,280,360 cells (42.1 %). Eight of
the 24 tiles lie entirely outside it: `(1,4) (1,5) (2,0) (2,4) (2,5) (3,0) (3,1) (3,5)`.
Every arm scores exactly 0 in those blocks, so they carry no information but do
inflate the residual spread of a conformal quantile.

**Rule R1 (fixed before the selection was run):** a block enters the procedure iff it
contains at least one held-out truth pixel. The rule is a function of the truth mask
only, never of an arm's score, so it cannot be used to steer the verdict. The 16
remaining blocks contain 100 % of the footprint.

---

## IR-46-05 — *Fixed:* the emitter's "harmless" candidate guard silently truncated emissions

**The defect.** `emitter.nms_thin` processed candidates in descending score order and
truncated the candidate list to `2.5 · (area / spacing²)` cells, on the theory that no
more than the packing limit can be accepted. The bound on *accepted* dots is true; the
bound on *candidates a score-ordered greedy must examine* is not. The highest-scoring
cells trace the same few ridges, so after ~5,600 accepted dots every remaining
candidate in the truncated list sat inside an already-blocked ball and the emission
stopped. Measured on the full 5,167,373-px footprint at r = 8 px:

| emitter | dots emitted (r = 8 px) |
| --- | --- |
| truncated candidate list (old) | 5,596 |
| every cell above the stopping bar (fixed) | **39,108** |

**Why the saved sweep is still valid.** The guard was per tile, so it never bound
there. The re-run sweep with the fixed emitter is **bit-identical per block** to the
saved one (`/tmp/full_sweep.log` vs `/tmp/full_sweep2.log`, compared line by line:
identical DTI *and* identical dot counts for every block and every spacing). The
selection evidence therefore did not change.

**Why this still mattered.** The *full-grid* file — the thing that actually gets
uploaded — was affected. The previously shipped r = 12 file from the earlier phase was
produced by the truncated path and has been superseded by the measured r = 8 file.
`evidence/submission_*.json` now records both the measured count and the sweep
extrapolation for every candidate arm.

---

## IR-46-06 — *Fixed:* the sweep's dot-count extrapolation overstates the full-grid count

`conformal_select` reports `median_dots_full_footprint = median(per-block dots) × 24`.
The median block emits more than the mean block, and tile-edge blocking differs from
global blocking, so this overstates the shipped count: 67,836 (extrapolated) vs 41,579
(pooled per-tile density moved to the full grid) vs **39,108 (measured)** at r = 8 px.

**Consequence for the decision:** `make_submission.py` applies rule R3 to the
**measured** count of every candidate arm. The arm ranking does not change (r = 8
still has the largest certified floor among admissible arms), but the record is now
the measurement rather than the extrapolation, and both numbers are stored side by
side.

---

## IR-46-07 — The declared scored-truth mass |G| is an assumption *(declared, swept)*

`|G| = 7,905 px` is the declared mass of the scored truth inside the footprint; it is
an assumption, not a measurement (the private labels are unavailable). Every analytic
statement that uses it states it, and `evidence/analytic_screen.json` carries the
sensitivity at `|G| ∈ {3,950, 7,905, 15,810}` px. The R3 admissibility threshold
(86,541 dots for the target 0.3345 at `|G| = 7,905`) scales the same way: at the
pessimistic `|G| = 3,950` the same target allows only 43,270 dots, so the shipped
39,108-dot arm remains admissible across the whole declared range.

---

## IR-46-08 — Band 10's unit is ambiguous and was *not* assumed *(flagged)*

Official band 10 ("distance to earthquake") has a footprint median of 622.8 and a
maximum of 4.96 × 10⁶ in the shipped raster. Whichever unit that is, 4.96 × 10⁶ m
would exceed the raster diagonal (~500 km), so the unit was **not** assumed anywhere:
the H1 test uses a global rank transform and a decay length equal to the band's own
median (unit-free by construction). A unit-dependent feature was therefore never
invented. See `docs/HYPOTHESES.md` §H1.

---

## IR-46-09 — An unverified third-party claim is *not* relied upon *(flagged)*

A third-party note claims that catalogue pixels are masked out of scoring. That claim
is not verified and is nowhere assumed in the code: no feature, no emitter rule and no
selection rule depends on it. It is used only as *motivation* for an experiment whose
conclusion is drawn from public leaderboard numbers (`docs/SCORE_ANALYSIS.md`).

---

## IR-46-10 — *Fixed:* two defects in the driver found during this audit

1. `scripts/run_pipeline.py` advertised `--stage` in its docstring but ran every stage
   unconditionally; and it produced its conformal evidence with
   `stage_conformal`, which called `P.split_folds(results, 0.5)` — the `0.5` landed in
   the `scheme` parameter and silently selected the **contiguous** split instead of the
   checkerboard split that rule R2 specifies. Selection now runs through a single
   implementation (`src/gems46/conformal.py`) used by both the driver and
   `scripts/reanalyse_conformal.py`, and `--stage post` re-runs only the selection from
   saved blocks.
2. `submit.audit` contained a placeholder boolean expression comparing an array to
   itself (`np.array_equal(np.isfinite(a), np.isfinite(a))`), which both raised a
   `ValueError` for arrays of more than one element and — worse — would have been
   vacuous if it had not. It now checks the out-of-footprint encoding against the
   footprint mask, per encoding, and asserts the byte-level positive count equals the
   emitted dot count.

---

## IR-46-12 — GitHub Pages serves the repository **root**, not `docs/` *(mitigated, cannot be changed from here)*

GitHub Pages for this repository is configured as **branch `main`, path `/`**
(`gh api repos/buffedlizard55-lab/GEMSDOE46/pages` reports
`"source": {"branch": "main", "path": "/"}`). The designed site lives in `docs/`, so the site root
would otherwise show a rendered README instead of the page with the download control.

**Attempted fix.** `PUT /repos/…/pages` with `source[path]=/docs` returns
`403 Resource not accessible by integration` — the automation token has no Pages-admin scope. This is
a repository-settings change the project owner can make in one click
(Settings → Pages → Source → `main` / `docs`), or the owner can leave it as is.

**Mitigation that is live now.** A root `index.html` (plus a root `.nojekyll`) is committed, so the
site root **is** the download page: the big download button is the first element, with the audit link,
the exact Note string, both encodings, the six key numbers, and links into the full executive summary,
analysis, hypothesis test and research-layer pages (all under `/docs/`).

**If the owner flips the setting to `/docs`**, `docs/index.html` becomes the root — it carries the
same download block first and the same navigation, so nothing else needs to change.

## IR-46-11 — Score anchors are owner-reported unless marked otherwise *(flagged)*

The score history used in `docs/SCORE_ANALYSIS.md` (0.1922 → 0.2477 → 0.2600 →
0.2708 → 0.2778) is owner-reported from the sibling portfolio. Two of those rows —
0.2600 and 0.2778 — are **also** visible on the live public leaderboard (ranks #20 and
#13 at the time of writing, column "Best DW-Tversky"), which is what licenses treating
the mechanism as real rather than as an artefact of reporting. The live top of the
board at the same time was 0.3345 / 0.3262 / 0.3222 / 0.3218 / 0.3195 / 0.3163 /
0.3060.
