"""Spatially blocked holdout, spacing sweep and split-conformal selection.

Design (nothing here is tuned on the evaluation data)
-----------------------------------------------------
* **Blocks.**  The grid is cut into ``N_TILE_ROWS x N_TILE_COLS`` fixed tiles.  A
  tile is the unit of spatial blocking: for fold *k* the model is trained with
  **every catalogue pixel inside tile k removed**, then asked to recover exactly
  those pixels from the 25 physical features.  This is a hide-and-recover proxy
  for the real task ("recover faults the catalogue does not contain").
* **Sweep.**  For each fold and each spacing ``r`` the emitter produces one
  complete emission inside the tile; the exact official metric is then evaluated
  on the tile's held-out catalogue pixels, with a window halo so that spatial
  blocking cannot change the metric's own 300 m reach.
* **Population matching (the fix for the proxy's known bias).**  Scored truth is
  the *new-fault* population, which is far sparser than the catalogue.  The
  family's own forensic analysis (GEMSDOE32 `IR-32-PROXY-01`, and the live
  sweep 0.2600@44k / 0.2477@60k / 0.1922@121k dots) shows what a catalogue-truth
  proxy does when this is ignored: it rewards dots that merely sit on the
  catalogue and therefore prefers far too *dense* an emission.  Every arm is
  therefore scored against two truth populations on the same bytes:

      ``pop_full``  the tile's catalogue pixels                     (density diag.)
      ``pop_thin``  a deterministic 12.96 % subsample of them        (primary)

  The subsample ratio is the declared ratio between the estimated scored-truth
  mass and the catalogue mass.  It is a *declared assumption*, swept in
  ``TRUTH_RATIOS`` for sensitivity and reported as such -- never hidden inside
  the verdict and never tuned on any score.
* **Selection / calibration split (split conformal).**  Tiles are split into a
  *selection* half and a *calibration* half.  Selection ranks the arms;
  calibration yields a finite-sample one-sided lower confidence bound

      q(s) = the ceil((n+1)(1-a))-th smallest residual  r_j(s) = s_j(s) - mean_cal(s)
      L(s) = mean_cal(s) - q(s)

  (Lei, G'Sell, Rinaldo, Tibshirani & Wasserman 2018, JASA 113(523), *Distribution-
  Free Predictive Inference for Regression*, Sec. 3 split conformal, applied to a
  population mean).  The shipped arm is the short-listed arm with the largest L.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from .emitter import emit_positions
from .window_metric import window_terms

# --- fixed, pre-declared constants (never tuned on the holdout) -------------
SPACINGS = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0)
N_TILE_ROWS = 4
N_TILE_COLS = 6
R_PIXELS = 3.0
INDEX_FLOOR = 0.26
CATALOGUE_EXCLUSION_PX = 1
NEW_FAULT_TO_CATALOGUE_RATIO = 0.1296   # declared primary population ratio
TRUTH_RATIOS = (1.0, 0.5, 0.25, 0.1296, 0.06)
PRIMARY_POP = "pop_thin"


@dataclass
class FoldResult:
    fold: int
    tile: tuple[int, int]
    selection: bool
    arms: dict = field(default_factory=dict)
    n_train_pos: int = 0
    n_train_neg: int = 0


def tile_bounds(shape, n_rows=N_TILE_ROWS, n_cols=N_TILE_COLS):
    h, w = shape
    rh = int(np.ceil(h / n_rows))
    rw = int(np.ceil(w / n_cols))
    out = []
    for i in range(n_rows):
        for j in range(n_cols):
            out.append((i, j, i * rh, min(h, (i + 1) * rh), j * rw, min(w, (j + 1) * rw)))
    return out


def hash_uniform(rows, cols, fold, salt=0x9E3779B1):
    """Deterministic uniform(0,1) value per (fold,row,col).

    A counter-based splitmix-style hash: stable, reproducible and identical
    across arms, so the *same* truth pixels are used for every sweep arm and the
    nested ratios (1.0 > 0.5 > 0.25 > 0.13 > 0.06) are strict subsets of one
    another.  No RNG state and no ordering effects.
    """
    h = (np.asarray(rows, dtype=np.uint64) * np.uint64(0x9E3779B97F4A7C15)
         ^ np.asarray(cols, dtype=np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F)
         ^ np.uint64((fold + 1) * 0x165667B1 + salt))
    h ^= h >> np.uint64(29)
    h = h * np.uint64(0xBF58476D1CE4E5B9)
    h ^= h >> np.uint64(32)
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def run_fold(flat_r, flat_c, footprint, truth, features, tile, catalogue_dist,
             model_factory, rng_seed, log=print, top_k_full=120_000, d_truth=None,
             ratios=TRUTH_RATIOS, spacings=SPACINGS):
    i, j, r0, r1, c0, c1 = tile
    in_tile = (flat_r >= r0) & (flat_r < r1) & (flat_c >= c0) & (flat_c < c1)
    pos_global = truth[flat_r, flat_c]
    train_mask = (~in_tile) & footprint[flat_r, flat_c]

    rng = np.random.default_rng(rng_seed)
    tr_pos = np.nonzero(train_mask & pos_global)[0]
    tr_neg_pool = np.nonzero(train_mask & ~pos_global)[0]
    n_neg = min(3 * len(tr_pos), len(tr_neg_pool))
    tr_neg = rng.choice(tr_neg_pool, size=n_neg, replace=False)
    tr_idx = np.concatenate([tr_pos, tr_neg])
    del tr_neg_pool, train_mask

    model = model_factory()
    model.fit(features[tr_idx], np.concatenate(
        [np.ones(len(tr_pos), dtype=np.int8), np.zeros(len(tr_neg), dtype=np.int8)]))
    del tr_idx

    # --- prior (intercept) correction ---------------------------------------
    # The training sample is a stratified subsample (all positives, 3x negatives),
    # so its log-odds are shifted relative to the population.  The emitter's
    # stopping rule is a *calibrated* expectation (bar = 0.2 * index), so the
    # shift must be undone before pi is used.  Exact log-odds re-centring:
    p_train = len(tr_pos) / (len(tr_pos) + n_neg)
    population = footprint[flat_r[~in_tile], flat_c[~in_tile]]
    p_pop = pos_global[~in_tile][population].mean() if population.any() else p_train
    logit_shift = np.log(p_train / (1 - p_train)) - np.log(p_pop / (1 - p_pop))

    halo = int(np.ceil(R_PIXELS)) + 1
    wr0, wr1 = max(0, r0 - halo), min(truth.shape[0], r1 + halo)
    wc0, wc1 = max(0, c0 - halo), min(truth.shape[1], c1 + halo)
    in_win = (flat_r >= wr0) & (flat_r < wr1) & (flat_c >= wc0) & (flat_c < wc1)
    win_rows = np.nonzero(in_win)[0]
    belief_win = np.zeros((wr1 - wr0, wc1 - wc0), dtype=np.float32)
    truth_win = np.zeros(belief_win.shape, dtype=bool)
    in_foot_win = np.zeros(belief_win.shape, dtype=bool)
    cat_dist_win = np.full(belief_win.shape, np.inf, dtype=np.float32)
    if len(win_rows):
        p_raw = model.predict_proba(features[win_rows])[:, 1].astype(np.float32)
        p_raw = np.clip(p_raw, 1e-9, 1 - 1e-9)
        lg = np.log(p_raw / (1.0 - p_raw)) - logit_shift
        p = (1.0 / (1.0 + np.exp(-lg))).astype(np.float32)
        lr = flat_r[win_rows] - wr0
        lc = flat_c[win_rows] - wc0
        belief_win[lr, lc] = p
        tv = pos_global[win_rows]
        truth_win[lr[tv], lc[tv]] = True
        in_foot_win[lr, lc] = footprint[flat_r[win_rows], flat_c[win_rows]]
        cat_dist_win[lr, lc] = catalogue_dist[flat_r[win_rows], flat_c[win_rows]]
        # per-ratio keep masks are thresholds on the SAME hash -> nested families
        hash_win = np.ones(belief_win.shape, dtype=np.float32)
        hash_win[lr, lc] = hash_uniform(flat_r[win_rows], flat_c[win_rows],
                                        i * N_TILE_COLS + j)
    else:
        hash_win = np.ones(belief_win.shape, dtype=np.float32)

    allow = in_foot_win & (cat_dist_win > CATALOGUE_EXCLUSION_PX)
    inside = np.zeros(belief_win.shape, dtype=bool)
    inside[max(0, r0 - wr0):(r1 - wr0), max(0, c0 - wc0):(c1 - wc0)] = True
    allow = allow & inside

    res = FoldResult(fold=i * N_TILE_COLS + j, tile=(i, j), selection=True,
                     n_train_pos=int(len(tr_pos)), n_train_neg=int(n_neg))
    for s in spacings:
        rr, cc = emit_positions(belief_win, allow, s, index_floor=INDEX_FLOOR,
                                max_dots=top_k_full)
        dots = np.stack([rr + wr0, cc + wc0], axis=1).astype(np.int32) if len(rr) \
            else np.zeros((0, 2), np.int32)
        arms = {}
        for ratio in ratios:
            t_use = truth_win & (hash_win < ratio) if ratio < 1.0 else truth_win
            if ratio >= 1.0:
                key = "pop_full"
            elif abs(ratio - NEW_FAULT_TO_CATALOGUE_RATIO) < 1e-12:
                key = "pop_thin"
            else:
                key = f"pop_r{ratio:g}"
            t = window_terms(dots, t_use, R_PIXELS, origin=(wr0, wc0), d_truth_global=d_truth)
            t.update({"spacing": float(s), "population": key, "ratio": float(ratio),
                      "emitted_px": int(len(dots))})
            arms[key] = t
        arms["dot_count"] = int(len(dots))
        res.arms[float(s)] = arms
    log(f"  fold {res.fold:>2} tile=({i},{j}) trainpos={len(tr_pos)} "
        f"truth_full={int(truth_win.sum())} truth_thin={int((truth_win & (hash_win < NEW_FAULT_TO_CATALOGUE_RATIO)).sum())} "
        + " ".join(f"r{s:g}={res.arms[s][PRIMARY_POP]['DTI']:.4f}/{res.arms[s]['dot_count']}"
                   for s in spacings))
    return res


def eligible(fold, pop_key=PRIMARY_POP):
    """Pre-observable eligibility rule: a block carries information iff it contains truth.

    This depends only on the *truth mask*, never on any arm's score, so applying it
    before looking at the sweep cannot bias the selection.  Blocks outside the
    survey footprint contain no catalogue pixels and every arm scores exactly 0
    there; including them would inflate the conformal residual quantile with
    blocks that carry no information about arm quality.
    """
    return all(fold.arms[s][pop_key]["G"] > 0 for s in fold.arms)


def conformal_select(folds, alpha, pop_key=PRIMARY_POP, ratio_key=None):
    """Split-conformal selection over the spacing sweep. Returns (chosen, shortlist, table)."""
    folds = [f for f in folds if eligible(f, pop_key)]
    sel = [f for f in folds if f.selection]
    cal = [f for f in folds if not f.selection]
    table, ranking = {}, {}
    for s in SPACINGS:
        sel_sc = np.array([f.arms[s][pop_key]["DTI"] for f in sel], dtype=float)
        cal_sc = np.array([f.arms[s][pop_key]["DTI"] for f in cal], dtype=float)
        m_sel, m_cal = float(sel_sc.mean()), float(cal_sc.mean())
        resid = cal_sc - m_cal
        n = len(resid)
        rank = int(np.ceil((n + 1) * (1.0 - alpha)))
        q = float("inf") if rank > n else float(np.sort(resid)[rank - 1])
        table[float(s)] = {
            "selection_mean": m_sel, "calibration_mean": m_cal,
            "calibration_std": float(cal_sc.std(ddof=1)) if n > 1 else 0.0,
            "calibration_min": float(cal_sc.min()) if n else float("nan"),
            "calibration_max": float(cal_sc.max()) if n else float("nan"),
            "conformal_quantile": q, "certified_floor": m_cal - q,
            "n_selection": len(sel_sc), "n_calibration": n,
            "median_dots_full_footprint": float(
                np.median([f.arms[s]["dot_count"] for f in folds]) * (N_TILE_ROWS * N_TILE_COLS)),
        }
        ranking[float(s)] = m_sel
    shortlist = sorted(SPACINGS, key=lambda s: -ranking[s])[:3]
    chosen = max(shortlist, key=lambda s: table[s]["certified_floor"])
    return float(chosen), shortlist, table


def split_folds(folds, scheme="checkerboard", frac_selection=0.5):
    """Assign blocks to the selection / calibration halves.

    ``checkerboard`` (default) alternates on the tile parity ``(i + j) % 2``.  It is
    used instead of splitting on a contiguous latitude band because the two halves
    then have comparable fault density and comparable distance to the survey edge,
    which is what the exchangeability the conformal bound relies on actually needs.
    The assignment depends only on the tile index, never on any score.
    """
    folds = sorted(folds, key=lambda f: f.fold)
    if scheme == "checkerboard":
        for f in folds:
            f.selection = ((f.tile[0] + f.tile[1]) % 2 == 0)
    else:
        n_sel = int(round(frac_selection * len(folds)))
        for k, f in enumerate(folds):
            f.selection = k < n_sel
    return folds
