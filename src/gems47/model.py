"""Catalogue-supervised detector: sampling, training, tiled inference.

Honest scope of the supervision: the published catalogue is the only ground truth available in
this environment, and it is *not* the competition truth (the scored truth is a private set of
newly identified faults that the catalogue lacks).  Training on the catalogue therefore optimises
P(a mapped fault lies at x | features); the emission stage (``emission.py``) converts that into a
dense-free dot set under the metric's own marginal rule.  Spatial blocking is used so that every
reported CV number is measured on faults the model never saw.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import features as F


@dataclass
class ModelConfig:
    n_pos: int = 60_000
    n_neg: int = 240_000
    neg_buffer_px: int = 5
    seed: int = 4701
    num_leaves: int = 63
    learning_rate: float = 0.06
    n_estimators: int = 400
    min_child_samples: int = 40
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0
    tile_rows: int = 128

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _sample_rows(labels: np.ndarray, footprint: np.ndarray, d_cat: np.ndarray,
                 train_mask: np.ndarray, cfg: ModelConfig, rng: np.random.Generator):
    """Return (rows, cols, y) sampled inside ``train_mask``."""
    valid = footprint & train_mask
    pos = labels & valid
    neg_ok = valid & ~labels & (d_cat > cfg.neg_buffer_px)
    py, px = np.nonzero(pos)
    ny, nx = np.nonzero(neg_ok)
    if py.size > cfg.n_pos:
        sel = rng.choice(py.size, cfg.n_pos, replace=False)
        py, px = py[sel], px[sel]
    if ny.size > cfg.n_neg:
        sel = rng.choice(ny.size, cfg.n_neg, replace=False)
        ny, nx = ny[sel], nx[sel]
    rows = np.concatenate([py, ny]).astype(np.int64)
    cols = np.concatenate([px, nx]).astype(np.int64)
    y = np.concatenate([np.ones(py.size, np.int8), np.zeros(ny.size, np.int8)])
    return rows, cols, y


def extract_rows(src, rows: np.ndarray, cols: np.ndarray, names: list[str],
                 tile_rows: int = 128) -> np.ndarray:
    """Feature matrix for the requested (row, col) pairs, computed tile by tile."""
    out = np.full((rows.size, len(names)), np.nan, dtype=np.float32)
    order = np.argsort(rows, kind="stable")
    H = src.height
    for r0 in range(0, H, tile_rows):
        r1 = min(H, r0 + tile_rows)
        sel = order[(rows[order] >= r0) & (rows[order] < r1)]
        if sel.size == 0:
            continue
        cube = F.compute_tile(src, r0, r1, names)
        rr = rows[sel] - r0
        out[sel] = cube[rr, cols[sel], :]
    return out


def train(X: np.ndarray, y: np.ndarray, cfg: ModelConfig, seed: int | None = None):
    """Fit a LightGBM binary classifier; NaNs are handled natively by LightGBM."""
    import lightgbm as lgb

    keep = np.isfinite(X).any(axis=1)
    X, y = X[keep], y[keep]
    pos = float((y == 1).sum())
    neg = float((y == 0).sum())
    model = lgb.LGBMClassifier(
        objective="binary",
        num_leaves=cfg.num_leaves,
        learning_rate=cfg.learning_rate,
        n_estimators=cfg.n_estimators,
        min_child_samples=cfg.min_child_samples,
        subsample=cfg.subsample,
        colsample_bytree=cfg.colsample_bytree,
        reg_lambda=cfg.reg_lambda,
        scale_pos_weight=(neg / pos) if pos else 1.0,
        random_state=cfg.seed if seed is None else seed,
        n_jobs=2,
        verbose=-1,
    )
    model.fit(X, y)
    return model


def predict_field(src, model, names: list[str], out: np.ndarray, tile_rows: int = 128,
                  rows: tuple[int, int] | None = None) -> None:
    """Fill ``out`` (H, W) float32 in place with the model score, tile by tile.

    ``rows`` optionally restricts the computation to one row interval (used by the blocked CV so a
    fold only pays for the quadrant it is scoring).
    """
    H = src.height
    lo, hi = (0, H) if rows is None else rows
    for r0 in range(lo, hi, tile_rows):
        r1 = min(hi, r0 + tile_rows)
        cube = F.compute_tile(src, r0, r1, names)
        flat = cube.reshape(-1, cube.shape[2])
        ok = np.isfinite(flat).any(axis=1)
        pred = np.zeros(flat.shape[0], dtype=np.float32)
        if ok.any():
            pred[ok] = model.predict_proba(flat[ok])[:, 1].astype(np.float32)
        out[r0:r1] = pred.reshape(r1 - r0, cube.shape[1])
