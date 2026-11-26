"""`ghost receipt` (large-workbook-lane, Requirement 7, Property 6). The runner is injected in most tests, so
no LibreOffice is needed; the last tests run a real challenge and are skipped without it.
The candidate modules are stand-ins written by hand (copies of the suspects), never AWS Transform output."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ghost import cli, receipt
from ghost.converter.mapping import read_mapping
from ghost.referee.locate import RefereeUnavailable, locate_soffice

ROOT = Path(__file__).resolve().parent.parent
SUSPECTS = ROOT / "samples" / "suspects"
SEED = 20261204


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


needs_soffice = pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")


def make_kit(tmp_path: Path, logic: str = "def compute(inputs):\n    return {'total': 0}\n", mapping=True) -> Path:
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "logic.py").write_text("# STAND-IN, hand-written; not AWS Transform output\n" + logic, encoding="utf-8")
    if mapping:
        (kit / "mapping.yaml").write_text(
            "version: 1\ninputs:\n  quantity:\n    cell: Calculator!B2\n    type: integer\n    min: 0\n"
            "outputs:\n  total:\n    cell: Calculator!B11\n    type: decimal\n", encoding="utf-8")
    return kit


def report(passed=True, cases=311, seed=SEED, mode="faithful", lo="LO 1"):
    return {"passed": passed, "cases_tested": cases, "seed": seed, "versions": {"libreoffice": lo}, "mode": mode}


class FakeRunner:
    """Stands in for subprocess.run: records the call, writes a report if asked, returns an exit code."""

    def __init__(self, rc=0, rep=None, raises=None):
        self.rc, self.rep, self.raises, self.calls = rc, rep, raises, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.raises:
            raise self.raises
        if self.rep is not None:
            out = Path(cmd[cmd.index("--out") + 1]) / "reports" / "faithful"
            out.mkdir(parents=True)
            (out / "proof-report.json").write_text(json.dumps(self.rep), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, self.rc)


def go(tmp_path, runner, **kw):
    kit = kw.pop("kit", None) or make_kit(tmp_path)
    wb = tmp_path / "w.xlsx"
    wb.write_bytes(b"workbook bytes")
    kw.setdefault("derive", lambda w: read_mapping(kit / "mapping.yaml") if (kit / "mapping.yaml").is_file() else None)
    return receipt.run_receipt(wb, kit, "AWS/vba-to-python-migration", "~/.aws/atx/custom/abc/logs", tmp_path / "r",
                               runner=runner, **kw)


# -- the five conditions (Property 6) ----------------------------------------------------------
def test_a_pass_needs_all_five_conditions(tmp_path):
    r = go(tmp_path, FakeRunner(0, report()))
    assert r["result"] == "pass" and r["exit_code"] == 0
    assert r["reason"] == "no difference found on 311 cases (the candidate ran in the verifier's process)"


@pytest.mark.parametrize("rc, rep", [
    (0, None),                         # exit 0 with no report: an error
    (0, report(passed=False)),
    (0, report(cases=0)),
    (0, report(seed=1)),
    (0, report(passed="yes")),
    (0, report(mode="intended")),
    (0, report(lo="")),
    (0, {**report(), "versions": {}}),
    (0, report(cases=True)),
    (3, report()),
    (-9, report()),
], ids=["no_report", "not_passed", "zero_cases", "wrong_seed", "passed_not_bool", "mode_intended", "no_lo_version", "no_versions", "cases_is_bool", "status_3", "signal"])
def test_anything_short_of_the_five_conditions_is_never_a_pass(tmp_path, rc, rep):
    runner = FakeRunner(rc, rep)
    r = go(tmp_path, runner)
    assert r["result"] != "pass"
    if rc == 0 and rep is None:
        assert r["result"] == "error" and r["report_found"] is False


outcomes = st.fixed_dictionaries({
    "rc": st.one_of(st.none(), st.integers(-10, 10)),
    "has_report": st.booleans(),
    "passed": st.one_of(st.booleans(), st.none(), st.just("true")),
    "cases": st.one_of(st.integers(-2, 400), st.none(), st.booleans(), st.just("12")),
    "seed": st.one_of(st.just(SEED), st.integers(0, 5), st.none()),
    "mode": st.sampled_from(["faithful", "intended", None]),
    "lo": st.sampled_from(["LO 1", "", None]),
})


# Feature: large-workbook-lane, Property 6: The receipt records a pass only when all conditions hold
@settings(max_examples=400, deadline=None)
@given(outcomes)
def test_property_6_pass_only_when_all_five_conditions_hold(o):
    """Property 6 (large-workbook-lane design). Validates Requirements 7.3 and 7.4."""
    rep = ({"passed": o["passed"], "cases_tested": o["cases"], "seed": o["seed"], "mode": o["mode"],
            "versions": {"libreoffice": o["lo"]}} if o["has_report"] else None)
    result, _ = receipt.judge(o["rc"], rep, SEED)
    five = (
        o["rc"] == 0 and rep is not None and rep["passed"] is True
        and isinstance(o["cases"], int) and not isinstance(o["cases"], bool) and o["cases"] > 0
        and o["seed"] == SEED and o["mode"] == "faithful" and o["lo"] == "LO 1"
    )
    assert (result == "pass") == five
    if o["rc"] == 0 and not five:
        assert result == "error"
    if o["rc"] not in (0, 1, 2):
        assert result == "error"


def test_exit_1_is_a_difference_only_with_a_report_that_says_so(tmp_path):
    assert go(tmp_path, FakeRunner(1, report(passed=False)))["result"] == "difference found"
    (tmp_path / "b").mkdir()
    assert go(tmp_path / "b", FakeRunner(1, None))["result"] == "error"
    assert receipt.judge(1, report(passed=True), SEED)[0] == "error"


def test_exit_2_is_could_not_be_refereed_and_the_reason_is_not_read(tmp_path):
    r = go(tmp_path, FakeRunner(2))
    assert r["result"] == "could not be refereed" and "run ghost challenge by hand" in r["reason"]


def test_an_os_error_from_the_runner_is_an_error(tmp_path):
    r = go(tmp_path, FakeRunner(raises=OSError("no such interpreter")))
    assert r["result"] == "error" and r["exit_code"] is None and r["timed_out"] is False


def test_the_hashes_are_of_the_files_before_the_candidate_ran(tmp_path):
    kit = make_kit(tmp_path)
    before = hashlib.sha256((kit / "logic.py").read_bytes()).hexdigest()

    class Rewriter(FakeRunner):
        def __call__(self, cmd, **kw):
            (kit / "logic.py").write_text("print('rewritten while running')\n", encoding="utf-8")
            return super().__call__(cmd, **kw)

    r = go(tmp_path, Rewriter(0, report()), kit=kit)
    assert r["candidate_sha256"] == before


@pytest.mark.parametrize("bad", [0, -1, float("nan")])
def test_a_non_positive_timeout_is_refused(tmp_path, bad):
    with pytest.raises(receipt.ReceiptError):
        go(tmp_path, FakeRunner(0, report()), timeout=bad)


def test_the_default_runner_kills_the_whole_process_group_on_timeout(tmp_path):
    import os, signal, time
    pid_file = tmp_path / "grandchild.pid"
    script = tmp_path / "s.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n", encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired):
        receipt._default_runner([sys.executable, str(script)], cwd=str(tmp_path), env=dict(os.environ), timeout=2,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = int(pid_file.read_text())
    time.sleep(0.5)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_a_timeout_is_an_error(tmp_path):
    r = go(tmp_path, FakeRunner(raises=subprocess.TimeoutExpired("x", 5)), timeout=5)
    assert r["result"] == "error" and r["timed_out"] is True and r["timeout_seconds"] == 5


# -- how the call is made (rules 4, 6, 7) ------------------------------------------------------
def test_the_call_is_absolute_under_the_receipt_folder_with_a_timeout_and_no_output_read(tmp_path):
    runner = FakeRunner(0, report())
    go(tmp_path, runner, timeout=77)
    cmd, kw = runner.calls[0]
    root = (tmp_path / "r").resolve()
    out = Path(cmd[cmd.index("--out") + 1])
    assert out.is_absolute() and out.resolve().parent == root
    cwd = Path(kw["cwd"]).resolve()
    assert cwd.parent == root and cwd.is_dir() and not any(cwd.iterdir())  # a working directory the command owns
    assert kw["timeout"] == 77
    assert kw["stdout"] == subprocess.DEVNULL and kw["stderr"] == subprocess.DEVNULL
    assert kw.get("capture_output") in (None, False)
    assert cmd[:3] == [sys.executable, "-m", "ghost.cli"] and cmd[3] == "challenge"
    assert "--mapping" in cmd and cmd[cmd.index("--seed") + 1] == str(SEED)


# -- what the receipt says (rules 8 and 9) -----------------------------------------------------
def test_the_receipt_states_what_it_may_not_claim(tmp_path):
    r = go(tmp_path, FakeRunner(0, report()))
    on_disk = json.loads((tmp_path / "r" / "transform-receipt.json").read_text(encoding="utf-8"))
    assert on_disk == r
    assert r["definition"] == {"value": "AWS/vba-to-python-migration", "status": "stated by the owner, not verified by Ghost"}
    assert r["log"]["status"] == "stated by the owner, not verified by Ghost"
    assert r["mapping"] == "given" and r["mapping_confirmed_by_person"] == "not recorded"
    assert r["mapping_sha256"] == hashlib.sha256((tmp_path / "kit" / "mapping.yaml").read_bytes()).hexdigest()
    assert r["mapping_pairs"] == {"inputs": {"quantity": "Calculator!B2"}, "outputs": {"total": "Calculator!B11"}}
    assert r["mapping_equals_ghost_derived"] is True
    assert "the check covers only outputs calculated by worksheet formulas" in " ".join(r["known_limits"]).lower()
    assert "says nothing about the migrated vba" in " ".join(r["known_limits"]).lower()
    assert "derived by Ghost" in r["mapping_note"] and "has not confirmed it" in r["mapping_note"]
    assert "runs in the verifier's own process" in r["limits_statement"]
    assert "not trying to defeat the check" in r["limits_statement"]
    assert r["checked_in_excel"] == "not checked"
    limits = " ".join(r["known_limits"]).lower()
    assert "no sandbox" in limits and "one self-contained file" in limits and "decisions are not consulted" in limits
    assert r["candidate_sha256"] == hashlib.sha256((tmp_path / "kit" / "logic.py").read_bytes()).hexdigest()
    assert "ghost has not seen where the file came from" in r["origin"].lower()
    text = json.dumps(r)
    assert str(tmp_path) not in text and "correct" not in text.lower() and "proven" not in text.lower()


def test_a_missing_mapping_is_recorded_as_derived(tmp_path):
    kit = make_kit(tmp_path, mapping=False)
    runner = FakeRunner(0, report())
    (tmp_path / "other").mkdir()
    other = make_kit(tmp_path / "other")  # only to have a mapping object to return as "derived"
    r = go(tmp_path, runner, kit=kit, derive=lambda w: read_mapping(other / "mapping.yaml"))
    assert r["mapping"] == "derived" and "--mapping" not in runner.calls[0][0]
    assert r["mapping_sha256"] is None and r["mapping_equals_ghost_derived"] is True


def test_a_missing_logic_py_is_an_error_before_anything_runs(tmp_path):
    kit = tmp_path / "kit"
    kit.mkdir()
    runner = FakeRunner(0, report())
    with pytest.raises(receipt.ReceiptError):
        go(tmp_path, runner, kit=kit)
    assert runner.calls == []


def test_a_non_empty_receipt_folder_is_refused(tmp_path):
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "x").write_text("x", encoding="utf-8")
    with pytest.raises(receipt.ReceiptError):
        go(tmp_path, FakeRunner(0, report()))


def test_the_cli_exit_codes_follow_the_result(tmp_path, monkeypatch, capsys):
    kit = make_kit(tmp_path)
    import ghost.handoff as handoff_mod
    monkeypatch.setattr(handoff_mod, "derive_mapping", lambda wb: (read_mapping(kit / "mapping.yaml"), None))
    wb = tmp_path / "w.xlsx"
    wb.write_bytes(b"x")
    for i, (rc, rep, want) in enumerate([(0, report(), 0), (1, report(passed=False), 1), (2, None, 2), (0, None, 2)]):
        monkeypatch.setattr(receipt, "_default_runner", FakeRunner(rc, rep))
        argv = ["receipt", str(wb), "--kit", str(kit), "--definition", "D", "--log", "L", "--out", str(tmp_path / f"r{i}")]
        assert cli.main(argv) == want
        out = capsys.readouterr().out
        assert "transform-receipt.json" in out and str(tmp_path) not in out.replace(str(tmp_path / f"r{i}"), "")


# -- real (LibreOffice) ------------------------------------------------------------------------
@needs_soffice
def test_a_real_receipt_for_a_stand_in_that_passes_and_one_that_differs(tmp_path):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_haunted
    finally:
        sys.path.remove(str(ROOT / "samples"))
    wb = make_haunted.build(tmp_path / "haunted.xlsx")
    from ghost import handoff
    for suspect, want in (("honest", "pass"), ("tidied", "difference found")):
        kit = tmp_path / f"kit_{suspect}"
        handoff.write_kit(wb, kit)  # the mapping Ghost derives, as RUN.md says
        (kit / "logic.py").write_text((SUSPECTS / "haunted" / f"{suspect}.py").read_text(encoding="utf-8"), encoding="utf-8")
        r = receipt.run_receipt(wb, kit, "AWS/vba-to-python-migration", "log", tmp_path / f"r_{suspect}", timeout=300)
        assert r["result"] == want, r
    assert r["report"]["passed"] is False and r["exit_code"] == 1


def test_an_altered_mapping_is_an_error_never_a_pass(tmp_path):
    kit = make_kit(tmp_path)
    derived = read_mapping(kit / "mapping.yaml")
    (kit / "mapping.yaml").write_text(
        "version: 1\ninputs:\n  quantity:\n    cell: Calculator!B2\n    type: integer\n    min: 0\n"
        "outputs:\n  total:\n    cell: Calculator!B9\n    type: decimal\n", encoding="utf-8")  # another output cell
    r = go(tmp_path, FakeRunner(0, report()), kit=kit, derive=lambda w: derived)
    assert r["mapping_equals_ghost_derived"] is False
    assert r["result"] == "error" and "mapping" in r["reason"].lower()
    assert r["reason"].endswith("If you changed mapping.yaml yourself, run ghost challenge with --mapping; "
                                "ghost receipt only referees the mapping Ghost derives.")
    assert r["mapping_pairs"]["outputs"] == {"total": "Calculator!B9"}


def test_an_altered_domain_is_an_error_too(tmp_path):
    kit = make_kit(tmp_path)
    derived = read_mapping(kit / "mapping.yaml")
    (kit / "mapping.yaml").write_text(
        "version: 1\ninputs:\n  quantity:\n    cell: Calculator!B2\n    type: integer\n    min: 0\n    max: 5\n"
        "outputs:\n  total:\n    cell: Calculator!B11\n    type: decimal\n", encoding="utf-8")
    assert go(tmp_path, FakeRunner(0, report()), kit=kit, derive=lambda w: derived)["result"] == "error"


def test_a_workbook_that_cannot_be_derived_is_an_error_and_nothing_ran(tmp_path):
    def cannot(w):
        raise ValueError("over the limits")
    runner = FakeRunner(0, report())
    r = go(tmp_path, runner, derive=cannot)
    assert r["result"] == "error" and r["mapping_equals_ghost_derived"] is None
    assert runner.calls == []
