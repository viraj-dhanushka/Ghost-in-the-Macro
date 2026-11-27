"""Before the repository goes public: no home-folder path in a tracked file, .env ignored, .kiro not ignored."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME_PATH = re.compile(r"(?:/Users|/home)/([A-Za-z0-9_.-]+)/|[A-Za-z]:\\Users\\([A-Za-z0-9_.-]+)\\")
# Invented names that tests and docs use as examples of a path that must be scrubbed.
EXAMPLE_NAMES = {"someone", "me", "you", "user", "name", "x", "<user>"}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_no_tracked_file_contains_a_home_folder_path():
    bad = []
    for rel in _git("ls-files").splitlines():
        if rel == "tests/test_repo_hygiene.py":
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for m in HOME_PATH.finditer(text):
            name = m.group(1) or m.group(2)
            if name not in EXAMPLE_NAMES:
                bad.append(f"{rel}: {m.group(0)}")
    assert not bad, bad


def test_the_current_home_folder_is_not_in_any_tracked_file():
    home = str(Path.home())
    hits = []
    for rel in _git("ls-files").splitlines():
        try:
            if home in (ROOT / rel).read_text(encoding="utf-8"):
                hits.append(rel)
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
    assert not hits, hits


def test_env_files_are_ignored_and_kiro_is_not():
    def ignored(path: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0

    assert ignored(".env") and ignored(".env.local")
    for path in (".kiro/hooks/guard-atx-aws.json", ".kiro/steering/ghost-guardrails.md", ".kiro/specs/front-door/design.md"):
        assert not ignored(path), path
    assert not _git("ls-files", ".env", ".env.local").strip()
