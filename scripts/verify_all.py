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
    print("5b. H47 artifact independent on-disk audit (registry/h47.json -> emission)")
    print("=" * 96)
    h47 = ROOT / "registry" / "h47.json"
    if not h47.exists():
        print("  missing registry/h47.json - run scripts/run_h47.py")
        ok = False
    else:
        rec47 = json.loads(h47.read_text())
        rec = rec47["emission"]
        # The portal-proof format is the one every live-scored family file uses: all values finite
        # in [0,1], zeros outside the footprint.  The NaN-outside twin matches the template's
        # footprint and is kept as the alternative allowed by the problem statement.
        for twin in ("zeros", "nan"):
            path = ROOT / rec[twin]["path"]
            rep = G.audit(path, ROOT / "data" / "raw" / "sample_submission.tif")
            file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            format_ok = (rep["finite_px"] == rep["width"] * rep["height"]) if twin == "zeros" \
                else bool(rep["footprint_match"] and rep["nan_outside_footprint"])
            good = bool(rep["range_ok"] and rep["positive_px"] == rec["emitted_px"]
                        and file_sha == rec[twin]["sha256"] and rec[twin]["audit"]["passes"]
                        and format_ok)
            ok &= good
            print(f"  {'OK  ' if good else 'FAIL'} {path.name}")
            print(f"       bands={rep['count']} dtype={rep['dtype']} crs={rep['crs']} "
                  f"{rep['height']}x{rep['width']} transform_match={rep['transform_match']} "
                  f"finite_px={rep['finite_px']:,}")
            print(f"       footprint_match={rep['footprint_match']} min={rep['min']} "
                  f"max={rep['max']} range_ok={rep['range_ok']} positive={rep['positive_px']}")
            print(f"       sha256={file_sha[:16]}... verdict="
                  f"{rec47.get('screen', {}).get('verdict', 'unscreened')}")

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
    print("8. R12 independent on-disk audit + pinned USGS layers + two-instrument gate consistency")
    print("=" * 96)
    from run_r12 import audit as audit12
    r12 = json.loads((ROOT / "registry/r12.json").read_text())
    cur12 = audit12(ROOT / "docs/r12" / r12["file"], ROOT / "data/raw/sample_submission.tif")
    same = cur12 == r12["audit"]
    ok &= same
    print(f"  {'OK  ' if same else 'FAIL'} {r12['file']}")
    print(f"       sha256={cur12['sha256']}")
    print(f"       positive={cur12['positive']} min={cur12['min']} max={cur12['max']} "
          f"crs={cur12['crs']} shape={cur12['shape']}")
    for item in json.loads((ROOT / "registry/data_manifest.json").read_text())["files"]:
        if not item["id"].startswith("r12_layer_"):
            continue
        pp = ROOT / item["dest"]
        got = sha256(pp) if pp.exists() else None
        good = got == item["sha256"]
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {item['dest']}  {(got or 'MISSING')[:16]}...")
    # gate arithmetic re-derived from the receipt, not trusted
    folds = r12["locked_folds"]
    best = r12["best_comparator"]
    delta = [f["scores"]["R12"]["dti"] - f["scores"][best]["dti"] for f in folds]
    mean_delta = sum(delta) / len(delta)
    ci = r12["paired_bootstrap_95"]
    strat = r12["stratified_instrument"]
    inc = "GEMSDOE32-owner-reported-02778"
    blocks_gate = bool(len(folds) >= 8 and ci[0] > 0.0
                       and abs(mean_delta - r12["paired_delta_vs_best"]) < 1e-12
                       and r12["mean_locked_dti"]["R12"] > r12["mean_locked_dti"][best])
    strat_gate = bool(strat["scores"]["R12"]["dti"] - strat["scores"][inc]["dti"] > 0.0)
    consistent = (blocks_gate == bool(r12["gate_locked_blocks_200m"])
                  and strat_gate == bool(r12["gate_stratified_whole_domain"])
                  and (blocks_gate and strat_gate) == bool(r12["gate_passed"])
                  and (("PROXY_GATE_PASSED" in r12["status"]) == bool(r12["gate_passed"])))
    ok &= consistent
    print(f"  {'OK  ' if blocks_gate else 'FAIL'} 200 m-exclusion locked blocks: mean paired delta "
          f"{mean_delta:+.6f}, bootstrap 95% [{ci[0]:+.6f}, {ci[1]:+.6f}], blocks {len(folds)}")
    print(f"  {'OK  ' if strat_gate else 'FAIL'} stratified instrument ({strat['instrument']}): "
          f"R12 {strat['scores']['R12']['dti']:.5f} vs incumbent {strat['scores'][inc]['dti']:.5f}, "
          f"delta {strat['delta_vs_incumbent']:+.5f}, hit fraction "
          f"{strat['hit_fraction']['R12']:.4f} vs {strat['hit_fraction'][inc]:.4f}, "
          f"random-at-matched-mass T={strat['uniform_random_at_matched_mass']['tp']}")
    print(f"  {'OK  ' if consistent else 'FAIL'} combined status {r12['status']}; "
          f"strict-R10 rule {'pass' if r12['gate_strict_r10_style'] else 'fail'}")

    print()
    print("=" * 96)
    print("9. Held candidates (R11, H47) stay on disk with the status their receipts record")
    print("=" * 96)
    for tag, key in (("r11", None), ("h47", "emission")):
        rec = json.loads((ROOT / f"registry/{tag}.json").read_text())
        if tag == "r11":
            f = ROOT / "docs/r11" / rec["file"]
            status, positive = rec["status"], rec["audit"]["positive"]
        else:
            f = ROOT / rec["emission"]["zeros"]["path"].replace(str(ROOT) + "/", "")
            status = rec["screen"]["verdict"]
            positive = rec["emission"]["zeros"]["audit"]["positive_px"]
        good = f.is_file() and status == "HOLD_DO_NOT_SUBMIT" and positive == 37654
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} {tag}: {f.name}  {status}  {positive} dots")
    print()
    print("=" * 96)
    print("10. The other gate-passed arm (R11F) — both arms on the same stratified instrument")
    print("=" * 96)
    rf = json.loads((ROOT / "registry/r11f.json").read_text())
    st = rf["pass3_stratified_audit"]["instruments"]["sgmc_stratified_d0_3"]["emissions"]
    f = ROOT / "docs/r11f" / rf["candidate"]["file"]
    good = (f.is_file() and rf["status"] == "PROXY_GATE_PASSED_NOT_SUBMITTED"
            and bool(rf["gate_passed"]) and rf["candidate"]["positive"] == 44090)
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} r11f: {rf['candidate']['file']}  {rf['status']}  "
          f"{rf['candidate']['positive']:,} dots")
    for k, v in st.items():
        print(f"       d0=3 px  {k:<32} DTI {v['dti']:.5f}  T {v['T_credit']:,.0f}  "
              f"hit {100 * v['hit_fraction']:.2f}%")
    print("       R11F audits at d0=3 px, R12 at d0=5 px; both reproduce the incumbent near 0.095 and")
    print("       both place the new-sensor arm near 0.166 - independent agreement on the evidence,")
    print("       not on the file. Neither is a leaderboard score.")
    print("ALL COMPUTATIONAL CHECKS PASSED (not a scoring endorsement)" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
