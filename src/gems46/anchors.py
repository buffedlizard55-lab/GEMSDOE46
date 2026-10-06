"""Anchor corpus: scored prior submissions as sparse dot lists, plus exact score functionals.

The 50 public artifacts in `data/raw/anchors/` are *evidence of shape*, and their reported
scores are the only observations this project has of the hidden label set.  Because the
overwhelming majority of their mass sits on dot-shaped pixels, each anchor is compressed to
three arrays (row, col, value), which makes the metric's sums exact and fast:

    S    = sum_dots v                                   emitted mass
    T(q) = sum_dots sum_off v*k*q[row+dy, col+dx]       expected TP_w under truth density q
    T(G) = sum_{g in G} max_dot,off v*k                 exact TP_w against a truth *set* G
    M(G) = sum_dots v*k(d dot -> nearest truth pixel)   the mass that relieves FP_w
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import xmetric as M

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Dots:
    """Sparse prediction raster."""
    row: np.ndarray
    col: np.ndarray
    val: np.ndarray
    name: str = ""

    def __len__(self) -> int:
        return int(self.row.size)

    @property
    def mass(self) -> float:
        return float(self.val.sum())

    def raster(self, shape: tuple[int, int]) -> np.ndarray:
        out = np.zeros(shape, np.float32)
        out[self.row, self.col] = self.val
        return out


def load_dots(path: Path, name: str = "") -> Dots:
    import rasterio
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    a[a < 0] = 0.0
    r, c = np.nonzero(a)
    return Dots(r, c, a[r, c], name or path.stem)


def coverage_map(dots: Dots, shape: tuple[int, int], offsets=None) -> np.ndarray:
    """C(x) = max over dots within R of v*k(d(x, dot)).  Exact, built by scatter-max."""
    offs = M.OFFSETS if offsets is None else offsets
    H, W = shape
    cov = np.zeros(shape, np.float32)
    for dy, dx, k in offs:
        r = dots.row + dy
        c = dots.col + dx
        ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
        if not ok.any():
            continue
        np.maximum.at(cov, (r[ok], c[ok]), dots.val[ok] * np.float32(k))
    return cov


def expected_tp(dots: Dots, q: np.ndarray, offsets=None) -> float:
    """T(q) = sum_dots sum_off v*k*q[neighbour] for a pixel-level truth density q."""
    offs = M.OFFSETS if offsets is None else offsets
    H, W = q.shape
    total = 0.0
    for dy, dx, k in offs:
        r = dots.row + dy
        c = dots.col + dx
        ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
        if ok.any():
            total += float((dots.val[ok] * np.float32(k) * q[r[ok], c[ok]]).sum())
    return total


def mass_on_mask(dots: Dots, mask: np.ndarray) -> float:
    """Emitted mass sitting on `mask` (use with the catalogue: that mass is wasted)."""
    return float(dots.val[mask[dots.row, dots.col]].sum())


def distance_to_mask(dots: Dots, mask: np.ndarray) -> np.ndarray:
    from scipy.ndimage import distance_transform_edt
    if not mask.any():
        return np.full(len(dots), np.inf)
    d = distance_transform_edt(~mask)
    return d[dots.row, dots.col]


def score_dots_vs_truth(dots: Dots, truth: np.ndarray, offsets=None) -> dict:
    """Exact DTI of `dots` against a binary truth mask (masking by catalogue is the caller's job)."""
    cov = coverage_map(dots, truth.shape, offsets)
    n = int(truth.sum())
    s = dots.mass
    t = float(cov[truth].sum())
    d = distance_to_mask(dots, truth)
    m = float((dots.val * M.kernel(np.where(np.isfinite(d), d, np.inf))).sum())
    fp = s - m
    return dict(tp=t, fp=fp, fn=n - t, n_truth=n, mass=s,
                dti=M.dti_from_parts(t, fp, n - t) if n else 0.0,
                coverage=(t / n) if n else 0.0)
