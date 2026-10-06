#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Deliberately offline: DrivenData is login-gated and its Terms prohibit
# unauthorized automated monitoring/copying. The user downloads an archive
# through the official participant portal and places it in data/inbox/.
if [[ -n "${GEMS_DATA_ARCHIVE:-}" ]]; then
  archive="$GEMS_DATA_ARCHIVE"
else
  shopt -s nullglob
  archives=(data/inbox/*.zip data/inbox/*.ZIP)
  shopt -u nullglob
  if (( ${#archives[@]} == 0 )); then
    cat >&2 <<'EOF'
No local competition ZIP found. No network request was made.

1. Enroll/sign in at the official DOE GEMS competition page.
2. Download the data archive through the authorized Data page.
3. Place the ZIP in this repository's data/inbox/ directory, then rerun this script.

Official page: https://www.drivendata.org/competitions/306/competition-doe-gems/data/
EOF
    exit 2
  fi
  if (( ${#archives[@]} > 1 )); then
    printf 'Found %d ZIP files; set GEMS_DATA_ARCHIVE to the intended path.\n' "${#archives[@]}" >&2
    printf '  %s\n' "${archives[@]}" >&2
    exit 2
  fi
  archive="${archives[0]}"
fi

python3 scripts/import_competition_archive.py --archive "$archive" --destination data/raw
