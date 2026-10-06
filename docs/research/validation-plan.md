# Locked spatial-validation plan

**Status:** protocol defined, not executed. Competition rasters, labels, sample grid, and current local holdout-best prediction are absent. This file deliberately does not invent a validation score.

## Objective and baseline

The decision is whether a preregistered candidate (initially H46-1) improves on the **current project holdout best**. A public leaderboard score such as 0.3195 or 0.3345 is not the baseline for this test. The baseline must be an identifiable candidate artifact/pipeline with its own reproducible out-of-fold predictions on the same split, grid, label semantics, and validity mask.

## Spatial holdout construction

1. Read the official training label raster and exact valid footprint only after authorized download. Confirm the competition grid (EPSG:32611, 100 m) and record checksums, shapes, affine transform, CRS, nodata, label values, and feature layer names.
2. Before inspecting candidate scores, divide the valid spatial domain into **four contiguous geographic blocks** using the projected grid (a balanced 2-by-2 partition is the starting design; adjust only if a region contains too few positive labels and record the reason).
3. For each fold, hold one block out and embargo every training label within **300 m** of that held-out block. Do not random-split pixels. Any model weights, thresholds, feature selection, or probability calibration that use labels must be fitted using the remaining training area only. Candidate data acquisition/processing is allowed only if it does not consume the held-out labels.
4. Generate fold-specific validation predictions. Stitch the four prediction blocks into an out-of-fold map so that every scored pixel is predicted without its local labels or labels within the 300 m embargo having trained/tuned its predictor.
5. Compute the published official DTI on the stitched map and full eligible truth mask. Also report foldwise diagnostics, positive-label counts, valid-area coverage, total prediction mass, and uncertainty. Do not rely on a single random seed or choose the best of many held-out thresholds.
6. Any foldwise DTI diagnostic must document how its 300 m neighborhood is treated at block edges. The global stitched-map DTI is the primary decision statistic; the folds are spatial stability diagnostics, not four independently optimized leaderboard estimates.

## Predeclared promotion gate

A candidate may proceed to submission-candidate packaging only if all of the following hold:

- It strictly beats the current holdout-best mean/global out-of-fold DTI on identical masks and folds.
- It improves over the baseline in at least **3 of 4** spatial blocks; report all fold results whether positive or negative.
- Candidate and baseline use a comparable prediction-mass budget. If a calibration is needed, fit it in training folds only; report both natural-mass and matched-mass results.
- The improvement is not caused by label leakage, an untracked data revision, extra invalid coverage, a grid/mask discrepancy, or repeated tuning on the final validation labels.
- Ablations/diagnostics support the named physical signature (for H46-1, coherent persistent displacement structure, not only pumping bowls, layover, or low-quality pixels).

This is a stricter internal guardrail, not a DrivenData rule. Passing only makes it eligible for a weekly feedback slot; it does not guarantee the private score or an eventual prize result. A candidate that fails the gate is archived as a negative result and does not use a weekly submission slot.

## Current blocker and honest conclusion

No official labels/features/sample, no current holdout-best artifact, and no candidate raster exist in the checkout. Therefore there is no valid split to freeze and no DTI comparison to run. The first-ranked hypothesis has an official catalogue-availability precheck, but that is not validation. The correct status is **blocked before model implementation**, not “candidate passed” or “model ready.”

## Score implementation requirements

The local scorer must be checked against the official metric definition, including the 300 m triangular kernel, maximum prediction credit per truth pixel, distance-weighted false positives, and `alpha=0.2`, `beta=0.8`. Edge cases must have automated tests (perfect aligned prediction, a prediction at an offset distance, no predicted mass, invalid values, and empty truth handling). If a future official scoring library is available, compare implementations on identical small arrays before using local scores for decisions.

## Reproducibility record required per run

- candidate ID, source code revision, environment/package versions;
- hashes and provenance for labels/features/external data and the official grid/sample;
- spatial fold/embargo definition and file hash;
- baseline artifact/model ID and out-of-fold predictions;
- per-fold and primary DTI, matched/natural probability mass, valid coverage, and uncertainty;
- parameter choices made without viewing final holdout results;
- decision (`promote` / `reject` / `blocked`) and reviewer notes.
