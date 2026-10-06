#!/usr/bin/env bash
# Restore the R12 external layers into data/external/ and verify their sha256.
#
# WHY: R12 (docs/research/session-r12-plan.md) is the first arm in this repository to use
# airborne gamma-ray spectrometry and the 2 m LiDAR scarp-morphology product.  Neither is in
# the organiser's training_features.tif.  Both are published by the USGS as part of the
# GeoDAWN data release:
#     https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
#     DOI 10.5066/P93LGLVQ  ·  ScienceBase item 657e1d85d34e23d3533209f7
#     mirror: https://gdr.openei.org/submissions/1591
# The bytes here are the group's public resampled copies of those grids (uint8 rank-quantised
# onto the competition grid); the mirror's own receipts record the MD5/SHA-256 of every source
# archive member.  These pins prove mirror consistency, NOT organiser authentication.
#
# This sandbox cannot reach usgs.gov / sciencebase.gov / gdr.openei.org (verified 2026-10-06:
# HTTP 000), so the restore goes through github.com, which is reachable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.mirror/GEMSDOE24"
DEST="$ROOT/data/external"
mkdir -p "$DEST"

if [ ! -d "$WORK/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/buffedlizard55-lab/GEMSDOE24.git "$WORK"
fi
git -C "$WORK" sparse-checkout add data/external

copy() {  # copy <mirror name> <dest name> <sha256>
  local src="$WORK/data/external/$1" dst="$DEST/$2" want="$3" got
  [ -f "$dst" ] || cp "$src" "$dst"
  got="$(sha256sum "$dst" | cut -d' ' -f1)"
  if [ "$got" != "$want" ]; then
    echo "SHA256 MISMATCH for $2: got $got want $want" >&2; exit 1
  fi
  echo "  OK  $2  $got"
}

copy geodawn_rad_u8.tif          geodawn_rad_u8.tif          c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682
copy geodawn_extensions_u8.tif   geodawn_extensions_u8.tif   a35a9c6d2a14786f4dab85481ee59769213072f5dab5b2535ea82ae4d9bb7d9b
copy lidar_scarp_features_u8.tif lidar_scarp_features_u8.tif d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568

echo "done. next: python3 scripts/run_r12.py"
