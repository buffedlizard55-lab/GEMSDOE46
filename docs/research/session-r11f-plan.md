# Session R11F preregistration — 2026-10-06

**Written before any R11F field was computed or any blocked-proxy score was inspected.**
Everything below is a *hypothesis* until the receipts in `registry/r11f.json` say otherwise.
No competition slot is spent by this session; no portal credentials were used.

## 0. What the previous session left open

R10 (H46-1, DFA slope crossover) was built, audited, and **held**: it failed the preregistered
blocked-proxy improvement gate against the incumbent (mean block DTI 0.0617 vs 0.1033). Its stated
most likely failure mode was *localization mismatch*: a 51 km DFA window was asked to place 100 m
dots. R11F therefore treats localization as a first-class requirement for any DFA arm, and adds a
second, independent evidence family that the competition's own 19-band stack does not contain.

## 1. Verified facts this session starts from (each re-measured, not inherited)

| Fact | Value | How verified |
|---|---|---|
| Official metric | `DTI = TPw/(TPw + 0.2·FPw + 0.8·FNw + ε)`, `k(d)=max(1−d/300 m,0)` | read from page 967, transcribed in `src/gems46/metric.py`, worked example checked in tests |
| Sparse identity | `DTI = T/(0.2·N + 0.8·G)` when no two dots best-cover the same truth pixel | algebra, `docs/SCORE_ANALYSIS.md` |
| Band 6 data-dictionary mismatch | band `tc` correlates **+0.997** with the GeoDAWN radiometric **total count** channel, i.e. it is not "tilt angle or total curvature" | measured this session on the hash-pinned rasters |
| Radiometric K, Th, U are absent from the 19 official bands | 19 descriptions listed; only `tc` overlaps the radiometric family | official GeoTIFF band descriptions |
| 1 m lidar coverage | 3,892,964 grid cells with real 3DEP lidar (75 % of footprint), 12 quantised terrain descriptors | `data/external/lidar_scarp_features.json` (706/716 tiles) |
| Off-catalogue proxy size | SGMC 83,593 px total; 66,277 px after removing catalogue-coincident pixels | `registry/data_manifest.json` |
| Current live board | 0.3774 (#1 xiaofanhu), 0.3345, 0.3262; 0.2778 is now #13 | leaderboard fetched 2026-10-06 this session |

## 2. Candidate hypotheses (ranked before implementation)

Each entry names the layers, the physical signature, why a fault *missing from USGS/INGENIOUS*
should be caught, how it differs from everything already implemented, expected DTI effect and cost.

### H-R11-1 — Radiometric compositional-contrast lineaments (rank 1)
- **Layers:** GeoDAWN contractor radiometric grids `K`, `Th`, `U`, `TC` and the ratio grids
  `Th/K`, `U/K`, `U/Th` (mirror provenance: DOI `10.5066/P93LGLVQ`, ScienceBase item
  `657e1d85d34e23d3533209f7`); official band 6 (`tc` = the same total-count grid) used only as a
  cross-check, never as a magnetic curvature.
- **Signature:** *compositional* edge — the horizontal gradient of the K and Th/K grids (a
  first-order radiometric contrast), not an amplitude, not a curvature.
- **Why off-catalogue:** the USGS Quaternary fault compilation requires evidence of Quaternary
  surface rupture; a fault that juxtaposes different radiometric source lithologies but has no
  young scarp or is buried is structurally real and absent from that compilation. Radiometric
  contrast survives burial of the scarp because it maps the *near-surface lithology contrast*, not
  the scarp itself.
- **Differs from repo:** no arm in this checkout or in the inspected GEMSDOE record uses the K/Th/U
  or ratio grids; the group's earlier radiometric arm (`6GEMSDOE`/`hgb88`) used grids as model
  features and scored 0.0286. Band 6 was previously treated as a magnetic curvature by this repo's
  own band dictionary — this candidate corrects that.
- **Expected:** medium. **Cost:** low (data already mirrored, no network).

### H-R11-2 — 1 m lidar scarp multi-channel matched detector with strike consistency (rank 2)
- **Layers:** `lidar_scarp_features_u8.tif` 12 channels (`step_max`, `downface_max`, `lapneg_max`,
  `lappos_max`, `cross_max`, `relief`, `coh100`, `strike`, `valid`, …), from the competition's own
  `1m_DEM_links.csv` family, aggregated to 100 m.
- **Signature:** a scarp is recognised by the *joint* pattern — a band-passed step, a convex crest
  and a concave base — plus a locally consistent strike over ≥ 2 km. That is a matched filter on a
  multi-channel terrain descriptor, not a single-channel ridge.
- **Why off-catalogue:** 1 m lidar resolves scarps that the 1:50 k–1:1 M compilation never
  contained, and the competition explicitly ships the DEM link list, i.e. the sponsor expects
  lidar-derived evidence to matter.
- **Differs from repo:** the only shipped lidar arm (`7GEMSDOE lidarscarp-ridge-top2pct`, 0.1461)
  thresholded one channel; this uses the channel *combination* and an orientation-consistency
  filter, then the metric-optimal emitter.
- **Expected:** medium–high (75 % lidar coverage caps it). **Cost:** low.

### H-R11-3 — Local DFA scaling-regime break, re-localised (rank 3, the standing brief's hypothesis)
- **Layers:** official band 2 `rtp`, band 14 `tmi`, band 1 `mag_anom`, band 13 `iso_grav_anom`,
  band 18 `iso_grav_anom_hg`.
- **Signature:** the *local* detrended-fluctuation exponent α of the grid along row and column
  transects, computed in **1.6–6.4 km** windows over **0.2–1.6 km** scales (R10: 12.8 km over
  0.8–12.8 km), and the flag is raised where the local α breaks from its own 31-window background
  regime (robust z) *and* the break is a genuine two-sided change point.
- **Why off-catalogue:** α measures the roughness/texture of the source distribution. Juxtaposed
  lithologies with different magnetic roughness, or hydrothermal magnetite destruction along a
  fracture corridor, change α without necessarily creating a sharp amplitude edge — exactly the
  kind of structure a surface-morphology catalogue under-records.
- **Differs from repo:** R10/H46-1 used 512-sample (51 km) windows; the standing brief and R10's own
  review both identify localization as the failure mode. Shorter windows, finer stride, a
  two-sided change-point test and a different emitter are all new.
- **Expected:** low–medium on the proxy (R10 was negative); retained because the standing brief
  requires it to be tested and its correlation with prior submissions must be shown to be low.
- **Cost:** medium (CPU, ~10 min).

### H-R11-4 — Dual-physics strike agreement (rank 4)
- **Layers:** `rtp`/`tmi` (magnetic) and `iso_grav_anom`/`iso_grav_anom_hg` (gravity).
- **Signature:** a lineament present in both fields *at the same place with the same strike*
  (orientation coherence), which cultural or topographic artefacts rarely produce.
- **Why off-catalogue:** a fault offsets both density and susceptibility; requiring both is a
  specificity filter that no mapping compilation used.
- **Differs from repo:** earlier corroboration arms took geometric means of transform magnitudes;
  none required strike agreement.
- **Expected:** low–medium (large overlap with H-R11-1/2 evidence). **Cost:** low.

### H-R11-5 — Raw hypocentre lineaments (rank 5, BLOCKED)
- **Needs:** `https://earthquake.usgs.gov/fdsnws/event/1/query` (free, official, no key).
- **Availability check this session:** sandbox egress to `earthquake.usgs.gov` returns HTTP 000
  (same result as the previous session). **BLOCKED — not proposed as viable here.**

## 3. Decision rule fixed in advance

1. Field-building weights are chosen on the **selection half** of the 4×4 spatial blocks only.
2. The gate is evaluated on the other half at matched emitted mass and identical masking:
   mean block DTI must exceed the incumbent's re-emitted field (`GEMSDOE32` primary, restored and
   hash-checked) by a positive paired difference, and the improvement must survive a seeded
   block bootstrap whose 95 % interval excludes zero.
3. Any candidate whose maximum absolute correlation with the prior shipped submissions exceeds 0.2
   may not be described as a new hypothesis.
4. The emitted candidate is written only if the raster contract passes (single band, float32,
   EPSG:32611, exact template transform, all-finite in [0,1], zero outside the footprint).
5. The proxy is a weak instrument (group measurement: Spearman ≈ +0.31 with live scores). A pass is
   a permission-to-consider, not a score forecast. A fail is reported as a negative result.

## 4. What the metric algebra says the emission must do

`DTI = T/(0.2N + 0.8G)`, so a unit-mass dot is worth emitting **iff its expected kernel credit
exceeds `0.2·DTI`** (≈ 0.056 at DTI 0.28). R11F therefore replaces the previous
"blur-field + fixed-budget + Chebyshev spacing" emitter with an expected-credit submodular
optimiser that (a) ranks by *marginal* credit — a dot that duplicates the coverage of its neighbour
is rejected — and (b) stops exactly at the break-even rule. This is a change to the emission, not
to the geology, and is reported separately from the field change.
