"""Live-test findings L-02 to L-05 (docs/LIVE_TEST_REPORT_2026-11-24.md).

Bug condition exploration tests, task 1 of ``.kiro/specs/live-fixes-2026-11-24``.
**Property 1: Bug Condition** - live findings L-02 to L-05 give wrong results.
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4**

Each test encodes the CORRECT behaviour and is marked ``xfail(strict=True)`` with
the finding it reproduces. A fix removes only the marker. The bugs are
deterministic, so each property is scoped to the concrete repro workbooks from the
live test, built here with openpyxl into ``tmp_path``. Tests that need the Referee
skip with a message when LibreOffice is not installed.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.models import Case, Mismatch, Mutant, MutationResult
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_json
from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute
from web.app import create_app

REPO = Path(__file__).resolve().parent.parent
JOB_TIMEOUT_S = 240


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


needs_referee = pytest.mark.skipif(
    not _has_soffice(), reason="LibreOffice (soffice) not installed: the Referee is unavailable"
)


# --------------------------------------------------------------------------
# Repro workbooks (from the live test report)
# --------------------------------------------------------------------------


def _book(path: Path, cells: dict[str, object], names: tuple[tuple[str, str], ...] = ()) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    for ref, value in cells.items():
        ws[ref] = value
    for name, target in names:
        wb.defined_names[name] = DefinedName(name, attr_text=target)
    wb.save(path)
    return path


def sem_index(tmp_path: Path, with_b3: bool = False) -> Path:
    """L-02 / L-03: B4 = INDEX(M1:M1,0) (R-30); the variant adds B3 = INDEX(M1:M3,0) on row 3."""
    cells: dict[str, object] = {
        "A1": "Amount", "B1": 4, "B2": "=B1*2",
        "M1": 7, "M2": 8, "M3": 9,
        "B4": "=INDEX(M1:M1,0)",
    }
    if with_b3:
        cells["B3"] = "=INDEX(M1:M3,0)"
    return _book(tmp_path / ("sem_index_b3.xlsx" if with_b3 else "sem_index.xlsx"), cells)


def sum_text(tmp_path: Path) -> Path:
    """L-02 (task 3.4): B2 = SUM("5",B1), a documented R-24 divergence.

    The Referee (LibreOffice) gives #VALUE!, Ghost follows Excel and gives 5 + B1,
    so every case is a mismatch whose Referee value is an Excel error
    (``.kiro/steering/excel-semantics.md``, "Where LibreOffice differs from Excel").
    """
    return _book(tmp_path / "sum_text.xlsx", {"A1": "Amount", "B1": 4, "B2": '=SUM("5",B1)'})


def tier(tmp_path: Path) -> Path:
    """L-04: tier rule on a calculated cell."""
    return _book(tmp_path / "tier.xlsx", {
        "A2": "Quantity", "B2": 3,
        "A3": "Price", "B3": 25.5,
        "A4": "Total", "B4": "=B2*B3",
        "A5": "Tier", "B5": '=IF(B4>=500,"Gold","Standard")',
    })


def sem_names(tmp_path: Path) -> Path:
    """L-05: C4 uses the dynamic name Dyn (OFFSET), which is not converted."""
    return _book(
        tmp_path / "sem_names.xlsx",
        {
            "A2": "Quantity", "B2": 30,
            "D1": "Bulk level", "E1": 50,
            "C2": "=Bulk*2", "C3": '=IF(B2>=Bulk,"bulk","small")', "C4": "=Dyn*2",
        },
        names=(("Bulk", "Calc!$E$1"), ("Dyn", "OFFSET(Calc!$E$1,0,0)")),
    )


# --------------------------------------------------------------------------
# Web helpers (FastAPI TestClient, as a browser would)
# --------------------------------------------------------------------------

_BOX = re.compile(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>')


def _boxes(page: str) -> dict[str, dict[str, list[str]]]:
    """Offered and pre-checked checkbox values on the autopsy page."""
    out = {"offered": {"inputs": [], "outputs": []}, "checked": {"inputs": [], "outputs": []}}
    for kind, value, rest in _BOX.findall(page):
        value = htmlmod.unescape(value)
        out["offered"][kind].append(value)
        if "checked" in rest:
            out["checked"][kind].append(value)
    return out


def _upload(tmp_path: Path, workbook: Path):
    app = create_app(session_root=tmp_path / "sessions")
    c = TestClient(app)
    r = c.post("/upload", files={"file": (workbook.name, workbook.read_bytes(),
                                          "application/octet-stream")})
    assert r.status_code == 200, r.text
    page = c.get("/autopsy")
    assert page.status_code == 200, page.text
    return app, c, page.text


def _verify(app, c: TestClient, inputs: list[str], outputs: list[str]):
    r = c.post("/verify", data={"inputs": inputs, "outputs": outputs})
    if r.status_code != 200:
        return r, None
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, JOB_TIMEOUT_S)
    return r, job


def _report(c: TestClient, job) -> dict | None:
    rep = c.get(f"/run/{job.id}/report.json")
    return json.loads(rep.content) if rep.status_code == 200 else None


def _tail(job) -> str:
    return "\n".join(job.events[-8:]) if job else ""


# --------------------------------------------------------------------------
# L-02: the report crashes on Excel error values
# --------------------------------------------------------------------------


def test_l02_report_to_json_serialises_excel_errors():
    mismatch = Mismatch(
        case=Case(inputs={"amount": 4}, referee={"y": Decimal("9")}, actual={"y": ExcelError("#VALUE!")}),
        output="y", cell="Calc!B3", mismatch_class="translation bug", minimal=True,
    )
    mutant = Mutant(
        mutant_id="M-00000001", operator="constant_plus_one", location="Calc!B4", killed=True,
        killed_by=Case(inputs={"amount": 4}, referee={"y": Decimal("7")}, actual={"y": ExcelError("#REF!")}),
    )
    report = build_report(
        seed=20261204, mode="faithful", cases_tested=1, passed=False,
        mismatches=[mismatch], mutation=MutationResult(mutants=[mutant], killed=1, total=1),
    )
    text = report_to_json(report)
    data = json.loads(text)
    assert data["mismatches"][0]["actual"]["y"] == "#VALUE!"
    assert data["mutation"]["mutants"][0]["killed_by"]["actual"]["y"] == "#REF!"
    page = render_html(report)
    assert "#VALUE!" in page and "#REF!" in page


@needs_referee
def test_l02_sem_index_b4_web_job_writes_report(tmp_path):
    app, c, _ = _upload(tmp_path, sem_index(tmp_path))
    r, job = _verify(app, c, ["Calc!B1"], ["Calc!B4"])
    assert r.status_code == 200, r.text
    assert job.status == "done", (job.status, job.error, _tail(job))
    data = _report(c, job)
    assert data is not None, ("report.json not available", job.error, _tail(job))
    assert data["mode"] == "faithful" and data["passed"] is True, data.get("mismatches")
    assert c.get(f"/run/{job.id}/report.html").status_code == 200
    mutation = data["mutation"]
    assert mutation.get("status") != "not checked" and mutation["total"] >= 1, mutation


def test_l02_report_write_failure_panel_text(tmp_path):
    app = create_app(session_root=tmp_path / "sessions")
    c = TestClient(app)
    assert c.post("/sample/haunted").status_code == 200
    # The CLI process dies the way it did live: an uncaught TypeError while
    # serialising an ExcelError, exit code 1, no report written.
    code = (
        "import json; from ghost.runtime.excel import ExcelError; "
        "print('[faithful] PASS'); json.dumps({'y': ExcelError('#REF!')})"
    )
    app.state.runner._command = lambda m, mode, seed, cases: [sys.executable, "-c", code]
    r, job = _verify(app, c, ["Calculator!B2"], ["Calculator!B11"])
    assert r.status_code == 200, r.text
    assert job.status == "failed", job.status
    panel = c.get(f"/run/{job.id}/panel").text
    for text in (job.error or "", panel):
        assert "Verification found mismatches." not in text, job.error
        assert "The report could not be written" in text, job.error
        assert "TypeError" in text, job.error
        for banned in (tempfile.gettempdir(), str(tmp_path), str(REPO)):
            assert banned not in text


@needs_referee
def test_l02_mismatch_holding_excel_error_is_reported(tmp_path):
    """Task 3.4: a mismatch whose Referee value is #VALUE! still gives a report listing it."""
    app, c, _ = _upload(tmp_path, sum_text(tmp_path))
    r, job = _verify(app, c, ["Calc!B1"], ["Calc!B2"])
    assert r.status_code == 200, r.text
    # A real mismatch: the job fails as a verification result, not as a crash.
    assert job.status == "failed", (job.status, job.error, _tail(job))
    assert job.error == "Verification found mismatches.", (job.error, _tail(job))
    data = _report(c, job)
    assert data is not None, ("report.json not available", job.error, _tail(job))
    assert data["passed"] is False
    assert data["mismatches"], data
    for m in data["mismatches"]:
        assert m["cell"] == "Calc!B2" and m["class"] == "translation bug", m
        assert m["expected"][m["output"]] == "#VALUE!", m
        amount = Decimal(str(m["inputs"]["amount"]))
        assert Decimal(m["actual"][m["output"]]) == amount + 5, m
    page = c.get(f"/run/{job.id}/report.html")
    assert page.status_code == 200
    assert "#VALUE!" in htmlmod.unescape(page.text)


@needs_referee
def test_l02_cli_and_mcp_write_reports_with_excel_errors(tmp_path, capsys):
    """Task 3.4: the L-02 repro through ``ghost verify`` and the MCP report tools."""
    from ghost import cli
    from mcp_server.server import call_tool_sync

    wb = sem_index(tmp_path)
    mdir = tmp_path / "mig"
    assert cli.main(["convert", str(wb), "--migration", str(mdir),
                     "--inputs", "Calc!B1", "--outputs", "Calc!B4"]) == 0
    rc = cli.main(["verify", str(mdir), "--mode", "faithful", "--cases", "50",
                   "--mutation-cases", "20"])
    out = capsys.readouterr()
    assert rc == 0, (out.out[-2000:], out.err[-2000:])
    data = json.loads((mdir / "proof-report.json").read_text(encoding="utf-8"))
    assert data["passed"] is True and data["mutation"]["total"] >= 1, data["mutation"]
    # The live crash: a mutant's counterexample holds an Excel error. It is now written as text.
    # Live (before task 3.7) the error was #REF! from the constant_minus_one mutant
    # INDEX(M1:M1,-1). Task 3.7 measured a negative INDEX index on the Referee
    # (LibreOffice 26.8.3.1 and 7.4.7.2: #VALUE!) and Ghost now gives #VALUE! too, so
    # either error text is accepted here (owner decision, 2026-11-24).
    killed_by = [m["killed_by"] for m in data["mutation"]["mutants"] if m.get("killed_by")]
    errors = [e for e in ("#REF!", "#VALUE!")
              if any(e in m["actual"].values() for m in killed_by)]
    assert errors, killed_by
    assert errors[0] in (mdir / "proof-report.html").read_text(encoding="utf-8")

    payload, is_error = call_tool_sync(
        "generate_proof_report", {"migration_dir": str(mdir), "mode": "faithful", "cases": 50})
    assert not is_error, payload
    assert payload["passed"] is True and payload["report"]["passed"] is True, payload
    assert (mdir / "proof-report.json").is_file() and (mdir / "proof-report.html").is_file()

    payload, is_error = call_tool_sync("verify_implementation", {
        "workbook": str(wb), "module": str(mdir / "logic.py"),
        "mapping": str(mdir / "mapping.yaml"), "cases": 50})
    assert not is_error, payload
    assert payload["passed"] is True and payload["mismatches"] == [], payload

    # A mismatch holding an Excel error reaches the MCP payload as its text.
    wb2 = sum_text(tmp_path)
    mdir2 = tmp_path / "mig_sum"
    assert cli.main(["convert", str(wb2), "--migration", str(mdir2),
                     "--inputs", "Calc!B1", "--outputs", "Calc!B2"]) == 0
    payload, is_error = call_tool_sync("verify_implementation", {
        "workbook": str(wb2), "module": str(mdir2 / "logic.py"),
        "mapping": str(mdir2 / "mapping.yaml"), "cases": 20})
    assert not is_error, payload
    assert payload["passed"] is False and payload["mismatches"], payload
    json.dumps(payload)  # the MCP wire format is JSON
    assert all(m["case"]["referee"][m["output"]] == "#VALUE!" for m in payload["mismatches"]), (
        payload["mismatches"])


# --------------------------------------------------------------------------
# L-03: INDEX(range,0) ignores implicit intersection
# --------------------------------------------------------------------------


@needs_referee
def test_l03_index_row0_inside_range_matches_referee(tmp_path):
    path = sem_index(tmp_path, with_b3=True)
    wb = load_workbook(str(path))
    mapping = generate_mapping(wb, {"Calc!B1": "INPUT", "Calc!B3": "OUTPUT"})
    (in_name,) = mapping.inputs
    (out_name,) = mapping.outputs
    ghost = load_compute(emit_python(wb, mapping))({in_name: 4})[out_name]
    with RefereeClient(None, path) as ref:
        referee = ref.eval({"Calc!B1": 4}, ["Calc!B3"])["Calc!B3"]
    referee = referee["error"] if isinstance(referee, dict) else referee
    assert values_equal(referee, 9, 1e-6), referee
    assert values_equal(referee, ghost, 1e-6), {"referee": referee, "ghost": ghost}


@needs_referee
def test_l03_sem_index_b3_b4_web_job_passes_faithful(tmp_path):
    """Task 3.8: the L-02 repro with B3 = INDEX(M1:M3,0) added as an output passes Faithful."""
    app, c, _ = _upload(tmp_path, sem_index(tmp_path, with_b3=True))
    r, job = _verify(app, c, ["Calc!B1"], ["Calc!B3", "Calc!B4"])
    assert r.status_code == 200, r.text
    assert job.status == "done", (job.status, job.error, _tail(job))
    data = _report(c, job)
    assert data is not None, ("report.json not available", job.error, _tail(job))
    assert data["mode"] == "faithful" and data["passed"] is True, data.get("mismatches")
    assert data["mismatches"] == [], data["mismatches"]
    assert c.get(f"/run/{job.id}/report.html").status_code == 200
    mutation = data["mutation"]
    assert mutation.get("status") != "not checked" and mutation["total"] >= 1, mutation


# --------------------------------------------------------------------------
# L-04: tier rule on a calculated cell is not proved at the boundary
# --------------------------------------------------------------------------


@needs_referee
def test_l04_tier_exact_hit_and_flip_mutant_killed(tmp_path):
    app, c, page = _upload(tmp_path, tier(tmp_path))
    boxes = _boxes(page)["checked"]
    assert boxes == {"inputs": ["Calc!B2", "Calc!B3"], "outputs": ["Calc!B5"]}, boxes
    r, job = _verify(app, c, boxes["inputs"], boxes["outputs"])
    assert r.status_code == 200, r.text
    data = _report(c, job)
    assert data is not None, ("report.json not available", job.status, job.error, _tail(job))
    assert data["passed"] is True, data.get("mismatches")

    problems = []
    b5 = [b for b in data["boundaries"] if b["cell"] == "Calc!B5"]
    if not any(b.get("exact") is not None for b in b5):
        problems.append(("no exact hit on Calc!B5", [
            (b["input_name"], b.get("below"), b.get("above"), b.get("exact")) for b in b5]))

    flips = [m for m in data["mutation"]["mutants"]
             if m["location"] == "Calc!B5" and m["operator"] == "flip_comparison"]
    if not flips:
        problems.append("no flip_comparison mutant on Calc!B5")
    for m in flips:
        if not m["killed"]:
            problems.append(("survived", m["mutant_id"], m.get("survivor_reason")))
            continue
        inputs = m["killed_by"]["inputs"]
        total = Decimal(str(inputs["quantity"])) * Decimal(str(inputs["price"]))
        if total != 500:
            problems.append(("killed away from Total = 500", m["mutant_id"], inputs))
    assert not problems, problems


# --------------------------------------------------------------------------
# L-05: a not-converted output is pre-checked, then fails as a "translation bug"
# --------------------------------------------------------------------------


def test_l05_autopsy_does_not_offer_not_converted_output(tmp_path):
    _, _, page = _upload(tmp_path, sem_names(tmp_path))
    boxes = _boxes(page)
    assert "Calc!C4" in htmlmod.unescape(page), "autopsy should still list Calc!C4 as not converted"
    assert "Calc!C4" not in boxes["checked"]["outputs"], boxes
    assert "Calc!C4" not in boxes["offered"]["outputs"], boxes
    assert boxes["checked"]["outputs"] == ["Calc!C2", "Calc!C3"], boxes


def test_l05_explicit_not_converted_output_is_rejected(tmp_path):
    app, c, _ = _upload(tmp_path, sem_names(tmp_path))
    r, job = _verify(app, c, ["Calc!B2", "Calc!E1"], ["Calc!C2", "Calc!C3", "Calc!C4"])
    accepted = None
    if job is not None:  # the request was accepted: record what the job did
        data = _report(c, job)
        accepted = {
            "status": job.status, "error": job.error,
            "mismatches": [(m["class"], m["output"], m["actual"].get(m["output"]))
                           for m in (data or {}).get("mismatches", [])],
            "mutation": (data or {}).get("mutation"),
        }
    assert r.status_code == 422, accepted
    body = htmlmod.unescape(r.text)
    assert "Calc!C4" in body, body
    assert "not converted" in body.lower() or "dynamic name" in body.lower(), body
    assert "translation bug" not in body
