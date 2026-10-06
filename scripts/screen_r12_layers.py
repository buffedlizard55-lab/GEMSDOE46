#!/usr/bin/env python3
"""R12 layer screen: which *unused* official/USGS layers carry off-catalogue fault signal?

Everything here is measured, not assumed.  The instrument is the same one used by
the earlier sessions (off-catalogue SGMC proxy truth, catalogue exclusion, matched
emitted mass, exact DTI from ``gems46.metric``) so the numbers are comparable with
the ~0.0991-0.1033 previously recorded for the family's best fields.

New layers screened here are NOT in ``training_features.tif`` and have never been
used by any arm in this repository:
  * USGS GeoDAWN airborne gamma-ray spectrometry  K, Th, U, TC   (DOI 10.5066/P93LGLVQ)
  * USGS GeoDAWN contractor ratio / derivative grids  Th/K, U/K, U/Th, TMI up-continued 150 m
  * 2 m LiDAR-derived scarp morphology bands (12 channels)

Both products are restored from the group's public, hash-pinned mirror of the USGS
ScienceBase item 657e1d85d34e23d3533209f7; they are rank-quantised to uint8, so only
monotone/structural information is meaningful (see docs/IRREGULARITIES.md).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import emission, metric  # noqa: E402

MIRROR = ROOT / ".mirror/GEMSDOE24/data/external"
BUDGET = 37654
MIN_DIST = 3
SMOOTH = 1.85


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Monotone rank transform to [0,1] over ``mask`` (quantisation-safe)."""
    v = a[mask]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return np.zeros_like(a, dtype=np.float32)
    order = np.argsort(v, kind="stable")
    ranks = np.empty(v.size, np.float32)
    ranks[order] = np.linspace(0.0, 1.0, v.size, dtype=np.float32)
    out = np.zeros(a.shape, np.float32)
    out[mask] = ranks
    return out


def gradmag(a: np.ndarray, sigma: float, mask: np.ndarray) -> np.ndarray:
    f = np.where(mask, np.nan_to_num(a.astype(np.float32)), 0.0)
    if sigma > 0:
        f = ndimage.gaussian_filter(f, sigma)
    gy, gx = np.gradient(f)
    return np.hypot(gy, gx).astype(np.float32)


def main() -> None:
    raw = ROOT / "data/raw"
    with rasterio.open(raw / "sample_submission.tif") as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(raw / "labels.tif") as s:
        cat = (s.read(1) > 0) & fp
    with rasterio.open(raw / "training_features.tif") as s:
        rtp = s.read(2, masked=True).filled(np.nan).astype(np.float32)
        tmi = s.read(14, masked=True).filled(np.nan).astype(np.float32)
        tmi_hg = s.read(3, masked=True).filled(np.nan).astype(np.float32)
        grav = s.read(13, masked=True).filled(np.nan).astype(np.float32)
    with rasterio.open(ROOT / "data/external/sgmc_faults_100m_u8.tif") as s:
        sgmc = s.read(1) > 0

    valid = fp & np.isfinite(rtp)
    exclusion = ndimage.binary_dilation(cat, iterations=2)
    domain = fp & ~exclusion
    truth = sgmc & domain
    print(f"domain {int(domain.sum())}  off-catalogue proxy truth {int(truth.sum())}", flush=True)

    rad = {}
    with rasterio.open(MIRROR / "geodawn_rad_u8.tif") as s:
        for i, n in enumerate(["K", "Th", "U", "TC"], 1):
            rad[n] = s.read(i).astype(np.float32)
    ext = {}
    with rasterio.open(MIRROR / "geodawn_extensions_u8.tif") as s:
        for i, n in enumerate(["ThK", "UK", "UTh", "TMI_up150"], 1):
            ext[n] = s.read(i).astype(np.float32)
    lid = {}
    names = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max",
             "downface_max", "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
    with rasterio.open(MIRROR / "lidar_scarp_features_u8.tif") as s:
        for i, n in enumerate(names, 1):
            lid[n] = s.read(i).astype(np.float32)
    lidar_ok = (lid["valid"] > 0) & fp

    fields: dict[str, np.ndarray] = {}
    # --- references already known to be strong on this instrument -------------
    fields["REF_rtp_grad_s1.5"] = gradmag(rtp, 1.5, valid)
    fields["REF_tmi_hg_band3"] = np.nan_to_num(tmi_hg, nan=0.0)
    fields["REF_grav_grad_s2"] = gradmag(grav, 2.0, valid)
    # --- new: gamma-ray spectrometry ------------------------------------------
    for n, a in rad.items():
        fields[f"NEW_rad_{n}_grad_s2"] = gradmag(a, 2.0, valid)
    for n, a in ext.items():
        if n == "TMI_up150":
            continue
        fields[f"NEW_ext_{n}_grad_s2"] = gradmag(a, 2.0, valid)
    # --- new: shallow magnetic source by upward continuation ------------------
    up = ext["TMI_up150"]
    up_r = np.where(valid, up, 0.0)
    fields["NEW_up150_grad_s2"] = gradmag(up_r, 2.0, valid)
    # rank-domain residual between the raw TMI and its 150 m up-continuation:
    # high values = shallow magnetic source (deep regional field removed).
    tmi_r = rank01(np.nan_to_num(tmi), valid)
    up_rank = rank01(up_r, valid)
    shallow = ndimage.gaussian_filter(tmi_r - up_rank, 1.0)
    fields["NEW_shallow_src_abs"] = np.abs(shallow).astype(np.float32)
    fields["NEW_shallow_src_grad"] = gradmag(shallow, 1.5, valid)
    # --- new: LiDAR scarp morphology ------------------------------------------
    for n in ["ex_max", "step_max", "lapneg_max", "lappos_max", "downface_max",
              "upface_max", "cross_max", "coh100"]:
        fields[f"NEW_lidar_{n}"] = np.where(lidar_ok, lid[n], 0.0).astype(np.float32)
    # --- composites: independent-physics concordance (geometric mean of ranks) -
    mag = rank01(fields["REF_rtp_grad_s1.5"], domain)
    radc = rank01(fields["NEW_rad_TC_grad_s2"], domain)
    thk = rank01(fields["NEW_ext_ThK_grad_s2"], domain)
    lidc = rank01(np.where(lidar_ok, lid["step_max"], 0.0), domain & lidar_ok)
    fields["CMP_mag_x_radTC"] = np.sqrt(np.maximum(mag, 0) * np.maximum(radc, 0))
    fields["CMP_mag_x_ThK"] = np.sqrt(np.maximum(mag, 0) * np.maximum(thk, 0))
    fields["CMP_mag_x_lidar"] = np.sqrt(np.maximum(mag, 0) * np.maximum(lidc, 0))
    fields["CMP_mag_x_rad_x_lidar"] = (np.maximum(mag, 0) * np.maximum(radc, 0)
                                       * np.maximum(lidc, 0)) ** (1.0 / 3.0)
    fields["CMP_shallow_x_ThK"] = np.sqrt(np.maximum(rank01(fields["NEW_shallow_src_abs"], domain), 0)
                                          * np.maximum(thk, 0))

    rows = []
    for name, f in fields.items():
        mask, _ = emission.greedy_emit(f, domain, BUDGET, min_dist=MIN_DIST, smooth_px=SMOOTH)
        c = metric.components_binary(mask, truth, valid=domain)
        # precision at the kernel scale: emitted dots within 300 m of a proxy trace
        d_truth = ndimage.distance_transform_edt(~truth)
        hit = float((metric.kernel(d_truth[mask]) > 0).sum())
        rows.append(dict(field=name, emitted=int(mask.sum()), dti=round(c.dti, 5),
                         tp=round(c.tp, 1), precision_300m=round(hit / max(mask.sum(), 1), 4),
                         mean_k=round(float(metric.kernel(d_truth[mask]).mean()), 4)))
        print(f"{name:32s} DTI {c.dti:.5f}  precision@300m {rows[-1]['precision_300m']:.4f}"
              f"  mean_k {rows[-1]['mean_k']:.4f}", flush=True)

    rows.sort(key=lambda r: -r["dti"])
    out = ROOT / "evidence/r12_layer_screen.json"
    out.write_text(json.dumps(dict(instrument="off-catalogue SGMC proxy, matched mass 37,654, "
                                  "min_dist 3, smooth 1.85, catalogue exclusion 2 iterations",
                                   budget=BUDGET, rows=rows), indent=2) + "\n")
    print("\nranked:", *[f"{r['field']} {r['dti']:.4f}" for r in rows[:8]], sep="\n  ")


if __name__ == "__main__":
    main()
