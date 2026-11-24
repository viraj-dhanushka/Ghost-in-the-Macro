"""Review 2026-11-24: autopsy, mapping, VBA visibility, decisions and packaging gaps.

No LibreOffice needed. Each xfail(strict=True) test states the expected behaviour and
fails today; see docs/TEST_REPORT_2026-11-24.md for evidence and suggested fixes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook

from ghost.autopsy.classify import classify
from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.thresholds import extract_thresholds
from ghost.cli import _load
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.router.explain import atx_dry_run_command
from samples import make_discount

ROOT = Path(__file__).resolve().parents[1]


def _book(path: Path, cells: dict[str, object]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "P"
    for ref, value in cells.items():
        ws[ref] = value
    wb.save(path)
    return path


def test_complementary_operators_are_not_a_finding(tmp_path):
    wb = load_workbook(str(_book(tmp_path / "p.xlsx", {"A1": 10, "B1": "=IF(A1>=50,1,0)", "B2": "=IF(A1<50,2,3)"})))
    assert detect_inconsistencies(extract_thresholds(wb)) == []


def test_input_value_is_not_treated_as_a_threshold(tmp_path):
    wb = load_workbook(str(_book(tmp_path / "p.xlsx", {"A9": 90, "E9": "=40+10", "B9": "=IF(A9>=E9,1,0)"})))
    assert [t for t in extract_thresholds(wb) if t.cell == "P!E9"] == []


def test_expression_and_percent_thresholds_are_recorded(tmp_path):
    wb = load_workbook(str(_book(tmp_path / "p.xlsx", {
        "A2": 10, "A3": 7, "A8": 0.3, "B3": "=IF(A2*A3>=500,1,0)", "B8": "=IF(A8>=50%,1,0)"})))
    found = {(t.source.cell, str(t.constant)) for t in extract_thresholds(wb)}
    assert ("P!B8", "0.5") in found and any(src == "P!B3" for src, _ in found)


def test_input_shared_by_two_formulas_is_an_input(tmp_path):
    wb = load_workbook(str(_book(tmp_path / "p.xlsx", {"A1": 10, "B1": "=IF(A1>=50,1,0)", "B2": "=A1*2"})))
    assert classify(wb)["P!A1"] == "INPUT"


def test_free_delivery_distance_is_a_parameter(tmp_path):
    wb = load_workbook(str(make_discount.build(tmp_path / "discount.xlsx")))
    assert classify(wb)["Calculator!E5"] == "PARAMETER"


def test_decimal_validation_wins_over_whole_number_sample(tmp_path):
    wb = load_workbook(str(make_discount.build(tmp_path / "discount.xlsx")))
    mapping = generate_mapping(wb)
    spec = next(s for s in mapping.inputs.values() if s.cell == "Calculator!B4")
    assert spec.type == "decimal"


def test_vba_found_in_renamed_macro_workbook(tmp_path, macro_samples):
    renamed = tmp_path / "renamed.xlsx"
    shutil.copy(macro_samples[0], renamed)
    assert _load(renamed).vba_modules


def test_upload_summary_reports_vba(tmp_path, macro_samples):
    from fastapi.testclient import TestClient

    from web.app import create_app

    app = create_app(session_root=tmp_path / "sessions")
    with TestClient(app) as c:
        r = c.post("/upload", files={"file": ("calc.xlsm", macro_samples[0].read_bytes(), "application/octet-stream")})
        assert r.status_code == 200 and r.json()["workbook"]["has_vba"] is True


def test_second_decision_for_same_finding_is_rejected(tmp_path):
    from mcp_server.server import call_tool_sync

    patch = {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="}
    args = {"migration_dir": str(tmp_path), "behaviour": "bulk is 50 or more", "reason": "r", "author": "a",
            "finding_id": "F-001", "patch": patch}
    first, first_err = call_tool_sync("record_decision", args)
    assert not first_err, first
    second, second_err = call_tool_sync("record_decision", args)
    assert second_err, second


def test_plugin_manifest_has_schema():
    manifest = json.loads((ROOT / "plugin" / "plugin.json").read_text())
    assert manifest.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def test_atx_dry_run_includes_trust_all_tools_with_non_interactive():
    cmd = atx_dry_run_command("samples/discount.xlsx").split()
    assert "-x" in cmd and ("-t" in cmd or "--trust-all-tools" in cmd)
