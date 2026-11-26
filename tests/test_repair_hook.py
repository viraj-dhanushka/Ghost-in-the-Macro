"""The repair step of scripts/ghost_hook.py (trial-by-workbook, Requirement 4). Written before it exists.

The step runs after a verification of a hand-written logic.py, writes repair-brief.json and appends one block to
repair-log.md. The log is written only here, from the proof report.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ghost_hook  # noqa: E402

FAIL = {"schema_version": "1", "ghost_version": "0.1.0", "seed": 20261204,
        "versions": {"libreoffice": "LibreOffice 26.8", "python": "3", "ghost": "0.1.0"}, "mode": "faithful",
        "cases_tested": 2, "cases_generated": 0, "cases_targeted": 2, "distinct_cases": 2, "passed": False,
        "mismatches": [{"inputs": {"delivery_distance_km": "12", "quantity": 50, "unit_price": "19.95"},
                        "expected": {"total": 1084.26}, "actual": {"total": "1077.30"}, "class": "translation bug",
                        "output": "total", "cell": "Calculator!B11", "rule_id": "R-794f519c", "minimal": True}],
        "boundaries": [], "rule_coverage": [], "mutation": {"status": "not checked"},
        "sanity": {"status": "not checked"}, "findings": [], "decisions": []}
PASS = {**FAIL, "passed": True, "mismatches": [], "cases_generated": 300, "cases_targeted": 11, "distinct_cases": 200,
        "cases_tested": 311}
RULES = "# Business rules\n## R-794f519c\nWHEN Total [Calculator!B11] is calculated THE SYSTEM SHALL set it.\nSource: Calculator!B11, Calculator!B8\n"


def folder(tmp_path, logic='"""Hand-written."""\ndef compute(inputs):\n    return {}\n', report=FAIL, newer=True):
    m = tmp_path / "mig"
    m.mkdir(exist_ok=True)
    if logic is not None:
        (m / "logic.py").write_text(logic, encoding="utf-8")
    (m / "rules.md").write_text(RULES, encoding="utf-8")
    write_report(m, report, newer)
    return m


def write_report(m, report, newer=True):
    r = m / "proof-report.json"
    r.write_text(json.dumps(report), encoding="utf-8")
    if (m / "logic.py").is_file():
        base = (m / "logic.py").stat().st_mtime
        os.utime(r, (base + (10 if newer else -10),) * 2)


def step(m, **kw):
    kw.setdefault("now", lambda: "2026-11-27T09:00:00")
    kw.setdefault("env", {})
    return ghost_hook.repair_step(m, **kw)


# -- what it does ------------------------------------------------------------------------------

def test_a_failed_round_writes_the_brief_and_the_first_block(tmp_path):
    m = folder(tmp_path)
    assert step(m) == "logged"
    brief = json.loads((m / "repair-brief.json").read_text())
    assert brief["status"] == "failed" and brief["counterexample"]["inputs"]["quantity"] == 50
    log = (m / "repair-log.md").read_text()
    assert log.startswith("# Repair log\n")
    assert "Do not edit by hand" in log
    block = log.split("## Round 1\n")[1]
    assert "- time: 2026-11-27T09:00:00" in block and "- seed: 20261204" in block
    assert "- cases: 0 generated, 2 targeted, 2 distinct" in block
    assert "- result: FAIL" in block
    assert ("- counterexample: delivery_distance_km=12, quantity=50, unit_price=19.95; output total "
            "(Calculator!B11): Referee 1084.26, actual 1077.30; rule R-794f519c; found by targeted boundary case") in block
    assert "planted" not in block and "not converged" not in block


def test_a_passing_round_is_logged_with_no_counterexample_and_a_passed_brief(tmp_path):
    m = folder(tmp_path, report=PASS)
    step(m)
    assert json.loads((m / "repair-brief.json").read_text()) == {"status": "passed"}
    block = (m / "repair-log.md").read_text().split("## Round 1\n")[1]
    assert "- result: PASS" in block and "- counterexample: none" in block
    assert "- cases: 300 generated, 11 targeted, 200 distinct" in block


def test_rounds_are_counted_and_each_run_appends_one_block(tmp_path):
    m = folder(tmp_path)
    step(m)
    write_report(m, FAIL)
    step(m)
    write_report(m, PASS)
    step(m)
    log = (m / "repair-log.md").read_text()
    assert re.findall(r"^## Round (\d+)$", log, re.M) == ["1", "2", "3"]
    assert log.count("- result: FAIL") == 2 and log.count("- result: PASS") == 1


def test_after_five_failed_rounds_the_status_is_not_converged(tmp_path):
    m = folder(tmp_path)
    for _ in range(5):
        write_report(m, FAIL)
        step(m)
    blocks = (m / "repair-log.md").read_text().split("## Round ")[1:]
    assert [("not converged" in b) for b in blocks] == [False, False, False, False, True]
    assert "- status: not converged after 5 failed rounds" in blocks[4]


def test_a_pass_resets_the_count_of_failed_rounds(tmp_path):
    m = folder(tmp_path)
    for rep in (FAIL, FAIL, PASS, FAIL, FAIL, FAIL, FAIL):
        write_report(m, rep)
        step(m)
    assert "not converged" not in (m / "repair-log.md").read_text()


def test_the_planted_label_appears_only_when_the_variable_names_it(tmp_path):
    m = folder(tmp_path)
    step(m)
    step(m, env={"GHOST_PLANTED": "changed '>' to '>=' in the free-delivery test"})
    blocks = (m / "repair-log.md").read_text().split("## Round ")[1:]
    assert "planted" not in blocks[0]
    assert "- planted: changed '>' to '>=' in the free-delivery test" in blocks[1]


# -- what it does not do -----------------------------------------------------------------------

@pytest.mark.parametrize("logic", ['"""Generated by Ghost (Faithful logic). Do not edit by hand."""\n', None])
def test_nothing_extra_for_generated_or_missing_code(tmp_path, logic):
    m = folder(tmp_path, logic=logic)
    assert step(m) == "skipped: logic.py is generated or missing"
    assert not (m / "repair-log.md").exists() and not (m / "repair-brief.json").exists()


def test_a_stale_report_is_not_logged_as_a_new_round(tmp_path):
    m = folder(tmp_path, newer=False)
    assert step(m) == "skipped: the proof report is older than logic.py or mapping.yaml (verification wrote no new report)"
    assert not (m / "repair-log.md").exists()


def test_a_mapping_save_with_no_new_report_is_not_logged(tmp_path):
    # Skeptic review: the hook also fires on mapping.yaml saves, whose mtime the old guard ignored.
    m = folder(tmp_path)
    (m / "mapping.yaml").write_text("version: 1\n", encoding="utf-8")
    base = (m / "proof-report.json").stat().st_mtime
    os.utime(m / "mapping.yaml", (base + 50, base + 50))  # mapping saved after the last report was written
    assert step(m).startswith("skipped: the proof report is older than logic.py or mapping.yaml")
    assert not (m / "repair-log.md").exists()


def test_a_report_that_verification_did_not_rewrite_is_not_logged(tmp_path):
    m = folder(tmp_path)
    before = (m / "proof-report.json").stat().st_mtime_ns
    assert step(m, newer_than_ns=before) == "skipped: verification wrote no new proof report"
    assert not (m / "repair-log.md").exists()
    write_report(m, FAIL)
    os.utime(m / "proof-report.json", ns=(before + 10**9, before + 10**9))
    assert step(m, newer_than_ns=before) == "logged"


def test_a_report_without_a_verdict_is_logged_as_not_available_not_as_a_failure(tmp_path):
    m = folder(tmp_path, report={**FAIL, "passed": None})
    step(m)
    block = (m / "repair-log.md").read_text().split("## Round 1\n")[1]
    assert "- result: NOT AVAILABLE" in block and "FAIL" not in block
    write_report(m, FAIL)
    step(m)
    assert "not converged" not in (m / "repair-log.md").read_text()


def test_no_report_means_nothing_is_logged(tmp_path):
    m = folder(tmp_path)
    (m / "proof-report.json").unlink()
    assert step(m).startswith("skipped: no proof report")
    assert not (m / "repair-log.md").exists()


def test_the_log_holds_no_absolute_path(tmp_path):
    m = folder(tmp_path)
    step(m)
    assert str(tmp_path) not in (m / "repair-log.md").read_text()


# -- wiring --------------------------------------------------------------------------------------

def test_the_existing_hook_file_is_unchanged_and_there_is_one_hook_on_logic_py():
    hooks = [json.loads(p.read_text()) for p in (ROOT / ".kiro" / "hooks").glob("*.json")]
    on_logic = [h for hk in hooks for h in hk["hooks"] if "logic" in h.get("matcher", "")]
    assert len(on_logic) == 1
    assert on_logic[0]["action"]["command"] == "scripts/ghost-py scripts/ghost_hook.py verify"


def test_the_verify_kind_runs_the_repair_step_after_verification(tmp_path, monkeypatch, capsys):
    m = folder(tmp_path)
    calls = []
    def fake_verify(cmd, **k):  # a verification that writes a new report
        calls.append(cmd)
        (m / "proof-report.json").write_text(json.dumps(FAIL), encoding="utf-8")
        os.utime(m / "proof-report.json", ns=(10**18, 10**18))
        return 1
    monkeypatch.setattr(ghost_hook.subprocess, "call", fake_verify)
    monkeypatch.setattr(sys, "argv", ["ghost_hook.py", "verify"])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps({"path": f"x/.kiro/specs/{m.name}/logic.py"})))
    seen = []
    monkeypatch.setattr(ghost_hook, "repair_step", lambda mdir, **k: seen.append(Path(mdir).name) or "logged")
    # the dispatcher resolves the folder from the payload; here the payload names .kiro/specs/<name>
    assert ghost_hook.main() == 1
    assert calls and "verify" in calls[0] and seen == [m.name]


def test_the_repair_kind_can_be_called_directly(tmp_path, monkeypatch, capsys):
    m = folder(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ghost_hook.py", "repair", str(m)])
    assert ghost_hook.main() == 0
    assert (m / "repair-log.md").is_file()
    assert "logged" in capsys.readouterr().out


@pytest.mark.parametrize("rc, writes", [(2, True), (3, True), (4, True), (1, False), (0, False)])
def test_the_verify_kind_logs_nothing_for_an_error_code_or_when_no_new_report_was_written(tmp_path, monkeypatch, rc, writes):
    m = folder(tmp_path)
    def fake_verify(cmd, **k):
        if writes:
            (m / "proof-report.json").write_text(json.dumps(FAIL), encoding="utf-8")
            os.utime(m / "proof-report.json", ns=(10**18, 10**18))
        return rc
    monkeypatch.setattr(ghost_hook.subprocess, "call", fake_verify)
    monkeypatch.setattr(sys, "argv", ["ghost_hook.py", "verify"])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps({"path": f"x/.kiro/specs/{m.name}/logic.py"})))
    monkeypatch.chdir(tmp_path.parent) if False else None
    monkeypatch.setattr(ghost_hook, "PATTERNS", {**ghost_hook.PATTERNS, "verify": r"mig(?=/logic\.py)"})
    assert ghost_hook.main() == rc
    assert not (m / "repair-log.md").exists()
# -- the attempt cap is enforced (Owner condition 8) -----------------------------------------------
def test_at_five_failed_rounds_the_brief_says_not_converged_with_no_counterexample(tmp_path, capsys):
    m = folder(tmp_path)
    for i in range(5):
        write_report(m, FAIL)
        result = step(m)
        brief = json.loads((m / "repair-brief.json").read_text())
        if i < 4:
            assert brief["status"] == "failed" and brief["counterexample"]
            assert result == "logged"
    assert brief["status"] == "not converged"
    assert "counterexample" not in brief and "rule" not in brief
    assert brief["failed_rounds"] == 5
    assert "not converged" in result
    # the log still records what that fifth round showed
    assert "- counterexample: delivery_distance_km=12, quantity=50" in (m / "repair-log.md").read_text().split("## Round 5")[1]
    # the verify kind prints the same status line
    write_report(m, FAIL)
    assert "not converged" in step(m)
    # a pass resets it
    write_report(m, PASS)
    step(m)
    assert json.loads((m / "repair-brief.json").read_text()) == {"status": "passed"}
