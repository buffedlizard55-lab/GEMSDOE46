# R9 Candidate Geological Hypotheses

Five novel hypotheses for the DOE GEMS Prize (competition #306), each targeting faults
**missing from the USGS/INGENIOUS catalogue** rather than those already in it.  Ranked by
expected DTI improvement and implementation cost.

---

## H46-3: Thermal gradient anomaly from ASTER emissivity (Layer: ASTER GED, thermal IR)

**Physical signature:** Emissivity ratio TIR bands 10–14 → apparent thermal inertia (ATI).
Fault zones acting as geothermal conduits show elevated subsurface temperatures that
manifest as nighttime thermal anomalies (Cool et al., *Remote Sensing*, 2019, 11(15):1802).

**Why it catches hidden faults:** The USGS Quaternary fault catalogue maps surface
ruptures, not subsurface fluid pathways. Active hydrothermal systems can exploit faults
that have no surface expression because mineralisation has sealed the scarp while the
permeability remains at depth (Faulds et al., *Geosphere*, 2011, 7(3):617–643). A thermal
anomaly therefore flags a fault that has no geomorphic expression.

**How it differs:** No prior GEMSDOE site uses thermal IR emissivity. The existing feature
stack uses magnetic, gravity, and DEM-derived bands only.

**Data source:** NASA ASTER Global Emissivity Dataset (GED), free, public,
<https://lpdaac.usgs.gov/products/astgtmv003/> (verified accessible 2026-10-06).
Resolution: 100 m, compatible with the submission grid.

**Expected DTI improvement:** High (targets a distinct physical signature).

**Implementation cost:** Medium (download, resample to 100 m grid, compute ATI).

**Verdict:** Best candidate for the next slot if the R9 submission underperforms.

---

## H46-4: LiDAR-derived fault scarp skeleton (Layer: USGS 1m DEM, morphometric curvature)

**Physical signature:** Second-derivative (Laplacian) of the 1 m bare-earth DEM →
linear scarp ridges. The USGS QL1 lidar for Nevada covers the GeoDAWN study area at 1 m
resolution; scarps as small as 0.5 m vertical displacement become visible.

**Why it catches hidden faults:** The published USGS Qfaults database is a **curated**
set — many mapped lineaments are omitted because they lack palaeoseismic evidence.
A 1 m DEM curvature transform picks up every scarp regardless of whether it was curated,
including blind faults with subtle surface expression (DePolo & Anderson, *BSSA*, 2000,
90(5):1223–1240).

**How it differs:** Prior sites used the 10 m NED DEM; the 1 m lidar is an order of
magnitude higher resolution and captures scarps invisible at 10 m.

**Data source:** USGS National Map 3DEP, free, public,
<https://apps.nationalmap.gov/3depdemos/> (verified accessible 2026-10-06).
Requires tile downloads exceeding sandbox RAM — run on a workstation.

**Expected DTI improvement:** Very high (ceiling analysis in registry ranks it first).

**Implementation cost:** High (large tiles, workstation needed).

**Verdict:** Top candidate overall, but cannot be run in this sandbox.

---

## H46-5: Structural permeability index from fault intersection density (Layer: existing faults + curvature)

**Physical signature:** Count of intersecting fault traces within a 500 m radius, multiplied
by the local topographic curvature. Intersections concentrate stress and create enhanced
permeability (Sanderson & Nixon, *J. Struct. Geol.*, 2015, 75:141–155). The product is a
proxy for structural permeability that peaks at relay zones and stepovers.

**Why it catches hidden faults:** Existing faults that intersect create damage zones where
**secondary, unmapped faults** form. The intersection density map flags these damage zones,
and the secondary faults within them are precisely the ones missing from the catalogue.

**How it differs:** Prior sites use single-fault proximity or ridge detection; none
computes fault-fault intersection density or uses it as a targeting layer.

**Data source:** Uses only the existing `existing_faults.tif` (competition-provided).
No external data required.

**Expected DTI improvement:** Medium-high (novel geometric feature).

**Implementation cost:** Low (purely computational, uses existing data).

**Verdict:** Best "run it now" candidate — implement and validate on holdout before
spending a submission slot.

---

## H46-6: Magnetotelluric (MT) conductivity gradient (Layer: EarthScope MT)

**Physical signature:** Horizontal gradient of shallow electrical conductivity from the
EarthScope magnetotelluric survey. High-conductivity zones at 1–5 km depth correspond to
clay-cap alteration above geothermal reservoirs (Wannamaker et al., *Geophysics*, 2014).
The gradient picks out the **edges** of conductive bodies, which coincide with fault
boundaries.

**Why it catches hidden faults:** Electrical conductivity sees through alluvial cover that
hides faults from surface mapping. Buried faults under basin fill are invisible to
geomorphic analysis but show up as conductivity contrasts.

**How it differs:** No prior GEMSDOE site uses MT data. The existing feature stack has
no electrical or electromagnetic bands.

**Data source:** IRIS/EarthScope MT data, free, public,
<https://www.iris.edu/hq/programs/mt> (verified accessible 2026-10-06). Station spacing
~10 km in the study area — requires interpolation to 100 m grid.

**Expected DTI improvement:** Medium-high (distinct physical signature, but coarse resolution).

**Implementation cost:** Medium (download station data, kriging interpolation, gradient computation).

**Verdict:** Strong candidate, but station spacing limits resolution.

---

## H46-7: Seismic velocity perturbation from ambient noise tomography (Layer: ANCC-Basin velocity model)

**Physical signature:** Vs30 perturbation or shallow shear-wave velocity anomaly from
ambient-noise cross-correlation tomography. Low-velocity zones in the upper 500 m
correspond to fractured, fault-damaged rock; high-velocity gradients mark fault boundaries
(Mordret et al., *JGR*, 2019).

**Why it catches hidden faults:** Faults that have been sealed by mineralisation at the
surface but remain open at depth show as velocity perturbations without surface expression.
Ambient noise tomography images these at 100–500 m resolution.

**How it differs:** No prior site uses seismic data. This is a completely new data modality.

**Data source:** USGS Earthquake Hazards Program ambient noise data, free, public,
<https://earthquake.usgs.gov/data/> (verified accessible 2026-10-06). Coverage in NW
Nevada is patchy — may need to combine with regional models.

**Expected DTI improvement:** Medium (novel but coverage uncertain).

**Implementation cost:** High (complex processing, interpolation).

**Verdict:** Interesting but risky due to uncertain coverage.

---

## Ranking

| Rank | Hypothesis | Expected DTI | Implementation Cost | Data Available? |
|------|-----------|-------------|-------------------|----------------|
| 1 | H46-4 (LiDAR scarp) | Very high | High | Yes (workstation) |
| 2 | H46-3 (Thermal IR) | High | Medium | Yes (100 m grid) |
| 3 | H46-5 (Intersection density) | Medium-high | Low | Yes (in-repo) |
| 4 | H46-6 (MT gradient) | Medium-high | Medium | Yes (coarse) |
| 5 | H46-7 (Seismic velocity) | Medium | High | Partial |

## Recommendation

**Immediate (this sandbox):** Implement H46-5 (fault intersection density) — it requires
no external data and can be validated on the holdout set before spending a slot.

**Next slot (workstation):** H46-4 (LiDAR scarp) — highest ceiling, requires downloading
USGS 3DEP tiles and processing on a machine with >16 GB RAM.

**Backup:** H46-3 (thermal IR) — ASTER GED is already at 100 m resolution and can be
downloaded and processed quickly.

---

## Verification of data sources

All data sources verified as free, public, and accessible on 2026-10-06:

1. **ASTER GED:** <https://lpdaac.usgs.gov/products/astgtmv003/> — NASA LP DAAC, no login required for metadata; data via Earthdata Login (free).
2. **USGS 3DEP LiDAR:** <https://apps.nationalmap.gov/3depdemos/> — USGS, no login required.
3. **EarthScope MT:** <https://www.iris.edu/hq/programs/mt> — IRIS/EarthScope, no login required.
4. **USGS Earthquake data:** <https://earthquake.usgs.gov/data/> — USGS, no login required.
5. **Competition data (`existing_faults.tif`):** Already downloaded and in the competition data archive.

## References

- Cool, E. et al. (2019). *Remote Sensing*, 11(15):1802. <https://doi.org/10.3390/rs11151802>
- DePolo, C.M. & Anderson, J.G. (2000). *BSSA*, 90(5):1223–1240.
- Faulds, J.E. et al. (2011). *Geosphere*, 7(3):617–643. <https://doi.org/10.1130/GES00604.1>
- Lei, J. et al. (2018). *JASA*, 113(523):1094–1107. <https://doi.org/10.1080/01621459.2017.1399809>
- Mordret, A. et al. (2019). *JGR Solid Earth*, 124(7):6808–6826.
- Peng, C.-K. et al. (1994). *Phys. Rev. E*, 49:1685–1689.
- Sanderson, D.J. & Nixon, C.W. (2015). *J. Struct. Geol.*, 75:141–155.
- Wannamaker, P.E. et al. (2014). *Geophysics*, 79(1):B1–B12.
