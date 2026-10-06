# Preregistered geological hypothesis register

**Register map (added 2026-10-06).** This file numbers *external-data* hypotheses **H46-1–H46-4**.
`docs/HYPOTHESES.md` numbers the brief's in-repo feature hypotheses **H1–H5**, and
`registry/hypotheses.json` is the machine register (**H46-N** shipped/blocked arms plus this
session's **H46-R11-N**). The identifiers overlap numerically; quote the file name with any id.

**Snapshot date:** 2026-10-06 (UTC)
**Status:** hypotheses only; no competition label/raster has been accessed, no candidate was implemented, and no DTI improvement has been measured.
**Scope:** rank 3–5 candidate signals before model implementation. Rankings are qualitative research priorities, **not numerical score forecasts**.

## Decision rule and novelty boundary

The competition target is fault presence, not geothermal-vent probability. The hypotheses below seek independent evidence of fault-controlled deformation or fluid pathways that could expose fault segments missing from the USGS/INGENIOUS fault catalogue. An anomaly is not itself a fault; each candidate must be interpreted as a fault hypothesis and evaluated against spatially held-out labels and known confounders.

The starting snapshot (2026-10-06) contained only `README.md`. This session has since added generic raster/validation/site infrastructure, but no geological candidate implementation; no prior candidate implementation can be audited from this checkout. The user-supplied history and inspected GEMSDOE32/40 pages rule out several ideas as novel (see [`sources.html`](../sources.html)). Novelty below means **not found in that inspected record**, not a proof that no prior run ever tested it. In particular, `tso1-conj_alteration_mag` may overlap the ASTER candidate; H46-3 stays conditional until its prior implementation is inspected.

**Estimated DTI upside** is an ordinal expectation relative to the other ideas, based on physical relevance, likely spatial coverage, and novelty. There is no defensible numerical `ΔDTI` without the official labels, the exact grid, feature layers, a current holdout-best raster, and a preregistered split. **Effort** is a rough engineering estimate after those inputs are available, not a measured project duration. H46-2 is ranked above H46-3 despite higher harmonization effort because it tests a distinct hydrologic signal; ASTER's likely overlap with `conj_alteration_mag` discounts its expected incremental value until the prior run is audited.

## Rank order

| Rank | ID / hypothesis | Expected incremental DTI upside | Implementation cost | Availability / decision |
|---|---|---|---|---|
| 1 | **H46-1 — OPERA DISP-S1 line-of-sight displacement gradients and persistent time-series steps** | **Medium, highly conditional.** Most distinct, fault-specific signal in this shortlist. Likely benefit is localized to actively deforming or hydrologically compartmentalizing structures; dormant faults may have no present-day InSAR expression. No numeric gain claimed. | **Medium–high**, roughly 4–8 engineering days using the preprocessed OPERA product; potentially 1–3+ weeks if raw-SLC processing is required. | NASA CMR returned DISP-S1 granules overlapping parts of the broad rectangle. A separate Copernicus OData query returned S1A-only products and did not establish a repeat-pass pair; raw-SLC feasibility remains unproven. No payload was downloaded; full grid coverage, quality, and holdout performance remain unchecked. **First experiment, but not yet cleared for implementation/submission.** |
| 2 | **H46-2 — USGS groundwater-head discontinuities and repeat-measurement residuals** | **Low–medium.** Faults can conduct or compartmentalize groundwater, but a sparse and uneven network may contribute only near monitored basins and springs. | **High**, roughly 3–6 days for data harmonization/quality screens, plus additional time if coverage is insufficient. | Official modern USGS field-measurements API returned groundwater-level records inside the broad study rectangle. Vertical datums, aquifers, times, and density vary; usable spatial support is unverified. |
| 3 | **H46-3 — ASTER-derived hydrothermal alteration-class edges and corridors** | **Low–medium at current confidence; potentially medium if the prior audit proves it is distinct.** Possible overlap lowers its expected value; hydrothermal alteration can mark long-lived fluid pathways, but polygon edges are not fault traces. | **Low–medium**, roughly 1–3 days to ingest/rasterize and audit dates, masks, registration, and overlap with prior runs. | Free official USGS map/data release exists for the northwestern conterminous U.S. The exact overlap/usable-pixel fraction on the competition grid is not yet tested. A user-listed `conj_alteration_mag` result may already test a related signal, so this is **conditional, not certified untried**. |
| 4 | **H46-4 — seasonally controlled Landsat Collection 2 surface-temperature residual corridors** | **Low.** Potential geothermal heat/discharge can be fault-controlled, but daytime land-surface temperature is strongly affected by weather, terrain, vegetation, emissivity, and human activity; thermal pixels are coarser than the delivered 30 m grid. | **Medium**, roughly 3–6 days for scene/QA selection, temporal compositing, covariate control, and regridding. | USGS Level-2 surface-temperature products are public/free. Exact cloud-free scene density over the competition grid was not checked. Prior `thermal-pop`/GDR work creates a conceptual-overlap check before calling this novel. |

## H46-1 — OPERA DISP-S1: primary hypothesis

### Layers and construction to test

- NASA/JPL/OPERA Level-3 **DISP-S1** radar line-of-sight (LOS) displacement/time-series products at 30 m posting; use only the variables and uncertainty/quality flags specified by the versioned product specification. The exact HDF5 variable names and scaling must be read from a downloaded product before coding.
- The companion **DISP-S1-STATIC** radar-geometry / layover-shadow layers, where they help define valid support and viewing geometry.
- A co-registered ascending/descending observation if the catalogue shows one; otherwise make no claim about separating vertical and horizontal motion.
- Build robust temporal rates/residuals and local cross-track gradients; do not treat an isolated subsidence bowl, single edge, layover boundary, or low-coherence area as a fault. Regrid 30 m observations to the competition grid with a documented, quality-aware aggregation; do not present interpolated 30 m values as independent 100 m observations.

### Physical signature and geological rationale

A candidate is a persistent, narrow, approximately linear LOS-velocity or displacement-gradient step that is repeated across suitable observations and is not better explained by basin compaction, groundwater pumping, mining, landsliding, seasonal loading, atmospheric error, or a frame/mask boundary. Check whether the edge follows or cross-cuts mapped lithologic/structural boundaries, and whether its continuity/intersection geometry is plausible for the regional fault system.

Faults can bound aquifers or channel fluids and can localize deformation. A buried fault under alluvium may lack a visible scarp while still separating groundwater compartments or controlling deformation. USGS documents that InSAR has revealed a previously unrecognized Santa Clara Valley fault subsequently confirmed by seismic reflection/refraction; that is a proof of method in a different setting, **not proof that OPERA will reveal a new GEMS fault**. USGS also warns that pumping-related deformation may obscure or mimic tectonic signals. This warning is central to the screen.

### Novelty relative to inspected work

No InSAR deformation-gradient experiment appears in the inspected user-provided hypothesis list or the current checkout's candidate-code inventory. This is the strongest novelty claim available, not an exhaustive audit of all prior repositories/artifacts. It is not a repackaged drainage alignment, raw seismicity/focal-mechanism map, generic magnetic tilt feature, Euler/depth cluster, or simple thermal-point buffer.

### External source and availability precheck

- Primary source: [NASA/JPL OPERA DISP-S1 Version 1, NASA ASF DAAC, DOI 10.5067/SNWG/OPL3DISPS1-V1](https://doi.org/10.5067/SNWG/OPL3DISPS1-V1). The NASA catalogue describes the product as an InSAR time-series LOS displacement product, 30 m posting, with North American coverage and records beginning in 2016. CMR also returned granules with 2025–2026 acquisition periods; reconcile that newer API metadata with the catalog's broad product-period statement before treating temporal coverage as complete/current. The companion [DISP-S1-STATIC product](https://doi.org/10.5067/SNWG/OPL3DISPS1ST-V1) supplies static radar geometry layers.
- Availability check (2026-10-06): unauthenticated official NASA CMR queries returned overlapping DISP-S1 granules in parts of the broad study rectangle, including granule F36543 (acquisition period 2025-12-04 to 2026-02-20) and central-area granule F38500 (2025-09-17 to 2025-09-23). A separate query west of the main rectangle returned F36542 (2025-12-16 to 2026-02-08). This proves product metadata/granules exist in overlapping portions, not complete AOI coverage or enough valid observations everywhere.
- Raw-SLC cross-check: the documented Copernicus Data Space OData query returned S1A-only catalog products for the broad rectangle. It did not establish a repeat-pass pair, S1C/S1D coverage, payload access, full-area coverage, or InSAR feasibility. Sentinel-1A operations ended on 2026-06-29; the current constellation transition does not establish that suitable current scenes cover this AOI. No Sentinel payload or perpendicular baseline was inspected.
- Sentinel data have a free/open reuse policy with required attribution; NASA describes OPERA products as openly shared. Competition rules still require external inputs to be shareable for independent organizer verification. Preserve product IDs, versions, citation, and the required “Contains modified Copernicus Sentinel data [year]” notice when applicable. An Earthdata/Copernicus account may be required for downloads; no account, token, or payload was obtained in this session.
- Direct query links and additional source details are in [`sources.html`](../sources.html). The bbox is an approximate broad rectangle, not the official label footprint.

### Validation design and stop conditions

1. Obtain the official sample/grid, feature/label rasters, and the current best **holdout** prediction/model. Record their checksums and verify EPSG:32611, 100 m, bounds, transform, nodata, and pixel semantics.
2. Query/download the OPERA granules only through the official access path. Build a per-pixel valid-observation count and quality mask; measure coverage over the exact competition footprint and by spatial fold before feature construction.
3. Freeze contiguous spatial folds with a 300 m exclusion/guard zone. Do not randomly split pixels. Any score calibration or feature selection must use training folds only; test-fold labels may be used only for final fold scoring.
4. Compare H46-1 with the versioned current holdout best using identical folds, scoring mask, distance kernel, and a matched total prediction-mass budget. Promotion gate: higher mean DTI **and** positive improvement in at least 3 of 4 folds. Publish foldwise values, uncertainty, valid-area counts, mass, and ablations. This is a preregistered engineering gate, not an official DrivenData threshold.
5. A pass would only justify considering a weekly feedback submission; it does not guarantee private-leaderboard improvement or demonstrate independent new-fault discovery. A fail or insufficient valid coverage means no slot is spent.

## H46-2 — groundwater-head discontinuities

### Layers and signal

Use USGS Water Data APIs' `field-measurements` groundwater-level observations and `monitoring-locations` attributes (well location, aquifer, depth, datum, agency). Where the data allow, form same-aquifer, temporally comparable water-level residuals and local hydraulic-head gradients. A fault candidate would be a persistent, geologically plausible line-like discontinuity or compartment boundary supported by multiple wells/springs—not a line inferred from a single isolated point.

Fault damage zones can transmit fluid, whereas clay-rich fault cores or juxtaposed units may impede it; either may create a groundwater-head contrast. Buried structures may be absent from a surface fault catalogue yet affect hydraulic communication. This is only a hypothesis: pumping, aquifer geometry, topography, well construction, mixed measurement dates, different vertical datums, and agency-specific reporting can produce similar patterns.

### Novelty and availability

The inspected prior record mentions thermal, geochemical, and water-quality features but not a datum-aware map of groundwater-head discontinuities; novelty is provisional pending the broader prior-run audit. The legacy USGS `/gwlevels` service was decommissioned in 2026; use the modern official `/field-measurements` API, not the retired endpoint. On 2026-10-06, the modern API returned groundwater-level field-measurement records within the broad rectangle and the monitoring-location endpoint returned groundwater wells there. This confirms examples exist, not a dense or uniformly useful network. No location-count/coverage study or measurement payload was saved.

## H46-3 — ASTER hydrothermal alteration classes

Use the official USGS northwest-U.S. ASTER map's exposed alteration/mineral classes, and, only if needed, pre-April-2008 ASTER SWIR scenes. Test connected, structurally plausible alteration corridors or class transitions near independently held-out fault labels. Hydrothermal alteration records past fluid-rock interaction and may be associated with fault-fed geothermal fluids; the mapped boundary can also reflect lithology, exposure, vegetation, or mining, so it is not a fault trace.

USGS publishes a CC0 2017 western-U.S. map and a separate central/southern Basin-and-Range map. The user-provided prior record includes a `conj_alteration_mag` experiment; until its code/input layers are reviewed, H46-3 cannot honestly be certified as untried. ASTER SWIR observations acquired since April 2008 are unusable due to the instrument anomaly. Verify acquisition dates, map provenance, pixel registration, and the exact competition-footprint overlap before promoting this candidate.

## H46-4 — Landsat surface-temperature residual corridors

Use Landsat Collection 2 Level-2 surface temperature (`ST_B10`/documented scale and QA) with cloud/uncertainty masks, reflectance-derived vegetation/land-cover controls, and topography. Test multi-date, season-aware temperature residuals after controlling for elevation, slope/aspect, land cover, and acquisition conditions. The proposed signal is persistent or repeatedly expressed warm/cool ground near fault-controlled fluid pathways or discharge—not raw LST thresholding. Landsat thermal sampling is coarser than the 30 m delivered grid, and daytime heating, albedo, vegetation, weather, emissivity, mining, and irrigation are strong confounders. This cannot be treated as a direct fault detector.

The official USGS Level-2 products are public/free; exact cloud-free AOI scene density was not checked. The prior project history includes `thermal-pop` and GDR temperatures, so the sensor-specific temporal-residual method must be compared against those implementations before calling it novel. Do not spend a submission slot on this idea without spatial holdout improvement.

## Common evaluation cautions

- The 0.3195 public leaderboard score is not a local holdout score. A prior repository's projected score is not a current verified baseline.
- The labeled training faults may be incomplete/biased; a blocked holdout tests transfer within known labels, not the existence or discoverability of hidden faults. Maintain that distinction in any claim.
- Candidate selection, thresholds, mask construction, and feature weights must be fixed before final holdout scoring. Report each fold and each ablation rather than a single selected maximum.
- Public leaderboard results are the organizer's feedback only. Do not infer why an unnamed candidate scored better from its row alone.
- No nonzero expected improvement is guaranteed. If a hypothesis loses to the holdout best, archive the negative result and do not upload it.
