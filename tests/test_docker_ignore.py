"""The Docker image ships .kiro/steering/routing-thresholds.md and no other file under .kiro
(large-workbook-lane, Requirement 8). The Docker build itself is not run here (not checked); this test applies
the documented .dockerignore rules (patterns in order, the last match wins, a pattern matches a path or any
parent directory, `*` does not cross a slash) to the real file list."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = ".kiro/steering/routing-thresholds.md"


def _patterns() -> list[tuple[bool, str]]:
    out = []
    for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        neg = line.startswith("!")
        out.append((neg, line[1:] if neg else line))
    return out


def _match(pattern: str, path: str) -> bool:
    if pattern.startswith("**/"):
        return any(_match(pattern[3:], "/".join(path.split("/")[i:])) for i in range(len(path.split("/"))))
    pp, parts = pattern.split("/"), path.split("/")
    return len(pp) == len(parts) and all(fnmatch.fnmatchcase(a, b) for a, b in zip(parts, pp))


def excluded(path: str) -> bool:
    parts = path.split("/")
    state = False
    for neg, pat in _patterns():
        if any(_match(pat, "/".join(parts[: i + 1])) for i in range(len(parts))):
            state = not neg
    return state


def _kiro_files() -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / ".kiro").rglob("*") if p.is_file())


def test_only_the_thresholds_file_is_let_in_from_dot_kiro():
    files = _kiro_files()
    assert THRESHOLDS in files
    assert [f for f in files if not excluded(f)] == [THRESHOLDS]


def test_the_negated_pattern_names_that_one_file_and_the_directory_stays_ignored():
    pats = _patterns()
    assert (True, THRESHOLDS) in pats
    assert [p for n, p in pats if n] == [".kiro/steering", THRESHOLDS]  # nothing else is re-included
    assert excluded(".kiro/hooks/reverify-on-logic-save.json") and excluded(".kiro/steering/product.md")
    assert excluded(".kiro/specs/large-workbook-lane/requirements.md")


def test_the_other_ignored_paths_are_unchanged():
    for path in ("tests/test_x.py", "docs/a.md", "scripts/demo.sh", ".git/config", "graveyard/haunted.xlsx",
                 "plugin/plugin.json", "a/__pycache__/b.pyc", ".venv/bin/python"):
        assert excluded(path), path
    for path in ("ghost/cli.py", "web/app.py", "samples/make_haunted.py", "mcp_server/server.py", "pyproject.toml"):
        assert not excluded(path), path


def test_the_dockerfile_copies_that_one_file_and_the_loader_finds_it_there():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copies = [ln for ln in text.splitlines() if ln.startswith("COPY") and ".kiro" in ln]
    assert copies == [f"COPY {THRESHOLDS} {THRESHOLDS}"]
    # the package sits in /app/ghost (editable install), so default_path() resolves to /app/.kiro/steering/...
    from ghost.router.thresholds import default_path
    assert default_path().relative_to(ROOT).as_posix() == THRESHOLDS
