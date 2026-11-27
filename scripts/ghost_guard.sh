#!/bin/sh
# Runs scripts/ghost_guard.py for the PreToolUse hook, and fails closed.
#   - It uses the repository's venv Python if there is one, else python3 (the guard needs only the standard library).
#   - Exit 0 means "let the tool call run" and is passed through only when the guard itself exits 0.
#   - Exit 2 (a block) is passed through. ANY other status (a crash, a missing interpreter, a bad script) becomes 2.
# The hook command is:  sh -c 'sh scripts/ghost_guard.sh || exit 2'   (so a missing script is a block too).
# The payload is read once from standard input and handed to the guard unchanged.
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || { echo "ghost_guard: blocked: cannot find its own folder" >&2; exit 2; }
payload="$(cat)"
if [ -x "$HERE/../.venv/bin/python" ]; then
  PY="$HERE/../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "ghost_guard: blocked: no Python was found to run the guard" >&2
  exit 2
fi
printf '%s' "$payload" | "$PY" "$HERE/ghost_guard.py"
code=$?
if [ "$code" -eq 0 ]; then exit 0; fi
if [ "$code" -eq 2 ]; then exit 2; fi
echo "ghost_guard: blocked: the guard exited with status $code" >&2
exit 2
