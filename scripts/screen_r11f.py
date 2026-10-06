#!/usr/bin/env python3
"""R11F screening: which *new* evidence channels actually separate hidden-fault proxies?

Screening harness, not a validation gate.  For every channel in the bank it answers one question:
does a higher value sit closer to a fault that is **absent from the official catalogue**?  Two
proxies are used and reported separately, never pooled:

* ``off`` = SGMC fault traces outside the official catalogue (the repository's weak instrument:
  state-map scale, not 100 m truth, and IR-46-04 already flags that this population is not the
  scored one);
* ``cat`` = the official catalogue itself (a *control*: a channel that only reproduces the catalogue
  adds nothing, because the competition already ships the catalogue).

The scored domain is also split into selection blocks and calibration blocks (even/odd 4x4 block
index) so a channel chosen here can be confirmed on blocks it never saw.

Memory discipline: channels are scored and discarded one at a time (a 19-band 100 m float32 stack is
~1 GB, and this sandbox has 4 GB).

Output: ``evidence/r11f-screen.json`` -- a superset of the earlier receipt's schema.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import grid  # noqa: E402

RAW = ROOT / "data/raw"
EXT = ROOT / ".mirror/GEMSDOE24/data/external"
GUARD = 1          # px of catalogue dilation excluded from the off-catalogue proxy
SEED = 20261006
NOD = np.float32(-1e37)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rank_norm(a: np.ndarray, support: np.ndarray) -> np.ndarray:
    out = np.zeros(a.shape, np.float32)
    v = a[support]
    if v.size == 0:
        return out
    order = np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(np.float32)
    out[support] = order / max(v.size - 1, 1)
    return out


def grad_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    gx = ndimage.gaussian_filter(a, sigma, order=(0, 1), mode="nearest")
    gy = ndimage.gaussian_filter(a, sigma, order=(1, 0), mode="nearest")
    return np.hypot(gx, gy)


def lap_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    return np.abs(ndimage.gaussian_laplace(a, sigma, mode="nearest"))


def auc(score: np.ndarray, pos: np.ndarray, neg: np.ndarray) -> tuple[float, int, int]:
    """Rank AUC (Mann-Whitney, mid-ranks).  Returns (auc, n_pos, n_neg)."""
    p, n = int(pos.sum()), int(neg.sum())
    if p < 20 or n < 20:
        return float("nan"), p, n
    s = np.concatenate([score[pos], score[neg]])
    r = np.argsort(np.argsort(s, kind="stable"), kind="stable").astype(np.float64) + 1.0
    return float((r[:p].sum() - p * (p + 1) / 2) / (p * n)), p, n


def main() -> int:
    fp = grid.footprint(RAW / "sample_submission.tif", RAW / "training_features.tif")
    with rasterio.open(RAW / "labels.tif") as s:
        cat = (s.read(1) > 0) & fp
    sgmc = rasterio.open(EXT / "derived_sgmc_faults_100m_u8.tif").read(1) > 0
    off = sgmc & fp & ~ndimage.binary_dilation(cat, np.ones((3, 3), bool), iterations=GUARD)

    h, w = fp.shape
    blocks = (np.arange(h) // (h // 4 + 1))[:, None] * 4 + (np.arange(w) // (w // 4 + 1))[None, :]
    sel = fp & ((blocks % 2) == 0)
    cal = fp & ~sel

    rng = np.random.default_rng(SEED)
    bg = fp & (rng.random(fp.shape) < 0.02) & ~cat & ~sgmc
    bg_sel, bg_cal = bg & sel, bg & cal
    print(f"support {int(fp.sum()):,}  catalogue {int(cat.sum()):,}  off-catalogue SGMC "
          f"{int(off.sum()):,}  background draw {int(bg.sum()):,}", flush=True)

    feats = rasterio.open(RAW / "training_features.tif")
    names = ["mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
             "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg",
             "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf", "ieq_n100a15", "cond_surf",
             "iso_grav_anom_hg", "det_elev_slope"]
    rad = rasterio.open(EXT / "geodawn_rad_u8.tif")
    ex = rasterio.open(EXT / "geodawn_extensions_u8.tif")
    lid = rasterio.open(EXT / "lidar_scarp_features_u8.tif")

    rows: list[dict] = []

    def score(name: str, family: str, arr: np.ndarray, support: np.ndarray, note: str = ""):
        q = rank_norm(arr.astype(np.float32), support & fp)
        a_off, n_off, n_neg = auc(q, off, bg)
        a_cat, n_cat, _ = auc(q, cat, bg)
        a_off_sel, _, _ = auc(q, off & sel, bg_sel)
        a_off_cal, _, _ = auc(q, off & cal, bg_cal)
        rows.append(dict(channel=name, family=family, note=note, auc_off=a_off, auc_cat=a_cat,
                         auc_off_sel=a_off_sel, auc_off_cal=a_off_cal, n_off=n_off,
                         n_cat=n_cat, n_background=n_neg, support_px=int((support & fp).sum())))
        print(f"{name:26s} off {a_off:.3f} (sel {a_off_sel:.3f} cal {a_off_cal:.3f}) "
              f"cat {a_cat:.3f}  n_off {n_off}", flush=True)

    # ---- radiometric compositional contrast: K, Th, U are absent from the official 19 bands -----
    radch = {n: rad.read(i + 1).astype(np.float32) for i, n in enumerate(["K", "Th", "U", "TC"])}
    rs = radch["K"] > 0
    for n, a in radch.items():
        score(f"rad_{n}", "radiometric", a, rs, "GeoDAWN contractor grid (u8, DOI 10.5066/P93LGLVQ)")
        score(f"rad_{n}_grad2", "radiometric", grad_mag(a, 2.0), rs, "|grad| sigma=2 px")
        del a
    k, th, u = radch["K"] + 1e-6, radch["Th"] + 1e-6, radch["U"] + 1e-6
    score("ratio_ThK", "radiometric", th / k, rs, "Th/K recomputed from the decoded channels")
    score("ratio_UK", "radiometric", u / k, rs, "U/K recomputed")
    score("ratio_UTh", "radiometric", u / th, rs, "U/Th recomputed")
    score("ratio_ThK_grad2", "radiometric", grad_mag(th / k, 2.0), rs, "|grad Th/K| sigma=2")
    score("ratio_ThK_lap2", "radiometric", lap_mag(th / k, 2.0), rs, "|LoG Th/K| sigma=2")
    del radch, th, u
    extch = {n: ex.read(i + 1).astype(np.float32) for i, n in enumerate(["ThK", "UK", "UTh", "TMI_up150"])}
    es = extch["ThK"] > 0
    for n, a in extch.items():
        score(f"ext_{n}", "radiometric", a, es, "GeoDAWN extension grid (contractor ratio / up150)")
        del a
    score("ext_ThK_grad2", "radiometric", grad_mag(extch["ThK"], 2.0), es, "|grad contractor Th/K| sigma=2")
    score("ext_UK_grad2", "radiometric", grad_mag(extch["UK"], 2.0), es, "|grad contractor U/K| sigma=2")
    del extch

    # ---- 1 m lidar terrain descriptors (2 m statistics aggregated to 100 m) ---------------------
    lidn = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
            "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
    L = {n: lid.read(i + 1).astype(np.float32) for i, n in enumerate(lidn)}
    ls = L["valid"] > 0
    for n in lidn[:-1]:
        score(f"lidar_{n}", "lidar-raw", L[n], ls, "12-channel 1 m lidar descriptor stack (2 m->100 m)")
    coh = L["coh100"] / 255.0
    crest = np.maximum(L["lapneg_max"], L["lappos_max"])
    score("lidar_scarp_coh", "lidar-combo", crest * coh, ls, "max(crest|base convexity) x coherence")
    score("lidar_step_coh", "lidar-combo", L["step_max"] * coh, ls, "band-passed step x coherence")
    score("lidar_step_grad2", "lidar-combo", grad_mag(L["step_max"], 2.0), ls, "|grad step_max| sigma=2")
    del L, crest, coh

    # ---- official bands, the way prior arms used them and the way they did not ------------------
    for want in ["rtp", "iso_grav_anom", "det_elev", "det_elev_slope", "cond_surf"]:
        a = feats.read(names.index(want) + 1).astype(np.float32)
        v = fp & np.isfinite(a) & (a > NOD)
        score(f"band_{want}", "official", a, v, f"official band {names.index(want)+1}")
        score(f"band_{want}_grad2", "official-grad", grad_mag(a, 2.0), v, "|grad| sigma=2 px")
        del a, v

    # ---- the preregistered local DFA regime-break field ----------------------------------------
    from run_r11 import local_dfa_break  # the frozen R11F implementation
    a = feats.read(names.index("rtp") + 1).astype(np.float32)
    v = fp & np.isfinite(a) & (a > NOD)
    score("dfa_break_rtp", "dfa", local_dfa_break(a, v), v,
          "local DFA regime-break (window 128 px, scales 4-32 px), RTP")
    del a, v

    best = sorted(rows, key=lambda r: -(r["auc_off"] if np.isfinite(r["auc_off"]) else 0))
    out = dict(
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        purpose="screen fixed evidence channels by their ability to rank off-catalogue SGMC fault "
                "pixels above a background sample; screening only, not a validation instrument",
        seed=SEED, guard_px=GUARD,
        counts=dict(catalogue_px=int(cat.sum()), off_catalogue_sgmc_px=int(off.sum()),
                    background_sample_px=int(bg.sum())),
        note="AUC is a ranking statistic on sampled pixels. It cannot establish that any channel "
             "detects faults, and it is computed on the same proxy population that "
             "registry/irregularities.json IR-46-04 and the R10 review already flag as weak.",
        inputs={p.name: sha256(p) for p in [RAW / "labels.tif", RAW / "sample_submission.tif",
                                            EXT / "derived_sgmc_faults_100m_u8.tif",
                                            EXT / "geodawn_rad_u8.tif",
                                            EXT / "geodawn_extensions_u8.tif",
                                            EXT / "lidar_scarp_features_u8.tif"]},
        channels=rows)
    (ROOT / "evidence/r11f-screen.json").write_text(json.dumps(out, indent=1) + "\n")
    print("\nTop 12 by off-catalogue AUC:")
    for r in best[:12]:
        print(f"  {r['channel']:26s} {r['auc_off']:.3f}  (catalogue {r['auc_cat']:.3f})")
    print(f"\n{len(rows)} channels screened -> evidence/r11f-screen.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
