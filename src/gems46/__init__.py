"""GEMSDOE46 - distance-weighted-Tversky-aware fault detection for the DOE GEMS Prize.

Modules
-------
grid        : GeoTIFF I/O against the official template (CRS/shape/transform contract).
metric      : the organiser's Distance-Weighted Tversky Index (DTI), transcribed from page 967.
dfa         : detrended fluctuation analysis (Peng et al. 1994) - 1-D reference + vectorised
              sliding-window scaling-exponent estimator used along raster transects.
fields      : loading/normalising the 19 official feature bands.
detector    : the H46 detector - local DFA scaling-exponent breaks along magnetic and gravity
              transects, background-relative robust z-scores, regime-boundary transform.
emission    : metric-derived emission (mass budget, spacing, greedy maximum coverage).
holdout     : spatially blocked validation instruments.
submission  : format-exact writer + independent re-read audit.
"""

__version__ = "46.0.0"
