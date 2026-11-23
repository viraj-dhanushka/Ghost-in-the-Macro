#!/usr/bin/env bash
# Ghost demo: samples (a) discount calculator and (b) haunted discount calculator.
# Generates the samples, runs autopsy, rules, convert, records D-001 for F-001,
# verifies Faithful and Intended against the LibreOffice Referee and writes proof reports.
# Usage: scripts/demo.sh [output-dir]   (default: demo-out)
# Env: GHOST_SOFFICE=/path/to/soffice if LibreOffice is not on the default path.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-demo-out}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY="${PYTHON:-python3}"; fi

"$PY" -m ghost.cli demo --out "$OUT"

echo
echo "Proof reports:"
for s in discount haunted; do
  for f in "$OUT/$s"/reports/*/proof-report.html; do echo "  $f"; done
done
