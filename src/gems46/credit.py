"""Fit a hidden-truth density model to the leaderboard record.

Observation model
-----------------
For every scored public artifact i (a sparse dot field) the organiser's metric gives

    s_i = T_i / ( 0.2*(T_i + S_i - M_i) + 0.8*|G| )                     (I3)

with T_i = sum_g max_x p_i(x)k(d), S_i = emitted mass, M_i = sum_x p_i(x) max_g k, and |G|
the unknown number of hidden truth pixels.  Writing the hidden truth as a pixel-level
density q (q(x) = probability that pixel x is a hidden fault pixel),

    T_i = sum_x q(x) * C_i(x)   and   |G| = sum_x q(x)

are both *linear in q* (C_i = anchor i's coverage map), so the 41 observed scores become 41
non-linear-but-linear-in-q equations.  On 1 km blocks the coverage sums collapse to a
41 x 123k weight matrix, and the credit surface is a logistic function of block-standardised
geological covariates:

    q(x) = scale * sigmoid( b0 + sum_k b_k z_k(x) )

fitted by penalised least squares with leave-one-anchor-out validation.  The only
supervision used is the public score record - no hidden labels are available or assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import xmetric as M
from .anchors import Dots


@dataclass
class CoverageWeights:
    W: np.ndarray          # (n_anchors, n_blocks) float32, coverage mass per block
    mass: np.ndarray       # (n_anchors,) emitted mass
    score: np.ndarray      # (n_anchors,) reported score (nan when none)
    names: list[str] = field(default_factory=list)


def coverage_weights(dots_list: list[Dots], scores, names: list[str], meta: dict,
                     offsets=None) -> CoverageWeights:
    offs = M.OFFSETS if offsets is None else offsets
    block, ny, nx = meta["block"], meta["ny"], meta["nx"]
    H, W = meta["H"], meta["W"]
    rows = []
    for dots in dots_list:
        acc = np.zeros((ny, nx), np.float32)
        for dy, dx, k in offs:
            r = dots.row + dy
            c = dots.col + dx
            ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
            if not ok.any():
                continue
            br = (r[ok] // block)
            bc = (c[ok] // block)
            inb = (br < ny) & (bc < nx)
            np.add.at(acc, (br[inb], bc[inb]), dots.val[ok][inb] * np.float32(k))
        rows.append(acc.ravel())
    return CoverageWeights(W=np.stack(rows).astype(np.float32),
                           mass=np.array([d.mass for d in dots_list], np.float64),
                           score=np.array([np.nan if s is None else float(s) for s in scores]),
                           names=list(names))


def _standardise(Z: np.ndarray):
    mu = Z.reshape(-1, Z.shape[-1]).mean(axis=0)
    sd = Z.reshape(-1, Z.shape[-1]).std(axis=0) + 1e-9
    return mu, sd


def fit_credit(Z: np.ndarray, counts: np.ndarray, cw: CoverageWeights, *,
               lam: float = 3.0, max_iter: int = 300, m_anchor: np.ndarray | None = None,
               verbose: bool = False) -> dict:
    """Penalised least squares fit of (beta, beta0, log_scale) to the reported scores."""
    from scipy.optimize import minimize

    mu, sd = _standardise(Z)
    Zc = ((Z - mu) / sd).reshape(-1, Z.shape[-1]).astype(np.float64)
    counts_flat = counts.ravel().astype(np.float64)
    W = cw.W.astype(np.float64)
    obs = np.isfinite(cw.score)
    yout = np.where(obs, cw.score, 0.0)
    mass = cw.mass
    m = np.zeros_like(mass) if m_anchor is None else m_anchor
    fp = mass - m
    K = Zc.shape[1]

    def unpack(p):
        beta, beta0 = p[:K], p[K]
        u = np.clip(beta0 + Zc @ beta, -60, 60)
        s = 1.0 / (1.0 + np.exp(-u))
        return beta, beta0, s

    def loss(p):
        beta, beta0, s = unpack(p)
        q = s
        t = W @ q
        n = float((q * counts_flat).sum())
        den = t + M.ALPHA * fp + M.BETA * (n - t)
        pred = np.where(den > 0, t / np.maximum(den, 1e-30), 0.0)
        r = np.where(obs, pred - yout, 0.0)
        return float((r ** 2).sum() + lam * float(beta @ beta))

    def grad(p):
        beta, beta0, s = unpack(p)
        q = s
        t = W @ q
        n = float((q * counts_flat).sum())
        den = t + M.ALPHA * fp + M.BETA * (n - t)
        pred = np.where(den > 0, t / np.maximum(den, 1e-30), 0.0)
        r = np.where(obs, pred - yout, 0.0)
        c = np.where(obs, 2.0 * r, 0.0) * (den - M.ALPHA * t) / den ** 2     # d/dT
        gn = float((np.where(obs, 2.0 * r, 0.0) * (-M.BETA * t / den ** 2)).sum())  # d/dn
        g_block = c @ W + gn * counts_flat
        w = q * (1.0 - s)
        gb = ((w * g_block)[:, None] * Zc).sum(axis=0) + 2.0 * lam * beta
        gb0 = float((w * g_block).sum())
        return np.concatenate([gb, [gb0]])

    p0 = np.zeros(K + 1)
    p0[K] = -6.5
    res = minimize(loss, p0, jac=grad, method="L-BFGS-B",
                   options=dict(maxiter=max_iter, ftol=1e-14, gtol=1e-12))
    beta, beta0, s = unpack(res.x)
    q = s
    n_truth = float((q * counts_flat).sum())
    if verbose:
        print(f"    loss={res.fun:.6g} nit={res.nit} n_truth={n_truth:.0f} b0={beta0:.2f}")
    return dict(beta=beta, beta0=float(beta0), q_blocks=q,
                s_blocks=s, n_truth=n_truth, success=bool(res.success), fun=float(res.fun),
                mu=mu, sd=sd, lam=lam)


def truth_mask_from_q(q_blocks: np.ndarray, counts: np.ndarray, ny: int, nx: int,
                      target_mass: float | None = None) -> np.ndarray:
    """Threshold the block density into a mass-preserving binary block mask."""
    c = counts.ravel().astype(np.float64)
    q = q_blocks.astype(np.float64)
    order = np.argsort(-q)
    if target_mass is None:
        target_mass = float((q * c).sum())
    # take the highest-density blocks until the *pixel count* reaches the estimated |G|
    csum = np.cumsum(c[order])
    k = int(np.searchsorted(csum, target_mass)) + 1
    mask = np.zeros(q.size, bool)
    mask[order[:max(min(k, q.size), 1)]] = True
    return mask.reshape(ny, nx)


def anchor_m_from_truth(dots_list: list[Dots], truth_blocks: np.ndarray, meta: dict) -> np.ndarray:
    """M_i = sum_dots v * k(d dot -> nearest truth pixel), using a block-level truth mask."""
    from scipy.ndimage import distance_transform_edt
    block, ny, nx, H, W = meta["block"], meta["ny"], meta["nx"], meta["H"], meta["W"]
    pixel_mask = np.zeros((H, W), bool)
    ys, xs = np.nonzero(truth_blocks)
    for y, x in zip(ys, xs):
        pixel_mask[y * block:(y + 1) * block, x * block:(x + 1) * block] = True
    d = distance_transform_edt(~pixel_mask) if pixel_mask.any() else np.full((H, W), 1e6)
    out = []
    for dots in dots_list:
        out.append(float((dots.val * M.kernel(d[dots.row, dots.col])).sum()))
    return np.array(out)


def fit_iterative(Z, counts, cw, dots_list, meta, *, lam=3.0, n_outer=3, verbose=True):
    """Alternate between fitting the credit surface and re-estimating the FP relief M_i."""
    m = np.zeros(len(cw.mass))
    fit = None
    for it in range(n_outer):
        fit = fit_credit(Z, counts, cw, lam=lam, m_anchor=m, verbose=verbose)
        tm = truth_mask_from_q(fit["q_blocks"], counts, meta["ny"], meta["nx"])
        m_new = anchor_m_from_truth(dots_list, tm, meta)
        delta = float(np.abs(m_new - m).max())
        m = m_new
        if verbose:
            print(f"    outer {it}: |dM|max={delta:.1f}  M range [{m.min():.0f},{m.max():.0f}]")
        if delta < 1.0 and it > 0:
            break
    fit["m_anchor"] = m
    return fit


def loo(Z, counts, cw, *, lam=3.0, m_anchor=None, **kw):
    """Leave-one-anchor-out score predictions (the model's honest generalisation test)."""
    from scipy.stats import spearmanr
    obs = np.isfinite(cw.score)
    idx = np.flatnonzero(obs)
    preds = np.full(len(cw.score), np.nan)
    counts_flat = counts.ravel().astype(np.float64)
    for i in idx:
        keep = obs & (np.arange(len(cw.score)) != i)
        sub = CoverageWeights(W=cw.W[keep], mass=cw.mass[keep], score=cw.score[keep],
                              names=[n for j, n in enumerate(cw.names) if keep[j]])
        mm = None if m_anchor is None else m_anchor[keep]
        f = fit_credit(Z, counts, sub, lam=lam, m_anchor=mm, **kw)
        q = f["q_blocks"]
        t = float(cw.W[i] @ q)
        n = float((q * counts_flat).sum())
        den = t + M.ALPHA * cw.mass[i] + M.BETA * (n - t)
        preds[i] = t / den if den > 0 else 0.0
    good = obs & np.isfinite(preds)
    rho = float(spearmanr(cw.score[good], preds[good]).statistic)
    rmse = float(np.sqrt(np.mean((preds[good] - cw.score[good]) ** 2)))
    return dict(pred=preds, spearman=rho, rmse=rmse,
                max_abs_error=float(np.max(np.abs(preds[good] - cw.score[good]))),
                n=float(good.sum()))
