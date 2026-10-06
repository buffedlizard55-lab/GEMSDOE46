#!/usr/bin/env python3
"""Fetch the public artifacts this project measures.

Everything here is fetched from public GitHub repositories by the owner of this
project (`buffedlizard55-lab`).  Nothing in this script touches a login-walled
service.  Every fetched file is hashed and recorded in ``data/fetch_receipt.json``.

Design rules (see README "Rules of evidence"):
  * a fetched scored raster is *evidence of a shape*, not organizer truth;
  * its score is `user-reported` unless an organizer receipt exists (none do);
  * the competition grid files (`labels.tif`, `sample_submission.tif`) are the
    only artifacts treated as authoritative for geometry.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ANCHORS = RAW / "anchors"
GRID = RAW / "grid"
FEATURES = RAW / "features"

# ---------------------------------------------------------------- grid + support rasters
# (repo, path, local name, role)
GRID_FILES = [
    ("GEMSDOE24", "data/bridge/labels.tif", "labels.tif",
     "USGS-Quaternary+INGENIOUS catalogue raster, int8, -1 outside footprint"),
    ("GEMSDOE24", "data/bridge/sample_submission.tif", "sample_submission.tif",
     "competition grid/footprint template"),
    ("GEMSDOE30", "data/external/derived_sgmc_faults_100m_u8.tif", "derived_sgmc_faults_100m_u8.tif",
     "owner-derived SGMC rasterisation (local validation proxy only)"),
    ("7GEMSDOE", "external/qfaults/qfaults_prior_u8.tif", "qfaults_prior_u8.tif",
     "owner-derived USGS QFaults prior rasterisation"),
    ("7GEMSDOE", "external/dem/lidar_scarp_features_u8.tif", "lidar_scarp_features_u8.tif",
     "owner-derived LiDAR scarp-feature stack (uint8)"),
    ("7GEMSDOE", "external/geodawn_rad/geodawn_rad_u8.tif", "geodawn_rad_u8.tif",
     "owner-derived GeoDAWN radiometric stack (uint8)"),
    ("7GEMSDOE", "external/geodawn_extensions/geodawn_extensions_u8.tif", "geodawn_extensions_u8.tif",
     "owner-derived GeoDAWN extension stack (uint8)"),
]


def gh_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"no GitHub token available: {exc}")


def fetch(repo: str, path: str, dest: Path, token: str, retries: int = 4) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://api.github.com/repos/buffedlizard55-lab/{repo}/contents/{path}?ref=main"
    if dest.exists() and dest.stat().st_size > 0:
        h = sha256(dest)
        return {"repo": repo, "path": path, "local": str(dest.relative_to(ROOT)),
                "bytes": dest.stat().st_size, "sha256": h, "status": "cached"}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.raw",
                "User-Agent": "gems46-fetch",
            })
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            h = sha256(dest)
            return {"repo": repo, "path": path, "local": str(dest.relative_to(ROOT)),
                    "bytes": len(data), "sha256": h, "status": "fetched"}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = repr(exc)
            time.sleep(2 + 3 * attempt)
    return {"repo": repo, "path": path, "local": str(dest.relative_to(ROOT)),
            "bytes": 0, "sha256": None, "status": f"FAILED: {last}"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    token = gh_token()
    receipts = []
    ANCHORS.mkdir(parents=True, exist_ok=True)
    GRID.mkdir(parents=True, exist_ok=True)

    with (ROOT / "data" / "anchor_manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        dest = ANCHORS / f"{row['anchor_id']}.tif"
        rec = fetch(row["repo"], row["path"], dest, token)
        rec.update({k: row[k] for k in ("anchor_id", "label", "reported_score", "score_status")})
        receipts.append(rec)
        print(f"{row['anchor_id']:5s} {rec['status']:20s} {rec['bytes']/1e6:8.2f}MB  {row['label'][:60]}")

    for repo, path, name, role in GRID_FILES:
        rec = fetch(repo, path, GRID / name, token)
        rec.update({"anchor_id": name, "role": role})
        receipts.append(rec)
        print(f"{name:34s} {rec['status']:20s} {rec['bytes']/1e6:8.2f}MB  {role[:50]}")

    out = ROOT / "data" / "fetch_receipt.json"
    payload = {
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "GitHub contents API, Accept: application/vnd.github.raw, owner repo buffedlizard55-lab",
        "note": ("Scores attached to anchors are user-reported in the project brief and are NOT "
                 "organizer receipts. No DrivenData endpoint is reachable from this sandbox "
                 "(TLS reset); see docs/irregularities.html IR-46-001."),
        "files": receipts,
    }
    out.write_text(json.dumps(payload, indent=1) + "\n")
    ok = sum(1 for r in receipts if r["status"] in ("cached", "fetched"))
    print(f"\n{ok}/{len(receipts)} files available; receipt -> {out.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
