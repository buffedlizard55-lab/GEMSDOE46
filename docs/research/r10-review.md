# R10 scientific review — 2026-10-06

## Executive decision

A unique, independently computed DFA-crossover GeoTIFF is available in `docs/r10/`. It passed raster-format and low-correlation checks, but failed the preregistered proxy-improvement gate. **HOLD; do not use a competition slot.** No organizer score exists. Complete measurements: [receipt](../r10/receipt.json). All displayed comparisons are local proxy measurements, not predictions of leaderboard scores.

## Why might GEMSDOE32 have scored 0.2778?

The owner's mapping of 0.2778 to H33-2-B2 is not independently authenticated. [The GEMSDOE32 page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html), retrieved this session, still calls that file UNSCORED and describes removing near-catalogue dots from an earlier sparse prediction. The official leaderboard lists a participant score, not a file hash. Treat the attribution as owner-reported.

From [the official metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/), define T=weighted truth coverage, S=prediction mass, M=sum over predictions of their nearest-truth kernel credit, G=number of truth pixels. Then exactly:

`DTI = T / [0.2(T+S−M) + 0.8G]`.

Sparse thinning can improve DTI by removing low-value predictions while preserving coverage, but `M=T` is an additional approximation, not a mathematical identity. A single emitted pixel can cover multiple truth pixels; multiple predictions can compete for one truth pixel. Nor does removing catalogue-adjacent predictions necessarily have zero lost coverage. Masking of known faults does not establish a 200 m exclusion as universally optimal.

The old README promoted `G≈14,089`, `T≈5,223` and zero-credit pruning to facts. They were model-dependent deductions under restrictive assumptions, not identifiable hidden-label measurements. The corrected conclusion is that mass efficiency is a plausible explanation for the family's reported score gains. A causal explanation requires organizer receipts plus controlled ablations; neither is available here.

**Can we beat it?** Possible in principle, not demonstrated by this experiment. At a fixed denominator, reaching 0.3195 from 0.2778 requires 15.0% more numerator, and reaching the freshly observed leader 0.3774 requires 35.9% more. These are conditional ratios, not score forecasts or estimates of fault counts. Improvements can come from better localization, better coverage, or better removal of false positives; there is no proof that only DFA or only new geophysical features can help.

## What R10 actually measures

Raw RTP magnetics (band 2) and isostatic gravity (band 13), row and column transects, 512 samples per window, centers 16 pixels apart. DFA1 detrends the cumulative demeaned signal separately inside each window. RMS residuals are measured at scales 8,16,32,64,96,128 samples (0.8–12.8 km). Short-scale and long-scale log-log slopes share the 32-sample pivot. The slope crossover magnitude and the long-scale slope's departure from a 31-center median background define each field's score; the lower normalized score of the two physics is retained. No raw-field gradient, curvature or previous prediction enters this ranking. A shared historical emission rule produces 37,654 binary dots.

This is a finite-scale texture test, **not a demonstration of asymptotic long-range dependence**, a fault, permeability, a geothermal vent, or an earthquake precursor. The 51.2 km support is much wider than the competition's 300 m matching kernel. That localization mismatch is a plausible reason for failure and must be addressed before further slot expenditure.

[Peng et al. 1994](https://doi.org/10.1103/PhysRevE.49.1685) introduced the cited analysis in a DNA-sequence setting, not a geothermal application. [Varotsos et al. 2009](https://doi.org/10.1063/1.3130931) reports magnetic time-series spikes behaving randomly at short time lags and showing exponent approximately 0.9 at longer lags; electric variations show approximately 1 over available scales. This is not direct evidence that a static spatial gravity raster crosses 0.5 to 1 at fault rupture. R10 deliberately avoids that absolute threshold.

## Validation and its limits

The fixed, label-free detector is compared on a 4×4 spatial tiling with three-pixel interior guards, the same catalogue exclusion, and identical prediction counts for every method in each evaluable block. Nine blocks are evaluable with shared positive emission capacity and proxy truth. Two additional truth-bearing blocks have zero R10 emission capacity; these are recorded as coverage failures and independently block promotion, not silently treated as evidence of performance. Five blocks have no proxy truth or an empty domain. Comparator predictions are re-emitted from their fields using the same rule; these are not scores of the original files. No proxy labels are used for parameter tuning in R10.

- R10 mean block DTI: **0.06169359**.
- Best tested comparison, GEMSDOE32: **0.10328873**.
- Paired mean difference: **−0.04159514**.
- Seeded block-bootstrap 95% interval: **[−0.06143257, −0.02199840]**.
- Largest absolute tested field Pearson/Spearman correlation: **0.05517048**.

The SGMC proxy has already been reused in previous sessions. It is not an untouched competition-representative holdout, and overlapping DFA windows couple neighboring blocks. Bootstrap intervals are descriptive, not independent-trial significance. The [USGS SGMC publication](https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc-geodatabase-conterminous-united-states) describes source map scales from 1:50,000 to 1:1,000,000; rasterizing at 100 m does not create 100 m positional accuracy. That page now links a newer 2026 release; it was not substituted into this locked experiment.

Low correlation is evidence of non-redundancy on the chosen mask, not proof of geological independence. The new candidate differs at the pixel level from every locally shipped TIF inspected and from the restored GEMSDOE32 primary. Universal novelty across every public GEMSDOE artifact was not established. The submitted hypothesis is new relative to inspected local implementations; every online site was not exhaustively audited.

## Three review passes

1. **Implement:** restored and hash-checked competition rasters and SGMC proxy; preregistered four hypotheses; implemented window-local DFA crossover; generated candidate; measured blocked comparisons and correlation.
2. **Review/fix:** corrected legacy DFA center indexing, added independent numerical-reference and affine-invariance tests, fixed empty-prediction metric credit at raster borders, fixed SGMC restoration (previously warned and returned success with missing data), removed invalid scientific claims from the active README.
3. **Recheck:** rerun tests, pinned-data/legacy audits, independent new-file audit and deterministic regeneration; check site links and gate status; retain failed gate prominently; PR/merge and deployment status are reported separately, not assumed.

## Next-session priorities and limitations

1. Do not tweak R10 parameters repeatedly on these same nine blocks. Lock a genuinely unused geographic evaluation region and obtain better-positioned independent validation before choosing among related transforms.
2. Test phase robustness and directional anisotropy only as new preregistered ablations. Neither has demonstrated benefit yet. Corrected legacy DFA maps invalidate claims that old artifacts exactly reproduce from current source; archived bytes remain available but must not be silently relabeled as corrected.
3. Investigate narrowing the localization support without treating interpolated coarse windows as 100 m evidence. Require synthetic regime-boundary localization tests and survey-processing controls.
4. Authenticate file-to-score mappings with actual submission receipts when available. No credentials are requested or stored. Private competition labels are intentionally unavailable and cannot be inferred uniquely from aggregate scores.
5. CPU execution succeeded; a GPU is not required for this detector. The prior statement that data placement is the only blocker to winning/training is misleading: data are now restored, but scientific validation and generalization remain unsolved. No neural-network training or automatic competition submission was performed.
6. Input hashes establish consistency with public family mirrors, not authentication by the organizer. The all-finite export avoids NaN/sentinel range failures, but portal acceptance has not been tested. Official format text mentions null/NaN outside bounds; this file exactly matches raster bounds and uses zero outside the template footprint.
7. Do not claim a continuously verified live feed: official board numbers are timestamped observations. Automated monitoring must respect site terms; the active page links directly to the live board and labels its cached snapshot date.
