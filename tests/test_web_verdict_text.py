"""Verdict sentence on the result page (owner decision, front-door task 17 follow-up).

The label stays "Passed" / "Not passed" and gets one sentence built only from the proof report:

* Faithful with 0 mismatches:      "Passed: no difference found on N cases"
* Intended, all explained by a Decision:
                                   "Passed: no unexplained difference found on N cases; K expected by decision <ids>"
* otherwise:                       "Not passed: K difference(s) found"

N is ``cases_tested``; K and the ids come from the report's ``mismatches``. The report the engine
writes is not changed; the tests only build report dictionaries and render ``_job.html``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

from web.flow import _report_summary, verdict_text

TEMPLATES = Path(__file__).resolve().parent.parent / "web" / "templates"


def _mismatch(cls, decision_id=None):
    m = {"cell": "Calculator!B11", "class": cls, "output": "total"}
    if decision_id:
        m["decision_id"] = decision_id
    return m


def _report(mode="faithful", passed=True, mismatches=(), cases_tested=311):
    d = {"mode": mode, "passed": passed, "mismatches": list(mismatches), "seed": 20261204,
         "cases_generated": 300, "cases_targeted": 11, "distinct_cases": 200}
    if cases_tested is not None:
        d["cases_tested"] = cases_tested
    return d


# -- the three sentences ------------------------------------------------------

def test_faithful_zero_mismatches():
    assert verdict_text(_report()) == "Passed: no difference found on 311 cases"


def test_intended_all_explained_by_one_decision():
    d = _report("intended", True, [_mismatch("expected by decision", "D-001")])
    assert verdict_text(d) == (
        "Passed: no unexplained difference found on 311 cases; 1 expected by decision D-001")


def test_intended_several_explained_lists_each_id_once_in_order():
    d = _report("intended", True, [
        _mismatch("expected by decision", "D-002"),
        _mismatch("expected by decision", "D-001"),
        _mismatch("expected by decision", "D-002"),
    ])
    assert verdict_text(d) == (
        "Passed: no unexplained difference found on 311 cases; 3 expected by decision D-001, D-002")


def test_intended_with_no_mismatch_at_all_says_no_difference():
    assert verdict_text(_report("intended", True, [])) == "Passed: no difference found on 311 cases"


def test_faithful_with_mismatches_is_not_passed_and_counts_them():
    d = _report("faithful", False, [_mismatch("translation bug"), _mismatch("translation bug")])
    assert verdict_text(d) == "Not passed: 2 difference(s) found"


def test_intended_not_passed_counts_only_the_unexplained_ones():
    d = _report("intended", False, [
        _mismatch("expected by decision", "D-001"),
        _mismatch("translation bug"),
        _mismatch("original workbook inconsistency"),
    ])
    assert verdict_text(d) == "Not passed: 2 difference(s) found"


# -- never contradict or invent -----------------------------------------------

def test_missing_case_count_is_written_not_checked_not_invented():
    text = verdict_text(_report(cases_tested=None))
    assert text == "Passed: no difference found; number of cases: not checked"


def test_passed_flag_with_unexplained_mismatches_does_not_claim_no_difference():
    # An inconsistent report: the label follows the report, the sentence claims nothing more.
    d = _report("faithful", True, [_mismatch("translation bug")])
    assert verdict_text(d) == "Passed"


def test_not_passed_without_countable_difference_is_the_bare_label():
    assert verdict_text(_report("faithful", False, [])) == "Not passed"


def test_missing_passed_field_reads_verdict_not_available():
    # Owner decision (task 17 follow-up): a report with no verdict is not "Not passed".
    d = _report("faithful", True, [])
    del d["passed"]
    assert verdict_text(d) == "Verdict not available"
    _, html = _render(d)
    m = re.search(r'<p class="verdict unavailable" role="status">(.*?)</p>', html, re.S)
    assert m, html
    assert " ".join(m.group(1).split()).startswith("Verdict not available")


@pytest.mark.parametrize("bad", ["x", 3, ["x"], [1], [{"class": "translation bug"}, "x"]])
def test_malformed_mismatches_give_the_bare_label_never_no_difference(bad):
    # Task 17 (Skeptic A-1): entries that are not dicts must not be dropped and then read as "none".
    d = _report("intended", True)
    d["mismatches"] = bad
    assert verdict_text(d) == "Passed"
    d["passed"] = False
    assert verdict_text(d) == "Not passed"


@pytest.mark.parametrize("bad", [None, [], {}])
def test_empty_or_absent_mismatches_count_as_none(bad):
    d = _report("faithful", True)
    d["mismatches"] = bad
    assert verdict_text(d) == "Passed: no difference found on 311 cases"


@pytest.mark.parametrize("n", [0, -3, "311", True, 3.5])
def test_case_count_that_is_not_a_positive_integer_is_not_checked(n):
    # Task 17 (Skeptic A-2): never print "no difference found on 0 cases".
    assert verdict_text(_report(cases_tested=n)) == "Passed: no difference found; number of cases: not checked"


def test_summary_does_not_raise_on_a_malformed_mismatches_field():
    d = _report("faithful", True)
    d["mismatches"] = 3
    assert _report_summary(_job(d))["mismatches"] == 0


def test_no_banned_words_in_any_sentence():
    texts = [
        verdict_text(_report()),
        verdict_text(_report("intended", True, [_mismatch("expected by decision", "D-001")])),
        verdict_text(_report("faithful", False, [_mismatch("translation bug")])),
    ]
    for t in texts:
        assert not re.search(r"correct|proven|verified", t, re.I), t


# -- through the summary and the template -------------------------------------

def _job(d):
    return SimpleNamespace(artifacts={"proof-report.json": json.dumps(d).encode()})


def _render(d):
    summary = _report_summary(_job(d))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)))
    rail = {"not_started": False, "status_line": "Proof written", "show_bar": False,
            "counts": SimpleNamespace(done=None, total=None), "mutation_not_checked": True,
            "tombstones": [], "survivors": [], "events": []}
    return summary, env.get_template("_job.html").render(
        job=SimpleNamespace(id="j1", status="done", queue_position=0, error=None),
        terminal=True, report=SimpleNamespace(**summary), rail=rail,
        has_faithful_report=False, has_module=False)


def test_summary_carries_the_sentence_and_keeps_its_other_fields():
    summary = _report_summary(_job(_report("intended", True, [_mismatch("expected by decision", "D-001")])))
    assert summary["verdict_text"].startswith("Passed: no unexplained difference found on 311 cases")
    assert summary["passed"] is True and summary["mode"] == "intended" and summary["mismatches"] == 1
    assert summary["seed"] == 20261204


def test_template_shows_sentence_inside_the_pinned_verdict_element():
    _, html = _render(_report("intended", True, [_mismatch("expected by decision", "D-001")]))
    m = re.search(r'<p class="verdict pass" role="status">(.*?)</p>', html, re.S)
    assert m, html
    text = " ".join(m.group(1).split())
    assert text.startswith("Passed: no unexplained difference found on 311 cases; 1 expected by decision D-001")
    # The existing detail stays: mode, case breakdown, mismatch count, seed, Excel cross-check.
    assert "(intended mode, 300 generated + 11 targeted, 200 distinct cases, 1 mismatch(es), seed 20261204)" in text
    assert "Excel cross-check: not checked." in text


def test_template_fail_state_keeps_class_and_role():
    _, html = _render(_report("faithful", False, [_mismatch("translation bug")]))
    m = re.search(r'<p class="verdict fail" role="status">(.*?)</p>', html, re.S)
    assert m, html
    assert " ".join(m.group(1).split()).startswith("Not passed: 1 difference(s) found")


def test_template_does_not_write_not_checked_cases():
    # Task 17 (Skeptic A-3): "not checked cases" read as a count of cases.
    _, html = _render(_report(cases_tested=None))
    text = " ".join(re.search(r'<p class="verdict pass" role="status">(.*?)</p>', html, re.S).group(1).split())
    assert "not checked cases" not in text
    assert "(faithful mode, cases: not checked, 0 mismatch(es), seed 20261204)" in text

def _excel_sentence(status):
    d = _report()
    if status is not None:
        d["sanity"] = {"status": status}
    _, html = _render(d)
    text = " ".join(re.search(r'<p class="verdict pass" role="status">(.*?)</p>', html, re.S).group(1).split())
    return text
def test_excel_status_that_already_says_it_is_printed_alone_as_a_sentence():
    # Owner decision 2026-11-25: no "Excel cross-check: not cross-checked against Excel".
    text = _excel_sentence("not cross-checked against Excel")
    assert text.endswith("Not cross-checked against Excel.")
    assert "Excel cross-check: not cross-checked" not in text
    assert text.count("Excel") == 1
def test_other_excel_statuses_keep_the_prefix():
    assert _excel_sentence("matched").endswith("Excel cross-check: matched.")
    assert _excel_sentence("differences").endswith("Excel cross-check: differences.")
    assert _excel_sentence(None).endswith("Excel cross-check: not checked.")
