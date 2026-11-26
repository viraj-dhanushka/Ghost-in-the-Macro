"""The Verdict_Card as rendered in the result page (readable-proof, Part A).

Written before web/templates/_verdict_card.html exists. Reports are built inside the tests; the
haunted Intended mismatch copies a real recorded run (quantity 50, Referee 6.0, new code 0).
Validates: Requirements 3, 4, 5, 6, 7 and 13.8 of .kiro/specs/readable-proof/requirements.md.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from fastapi.testclient import TestClient

from web.app import create_app
from web.flow import _report_summary
from web.verdict import build_verdict

TEMPLATES = Path(__file__).resolve().parent.parent / "web" / "templates"
BASE = {
    "schema_version": "1", "ghost_version": "0.1.0", "seed": 20261204, "versions": {}, "mode": "faithful",
    "cases_tested": 311, "cases_generated": 300, "cases_targeted": 11, "distinct_cases": 200,
    "passed": True, "mismatches": [], "boundaries": [], "rule_coverage": [],
    "mutation": {"status": "not checked"},
    "sanity": {"status": "not cross-checked against Excel", "matched": 0, "total": 0, "differences": []},
    "findings": [], "decisions": [], "boundary_notes": [], "tested_domains": [],
}
HAUNTED_MISMATCH = {
    "actual": {"total": "0"}, "cases": 26, "cell": "Calculator!B11", "class": "expected by decision",
    "decision_id": "D-001", "expected": {"total": 6.0}, "finding_id": "F-001",
    "inputs": {"delivery_distance_km": "0", "quantity": 50, "unit_price": "0"}, "minimal": True,
    "output": "total", "rule_id": "R-794f519c",
}


def report(**over):
    return {**BASE, **over}


def _render(d, *, with_card=True, job_id="j1"):
    raw = json.dumps(d).encode() if d is not None else None
    job = SimpleNamespace(artifacts={"proof-report.json": raw} if raw else {})
    summary = _report_summary(job)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), autoescape=True)  # as Starlette's Jinja2Templates
    rail = {"not_started": False, "status_line": "Proof written", "show_bar": False,
            "counts": SimpleNamespace(done=None, total=None), "mutation_not_checked": True,
            "tombstones": [], "survivors": [], "events": []}
    return env.get_template("_job.html").render(
        job=SimpleNamespace(id=job_id, status="done", queue_position=0, error="No report."),
        terminal=True, report=SimpleNamespace(**summary) if summary else None, rail=rail,
        has_faithful_report=False, has_module=False,
        verdict=build_verdict(d) if (with_card and d is not None) else None)


def _card(html):
    m = re.search(r'<section class="verdict-card".*?</section>\s*(?=<p class="verdict|<p class="mutation|<figure)',
                  html, re.S)
    assert m, html
    return m.group(0)


def _text(fragment):
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).replace("&#39;", "'").split())


# -- failing report, haunted Intended card --------------------------------------------------

def test_a_failing_report_shows_the_failure_style_and_the_counterexample():
    bug = {**HAUNTED_MISMATCH, "class": "translation bug", "decision_id": None, "finding_id": None}
    html = _render(report(passed=False, mismatches=[bug]))
    card = _card(html)
    assert 'data-state="not_passed"' in card
    assert "Not passed: 1 difference(s) found" in _text(card)
    assert "workbook says" in _text(card) and "new code says" in _text(card)
    assert "the new code differs from the workbook, and no Finding or Decision accounts for it" in _text(card)
    assert "(translation bug)" in _text(card)


def test_haunted_intended_card():
    html = _render(report(mode="intended", mismatches=[HAUNTED_MISMATCH]))
    t = _text(_card(html))
    assert 'data-state="explained"' in _card(html)
    assert "quantity 50" in t
    assert "workbook says 6.0" in t and "new code says 0" in t
    assert "D-001" in t and "F-001" in t
    assert t.count("expected by decision") >= 1
    assert "Passed: no unexplained difference found on 311 cases; 1 expected by decision D-001" in t


def test_agreement_card_has_no_counterexample():
    card = _card(_render(report()))
    assert 'data-state="agreement"' in card and "counterexample" not in card.lower()
    assert "Passed: no difference found on 311 cases" in _text(card)


# -- tiles ---------------------------------------------------------------------------------

def test_inputs_and_disagreements_tiles():
    t = _text(_card(_render(report())))
    for s in ("300 generated", "11 targeted", "200 distinct"):
        assert s in t, t


def test_planted_bugs_zero_of_zero_has_no_bar():
    card = _card(_render(report(mutation={"mutants": [], "killed": 0, "total": 0})))
    assert "0 of 0" in _text(card) and "<progress" not in card


def test_planted_bugs_with_bar_and_listed_survivors():
    m = {"mutants": [{"mutant_id": "M-1", "killed": True}, {"mutant_id": "M-2", "killed": False,
                                                           "survivor_reason": "no difference found on 95 cases"}],
         "killed": 1, "total": 2}
    card = _card(_render(report(mutation=m)))
    assert "1 of 2" in _text(card) and '<progress' in card and 'value="1"' in card and 'max="2"' in card
    assert "M-2" in card and "no difference found on 95 cases" in card
    assert "M-1" not in card  # a killed mutant is not listed


def test_planted_bugs_not_checked_reads_exactly_that_and_has_no_bar():
    card = _card(_render(report()))
    assert re.search(r'class="tile-value"[^>]*>\s*not checked\s*<', card) and "<progress" not in card


# -- not proven strip, reproduce line, glossary -----------------------------------------------

def test_not_proven_strip_has_a_tile_container_and_lists_everything():
    d = report(boundary_notes=["no flip found for B7#1"],
               tested_domains=[{"input": "unit_price", "type": "decimal", "not_tested": True}],
               rule_coverage=[{"rule_id": "R-2", "condition_id": "R-2-C1", "seen_true": True, "seen_false": False}],
               not_converted=[{"cell": "Calc!C4", "reason": "VBA call"}])
    card = _card(_render(d))
    assert re.search(r'<section class="tile not-proven"', card)
    assert re.search(r'<h4 class="tile-title"[^>]*>What was not proven</h4>', card)
    assert len(re.findall(r'<h4 class="tile-title"', card)) >= 4  # three tiles and the strip share one heading style
    t = _text(card)
    for s in ("no flip found for B7#1", "unit_price", "R-2", "R-2-C1", "Calc!C4", "VBA call"):
        assert s in t, s


def test_excel_status_is_printed_once_without_the_label():
    t = _text(_card(_render(report())))
    assert t.count("Not cross-checked against Excel.") == 1 and "Excel cross-check: not cross-checked" not in t
    t = _text(_card(_render(report(sanity={"status": "matched", "matched": 2, "total": 2, "differences": []}))))
    assert "Excel cross-check: matched." in t


def test_reproduce_line_and_caption():
    card = _card(_render(report()))
    assert "python -m ghost.cli verify &lt;migration-dir&gt; --mode faithful --seed 20261204" in card
    assert "--cases" not in card
    assert "Run from the migration folder; add --mutation-cases to repeat the planted-bug check." in _text(card)


def test_glossary_is_a_closed_details_element():
    card = _card(_render(report()))
    m = re.search(r"<details\b([^>]*)>", card)
    assert m and "glossary" in m.group(1) and "open" not in m.group(1).split()
    t = _text(card)
    for term in ("Referee", "Mutant", "Faithful", "Intended"):
        assert term in t


# -- placement and the old text ---------------------------------------------------------------

def test_card_is_above_the_iframe_and_the_old_paragraph_and_mutation_line_are_below_it():
    html = _render(report(mutation={"mutants": [{"mutant_id": "M-1", "killed": True}], "killed": 1, "total": 1}))
    i_card, i_para = html.index('class="verdict-card"'), html.index('<p class="verdict pass"')
    i_mut, i_frame = html.index('class="mutation mutation-summary"'), html.index("<iframe")
    assert i_card < i_para < i_mut < i_frame


def test_old_paragraph_keeps_its_text_classes_and_role_and_is_not_hidden():
    html = _render(report())
    m = re.search(r'<p class="verdict pass" role="status">(.*?)</p>', html, re.S)
    assert m
    t = _text(m.group(1))
    assert t.startswith("Passed: no difference found on 311 cases (faithful mode, 300 generated + 11 targeted, "
                        "200 distinct cases, 0 mismatch(es), seed 20261204).")
    assert "Not cross-checked against Excel." in t
    assert "aria-hidden" not in m.group(0)
    assert 'aria-hidden="true"' not in html[html.index('<p class="verdict'):html.index("<iframe")].replace(
        'class="tile-icon" aria-hidden="true"', "")


def test_the_card_does_not_announce_itself_as_a_second_status():
    card = _card(_render(report()))
    assert 'role="status"' not in card and 'aria-live' not in card


def test_headline_is_the_card_heading():
    card = _card(_render(report()))
    m = re.search(r'<h3 id="(vc-h-[^"]+)" class="vc-headline">(.*?)</h3>', card, re.S)
    assert m and 'aria-labelledby="%s"' % m.group(1) in card
    assert _text(m.group(2)) == "Passed: no difference found on 311 cases"


def test_no_report_means_no_card_and_the_existing_error_text():
    html = _render(None)
    assert "verdict-card" not in html and "No report." in html


# -- wiring through the app -----------------------------------------------------------------

_FORM = {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"], "outputs": ["Calculator!B11"]}


def _finished(tmp_path, artifact):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    import sys
    app.state.runner._command = lambda mdir, mode, seed, cases: [sys.executable, "-c", "pass"]
    c.post("/sample/haunted")
    r = c.post("/verify", data=_FORM)
    jid = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(jid, 20)
    if artifact is not None:
        job.artifacts["proof-report.json"] = artifact
    return c, jid


def test_the_panel_route_renders_the_card_from_the_job_report(tmp_path):
    c, jid = _finished(tmp_path, json.dumps(report(mode="intended", mismatches=[HAUNTED_MISMATCH])).encode())
    html = c.get(f"/run/{jid}/panel").text
    assert 'class="verdict-card"' in html and 'data-state="explained"' in html
    assert "workbook says 6.0" in _text(html)


def test_the_panel_route_shows_no_card_for_an_unparseable_report(tmp_path):
    c, jid = _finished(tmp_path, b"not json")
    html = c.get(f"/run/{jid}/panel").text
    assert "verdict-card" not in html


def test_cases_line_and_none_sentences_are_rendered():
    t = _text(_card(_render(report(passed=False, mismatches=[{**HAUNTED_MISMATCH, "class": "translation bug",
                                                              "cases": 26}]))))
    assert "26 of the 200 distinct cases differ in this way; the simplest is shown." in t
    t = _text(_card(_render(report())))
    assert "The report lists no boundary notes." in t and "The report lists no cell as not converted." in t
    t = _text(_card(_render(report(boundary_notes=["a note"]))))
    assert "The report lists no boundary notes." not in t and "a note" in t


def test_the_finding_id_is_not_printed_twice_in_the_class_line():
    m = {**HAUNTED_MISMATCH, "class": "original workbook inconsistency", "decision_id": None}
    t = _text(_card(_render(report(passed=False, mismatches=[m]))))
    assert t.count("F-001") == 1 and "(Finding F-001) (original workbook inconsistency)" in t


def test_a_missing_count_reads_label_first_not_not_checked_generated():
    d = report()
    del d["cases_generated"]
    t = _text(_card(_render(d)))
    assert "generated: not checked" in t and "not checked generated" not in t
    assert "11 targeted" in t and "200 distinct" in t


_NUMBER = re.compile(r"(?<![\w.-])\d+(?![\w-])")


@pytest.mark.parametrize("d", [
    report(),
    report(mode="intended", mismatches=[HAUNTED_MISMATCH],
           mutation={"mutants": [{"mutant_id": "M-1", "killed": True}, {"mutant_id": "M-2", "killed": False}],
                     "killed": 1, "total": 2}),
    report(passed=False, mismatches=[{**HAUNTED_MISMATCH, "class": "translation bug", "cases": 26}],
           boundary_notes=["a", "b"], not_converted=[{"cell": "C4", "reason": "x"}]),
])
def test_every_number_printed_in_the_card_is_in_the_numbers_field(d):
    # The template prints no number of its own (Requirement 1.7): drop the verbatim parts (counterexample
    # inputs and values, the reproduce line with its seed, mutant ids) and check what is left.
    card = _card(_render(d))
    card = re.sub(r'<div class="counterexample">.*?(?=<div class="tiles">)', "", card, flags=re.S)
    card = re.sub(r'<div class="reproduce">.*?</div>', "", card, flags=re.S)
    card = re.sub(r'<p class="lo-version">.*?</p>', "", card, flags=re.S)
    printed = {int(n) for n in _NUMBER.findall(_text(card))}
    assert printed <= set(build_verdict(d)["numbers"].values()), printed
    assert printed  # the check looked at something


def test_the_intended_card_titles_its_box_expected_difference():
    card = _card(_render(report(mode="intended", mismatches=[HAUNTED_MISMATCH])))
    assert re.search(r'<h4 class="ce-title">Expected difference</h4>', card) and "Counterexample" not in card
    t = _text(card)
    assert "expected by decision" in t and "D-001" in t and "F-001" in t


def test_other_classes_keep_the_counterexample_title():
    bug = {**HAUNTED_MISMATCH, "class": "translation bug", "decision_id": None, "finding_id": None}
    card = _card(_render(report(passed=False, mismatches=[bug])))
    assert re.search(r'<h4 class="ce-title">Counterexample</h4>', card) and "Expected difference" not in card


STOP = "The run stops at the first unexplained difference, so later cases were not tried."


def test_the_early_stop_line_sits_under_the_inputs_tile_of_a_failing_card_only():
    bug = {**HAUNTED_MISMATCH, "class": "translation bug", "decision_id": None, "finding_id": None}
    failing = _card(_render(report(passed=False, mismatches=[bug])))
    tile = re.search(r'<section class="tile tile-inputs".*?</section>', failing, re.S).group(0)
    assert STOP in _text(tile)
    for ok in (report(), report(mode="intended", mismatches=[HAUNTED_MISMATCH])):
        assert STOP not in _text(_card(_render(ok)))


@pytest.mark.parametrize("d", [
    report(),
    report(mode="intended", mismatches=[HAUNTED_MISMATCH]),
    report(passed=False, mismatches=[{**HAUNTED_MISMATCH, "class": "translation bug"}]),
    report(passed=None),
])
def test_the_libreoffice_line_is_always_visible_beside_the_excel_status(d):
    card = _card(_render(d))
    strip = re.search(r'<section class="tile not-proven".*?</section>', card, re.S).group(0)
    assert "LibreOffice version: not checked" in _text(strip) and 'class="excel-status"' in strip
    assert strip.index('class="excel-status"') < strip.index('class="lo-version"')


def test_the_libreoffice_line_prints_the_recorded_version_without_doubling_the_name():
    d = report(versions={"libreoffice": "LibreOffice 26.8.3.1 861effc", "python": "3", "ghost": "0.1.0"})
    t = _text(_card(_render(d)))
    assert "Compared with the workbook as recalculated by LibreOffice 26.8.3.1 861effc." in t
    assert "LibreOffice LibreOffice" not in t
