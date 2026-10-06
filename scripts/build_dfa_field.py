#!/usr/bin/env python3
"""Compute the H46-1 DFA scaling-exponent-break fields for the magnetic and gravity bands.

Outputs (data/derived/):
  dfa_<band>_<variant>.npz   per-band |z| (exponent break) and |grad z| (regime boundary)
  dfa_groups.npz             magnetic / gravity group means, their corroborated minimum, and the
                             gradient/curvature baselines used for the distinctness test
  dfa_stats.json             per-band exponent statistics (median alpha, spread) for the receipt

Everything is derived from the official 19-band GeoTIFF and the official template footprint; no
external data and no per-pixel tuning are used.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import detector as D  # noqa: E402
from gems46 import grid as G  # noqa: E402

DATA = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
WINDOW, STRIDE = 128, 8
SCALES = (8, 16, 32, 64)
RESID_SIGMA = 20.0   # px; high-pass scale for the 'resid' variant (2 km)


def highpass(band: np.ndarray, sigma: float, valid: np.ndarray) -> np.ndarray:
    filled = np.where(np.isfinite(band), band, 0.0).astype(np.float32)
    num = ndimage.gaussian_filter(filled, sigma, mode="nearest")
    den = ndimage.gaussian_filter(valid.astype(np.float32), sigma, mode="nearest")
    blur = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    out = filled - blur
    out[~valid] = np.nan
    return out.astype(np.float32)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    feat = DATA / "training_features.tif"
    tmpl = DATA / "sample_submission.tif"
    fp = G.footprint(tmpl, feat)
    print(f"footprint: {int(fp.sum())} px of {fp.size}")

    variants = [(n, "raw") for n in list(D.MAGNETIC) + list(D.GRAVITY)] + \
               [(n, "resid") for n in ("tmi", "rtp", "iso_grav_anom", "mag_anom")]
    per_band = {}
    sums = {"mag_abs": None, "mag_bnd": None, "grav_abs": None, "grav_bnd": None}
    counts = {k: None for k in sums}
    mins = {"mag_abs": None, "mag_bnd": None, "grav_abs": None, "grav_bnd": None}
    stats = {}
    with rasterio.open(feat) as src:
        nd = src.nodatavals
        for name, variant in variants:
            t0 = time.time()
            raw = src.read(D.BAND_INDEX[name]).astype(np.float32)
            bad = ~np.isfinite(raw) | (raw <= np.float32(nd[D.BAND_INDEX[name] - 1]) *
                                       np.float32(0.999999))
            raw[bad] = np.nan
            valid = fp & np.isfinite(raw)
            band = raw if variant == "raw" else highpass(raw, RESID_SIGMA, valid)
            f = D.dfa_break_field(band, valid, window=WINDOW, stride=STRIDE, scales=SCALES)
            absz = f["absz"]
            bnd = f["boundary"]
            np.savez_compressed(OUT / f"dfa_{name}_{variant}.npz",
                                absz=absz.astype(np.float32), boundary=bnd.astype(np.float32),
                                valid=valid)
            key = f"{name}_{variant}"
            per_band[key] = key
            coarse = f["coarse_row"]
            with np.errstate(invalid="ignore"):
                stats[key] = dict(
                    alpha_median_row=float(np.nanmedian(coarse)) if np.isfinite(coarse).any() else None,
                    alpha_iqr_row=float(np.nanpercentile(coarse, 75) - np.nanpercentile(coarse, 25))
                    if np.isfinite(coarse).any() else None,
                    absz_median=float(np.nanmedian(absz)) if np.isfinite(absz).any() else None,
                    absz_p99=float(np.nanpercentile(absz, 99)) if np.isfinite(absz).any() else None,
                    boundary_p99=float(np.nanpercentile(bnd, 99)) if np.isfinite(bnd).any() else None,
                    valid_px=int(valid.sum()), seconds=round(time.time() - t0, 1))
            print(f"  {key:24s} alpha_med={stats[key]['alpha_median_row']} "
                  f"({time.time() - t0:.1f}s)")
            if variant != "raw":
                continue
            group = "mag" if name in D.MAGNETIC else "grav"
            for tag, arr in (("abs", absz), ("bnd", bnd)):
                k_sum, k_cnt, k_min = f"{group}_{tag}", f"{group}_{tag}_cnt", f"{group}_{tag}"
                a = np.nan_to_num(arr, nan=0.0).astype(np.float32)
                fin = np.isfinite(arr)
                sums[k_sum] = a if sums[k_sum] is None else sums[k_sum] + a
                counts[group + "_" + tag] = fin.astype(np.int16) if counts[group + "_" + tag] is None \
                    else counts[group + "_" + tag] + fin.astype(np.int16)
                cur = np.where(fin, arr, np.inf).astype(np.float32)
                mins[k_min] = cur if mins[k_min] is None else np.minimum(mins[k_min], cur)

    groups = {}
    for group in ("mag", "grav"):
        for tag in ("abs", "bnd"):
            s = sums[f"{group}_{tag}"]
            c = counts[f"{group}_{tag}"]
            mean = np.where(c > 0, s / np.maximum(c, 1), np.nan).astype(np.float32)
            groups[f"{group}_{tag}"] = mean
    for tag in ("abs", "bnd"):
        m, g = groups[f"mag_{tag}"], groups[f"grav_{tag}"]
        groups[f"both_{tag}"] = np.fmin(m, g).astype(np.float32)   # corroborated by both physics
        groups[f"any_{tag}"] = np.fmax(m, g).astype(np.float32)
    np.savez_compressed(OUT / "dfa_groups.npz", **groups)

    # ---- gradient / curvature baselines from the same official bands (distinctness comparison)
    bases = {}
    with rasterio.open(feat) as src:
        for name, tf in (("tmi", "grad"), ("iso_grav_anom", "grad"), ("det_elev", "grad"),
                         ("det_elev", "lap"), ("tc", "raw"), ("iso_grav_anom_hg", "raw"),
                         ("tmi_hg", "raw")):
            a = src.read(D.BAND_INDEX[name]).astype(np.float32)
            ndb = src.nodatavals[D.BAND_INDEX[name] - 1]
            a = np.where(a <= np.float32(ndb) * np.float32(0.999999), np.nan, a)
            v = fp & np.isfinite(a)
            filled = np.where(v, np.nan_to_num(a), 0.0).astype(np.float32)
            if tf == "grad":
                gy, gx = np.gradient(ndimage.gaussian_filter(filled, 3.0, mode="nearest"))
                b = np.hypot(gy, gx)
            elif tf == "lap":
                b = np.abs(ndimage.laplace(ndimage.gaussian_filter(filled, 3.0, mode="nearest")))
            else:
                b = np.abs(filled)
            b = np.where(v, b, np.nan).astype(np.float32)
            bases[f"{name}_{tf}"] = b
            print(f"  baseline {name}_{tf}: p99={np.nanpercentile(b, 99):.4g}")
    np.savez_compressed(OUT / "baselines.npz", **bases)
    (OUT / "dfa_stats.json").write_text(json.dumps(dict(
        window=WINDOW, stride=STRIDE, scales=list(SCALES), residual_sigma_px=RESID_SIGMA,
        footprint_px=int(fp.sum()), bands=stats,
        note="alpha = local DFA exponent (log-log slope of F(n) over the listed scales); absz = "
             "|robust z| of alpha against a 31-window (24.8 km) median background; boundary = "
             "|grad absz|."), indent=1) + "\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
