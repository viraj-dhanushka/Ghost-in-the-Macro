"""The repair brief (trial-by-workbook, Requirement 3 and Property 3). Written before scripts/repair_brief.py.

The brief is built only from the proof report of a failed round, plus the rule text (from rules.md) and the
source formula (from the workbook). It never holds an absolute path.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl
import pytest
from hypothesis import given, seed, settings

from tests.test_property_verdict import reports

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import repair_brief as rb  # noqa: E402

RULES = """# Business rules
## R-02486486
WHEN Subtotal [Calculator!B6] is calculated THE SYSTEM SHALL set Subtotal [Calculator!B6] to (Quantity [Calculator!B2] times Unit price [Calculator!B3]).
Source: Calculator!B6, Calculator!B2, Calculator!B3
## R-794f519c
WHEN Total [Calculator!B11] is calculated THE SYSTEM SHALL set Total [Calculator!B11] to ((Net goods [Calculator!B8] plus Delivery fee [Calculator!B9]) plus VAT [Calculator!B10]).
Source: Calculator!B11, Calculator!B8, Calculator!B9, Calculator!B10
"""
FORMULAS = {"Calculator!B11": "=B8+B9+B10", "Calculator!B6": "=B2*B3"}


def report(**over):
    d = {"schema_version": "1", "ghost_version": "0.1.0", "seed": 20261204,
         "versions": {"libreoffice": "LO", "python": "3", "ghost": "0.1.0"}, "mode": "faithful",
         "cases_tested": 2, "cases_generated": 0, "cases_targeted": 2, "distinct_cases": 2, "passed": False,
         "mismatches": [{"inputs": {"delivery_distance_km": "12", "quantity": 50, "unit_price": "19.95"},
                         "expected": {"total": 1084.26}, "actual": {"total": "1077.30"},
                         "class": "translation bug", "output": "total", "cell": "Calculator!B11",
                         "rule_id": "R-794f519c", "minimal": True, "cases": 1}],
         "boundaries": [], "rule_coverage": [], "mutation": {"status": "not checked"},
         "sanity": {"status": "not checked"}, "findings": [], "decisions": []}
    d.update(over)
    return d


def brief(rep=None, rules=RULES, formulas=FORMULAS):
    return rb.build_brief(rep if rep is not None else report(), rules, formulas.get)


# -- shape -----------------------------------------------------------------------------------

def test_a_passing_report_gives_only_a_status():
    assert brief(report(passed=True, mismatches=[])) == {"status": "passed"}


def test_a_failing_report_gives_the_minimal_counterexample_and_its_rule():
    b = brief()
    assert b["status"] == "failed" and b["mode"] == "faithful" and b["seed"] == 20261204
    ce = b["counterexample"]
    assert ce["inputs"] == {"delivery_distance_km": "12", "quantity": 50, "unit_price": "19.95"}
    assert ce["referee"] == {"total": 1084.26} and ce["actual"] == {"total": "1077.30"}
    assert ce["output"] == "total" and ce["cell"] == "Calculator!B11"
    assert b["found_by"] == "targeted boundary case"
    assert b["rule"] == {
        "rule_id": "R-794f519c",
        "rule_text": "WHEN Total [Calculator!B11] is calculated THE SYSTEM SHALL set Total [Calculator!B11] to "
                     "((Net goods [Calculator!B8] plus Delivery fee [Calculator!B9]) plus VAT [Calculator!B10]).",
        "source_formula": "=B8+B9+B10",
    }


def test_a_failure_found_by_the_search_is_labelled_shrunk():
    assert brief(report(cases_generated=40))["found_by"] == "search (shrunk)"


def test_the_minimal_unexplained_mismatch_is_chosen():
    other = {"inputs": {"quantity": 9}, "expected": {"total": 1}, "actual": {"total": 2}, "class": "translation bug",
             "output": "total", "rule_id": "R-02486486", "minimal": False}
    mini = report()["mismatches"][0]
    explained = {**other, "class": "expected by decision", "minimal": True, "inputs": {"quantity": 1}}
    assert brief(report(mismatches=[other, mini]))["counterexample"]["inputs"]["quantity"] == 50
    assert brief(report(mismatches=[explained, other]))["counterexample"]["inputs"]["quantity"] == 9
    assert brief(report(mismatches=[other]))["counterexample"]["inputs"]["quantity"] == 9


def test_a_missing_rule_id_or_text_is_not_available():
    m = {**report()["mismatches"][0]}
    del m["rule_id"]
    b = brief(report(mismatches=[m]))
    assert b["rule"] == {"rule_id": "not available", "rule_text": "not available", "source_formula": "not available"}
    m["rule_id"] = "R-ffffffff"  # an id that rules.md does not have
    b = brief(report(mismatches=[m]))
    assert b["rule"]["rule_id"] == "R-ffffffff" and b["rule"]["rule_text"] == "not available"
    assert b["rule"]["source_formula"] == "not available"


def test_a_rule_whose_cell_has_no_formula_has_no_source_formula():
    assert brief(formulas={})["rule"]["source_formula"] == "not available"


def test_a_failing_report_without_a_mismatch_says_so_and_invents_nothing():
    b = brief(report(mismatches=[]))
    assert b == {"status": "failed", "mode": "faithful", "seed": 20261204, "counterexample": None,
                 "note": "the report lists no mismatch"}


def test_a_report_without_a_verdict_is_not_available():
    d = report()
    del d["passed"]
    assert brief(d) == {"status": "not available"}


def test_the_brief_never_holds_a_path_or_the_workbook_name():
    blob = json.dumps(brief())
    assert not re.search(r"(/Users/|/tmp/|/private/|/var/|[A-Za-z]:\\|\.xlsx|\.xlsm)", blob)


# -- the folder wrapper ------------------------------------------------------------------------

def make_folder(tmp_path, rep):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calculator"
    ws["B11"] = "=B8+B9+B10"
    wb.save(tmp_path / "book.xlsx")
    m = tmp_path / "mig"
    m.mkdir()
    (m / "rules.md").write_text(RULES, encoding="utf-8")
    (m / "source.yaml").write_text("workbook: ../book.xlsx\n", encoding="utf-8")
    (m / "proof-report.json").write_text(json.dumps(rep), encoding="utf-8")
    return m


def test_write_brief_reads_the_folder_and_writes_repair_brief_json(tmp_path):
    m = make_folder(tmp_path, report())
    out = rb.write_brief(m)
    text = (m / "repair-brief.json").read_text(encoding="utf-8")
    assert json.loads(text) == out and text.endswith("\n")
    assert out["rule"]["source_formula"] == "=B8+B9+B10"
    assert str(tmp_path) not in text and "book.xlsx" not in text
    assert text == json.dumps(out, indent=2, sort_keys=True) + "\n"  # deterministic


def test_write_brief_for_a_passing_report(tmp_path):
    m = make_folder(tmp_path, report(passed=True, mismatches=[]))
    assert rb.write_brief(m) == {"status": "passed"}
    assert json.loads((m / "repair-brief.json").read_text()) == {"status": "passed"}


def test_write_brief_without_a_report_is_an_error_not_a_made_up_brief(tmp_path):
    m = tmp_path / "empty"
    m.mkdir()
    with pytest.raises(FileNotFoundError):
        rb.write_brief(m)


# -- Property 3 ----------------------------------------------------------------------------------

def _leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _leaves(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _leaves(v)
    else:
        yield x


# Feature: trial-by-workbook, Property 3: the brief holds no value that is absent from its report
@seed(20261204)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(reports())
def test_property_3_the_brief_holds_no_value_absent_from_the_report_and_no_path(rep):
    b = rb.build_brief(rep, RULES, FORMULAS.get)
    if rep["passed"] is True:
        assert b == {"status": "passed"}
        return
    assert b["status"] == "failed"
    if b["counterexample"] is None:
        assert rep["mismatches"] == []
        return
    ce = b["counterexample"]
    chosen = [m for m in rep["mismatches"] if m["inputs"] == ce["inputs"] and m["expected"] == ce["referee"]
              and m["actual"] == ce["actual"]]
    assert chosen, "the counterexample is one of the report's mismatches, copied as recorded"
    assert any(ce["output"] == (m.get("output") or "not available") and ce["cell"] == (m.get("cell") or "not available")
               and b["rule"]["rule_id"] == (m.get("rule_id") or "not available") for m in chosen)
    assert b["mode"] == rep["mode"] and b["seed"] == rep["seed"]
    for leaf in _leaves(ce):
        assert any(leaf in set(_leaves(m)) | {"not available"} for m in chosen)
    blob = json.dumps(b)
    assert not re.search(r"(/Users/|/tmp/|/private/|[A-Za-z]:\\\\)", blob)
# -- decisions in a faithful report (Owner condition 9) ---------------------------------------------
def test_a_faithful_report_with_decisions_warns_the_agent_to_ask_the_user():
    rep = report(decisions=[{"decision_id": "D-001", "behaviour": "x", "reason": "y", "author": "z",
                             "date": "2026-11-27", "finding_id": "F-001"}])
    b = brief(rep)
    assert b["decision_ids"] == ["D-001"]
    assert "intended" in b["warning"].lower() and "ask the user" in b["warning"].lower()
    assert "decision_ids" not in brief(report(decisions=[]))
    assert "warning" not in brief(report(decisions=[]))
    assert "warning" not in brief(report(decisions=[{"decision_id": "D-001"}], mode="intended"))
