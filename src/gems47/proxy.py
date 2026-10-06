"""Validation instruments for the GEMS Prize metric, with the organizer masking rule applied.

Two instruments, both scored with the *published* metric transcribed in ``src/gems46/metric.py``
(``components_binary``) so that no second implementation of the metric exists in this repository:

``instrument_catalogue_block``   [MEASURED]  Truth = catalogue pixels inside one spatial block; the
    catalogue everywhere else is "known" and is masked out of the penalty terms exactly as the
    organizer confirmed for the live scorer (DrivenData staff, forum thread 11516: "Pixels
    corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation").  This
    emulates the live set-up: one hidden fault population plus one masked known population.

``instrument_sgmc_stratified``   [MEASURED]  Truth = USGS State Geologic Map Compilation fault
    pixels that lie *more than* ``d0`` pixels (default 5 px = 500 m) from any published catalogue
    pixel, with the catalogue masked as above.  The stratification is the fix for the defect the
    family measured in the naive version of this instrument: SGMC traces include the same faults as
    the catalogue, so an un-stratified "off-catalogue SGMC" truth is still catalogue-correlated and
    rewards mass hugging the catalogue, which is *anti-monotone* with the live board.  Measured here
    (scripts/run_h47.py, receipt): with d0 = 0 the instrument ranks the three live-scored incumbents
    0.2600 > 0.2708 > 0.2778 (inverted); with d0 >= 5 px it ranks them 0.2600 < 0.2708 < 0.2778,
    reproducing all three known live orderings.

Neither instrument is a score forecast.  They are screens; the live metric sees a truth set this
environment cannot obtain (see ``docs/IRREGULARITIES`` / ``registry/irregularities.json``).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from gems46 import metric as M


def block_ids(shape: tuple[int, int], n_rows: int = 4, n_cols: int = 4) -> np.ndarray:
    h, w = shape
    ids = np.zeros((h, w), dtype=np.int16)
    er = np.linspace(0, h, n_rows + 1).astype(int)
    ec = np.linspace(0, w, n_cols + 1).astype(int)
    for i in range(n_rows):
        for j in range(n_cols):
            ids[er[i]:er[i + 1], ec[j]:ec[j + 1]] = i * n_cols + j
    return ids


def instrument_catalogue_block(labels: np.ndarray, footprint: np.ndarray, ids: np.ndarray,
                               hold: int):
    in_block = ids == hold
    truth = labels.astype(bool) & in_block
    known = labels.astype(bool) & ~in_block
    domain = footprint & ~known
    return truth, known, domain


def instrument_sgmc_stratified(sgmc: np.ndarray, labels: np.ndarray, footprint: np.ndarray,
                               d_cat: np.ndarray, d0: float = 5.0):
    truth = sgmc.astype(bool) & footprint & (d_cat > float(d0))
    known = labels.astype(bool)
    domain = footprint & ~known
    return truth, known, domain


def score_emission(emit: np.ndarray, truth: np.ndarray, known: np.ndarray,
                   domain: np.ndarray) -> dict:
    """Exact published-metric components for a binary emission under the masking rule."""
    emit = np.asarray(emit, dtype=bool) & domain
    comp = M.components_binary(emit, truth, valid=domain, known=known)
    d = comp.as_dict()
    d["emitted_px"] = int(emit.sum())
    d["truth_px"] = int(truth.sum())
    d["dti"] = comp.dti
    return d


def masked_credit_to_truth(emit: np.ndarray, truth: np.ndarray, radius_px: float = M.RADIUS_PX):
    """Per-dot kernel credit to the nearest truth pixel (0 outside the 300 m support)."""
    emit = np.asarray(emit, dtype=bool)
    d = ndi.distance_transform_edt(~np.asarray(truth, bool))
    return M.kernel(d[emit])


def distance_to(mask: np.ndarray, points: np.ndarray | None = None) -> np.ndarray:
    """Euclidean distance transform helpers used by the receipts."""
    return ndi.distance_transform_edt(~np.asarray(mask, bool))
