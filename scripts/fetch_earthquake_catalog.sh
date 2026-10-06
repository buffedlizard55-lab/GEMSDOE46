#!/usr/bin/env bash
# Fetch the raw USGS earthquake catalogue for the GeoDAWN footprint (hypothesis H46-3).
#
# WHY: the competition's seismic bands (`ieq_n100a15`, `deq_n100a15`) are 100 km-radius smoothers
# and cannot express a fault-scale (300 m) signal.  Raw hypocentres can be grouped into
# strike-parallel lineaments, which is a fault-*activity* signature rather than a rock-property one.
#
# SOURCE (official, free, no key):
#   service : https://earthquake.usgs.gov/fdsnws/event/1/query
#   docs    : https://earthquake.usgs.gov/fdsnws/event/1/
#   search UI: https://earthquake.usgs.gov/earthquakes/search/
#
# STATUS: NOT runnable from the Arena sandbox - egress to earthquake.usgs.gov returns HTTP 000
# (re-measured 2026-10-06; the group measured the same on 2026-10-04).  Run it on any unrestricted
# machine, then copy data/external/eq_catalog.csv into this repository.
#
# Usage: bash scripts/fetch_earthquake_catalog.sh [outdir]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/data/external}"
mkdir -p "$OUT"
# Footprint (EPSG:32611, origin 243350/4508550, 3730x3292 cells at 100 m) is roughly
# 38.0-41.0 N, 120.5-117.0 W; a slightly wider box is requested so edge events keep context.
curl -sS --fail --retry 3 --max-time 900 \
  "https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=1900-01-01&minmagnitude=1.5&minlatitude=37.5&maxlatitude=41.5&minlongitude=-121.0&maxlongitude=-116.5&orderby=time" \
  -o "$OUT/eq_catalog.csv"
python3 - "$OUT/eq_catalog.csv" <<'PY'
import hashlib, pathlib, sys
p = pathlib.Path(sys.argv[1])
print("bytes :", p.stat().st_size)
print("sha256:", hashlib.sha256(p.read_bytes()).hexdigest())
print("source: USGS FDSN event web service (official, free, no key)")
PY
