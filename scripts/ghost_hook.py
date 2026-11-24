"""Dispatcher for the Kiro hooks in .kiro/hooks/. Run through scripts/ghost-py.

Usage: ghost_hook.py {autopsy|report|verify|golden}
The hook payload (JSON, on stdin) is searched for the path the hook cares about.
Nothing is invented: output is whatever the Ghost command prints.
"""
from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "autopsy": r'[^"\s]*graveyard/[^/"\s]+\.xls[xm]',
    "report": r'\.kiro/specs/[^/"]+(?=/decisions\.yaml)',
    "verify": r'\.kiro/specs/[^/"]+(?=/(?:logic\.py|mapping\.yaml))',
}


def main() -> int:
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    if kind == "golden":
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-m", "golden", "-q"],
            capture_output=True, text=True,
        )
        sys.stdout.write(proc.stdout + proc.stderr)
        if proc.returncode == 5:  # pytest: no tests collected/selected
            # Safety net: golden tests exist (tests/golden/), so this only fires if the
            # selection becomes empty again (marker removed or tests deleted).
            print("GOLDEN HOOK: NOT CHECKED. 0 golden tests are selected "
                  "(no test carries @pytest.mark.golden).")
            return 1
        return proc.returncode
    if kind not in PATTERNS:
        print(f"ghost_hook: unknown kind {kind!r}", file=sys.stderr)
        return 1
    m = re.search(PATTERNS[kind], sys.stdin.read())
    if not m:
        print(f"ghost_hook {kind}: no matching path in the hook payload; nothing run.")
        return 0
    target = m.group(0)
    sub = {"autopsy": "autopsy", "report": "report", "verify": "verify"}[kind]
    return subprocess.call([sys.executable, "-m", "ghost.cli", sub, target])


if __name__ == "__main__":
    sys.exit(main())
