"""Hide server paths from text that is shown to the browser (R-21).

Job output, job errors and error messages can contain absolute paths of the
server (session folders, temp dirs, the install dir, home dirs). `scrub_paths`
replaces the run directory with "." and any other absolute path with its last
name, so a reader sees `./logic_intended.py` or `ghost-referee-ab12`, never
`/tmp/ghost-sessions-x/<session>/run-1/...`.
"""

from __future__ import annotations

import re
from pathlib import Path

_SEG = r"[\w.\-@+~]"
# POSIX absolute path: starts at a "/" that is not part of a word, URL or
# relative path, and has at least one name segment.
_POSIX = re.compile(rf"(?<![\w./:~\-])/{_SEG}+(?:/{_SEG}*)*")
# Windows drive path such as C:\Users\x\file.py
_WINDOWS = re.compile(rf"(?<![\w])[A-Za-z]:\\(?:{_SEG}+\\?)+")


def _basename(match: re.Match) -> str:
    text = match.group(0).rstrip("/\\")
    return re.split(r"[\\/]", text)[-1] or "."


def scrub_paths(text: str, *run_dirs: Path | str) -> str:
    """Return `text` with `run_dirs` shown as "." and other absolute paths shortened."""
    if not text:
        return text
    prefixes: set[str] = set()
    for d in run_dirs:
        p = Path(d)
        prefixes.add(str(p))
        try:
            prefixes.add(str(p.resolve()))
        except OSError:
            pass
    for prefix in sorted(prefixes, key=len, reverse=True):
        # Longest first. Only replace at a path boundary.
        text = re.sub(re.escape(prefix) + r"(?![\w.\-@+~])", ".", text)
    text = _WINDOWS.sub(_basename, text)
    return _POSIX.sub(_basename, text)
