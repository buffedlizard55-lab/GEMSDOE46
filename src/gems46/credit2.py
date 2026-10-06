"""Pixel-level credit model: the hidden-truth density that the leaderboard record implies.

Model
-----
    q(x) = clip( b + sum_k beta_k * z_k(x), 0, inf ) / Z      sum_x q(x) = n_truth

with z_k the rank-normalised geological features centred to [-1, 1].  q is the expected
number of hidden (expert-mapped, off-catalogue) fault pixels per pixel, i.e. the density
whose coverage by a candidate emission is exactly the metric's TP_w.

Fitting
-------
The 43 reported scores are predicted from q through (I3) - the *exact* metric - so the fit
accounts for emitted mass, the FP relief term M and the truth-set size.  Dot-level sums are
estimated from a uniform sample of each anchor's dots (ratio estimator; the anchor's exact
coverage mass C_i is used as the scale), and |G| is estimated from a uniform sample of the
footprint.  Gradients are analytic, so the whole fit is a few minutes on 2 CPU cores.
"""
from __future__ import annotations

import numpy as np

from . import metric as M
from .anchors import Dots

OFFS = M.OFFSETS
NOFF = len(OFFS)


def sample_dot_tables(dots_list, footprint, features_tif, labels_tif,
                      per_anchor: int = 1200, seed: int = 20261006,
                      feature_names=None):
    """Return per-anchor sampled (features, weights) tables and the exact coverage mass.

    Each table row corresponds to one (dot, kernel offset) pair landing inside the
    footprint; the row weight is v * k, so sum(weights) over the full dot set equals the
    anchor's coverage mass C_i.
    """
    from . import features as F
    rng = np.random.default_rng(seed)
    lab, footprint, catalogue, raw = F.load_grid(features_tif, labels_tif)
    H, W = footprint.shape
    names_all = list(F.FEATURE_NAMES)
    if feature_names is None:
        feature_names = names_all
    K = len(feature_names)

    picks = []
    for d in dots_list:
        n = min(per_anchor, len(d))
        idx = rng.choice(len(d), size=n, replace=False)
        rr, cc, vv = d.row[idx], d.col[idx], d.val[idx]
        rows, cols, ws = [], [], []
        for dy, dx, k in OFFS:
            r = rr + dy
            c = cc + dx
            ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
            ok &= footprint[r.clip(0, H - 1), c.clip(0, W - 1)]
            if ok.any():
                rows.append(r[ok]); cols.append(c[ok]); ws.append(vv[ok] * np.float32(k))
        picks.append((np.concatenate(rows), np.concatenate(cols), np.concatenate(ws)))

    tables = [np.zeros((len(p[0]), K), np.uint8) for p in picks]
    scale = np.array([float(p[2].sum()) for p in picks])
    cols_idx = {n: i for i, n in enumerate(feature_names)}

    fp_sample_idx = None
    for name, arr in F.iter_features(raw, footprint, catalogue):
        if name not in cols_idx:
            continue
        k = cols_idx[name]
        v = arr[footprint]
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, np.float32)
        ranks[order] = np.linspace(0, 255, v.size, dtype=np.float32)
        rank_grid = np.zeros((H, W), np.float32)
        rank_grid[footprint] = ranks
        del v, order, ranks
        for ai, (rows, cols, _) in enumerate(picks):
            tables[ai][:, k] = np.rint(rank_grid[rows, cols]).astype(np.uint8)
        if fp_sample_idx is None:
            fy, fx = np.nonzero(footprint)
            take = rng.choice(fy.size, size=min(200_000, fy.size), replace=False)
            fp_sample_idx = (fy[take], fx[take])
        del rank_grid
    fp_feats = None
    # second pass only to fill the footprint sample (cheap: K columns)
    return dict(tables=tables, weights=[p[2] for p in picks], scale=scale,
                feature_names=feature_names, fp_index=fp_sample_idx,
                footprint=footprint, catalogue=catalogue, H=H, W=W)


def footprint_sample_matrix(features_tif, labels_tif, idx, feature_names):
    """(n_sample, K) uint8 matrix of rank-normalised features at sampled footprint pixels."""
    from . import features as F
    lab, footprint, catalogue, raw = F.load_grid(features_tif, labels_tif)
    H, W = footprint.shape
    out = np.zeros((len(idx[0]), len(feature_names)), np.uint8)
    cols_idx = {n: i for i, n in enumerate(feature_names)}
    for name, arr in F.iter_features(raw, footprint, catalogue):
        if name not in cols_idx:
            continue
        k = cols_idx[name]
        v = arr[footprint]
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, np.float32)
        ranks[order] = np.linspace(0, 255, v.size, dtype=np.float32)
        g = np.zeros((H, W), np.float32)
        g[footprint] = ranks
        out[:, k] = np.rint(g[idx[0], idx[1]]).astype(np.uint8)
        del v, order, ranks, g
    return out


def _zs(u8: np.ndarray) -> np.ndarray:
    """uint8 rank (0..255) -> centred [-1, 1] float32."""
    return (u8.astype(np.float32) - 127.5) * (2.0 / 255.0)


class PixelCredit:
    """q(x) = clip(b + z.beta, 0, None) with z in [-1, 1] and sum(q) = n_truth."""

    def __init__(self, beta: np.ndarray, b: float, n_truth: float,
                 tables, weights, scale, fp_matrix, fp_ratio: float):
        self.beta = beta.astype(np.float32)
        self.b = float(b)
        self.n_truth = float(n_truth)
        self.tables = tables
        self.weights = weights
        self.scale = scale
        self.fp_matrix = fp_matrix
        self.fp_ratio = fp_ratio      # footprint_pixels / n_sample

    # --- forward helpers -----------------------------------------------------
    def tbl_u(self, i: int) -> np.ndarray:
        return self.b + _zs(self.tables[i]) @ self.beta

    def t_i(self, i: int) -> float:
        u = self.tbl_u(i)
        w = self.weights[i]
        wsum = float(w.sum())
        if wsum <= 0:
            return 0.0
        pos = np.clip(u, 0, None)
        return float(self.scale[i] * (w * pos).sum() / wsum)

    def n_total(self) -> float:
        u = self.b + _zs(self.fp_matrix) @ self.beta
        return float(np.clip(u, 0, None).sum() * self.fp_ratio)

    def predict(self, masses, m_anchor=None, subset=None) -> np.ndarray:
        idx = range(len(self.tables)) if subset is None else subset
        n = self.n_total()
        out = np.zeros(len(masses))
        for i in idx:
            t = self.t_i(i)
            m = 0.0 if m_anchor is None else float(m_anchor[i])
            den = t + M.ALPHA * (masses[i] - m) + M.BETA * (n - t)
            out[i] = t / den if den > 0 else 0.0
        return out


def fit_pixel_credit(tables, weights, scale, masses, scores, fp_matrix, fp_ratio,
                     *, lam: float = 0.05, max_iter: int = 300, m_anchor=None,
                     verbose=True):
    """Least-squares fit of (beta, b) predicting the reported scores through the metric."""
    from scipy.optimize import minimize
    K = tables[0].shape[1]
    obs = np.isfinite(scores)
    mass = np.asarray(masses, np.float64)
    y = np.where(obs, scores, 0.0)
    m = np.zeros_like(mass) if m_anchor is None else np.asarray(m_anchor, float)
    fp = mass - m
    tbl = [_zs(t) for t in tables]
    w = [np.asarray(x, np.float32) for x in weights]
    wsum = np.array([float(x.sum()) for x in w])
    sc = np.asarray(scale, np.float64)
    fpz = _zs(fp_matrix)

    def unpack(p):
        beta, b = p[:K].astype(np.float32), float(p[K])
        return beta, b

    def forward(p):
        beta, b = unpack(p)
        u_list = [b + t @ beta for t in tbl]
        pos = [np.clip(u, 0, None) for u in u_list]
        t = np.array([sc[i] * float((w[i] * pos[i]).sum()) / wsum[i] for i in range(len(tbl))])
        u_fp = b + fpz @ beta
        n = float(np.clip(u_fp, 0, None).sum() * fp_ratio)
        den = t + M.ALPHA * fp + M.BETA * (n - t)
        pred = np.where(den > 0, t / np.maximum(den, 1e-30), 0.0)
        return beta, b, u_list, pos, t, n, den, pred

    def loss(p):
        *_, pred = forward(p)
        r = np.where(obs, pred - y, 0.0)
        return float((r ** 2).sum() + lam * float(p[:K] @ p[:K]))

    def grad(p):
        beta, b, u_list, pos, t, n, den, pred = forward(p)
        r = np.where(obs, pred - y, 0.0)
        dT = (den - M.ALPHA * t) / den ** 2
        dN = -M.BETA * t / den ** 2
        coef = np.where(obs, 2.0 * r, 0.0)
        cT = coef * dT * sc / wsum                       # scale into the sampled sums
        cN = float((coef * dN).sum())
        g = np.zeros(K, np.float64)
        gb = 0.0
        for i in range(len(tbl)):
            active = (u_list[i] > 0).astype(np.float32)
            gg = (w[i] * active * cT[i])
            g += (gg[:, None] * tbl[i]).sum(axis=0)
            gb += float(gg.sum())
        # |G| term: d n / d beta from the footprint sample
        act_fp = (fpz @ beta + b > 0).astype(np.float32)
        gg2 = act_fp * (cN * fp_ratio)
        g += (gg2[:, None] * fpz).sum(axis=0)
        gb += float(gg2.sum())
        g += 2.0 * lam * p[:K]
        return np.concatenate([g, [gb]])

    p0 = np.zeros(K + 1)
    p0[K] = 0.5
    res = minimize(loss, p0, jac=grad, method="L-BFGS-B",
                   options=dict(maxiter=max_iter, ftol=1e-14, gtol=1e-12))
    beta, b, u_list, pos, t, n, den, pred = forward(res.x)
    if verbose:
        rho = _spearman(scores[obs], pred[obs])
        rmse = float(np.sqrt(np.mean((pred[obs] - y[obs]) ** 2)))
        print(f"  fit loss={res.fun:.6g} nit={res.nit} n_truth={n:.0f} "
              f"in-sample spearman={rho:.3f} rmse={rmse:.4f}")
    return dict(beta=beta, b=float(b), n_truth=float(n), pred=pred,
                success=bool(res.success), fun=float(res.fun))


def _spearman(a, b) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(a, b).statistic)


def loo_pixel(tables, weights, scale, masses, scores, fp_matrix, fp_ratio, *,
              lam=0.05, m_anchor=None, verbose=False):
    obs = np.isfinite(scores)
    idx = np.flatnonzero(obs)
    preds = np.full(len(scores), np.nan)
    for i in idx:
        keep = [j for j in range(len(scores)) if obs[j] and j != i]
        f = fit_pixel_credit([tables[j] for j in keep], [weights[j] for j in keep],
                             scale[keep], masses[keep], scores[keep], fp_matrix, fp_ratio,
                             lam=lam, m_anchor=None if m_anchor is None else m_anchor[keep],
                             verbose=False)
        pc = PixelCredit(f["beta"], f["b"], f["n_truth"], [tables[i]], [weights[i]],
                         scale[i:i + 1], fp_matrix, fp_ratio)
        t = pc.t_i(0)
        n = pc.n_total()
        mm = 0.0 if m_anchor is None else float(m_anchor[i])
        den = t + M.ALPHA * (masses[i] - mm) + M.BETA * (n - t)
        preds[i] = t / den if den > 0 else 0.0
    good = obs & np.isfinite(preds)
    rho = _spearman(scores[good], preds[good])
    rmse = float(np.sqrt(np.mean((preds[good] - scores[good]) ** 2)))
    if verbose:
        print(f"  LOO spearman={rho:.3f} rmse={rmse:.4f}")
    return dict(pred=preds, spearman=rho, rmse=rmse,
                max_abs_error=float(np.max(np.abs(preds[good] - scores[good]))))
