#!/usr/bin/env bash
# A comparison only: no previous submission pixels enter R10 generation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.mirror/GEMSDOE32"
DEST="$ROOT/data/derived/incumbent_02778.tif"
WANT=c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9
mkdir -p "$ROOT/data/derived"
if [ ! -f "$DEST" ]; then
  if [ ! -d "$WORK/.git" ]; then
    git clone --depth 1 --filter=blob:none --sparse https://github.com/buffedlizard55-lab/GEMSDOE32.git "$WORK"
  fi
  git -C "$WORK" sparse-checkout add docs/downloads
  cp "$WORK/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif" "$DEST"
fi
printf '%s  %s\n' "$WANT" "$DEST" | sha256sum --check
