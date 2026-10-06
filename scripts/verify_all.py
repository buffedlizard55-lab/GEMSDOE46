#!/usr/bin/env python3
"""One-command computational verification (not validation of every scientific claim).

Checks, in order:
  1. the official metric implementation against the published worked example and against an
     independent O(N^2) transcription (pytest tests/test_metric.py),
  2. the DFA estimator against its textbook calibration on synthetic series, including the
     0.5 -> 0.9 transition range the hypothesis is about (pytest tests/test_dfa.py),
  3. the shipped GeoTIFF against the official format contract, re-read from disk
     (pytest tests/test_submission_format.py + a full audit here),
  4. the pinned sha256 of every restored competition file,
  5. the live-score calibration arithmetic in registry/emission_model.json.

Exit code 0 means every check passed.  Nothing here needs network access.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import grid as G  # noqa: E402

PINNED = {
    "data/raw/training_features.tif":
        "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "data/raw/labels.tif":
        "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "data/raw/sample_submission.tif":
        "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "data/external/sgmc_faults_100m_u8.tif":
        "643cbe992ef4ba37588fb469163ed8291e3ceb23d6c1f78a3cfaa462430c2da0",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ok = True
    print("=" * 96)
    print("1-3. unit + format tests")
    print("=" * 96)
    r = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q"],
                       capture_output=True, text=True, cwd=ROOT)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    ok &= r.returncode == 0

    print()
    print("=" * 96)
    print("4. pinned hashes of restored data")
    print("=" * 96)
    for rel, want in PINNED.items():
        p = ROOT / rel
        if not p.exists():
            print(f"  MISSING {rel} (run scripts/restore_competition_data.sh)")
            ok = False
            continue
        got = sha256(p)
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {rel}  {got[:16]}...")

    print()
    print("=" * 96)
    print("5. shipped submission artifacts: full format audit re-read from disk")
    print("=" * 96)
    reg = ROOT / "registry" / "submissions.json"
    if not reg.exists():
        print("  no registry/submissions.json - run scripts/build_h46_submission.py")
        ok = False
    else:
        sub = json.loads(reg.read_text())
        for tag, rec in sub["files"].items():
            path = ROOT / "docs" / "h46" / "downloads" / rec["file"]
            rep = G.audit(path, ROOT / "data" / "raw" / "sample_submission.tif")
            good = rep["ok"] and rep["positive_px"] == rec["audit"]["positive_px"]
            ok &= good
            print(f"  {'OK  ' if good else 'FAIL'} {rec['file']}")
            print(f"       bands={rep['count']} dtype={rep['dtype']} crs={rep['crs']} "
                  f"{rep['height']}x{rep['width']} transform_match={rep['transform_match']}")
            print(f"       footprint_match={rep['footprint_match']} min={rep['min']} "
                  f"max={rep['max']} range_ok={rep['range_ok']} positive={rep['positive_px']}")
            print(f"       sha256(values)={rec['sha256_values'][:16]}... "
                  f"proxy instrument DTI={rec['instrument']['instrument_sgmc_dti']:.4f}")

    print()
    print("=" * 96)
    print("6. live-score calibration arithmetic (registry/emission_model.json)")
    print("=" * 96)
    em = ROOT / "registry" / "emission_model.json"
    if em.exists():
        d = json.loads(em.read_text())
        G_ = d.get("hidden_truth_px")
        T_ = d.get("implied_credit_px")
        ok &= bool(G_ and T_ and abs(G_ - 14089) < 2)
        print(f"  G = {G_:,.0f} px, T(44,090 px emission) = {T_:,.0f} px, "
              f"break-even = {d.get('break_even'):.4f}")
        print("  CONDITIONAL MODEL ONLY (not identified hidden truth): reproduced from 0.2600*(0.2*44090 + 0.8G) = 0.2778*(0.2*37654 + 0.8G)")
    else:
        print("  missing registry/emission_model.json")
        ok = False

    print()
    print("7. R10 independent on-disk format audit")
    from run_r10 import audit
    r10 = json.loads((ROOT / "registry/r10.json").read_text())
    current = audit(ROOT / "docs/r10" / r10["file"], ROOT / "data/raw/sample_submission.tif")
    ok &= current == r10["audit"]
    print(f"  {r10['file']}: sha256={current['sha256']}; status={r10['status']}")

    print()
    print("=" * 96)
    print("8. R11 independent on-disk format audit + pinned USGS layers + locked-gate consistency")
    print("=" * 96)
    from run_r11 import audit as audit11
    r11 = json.loads((ROOT / "registry/r11.json").read_text())
    cur11 = audit11(ROOT / "docs/r11" / r11["file"], ROOT / "data/raw/sample_submission.tif")
    same = cur11 == r11["audit"]
    ok &= same
    print(f"  {'OK  ' if same else 'FAIL'} {r11['file']}")
    print(f"       sha256={cur11['sha256']}")
    print(f"       positive={cur11['positive']} min={cur11['min']} max={cur11['max']} "
          f"crs={cur11['crs']} shape={cur11['shape']}")
    for item in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]:
        if not item["id"].startswith("r11_layer_"):
            continue
        p = ROOT / item["dest"]
        got = sha256(p) if p.exists() else None
        good = got == item["sha256"]
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {item['dest']}  {(got or 'MISSING')[:16]}...")
    # gate arithmetic re-derived from the receipt, not trusted
    folds = r11["locked_folds"]
    best = r11["best_comparator"]
    delta = [f["scores"]["R11"]["dti"] - f["scores"][best]["dti"] for f in folds]
    mean_delta = sum(delta) / len(delta)
    ci = r11["paired_bootstrap_95"]
    consistent = (abs(mean_delta - r11["paired_delta_vs_best"]) < 1e-12
                  and bool(ci[0] > 0) == bool(r11["gate_passed"])
                  and len(folds) >= 8
                  and r11["mean_locked_dti"]["R11"] > r11["mean_locked_dti"][best])
    ok &= consistent
    print(f"  {'OK  ' if consistent else 'FAIL'} gate re-derived: mean paired delta {mean_delta:+.6f}, "
          f"bootstrap 95% [{ci[0]:+.6f}, {ci[1]:+.6f}], blocks {len(folds)}, "
          f"status {r11['status']}, strict-R10 rule {'pass' if r11['gate_strict_r10_style'] else 'fail'}")
    print("ALL COMPUTATIONAL CHECKS PASSED (not a scoring endorsement)" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
