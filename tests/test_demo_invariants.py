"""Preservation tests: the demo storyline must hold after every review fix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6** (design Property 2).

Runs the real ``ghost demo`` flow into a temp folder and reads only the engine's
own proof-report.json files. It asserts "exactly one expected difference with
minimal quantity = 50" and not the Intended case count, which R-01 will raise.
Skipped when soffice is not available.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghost import cli
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.report.model import validate_report_dict

try:
    locate_soffice()
    _HAVE_SOFFICE = True
except RefereeUnavailable:
    _HAVE_SOFFICE = False

pytestmark = pytest.mark.skipif(not _HAVE_SOFFICE, reason="soffice not available")


def _report(root: Path, sample: str, mode: str) -> dict:
    path = root / sample / "reports" / mode / "proof-report.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demo_out(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("demo")
    assert cli.main(["demo", "--out", str(out)]) == 0
    return out


def test_discount_passes_faithful(demo_out):
    r = _report(demo_out, "discount", "faithful")
    assert r["mode"] == "faithful"
    assert r["passed"] is True
    assert r["mismatches"] == []
    assert r["cases_tested"] >= 300
    assert r["findings"] == []


def test_haunted_raises_f001(demo_out):
    r = _report(demo_out, "haunted", "faithful")
    assert [f["finding_id"] for f in r["findings"]] == ["F-001"]


def test_haunted_faithful_passes_300_cases(demo_out):
    r = _report(demo_out, "haunted", "faithful")
    assert r["mode"] == "faithful"
    assert r["passed"] is True
    assert r["mismatches"] == []
    assert r["cases_tested"] >= 300


def test_haunted_intended_has_one_expected_difference_at_quantity_50(demo_out):
    r = _report(demo_out, "haunted", "intended")
    assert r["mode"] == "intended"
    assert r["passed"] is True
    assert [d["decision_id"] for d in r["decisions"]] == ["D-001"]
    assert len(r["mismatches"]) == 1
    (m,) = r["mismatches"]
    assert m["class"] == "expected by decision"
    assert m["finding_id"] == "F-001"
    assert m["decision_id"] == "D-001"
    assert m["minimal"] is True
    assert m["inputs"]["quantity"] == 50


def test_demo_reports_validate_against_schema(demo_out):
    for sample, mode in [("discount", "faithful"), ("haunted", "faithful"), ("haunted", "intended")]:
        validate_report_dict(_report(demo_out, sample, mode))


def test_primary_report_is_intended_for_haunted_and_faithful_for_discount(demo_out):
    haunted = json.loads((demo_out / "haunted" / "proof-report.json").read_text(encoding="utf-8"))
    discount = json.loads((demo_out / "discount" / "proof-report.json").read_text(encoding="utf-8"))
    assert haunted["mode"] == "intended"
    assert discount["mode"] == "faithful"
