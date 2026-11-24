"""CLI end-to-end: run ``scripts/demo.sh`` as a subprocess and check its files.

**Validates: Requirements 1.31, 2.31, 3.6** (review-fixes task 9.5, R-20).

The shell script itself is exercised (not ``cli.main`` in-process). Demo
storyline numbers are covered in ``test_demo_invariants.py``; this file checks
the script, the exit code, stdout and the files it leaves behind.
Skipped when soffice is not available.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.report.model import validate_report_dict

ROOT = Path(__file__).resolve().parents[1]

try:
    locate_soffice()
    _HAVE_SOFFICE = True
except RefereeUnavailable:
    _HAVE_SOFFICE = False

pytestmark = pytest.mark.skipif(not _HAVE_SOFFICE, reason="soffice not available; demo.sh needs LibreOffice")

MIGRATION_FILES = ["rules.md", "traceability.yaml", "findings.yaml", "mapping.yaml", "logic.py", "excel.py"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo_sh")
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts" / "demo.sh"), str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        env=os.environ.copy(),
    )
    return out, proc


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_sh_exits_zero(demo):
    _, proc = demo
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_stdout_has_pass_lines_and_no_fail(demo):
    _, proc = demo
    lines = proc.stdout.splitlines()
    assert sum(1 for ln in lines if ln.startswith("[faithful] PASS")) == 2  # discount, haunted
    assert sum(1 for ln in lines if ln.startswith("[intended] PASS")) == 1  # haunted
    assert not any("] FAIL" in ln for ln in lines)


def test_migration_folders_have_expected_files(demo):
    out, _ = demo
    for sample in ("discount", "haunted"):
        for name in MIGRATION_FILES:
            assert (out / sample / name).is_file(), f"{sample}/{name} missing"
        for ext in ("json", "html"):
            assert (out / sample / "reports" / "faithful" / f"proof-report.{ext}").is_file()
    assert (out / "haunted" / "decisions.yaml").is_file()
    for ext in ("json", "html"):
        assert (out / "haunted" / "reports" / "intended" / f"proof-report.{ext}").is_file()


def test_all_report_jsons_validate(demo):
    out, _ = demo
    paths = sorted(out.glob("*/reports/*/proof-report.json"))
    assert len(paths) == 3
    for p in paths:
        validate_report_dict(_load(p))


def test_haunted_findings_yaml_has_f001(demo):
    out, _ = demo
    assert "F-001" in (out / "haunted" / "findings.yaml").read_text(encoding="utf-8")


def test_haunted_intended_report_has_one_expected_difference_at_quantity_50(demo):
    out, _ = demo
    r = _load(out / "haunted" / "reports" / "intended" / "proof-report.json")
    assert r["passed"] is True
    assert len(r["mismatches"]) == 1
    (m,) = r["mismatches"]
    assert m["class"] == "expected by decision"
    assert m["inputs"]["quantity"] == 50
