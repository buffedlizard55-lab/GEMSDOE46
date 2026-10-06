"""Local implementation of the published distance-weighted Tversky metric.

This implements the published formula for development diagnostics. It is not a
claim that it is bit-for-bit identical to the organizer's production scorer.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt


@dataclass(frozen=True)
class DTIComponents:
    """Weighted components for one scoring region."""

    score: float
    true_positive: float
    false_positive: float
    false_negative: float
    truth_pixels: int
    prediction_mass: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_arrays(
    predictions: np.ndarray,
    truth: np.ndarray,
    valid_mask: np.ndarray | None,
    score_mask: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    p = np.asarray(predictions)
    y = np.asarray(truth)

    if p.ndim != 2 or y.ndim != 2:
        raise ValueError("predictions and truth must be 2-D single-band arrays")
    if p.shape != y.shape:
        raise ValueError(f"shape mismatch: predictions {p.shape}, truth {y.shape}")

    if valid_mask is None:
        valid = np.ones(p.shape, dtype=bool)
    else:
        valid = np.asarray(valid_mask, dtype=bool)
        if valid.shape != p.shape:
            raise ValueError("valid_mask shape does not match predictions")

    if score_mask is None:
        scored = valid.copy()
    else:
        scored = np.asarray(score_mask, dtype=bool)
        if scored.shape != p.shape:
            raise ValueError("score_mask shape does not match predictions")
        if np.any(scored & ~valid):
            raise ValueError("score_mask includes cells outside valid_mask")

    if not valid.any():
        raise ValueError("valid_mask contains no cells")

    try:
        p64 = p.astype(np.float64, copy=False)
        y64 = y.astype(np.float64, copy=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("predictions and truth must be numeric arrays") from exc

    if not np.isfinite(p64[valid]).all():
        raise ValueError("predictions must be finite inside valid_mask")
    if np.any((p64[valid] < 0.0) | (p64[valid] > 1.0)):
        raise ValueError("predictions must lie in [0, 1] inside valid_mask")
    if not np.isfinite(y64[valid]).all():
        raise ValueError("truth must be finite inside valid_mask")
    if np.any(~np.isin(y64[valid], (0.0, 1.0))):
        raise ValueError("truth must contain only binary 0/1 values inside valid_mask")

    p_work = np.zeros(p.shape, dtype=np.float64)
    p_work[valid] = p64[valid]
    truth_mask = (y64 == 1.0) & valid
    return p_work, truth_mask, valid, scored


def _max_prediction_credit(
    predictions: np.ndarray,
    truth_mask: np.ndarray,
    valid_mask: np.ndarray,
    *,
    cell_size_m: float,
    radius_m: float,
) -> np.ndarray:
    """For every truth cell, find max_x p(x) * triangular_kernel(distance)."""
    height, width = predictions.shape
    credit = np.zeros(predictions.shape, dtype=np.float64)
    reach = math.ceil(radius_m / cell_size_m)

    for row_offset in range(-reach, reach + 1):
        for col_offset in range(-reach, reach + 1):
            distance = math.hypot(row_offset * cell_size_m, col_offset * cell_size_m)
            if distance > radius_m + 1e-12:
                continue
            weight = max(0.0, 1.0 - distance / radius_m)

            # For a truth at (r, c), compare prediction at (r+row_offset,
            # c+col_offset). Keep the corresponding overlapping slices only.
            r0 = max(0, -row_offset)
            r1 = min(height, height - row_offset)
            c0 = max(0, -col_offset)
            c1 = min(width, width - col_offset)
            if r0 >= r1 or c0 >= c1:
                continue

            neighbor_predictions = predictions[
                r0 + row_offset : r1 + row_offset,
                c0 + col_offset : c1 + col_offset,
            ]
            neighbor_valid = valid_mask[
                r0 + row_offset : r1 + row_offset,
                c0 + col_offset : c1 + col_offset,
            ]
            target_credit = credit[r0:r1, c0:c1]
            candidate_credit = np.where(neighbor_valid, neighbor_predictions * weight, 0.0)
            np.maximum(target_credit, candidate_credit, out=target_credit)

    # Values away from truth are unused, but zeroing them makes diagnostics
    # deterministic and avoids confusing downstream readers.
    credit[~truth_mask] = 0.0
    return credit


def dti_components(
    predictions: np.ndarray,
    truth: np.ndarray,
    *,
    valid_mask: np.ndarray | None = None,
    score_mask: np.ndarray | None = None,
    cell_size_m: float = 100.0,
    radius_m: float = 300.0,
    alpha: float = 0.2,
    beta: float = 0.8,
) -> DTIComponents:
    """Compute official-formula DTI components for a scoring region.

    ``valid_mask`` controls the prediction/truth context. ``score_mask`` only
    selects which truth and prediction terms are attributed to this region.
    The full valid context is used for distance credit, so disjoint score masks
    can be summed without introducing artificial fold-edge effects.
    """
    if cell_size_m <= 0 or radius_m <= 0:
        raise ValueError("cell_size_m and radius_m must be positive")
    if alpha < 0 or beta < 0:
        raise ValueError("alpha and beta must be nonnegative")
    if not math.isfinite(alpha) or not math.isfinite(beta):
        raise ValueError("alpha and beta must be finite")

    p, truth_mask, valid, scored = _validate_arrays(predictions, truth, valid_mask, score_mask)
    if not scored.any():
        raise ValueError("score_mask contains no cells")
    truth_scored = truth_mask & scored
    truth_count = int(truth_scored.sum())
    if truth_count == 0:
        raise ValueError("score_mask contains no positive truth pixels")
    truth_context_count = int(truth_mask.sum())
    if truth_context_count == 0:
        raise ValueError("valid_mask contains no positive truth pixels")

    credit = _max_prediction_credit(
        p,
        truth_mask,
        valid,
        cell_size_m=cell_size_m,
        radius_m=radius_m,
    )
    tp = float(credit[truth_scored].sum(dtype=np.float64))
    fn = float((1.0 - credit[truth_scored]).sum(dtype=np.float64))

    # Distance to the nearest positive truth pixel in the full valid context.
    distance_m = distance_transform_edt(~truth_mask, sampling=(cell_size_m, cell_size_m))
    truth_kernel = np.maximum(0.0, 1.0 - distance_m / radius_m)
    fp_weights = 1.0 - truth_kernel
    fp = float((p[scored] * fp_weights[scored]).sum(dtype=np.float64))

    denominator = tp + alpha * fp + beta * fn
    if denominator <= 0.0:
        raise ValueError("DTI denominator is zero")
    score = tp / denominator
    return DTIComponents(
        score=float(score),
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        truth_pixels=truth_count,
        prediction_mass=float(p[scored].sum(dtype=np.float64)),
    )


def dti_score(*args: Any, **kwargs: Any) -> float:
    """Convenience wrapper returning only the DTI score."""
    return dti_components(*args, **kwargs).score
