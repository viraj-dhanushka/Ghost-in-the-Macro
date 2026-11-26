#!/bin/sh
# Preflight for recording the demo video: GET-only checks of /healthz and / on the live URL.
# Usage: scripts/preflight_demo.sh [base-url]      (default: the live URL in the README)
# It only reads: two GET requests, no upload, no POST, no session, nothing is changed on the site.
# Exit 0: both answered as expected. Exit 1: one did not. Exit 2: usage or curl missing.
BASE="${1:-https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws}"
BASE="${BASE%/}"
command -v curl >/dev/null 2>&1 || { echo "preflight: curl is not installed" >&2; exit 2; }
fail=0
check() {  # name, path, expected substring in the body
  out="$(curl -sS -m 30 -w '\n%{http_code}' "$BASE$2" 2>&1)"
  code="$(printf '%s' "$out" | tail -n 1)"
  body="$(printf '%s' "$out" | sed '$d')"
  if [ "$code" = "200" ] && printf '%s' "$body" | grep -q "$3"; then
    echo "ok    GET $2 -> 200, found: $3"
  else
    echo "FAIL  GET $2 -> $code (wanted 200 and the text: $3)"
    fail=1
  fi
}
echo "preflight against $BASE"
check "health" "/healthz" '"status":"ok"'
check "landing" "/" "Ghost in the Macro"
if [ "$fail" = "0" ]; then
  echo "Both checks passed. This says the site answers; it does not say the Referee will start a verification, the samples will load, or a run will finish: try one sample by hand before recording."
  exit 0
fi
echo "At least one check failed. Do not record against this site; shoot locally with: uvicorn web.app:app"
exit 1
