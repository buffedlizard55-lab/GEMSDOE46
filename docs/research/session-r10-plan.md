# R10 preregistration — 2026-10-06

Written before implementation. No numeric DTI gain is defensible in advance. Ranking is qualitative expected benefit adjusted for failure risk, not a forecast. All four proposals use restored competition bands; no new external data is required. Novelty here means absent from the inspected local implementations, not an exhaustive proof across every family repository.

| Rank | Hypothesis / layers | Physical signature and off-catalogue rationale | Difference from existing work | Expected improvement / cost |
|---|---|---|---|---|
| 1 | H46-R10: raw-field DFA crossover corroboration; RTP band 2 and isostatic gravity band 13 | Difference of short-scale (0.8–3.2 km) and long-scale (3.2–12.8 km) DFA slopes, plus long-slope departure from the regional background; coincident anomalies may indicate buried changes in source texture without amplitude edges. Lithology and survey processing remain confounders. | Existing DFA fits one slope, includes derivative bands and high-pass variants, and takes a maximum. This arm uses raw fields only, six scales, exact window-local detrending and a minimum across the two physics. | Unknown; best direct test of requested mechanism; low/medium CPU cost. |
| 2 | Directional crossover disagreement; bands 2,13 | Compare row/column slope-crossover anisotropy between physics; possible buried shear-fabric corridor absent from surface maps. | Existing row/column exponents are averaged; retain their disagreement and shared direction instead. | Unknown, potentially useful but raster-direction bias; medium cost. |
| 3 | Scale-persistent exponent change; bands 2,13 | Require local-background exponent contrast to persist at 25.6 and 51.2 km windows; seek a source-population boundary under alluvium rather than a narrow scarp. | Existing implementation uses one 12.8 km support, no support-persistence check. | Unknown, less finite-window noise but poorer localization; medium cost. |
| 4 | DFA phase stability; bands 2,13 | Reject crossover anomalies that disappear when block starts shift by half a scale; spatial texture changes should not depend on arbitrary partition phase. | Existing code uses global non-overlapping blocks and no phase robustness gate. | Unknown, primarily artifact suppression rather than discovery; medium cost. |

## Locked R10 experiment
- 512-sample windows, centers on a 16-pixel grid; raw row/column transects only.
- DFA1 scales 8,16,32,64,96,128 samples. All windows require every sample valid; at least four largest-scale blocks.
- Score is geometric mean of absolute slope crossover and absolute long-scale slope departure from a 31-cell regional median. Normalize each physical layer by its valid 99th percentile, clip [0,1], and require both layers through a minimum. No gradient/ridge field enters ranking.
- Emit 37,654 binary cells using the existing spacing-constrained emitter; published catalogue excluded with the existing two-iteration cross dilation (Manhattan, NOT a Euclidean 200 m disk).
- Compare against shipped structural/DFA and conformal files and the downloaded GEMSDOE32 primary at identical exclusion and per-block emission counts. Four-by-four spatial blocks, three-pixel interior guard. This is a fixed detector, not supervised training; no block labels used to tune parameters.
- Measure raw and 800 m-smoothed Pearson/Spearman field correlations, prediction correlations and support overlap. Low correlation threshold: |r| and |rho| <0.2 on all available comparators. Failing it prohibits a distinctness claim.
- No weekly slot unless candidate beats every available comparator in mean paired blocked off-catalogue SGMC DTI and a paired block-bootstrap 95% lower bound is positive. Even passing is only a proxy gate, not evidence of beating the hidden competition set. The proxy has been reused previously, so an untouched independent validation set is still needed.

## Audit findings before implementation
- `alpha_map` maps centers using `center//stride` but labels columns using `j*stride+window//2`: potential window/2 displacement and truncation. Add a regression test and fix placement.
- The existing 128-sample window accepts two 64-sample blocks only at particular phases; new estimator uses independent window-local profiles.
- README claims low Pearson correlation proves physical independence: false. It is only a redundancy diagnostic.
- README's unconditional hidden-truth size and causal score explanation are not identified by the available receipts.
- Live official leaderboard fetched this session: xiaofanhu 0.3774, not 0.3195 or 0.3345. Historical file-to-score mapping remains owner-reported; GEMSDOE32 itself still labels its primary UNSCORED.
