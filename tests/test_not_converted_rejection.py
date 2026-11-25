"""L-05 (task 3.15): an explicit not-converted or not-verifiable output is rejected.

Web ``POST /verify`` gives 422, the MCP tools give ``invalid_argument`` naming
``outputs.<cell>``, and ``ghost convert/verify`` exits with a CliError message, all
through ``ghost.cli.require_verifiable_outputs``. The report lists not-converted
cells in the optional ``not_converted`` field.

**Validates: Requirements 2.4, 3.7, 3.12**
"""
from __future__ import annotations

import html as htmlmod
import json

import pytest
from fastapi.testclient import TestClient

from ghost import cli
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_json
from mcp_server.server import call_tool_sync
from tests.test_live_findings import _book, _upload, _verify, needs_referee, sem_names
from web.app import create_app


def volatile_book(tmp_path):
    return _book(tmp_path / "vol.xlsx", {
        "A1": "Amount", "B1": 4, "C1": "=B1*2", "C2": "=NOW()", "C3": "=C2+1",
    })


def test_web_rejects_not_converted_output_with_422(tmp_path):
    app, c, _ = _upload(tmp_path, sem_names(tmp_path))
    r, job = _verify(app, c, ["Calc!B2", "Calc!E1"], ["Calc!C2", "Calc!C4"])
    assert job is None and r.status_code == 422
    body = htmlmod.unescape(r.text)
    assert "Calc!C4" in body and "not converted" in body
    assert "dynamic name" in body.lower() or "Dyn" in body
    assert "translation bug" not in body
    # nothing was stored: the autopsy page still shows the defaults
    assert c.get("/autopsy").status_code == 200


def test_web_rejects_volatile_output_with_422(tmp_path):
    app, c, _ = _upload(tmp_path, volatile_book(tmp_path))
    for cell in ("Calc!C2", "Calc!C3"):  # NOW() itself, and its dependant
        r, job = _verify(app, c, ["Calc!B1"], ["Calc!C1", cell])
        assert job is None and r.status_code == 422, cell
        body = htmlmod.unescape(r.text)
        assert cell in body and "not converted" in body, body
        assert "translation bug" not in body


def test_mcp_verify_implementation_invalid_argument(tmp_path):
    wb = sem_names(tmp_path)
    mapping = {
        "inputs": {"quantity": {"cell": "Calc!B2", "type": "integer"}},
        "outputs": {"calc_c4": {"cell": "Calc!C4", "type": "decimal"}},
    }
    payload, is_error = call_tool_sync("verify_implementation", {
        "workbook": str(wb), "module": "def compute(i):\n    return {'calc_c4': 0}\n",
        "mapping": mapping})
    assert is_error, payload
    err = payload["error"]
    assert err["type"] == "invalid_argument" and err["argument"] == "outputs.Calc!C4", err
    assert "not converted" in err["message"] and "Calc!C4" in err["message"]


def test_cli_convert_and_mcp_report_tools_reject(tmp_path, capsys):
    wb = sem_names(tmp_path)
    mdir = tmp_path / "mig"
    with pytest.raises(cli.CliError) as exc:
        cli.cmd_convert(type("A", (), {
            "workbook": str(wb), "migration": str(mdir), "inputs": "Calc!B2",
            "outputs": "Calc!C2,Calc!C4", "mapping": None})())
    assert "Calc!C4" in str(exc.value) and "not converted" in str(exc.value)
    assert cli.main(["convert", str(wb), "--migration", str(mdir),
                     "--inputs", "Calc!B2", "--outputs", "Calc!C4"]) != 0
    assert "Calc!C4" in capsys.readouterr().err

    # A mapping.yaml that names C4 (hand-written) is rejected at verification time.
    mdir2 = tmp_path / "mig2"
    mdir2.mkdir()
    (mdir2 / "source.yaml").write_text(f"workbook: {wb}\n", encoding="utf-8")
    (mdir2 / "mapping.yaml").write_text(
        "inputs:\n  quantity: {cell: 'Calc!B2', type: integer}\n"
        "outputs:\n  calc_c4: {cell: 'Calc!C4', type: decimal}\n", encoding="utf-8")
    for tool in ("generate_proof_report", "mutation_check"):
        payload, is_error = call_tool_sync(tool, {"migration_dir": str(mdir2)})
        assert is_error, (tool, payload)
        assert payload["error"]["type"] == "invalid_argument", payload
        assert payload["error"]["argument"] == "outputs.Calc!C4", payload
    with pytest.raises(cli.UnverifiableOutput):
        cli.run_verification(mdir2)


def test_report_lists_not_converted_and_old_reports_stay_valid():
    plain = build_report(seed=1, mode="faithful", cases_tested=1, passed=True)
    assert "not_converted" not in json.loads(report_to_json(plain))
    assert "Not converted" not in render_html(plain)
    rep = build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                       not_converted=[{"cell": "Calc!C4", "reason": "dynamic name Dyn"}])
    data = json.loads(report_to_json(rep))
    assert data["not_converted"] == [{"cell": "Calc!C4", "reason": "dynamic name Dyn"}]
    page = htmlmod.unescape(render_html(rep))
    assert "Not converted" in page and "Calc!C4" in page and "dynamic name Dyn" in page
    assert report_to_json(rep) == report_to_json(rep)


@needs_referee
def test_default_boxes_pass_faithful_and_report_lists_c4(tmp_path):
    app, c, page = _upload(tmp_path, sem_names(tmp_path))
    from tests.test_live_findings import _boxes, _report
    boxes = _boxes(page)["checked"]
    assert "Calc!C4" not in boxes["outputs"] and boxes["outputs"] == ["Calc!C2", "Calc!C3"]
    r, job = _verify(app, c, boxes["inputs"], boxes["outputs"])
    assert r.status_code == 200, r.text
    assert job.status == "done", (job.status, job.error)
    data = _report(c, job)
    assert data["mode"] == "faithful" and data["passed"] is True, data["mismatches"]
    assert [e["cell"] for e in data["not_converted"]] == ["Calc!C4"], data.get("not_converted")
    assert "Calc!C4" in htmlmod.unescape(c.get(f"/run/{job.id}/report.html").text)


def test_not_verifiable_only_cell_is_rejected_with_its_reason(tmp_path):
    """A convertible cell flagged volatile is rejected as "not verifiable as-is"."""
    from ghost.autopsy.classify import unverifiable_output_reasons
    from ghost.ingest.features import scan_features
    from ghost.ingest.workbook import load_workbook
    from ghost.models import FeatureFlag

    wb = load_workbook(str(volatile_book(tmp_path)))
    wb.features = scan_features(wb) + [
        FeatureFlag(kind="volatile", cell="Calc!C1", detail="RAND", not_verifiable=True)]
    reasons = unverifiable_output_reasons(wb, ["Calc!C1", "Calc!B1"])
    assert set(reasons) == {"Calc!C1"}
    assert reasons["Calc!C1"] == "not verifiable as-is: volatile RAND"
    with pytest.raises(cli.UnverifiableOutput) as exc:
        cli.require_verifiable_outputs(wb, ["Calc!B1", "Calc!C1"])
    assert exc.value.cell == "Calc!C1" and "not verifiable as-is" in str(exc.value)
