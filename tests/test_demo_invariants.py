"""Preservation tests: the demo storyline must hold after every review fix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6** (design Property 2).

Runs the real ``ghost demo`` flow into a temp folder and reads only the engine's
own proof-report.json files. It asserts "exactly one expected difference with
minimal quantity = 50" and not the Intended case count, which R-01 will raise.
Skipped when soffice is not available.

Also the preservation baseline of ``.kiro/specs/live-fixes-2026-11-24`` (task 2,
**Property 2: Preservation**, **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**).
Real output on the unfixed code (24 Nov 2026, LibreOffice 26.8.3, seed 20261204):

* ``scripts/demo.sh``: discount Faithful PASS, 300 generated + 6 targeted, 195
  distinct, 0 mismatches. Haunted raises F-001 (B7 ``>=`` against B9 ``>``),
  Faithful PASS, 300 generated + 9 targeted, 198 distinct, 0 mismatches.
  Haunted Intended with D-001 PASS with one mismatch: total (Calculator!B11)
  referee 6.0, new code 0, inputs quantity=50, unit_price=0,
  delivery_distance_km=0, "expected by decision" F-001 D-001, explains 26
  distinct generated cases.
* ``ghost mutate`` (default 100 cases per Mutant, Faithful): discount 31/33,
  haunted 33/35. Survivors on both: M-3cbed5dc (B9) and M-687cf270 (B10),
  ``rounding_mode``.

After L-08 (task 5.7, 25 Nov 2026) the current numbers are: discount 300 generated + 8
targeted, 197 distinct; haunted 300 generated + 11 targeted, 200 distinct (the selection
search adds 2 cases for each ``MAX(0,...)``); mutation 31/33 and 33/35 unchanged;
scenarios 300 + 54 targeted, 206 distinct, mutation 70/132. The numbers above are the
baseline before the live fixes.

L-04 and L-07 change the targeted case set, so the case counts above are
recorded here, not asserted. The mutation tests assert floors: the killed count
may rise, the mutant total may not drop (no mutant removed or hidden), and the
survivor count may not rise, so the score cannot fall below 33/35 or 31/33.
"""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
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


# --------------------------------------------------------------------------
# live-fixes-2026-11-24 task 2: preservation clauses not asserted above
# --------------------------------------------------------------------------


def test_haunted_expected_difference_is_referee_6_and_new_code_0(demo_out):
    """Clause 3.4: the one expected difference is total 6.0 (Referee) against 0 (new code)."""
    (m,) = _report(demo_out, "haunted", "intended")["mismatches"]
    assert m["output"] == "total" and m["cell"] == "Calculator!B11"
    assert Decimal(str(m["expected"]["total"])) == Decimal("6")
    assert Decimal(str(m["actual"]["total"])) == Decimal("0")


# Measured on the unfixed code (see the module docstring): killed / total.
MUTATION_FLOORS = {"discount": (31, 33), "haunted": (33, 35)}


@pytest.fixture(scope="module")
def mutated(demo_out, tmp_path_factory) -> Path:
    """``ghost mutate`` on a copy of the demo output, so the demo reports above stay as written."""
    out = tmp_path_factory.mktemp("mutate") / "demo"
    shutil.copytree(demo_out, out)
    for sample in MUTATION_FLOORS:
        assert cli.main(["mutate", str(out / sample), "--mode", "faithful"]) == 0
    return out


@pytest.mark.parametrize("sample", sorted(MUTATION_FLOORS))
def test_mutation_score_does_not_fall(mutated, sample):
    """Clauses 3.5 and 3.8: killed >= floor, total not lower, survivors not more."""
    floor_killed, floor_total = MUTATION_FLOORS[sample]
    report = _report(mutated, sample, "faithful")
    validate_report_dict(report)
    mutation = report["mutation"]
    assert mutation.get("status") != "not checked", mutation
    mutants = mutation["mutants"]
    killed, total = mutation["killed"], mutation["total"]
    # Every generated Mutant is counted (no mutant removed or hidden).
    assert total == len(mutants)
    assert killed == sum(1 for m in mutants if m["killed"])
    assert total >= floor_total, (sample, killed, total)
    assert killed >= floor_killed, (sample, killed, total)
    assert total - killed <= floor_total - floor_killed, (sample, killed, total)
    for m in mutants:
        if not m["killed"]:
            assert m["survivor_reason"].startswith("no difference found on "), m
