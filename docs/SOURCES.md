# Sources — every external claim used by this repository, with the link

Rule used throughout: a claim is written down only if it was read on the page linked
next to it, or is a direct arithmetic consequence of numbers read on that page. If a
claim is *not* verified it is marked **flagged** in `docs/IRREGULARITIES.md` instead
of being repeated here.

## 1. The competition itself

| what | source | what was taken from it |
| --- | --- | --- |
| Task, metric, format, deadline, prize | <https://www.drivendata.org/competitions/306/competition-doe-gems/> | deadline 3 Dec 2026 23:59 UTC; $300,000 prize pool (Initial $50k / Final $250k); external data explicitly allowed when licensed/shareable |
| Problem description (full page) | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> | the 19 input layers and their physical meanings; the `DTI` metric and its constants (300 m support, α = 0.2, β = 0.8); the submission format (EPSG:32611, 100 m, single-band float32 in [0, 1], NaN outside the survey bounds); **the scored test set is new faults curated by an expert panel for this competition, not present in USGS QFaults nor the INGENIOUS/SGMC catalogues**; the optional `Note` field ("A short comment to help you or your team tell submissions apart later") |
| Data tab | <https://www.drivendata.org/competitions/306/competition-doe-gems/data/> | the three files this repository needs (`training_features.tif`, `labels.tif`, `sample_submission.tif`); the download requires a signed-in account (**flagged** in `IRREGULARITIES.md` IR-46-01: this sandbox has no account) |
| Leaderboard | <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> | the anchors used everywhere in the docs: 0.3345 (alexoktaba, best public DW-Tversky), 0.3262, 0.3222, 0.3218, 0.3195, 0.3163, 0.3060 … 0.2778 (the project owner's own submission, `h33-h33-2-b2-…-e5eb6e7e-zeros`) |
| Community forum | <https://community.drivendata.org/c/gems-prize-challenge/111> | the official channel for questions about this competition |
| Organizer reference solution | <https://github.com/drivendataorg/gems-prize-reference-solution> | MC-CV U-Net baseline, Tversky α = 0.2 / β = 0.8, 128 px patches, 5 epochs; the reference repository ships **no** metric implementation, which is why `src/gems46/metric.py` is transcribed from the problem page instead |

### Data conventions verified in this checkout

* `labels.tif` uses three values: **1** = catalogue fault (60,988 cells), **0** = no catalogue fault
  (5,106,385 cells), **-1** = outside the surveyed area (7,111,787 cells). The cross-check is exact:
  `1 + 0` cells = 5,167,373 = the number of finite `sample_submission.tif` cells, and the `-1` cells =
  7,111,787 = the number of `NaN` cells. `scripts/prepare_data.py` asserts both.
* `sample_submission.tif` is therefore the survey-footprint mask as well as the format template.
* All three rasters are EPSG:32611, 100 m, shape (3730, 3292), transform (100, 0, 243350, 0, -100, 4508550).

## 2. The data layers (why they physically mean what the code assumes)

| what | source | takeaway used |
| --- | --- | --- |
| GeoDAWN airborne magnetic + radiometric surveys, NW Great Basin | <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and> — DOI 10.5066/P93LGLVQ (Glen & Earney, 2024); mirror <https://gdr.openei.org/submissions/1591> | 149,030 line-km over 51,857 km² in four blocks (Winnemucca, Fallon, **Hawthorne**, **Tonopah**), Area 1 centred on Clayton Valley; 1 m LiDAR flown alongside from 3DEP; 2 m station spacing gravity and HTEM acquired in the BRIDGE project. This is why the official rasters look the way they do and why the surveyed area is a *fraction* of the raster (see IR-46-04) |
| GeoDAWN airborne **gamma-ray spectrometry** grids (K, Th, U, total count) | <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and> — DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ), ScienceBase item `657e1d85d34e23d3533209f7`; mirror <https://gdr.openei.org/submissions/1591> | **New to this repository in R11.** Gamma rays sample only the top ~0.3–0.5 m, so a fault that juxtaposes or hydrothermally alters regolith produces a linear break in total count and in Th/K even where the topography shows nothing. Not in `training_features.tif`. Restored as `data/external/geodawn_rad_u8.tif`, sha256 `c22420f7…` equals the mirror's recorded `product_sha256` (IR-46-08) |
| GeoDAWN contractor ratio / derivative grids (Th/K, U/K, U/Th, TMI up-continued to 150 m) | same DOI and ScienceBase item | Rank-quantised uint8, units not preserved; used by R11 only as ordering/structure. Th/K gradient was the strongest single radiometric field in the exploratory screen (proxy DTI 0.11215 vs 0.07908 for the RTP magnetic gradient) |
| 2 m LiDAR scarp-morphology channels derived from 1 m 3DEP LiDAR | <https://www.usgs.gov/3d-elevation-program> (LiDAR flown alongside GeoDAWN) | **New to this repository in R11.** Twelve channels; R11 uses the *oriented* slope-break set (`downface_max`, `upface_max`, `step_max`, `lappos_max`). Coverage measured here: 75.37 % of the footprint and 75.13 % of the emittable domain — the reason R11 needs a radiometric fallback |
| Scored footprint vs survey extent (measured here) | `sample_submission.tif` finite pixels vs band-2 valid pixels | 5,167,373 finite template pixels = 51,674 km² against the survey's published 51,857 km² (0.35 % apart), and band 2 has 5,165,852 valid pixels. **The scored footprint is the GeoDAWN survey area**, which is why 53.8 % of 64-px blocks of the official rasters are constant: they lie outside the footprint, not a data defect |
| BRIDGE final report | <https://gdr.openei.org/files/1682/BRIDGE_Final_Report_SAND2025-01826.pdf> | step-over and fault-intersection targets; CBA **HGM** and **1VD** derivatives; GeoDAWN **RTP** magnetic anomaly; basin-fill resistivity as a cover-thickness proxy; known systems used as training targets. Used to justify hypotheses H3 and H5 in `docs/HYPOTHESES.md` |
| Granite Mountain (Buena Vista Valley, Pershing County) | <https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Adams.pdf> | free-air / 2.45 g·cm⁻³ CBA, HGM, 1VD, analytic signal and RTP processing of 2 m temperature surveys; explicit statement that **most Great Basin resources are blind, with no surface manifestation** — i.e. the population most likely to be labelled "new" |
| 2020 Mw 6.5 Monte Cristo Range earthquake | <https://pubs.usgs.gov/publication/70220306> and <https://data.nbmg.unr.edu/public/OpenData/EQ/docs/Koehler_et_al_2021_SRL.pdf> | 15 May 2020; epicentre 38.169 °N, 117.850 °W (≈ 74 km SE of Hawthorne); a **28 km surface-rupture zone on largely unmapped parts of the Candelaria fault**, distributed across a 2.5–5 km width, rupturing oblique north-striking faults, incoherent with the QFaults compilation. This is the concrete validation instance for hypothesis H1 |
| USGS/ANSS ComCat | <https://earthquake.usgs.gov/data/comcat/> | the free, official, programmatically queryable earthquake catalogue behind official band 10 (distance to earthquake) and band 16 (earthquake density). Named as the source any *extension* of H1 would need; **not** needed for the shipped submission because both bands are already inside `training_features.tif` |

## 3. The method

| what | source | takeaway used |
| --- | --- | --- |
| Split conformal prediction for a population mean | Jing Lei, Max G'Sell, Alessandro Rinaldo, Ryan J. Tibshirani, Larry Wasserman, *Distribution-Free Predictive Inference for Regression*, **Journal of the American Statistical Association 113(523): 1094–1111, 2018** (citation confirmed via <https://www.stat.cmu.edu/~ryantibs/research.html>) | the calibration-half quantile rule implemented in `src/gems46/pipeline.py::conformal_select` and re-exported by `src/gems46/conformal.py`; the finite-sample floor `L(s) = mean_cal(s) − q(s)` with `q` the `ceil((n+1)(1−α))`-th smallest residual |
| Ridge / edge detection in scale space | Lindeberg, *Edge detection and ridge detection with scale-space properties*, **IJCV 30(2): 117–154, 1998** | the `L_nn` second-directional-derivative ridge transform in `src/gems46/features.py` |
| Spatial blocking for spatially autocorrelated labels | see `docs/IRREGULARITIES.md` IR-46-03 (third-party note that random pixel splits leak along long fault traces) | why this repository scores whole 4 × 6 tiles instead of random pixels |

## 4. What is deliberately **not** used as a source

* **No third-party GEMS submission or repository is used to build the shipped file.** The
  sibling submissions are read only as *public score history* (the numbers on the
  leaderboard, plus one owner-reported sequence reproduced in `docs/SCORE_ANALYSIS.md`),
  which is exactly what the brief allows: "do not copy a previous submission unless it
  is for learning and education". No raster, model, weight or dot list from any other
  submission is copied, downloaded or re-used here.
* The unverified third-party claim that "catalogue pixels are masked out of scoring" is
  **not** treated as fact anywhere in the code. It is used only as the *motivation* for
  the catalogue-exclusion experiment in `docs/SCORE_ANALYSIS.md`, whose conclusion
  (deleting dots near the catalogue monotonically lowered the score of the sibling
  family) is measured from the leaderboard numbers themselves.
