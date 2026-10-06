#!/usr/bin/env python3
"""Build the credit-direction raster r(x) = sum_k beta_k * z_k(x) (z = centred rank in [-1,1]).

beta comes from the leave-one-anchor-out-validated ridge fit of the reported leaderboard
scores on the coverage-weighted feature means of 43 scored anchors
(scripts/build_credit_model.py, LOO Spearman +0.63).  r is the field whose kernel-smoothed
average over an emission's dots predicts the metric the way the leaderboard behaved.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/user/GEMSDOE46/src")
from gems46 import features as F  # noqa: E402

DATA = Path("/tmp/gems46/data")


def main() -> int:
    z = np.load(DATA / "credit_model.npz", allow_pickle=True)
    beta = z["beta_rank"].astype(np.float32)
    names = [str(s) for s in z["names"]]
    footprint = z["footprint"]
    print(f"beta: {int((beta != 0).sum())} active features of {len(beta)}")

    lab, fp, cat, raw = F.load_grid(DATA / "features_national.tif",
                                    "/home/user/GEMSDOE46/data/raw/grid/labels.tif")
    H, W = fp.shape
    r = np.zeros((H, W), np.float32)
    t0 = time.time()
    seen = []
    for name, arr in F.iter_features(raw, fp, cat):
        k = names.index(name)
        if beta[k] == 0:
            continue
        v = arr[fp]
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, np.float32)
        ranks[order] = np.linspace(-1.0, 1.0, v.size, dtype=np.float32)
        g = np.zeros((H, W), np.float32)
        g[fp] = ranks
        r += beta[k] * g
        seen.append(name)
        del v, order, ranks, g
        print(f"  {name:20s} {time.time()-t0:6.1f}s  r range [{r.min():.3f},{r.max():.3f}]")
    np.save(DATA / "credit_r.npy", r)
    print(f"saved r ({time.time()-t0:.0f}s), {len(seen)} layers used, "
          f"r mean {r[fp].mean():.4f} sd {r[fp].std():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
