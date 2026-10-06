"""Spatially blocked validation instruments.

Instrument A ("cat-held-out"): hide the catalogue faults inside a spatial block; the catalogue
outside the block plays the role the real scorer gives the published catalogue (masked / excluded),
so this emulates the live setup: one hidden fault population + one masked known population.

Instrument B ("off-catalogue-SGMC"): the truth is the USGS State Geologic Map Compilation (SGMC)
fault raster restored in the group's public mirror (derived_sgmc_faults_100m_u8.tif), with every
SGMC pixel that also sits on the published catalogue removed, and the catalogue itself masked.
This is a genuinely *off-catalogue* fault population, i.e. the closest available analogue of the
private test set ("newly identified faults that are not in the USGS database").

Both instruments are documented as weak in the literature of this project: the group measured
Spearman +0.09 (instrument A) and +0.31 (instrument B) against 11 official leaderboard scores, so
neither may be used as a score forecast; they are used only for *relative* comparisons at matched
emitted mass, together with the emission-size calibration that was measured to track the live board.
"""

from __future__ import annotations

import numpy as np

from . import metric as M


def blocks(shape, n_rows: int = 3, n_cols: int = 3):
    """Deterministic spatial blocks covering the raster (block id per cell)."""
    h, w = shape
    ids = np.zeros((h, w), dtype=np.int16)
    edges_r = np.linspace(0, h, n_rows + 1).astype(int)
    edges_c = np.linspace(0, w, n_cols + 1).astype(int)
    for i in range(n_rows):
        for j in range(n_cols):
            ids[edges_r[i]:edges_r[i + 1], edges_c[j]:edges_c[j + 1]] = i * n_cols + j
    return ids, (edges_r, edges_c)


def instrument_cat(labels: np.ndarray, footprint: np.ndarray, block_id: np.ndarray, hold: int):
    """Return (truth, known, domain) for one held-out block of the catalogue."""
    in_block = block_id == hold
    truth = labels.astype(bool) & in_block
    known = labels.astype(bool) & ~in_block
    domain = footprint & ~known
    return truth, known, domain


def instrument_sgmc(sgmc: np.ndarray, labels: np.ndarray, footprint: np.ndarray, block_id=None,
                    hold: int | None = None, min_offcat_px: int = 2):
    """Off-catalogue SGMC truth: SGMC fault pixels that are >= ``min_offcat_px`` from the catalogue."""
    from scipy import ndimage

    cand = sgmc.astype(bool) & footprint
    if block_id is not None and hold is not None:
        cand = cand & (block_id == hold)
    near_cat = ndimage.binary_dilation(labels.astype(bool), iterations=int(min_offcat_px))
    truth = cand & ~near_cat
    known = labels.astype(bool)
    domain = footprint & ~known
    return truth, known, domain


def evaluate(pred_binary: np.ndarray, truth: np.ndarray, known: np.ndarray,
             footprint: np.ndarray) -> dict:
    """DTI of a binary prediction against one instrument, with the known-fault masking rule."""
    emit = np.asarray(pred_binary, dtype=bool) & footprint
    comp = M.components_binary(emit, truth, valid=footprint, known=known)
    d = comp.as_dict()
    d["emitted_px"] = int(emit.sum())
    d["truth_px"] = int(truth.sum())
    return d


def score_field(field: np.ndarray, truth: np.ndarray, known: np.ndarray, footprint: np.ndarray,
                budget: int, min_dist: int = 3, smooth_px: float = 1.85) -> dict:
    """Emit ``budget`` dots from a field with the shared emission rule and score them."""
    from .emission import greedy_emit

    domain = footprint & ~known
    emit, _ = greedy_emit(field, domain, budget, min_dist=min_dist, smooth_px=smooth_px)
    return evaluate(emit, truth, known, footprint)
