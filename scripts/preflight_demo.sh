#!/bin/sh
# Preflight for the demo video and for submitting.
#   scripts/preflight_demo.sh [base-url]   GET-only checks of /healthz, / and /kiro on the live URL (default: the README's).
#   scripts/preflight_demo.sh --submit     no network: fails if README.md, docs/DEVPOST_WRITEUP.md, docs/KIRO_STORY.md
#                                          or docs/DEMO_VIDEO_SCRIPT.md still contains an Owner placeholder or a draft marker.
# The URL mode makes three GET requests and nothing else: no upload, no verification, no write.
# Note: GET / starts an empty session on the server (a cookie is set and an empty session folder is created; the idle
# sweeper removes it). GET /kiro fails on a build older than the Built with Kiro page, so a stale deploy is caught.
# Exit 0: all checks passed. Exit 1: one failed. Exit 2: usage or curl missing.
ROOT="${GHOST_SUBMIT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
fail=0

submit_check() {  # file, marker pattern (fixed strings), description
  for f in README.md docs/DEVPOST_WRITEUP.md docs/KIRO_STORY.md docs/DEMO_VIDEO_SCRIPT.md; do
    if [ ! -f "$ROOT/$f" ]; then
      echo "FAIL  $f is missing"
      fail=1
      continue
    fi
    if grep -n --fixed-strings -e '[OWNER' -e '(draft)' -e 'Draft for the Owner' -e 'for the Owner to complete' "$ROOT/$f" >/dev/null 2>&1; then
      echo "FAIL  $f still contains [OWNER, (draft), "Draft for the Owner" or "for the Owner to complete":"
      grep -n --fixed-strings -e '[OWNER' -e '(draft)' -e 'Draft for the Owner' -e 'for the Owner to complete' "$ROOT/$f" | head -5 | cut -c1-140
      fail=1
    else
      echo "ok    $f has no Owner placeholder and no draft marker"
    fi
  done
}

if [ "$1" = "--submit" ]; then
  echo "submit check (files only, no network)"
  submit_check
  if [ "$fail" = "0" ]; then
    echo "Submit check passed. It looks for placeholders only; it does not say the write-up is complete or the links work."
    exit 0
  fi
  echo "Submit check failed: fill in or remove the marked text, then run scripts/ghost-py scripts/kiro_ledger.py."
  exit 1
fi

BASE="${1:-https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws}"
BASE="${BASE%/}"
command -v curl >/dev/null 2>&1 || { echo "preflight: curl is not installed" >&2; exit 2; }
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
check "kiro" "/kiro" "Built with Kiro"
if [ "$fail" = "0" ]; then
  echo "All three checks passed. This says the site answers and is a recent build; it does not say the Referee will start a verification, the samples will load, or a run will finish: try one sample by hand before recording."
  exit 0
fi
echo "At least one check failed. Do not record against this site; shoot locally with: .venv/bin/python -m uvicorn web.app:app --port 8080"
exit 1
