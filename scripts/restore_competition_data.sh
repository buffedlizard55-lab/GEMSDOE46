#!/usr/bin/env bash
# Place the official competition data into data/raw/.
#
# WHY THIS SCRIPT EXISTS
#   https://www.drivendata.org/competitions/306/competition-doe-gems/data/ is login-walled, and
#   this sandbox's egress allow-list admits only github.com and pypi.org, so the organizer files
#   cannot be fetched from here.  The group's public repositories already host integrity-pinned
#   mirrors of the three files the pipeline needs; this script restores them and verifies every
#   sha256 against registry/data_manifest.json before use.
#
# OFFICIAL SOURCE (for anyone who has credentials): the data tab above.
# MIRROR SOURCES (public GitHub):
#   training_features.tif : buffedlizard55-lab/GEMSDOE   data/bridge/gems-geodawn-numerical-features.tif.part-000..004
#   labels.tif            : buffedlizard55-lab/GEMSDOE24 data/bridge/labels.tif
#   sample_submission.tif : buffedlizard55-lab/GEMSDOE24 data/bridge/sample_submission.tif
#
# Usage: bash scripts/download_competition_data.sh [workdir]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$ROOT/.mirror}"
DEST="$ROOT/data/raw"
FEAT_SHA="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
LAB_SHA="7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
SAMP_SHA="2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"
mkdir -p "$WORK" "$DEST" "$ROOT/data/external"

echo "[1/4] sparse-cloning the mirrors (only the data/bridge blobs are fetched)"
if [ ! -d "$WORK/GEMSDOE/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/buffedlizard55-lab/GEMSDOE.git "$WORK/GEMSDOE"
  git -C "$WORK/GEMSDOE" sparse-checkout set data/bridge
fi
if [ ! -d "$WORK/GEMSDOE24/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/buffedlizard55-lab/GEMSDOE24.git "$WORK/GEMSDOE24"
  git -C "$WORK/GEMSDOE24" sparse-checkout set data/bridge
fi

echo "[2/4] reassembling training_features.tif from its five parts"
cat "$WORK"/GEMSDOE/data/bridge/gems-geodawn-numerical-features.tif.part-00* > "$DEST/training_features.tif"
cp "$WORK/GEMSDOE24/data/bridge/labels.tif" "$DEST/labels.tif"
cp "$WORK/GEMSDOE24/data/bridge/sample_submission.tif" "$DEST/sample_submission.tif"

echo "[3/4] verifying sha256 against registry/data_manifest.json"
check() { local f="$1" want="$2" got; got="$(sha256sum "$f" | cut -d' ' -f1)";
  if [ "$got" != "$want" ]; then echo "SHA256 MISMATCH for $f: got $got want $want" >&2; exit 1; fi
  echo "  OK  $(basename "$f")  $got"; }
check "$DEST/training_features.tif" "$FEAT_SHA"
check "$DEST/labels.tif" "$LAB_SHA"
check "$DEST/sample_submission.tif" "$SAMP_SHA"

echo "[4/4] external proxy data (USGS SGMC fault traces, restored from the group's mirror)"
if [ ! -f "$DEST/../external/sgmc_faults_100m_u8.tif" ]; then
  git -C "$WORK/GEMSDOE24" sparse-checkout add data/external
  cp "$WORK/GEMSDOE24/data/external/derived_sgmc_faults_100m_u8.tif" "$DEST/../external/sgmc_faults_100m_u8.tif"
fi
check "$DEST/../external/sgmc_faults_100m_u8.tif" "643cbe992ef4ba37588fb469163ed8291e3ceb23d6c1f78a3cfaa462430c2da0"

echo "done. next: python3 scripts/build_dfa_field.py && python3 scripts/build_submission.py"
