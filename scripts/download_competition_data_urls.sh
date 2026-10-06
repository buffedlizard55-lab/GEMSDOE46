#!/usr/bin/env bash
# Fetch the three official competition rasters into data/.
#
# WHY THERE IS NO HARD-CODED URL IN THIS FILE
# ------------------------------------------
# The competition data tab (https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
# serves the files behind a signed-in session, and the URLs are session-specific and change.
# Hard-coding a guessed URL here would be fabrication, so this script instead accepts the exact
# URLs you see on that page (right-click -> "Copy link address" on each file) and then verifies
# every download against the sha256 pins recorded when the project owner first obtained them.
#
# Usage
# -----
#   export DD_URL_TRAINING_FEATURES='https://...'   # copy from the data tab (signed in)
#   export DD_URL_LABELS='https://...'
#   export DD_URL_SAMPLE_SUBMISSION='https://...'
#   bash scripts/download_competition_data.sh
#
#   # or, if the files are already downloaded in a browser:
#   python scripts/prepare_data.py --from-dir ~/Downloads
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data

need() { # name, env var
  if [[ -z "${2:-}" ]]; then
    echo "missing $2 (copy the link from https://www.drivendata.org/competitions/306/competition-doe-gems/data/ while signed in)" >&2
    exit 2
  fi
  echo "==> $1"
  curl -fL --retry 3 --retry-delay 2 -o "data/$1" "$2"
}

need training_features.tif "${DD_URL_TRAINING_FEATURES:-}"
need labels.tif            "${DD_URL_LABELS:-}"
need sample_submission.tif "${DD_URL_SAMPLE_SUBMISSION:-}"

echo "==> verifying sha256 pins"
python3 scripts/prepare_data.py
