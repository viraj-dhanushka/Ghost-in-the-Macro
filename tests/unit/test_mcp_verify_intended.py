"""MCP ``verify_implementation`` uses the three-condition Intended-mode test (R-01, task 4.3).

Needs the real Referee (LibreOffice); skipped with a message when soffice is missing.
Requirements: 1.5, 2.5.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ghost.autopsy.classify import classify
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.decisions.store import load_decisions, record
from ghost.ingest.workbook import load_workbook
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from mcp_server import server as srv
from samples import make_haunted

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available: MCP verify_implementation needs the real Referee",
                allow_module_level=True)

USER_INPUTS = ("Calculator!B2", "Calculator!B3", "Calculator!B4")


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    d = tmp_path_factory.mktemp("mcp-intended")
    path = make_haunted.build(d / "haunted.xlsx")
    wb = load_workbook(str(path))
    roles = {r: ("PARAMETER" if v == "INPUT" else v) for r, v in classify(wb, ["Calculator!B11"]).items()}
    roles.update({r: "INPUT" for r in USER_INPUTS})
    for r, v in list(roles.items()):
        if v == "OUTPUT" and r != "Calculator!B11":
            roles[r] = "INTERMEDIATE"
    mapping = generate_mapping(wb, roles)
    mig = d / "mig"
    mig.mkdir()
    record(mig, {
        "finding_id": "F-001", "behaviour": "bulk means 50 or more", "reason": "agree with discount",
        "author": "test", "date": "2026-11-24",
        "patch": {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="},
    })
    code = emit_python(wb, mapping, "intended", load_decisions(mig))
    return path, mapping.model_dump(mode="json"), mig, code


def _call(setup, module: str):
    path, mapping, mig, _ = setup
    return srv.call_tool_sync("verify_implementation", {
        "workbook": str(path), "module": module, "mapping": mapping,
        "mode": "intended", "migration_dir": str(mig), "cases": 100,
    })


def test_d001_plus_vat_bug_is_a_translation_bug(setup):
    code = setup[3]
    old = "'Calculator!E7': Decimal('0.2'),"
    assert code.count(old) == 1
    payload, is_error = _call(setup, code.replace(old, "'Calculator!E7': Decimal('0.21'),"))
    assert not is_error, payload
    assert payload["passed"] is False
    assert any(m["mismatch_class"] == "translation bug" for m in payload["mismatches"])


def test_correct_d001_module_passes_with_one_expected_difference(setup):
    payload, is_error = _call(setup, setup[3])
    assert not is_error, payload
    assert payload["passed"] is True
    ms = payload["mismatches"]
    assert len(ms) == 1 and ms[0]["mismatch_class"] == "expected by decision"
    assert ms[0]["decision_id"] == "D-001"
    assert str(ms[0]["case"]["inputs"]["quantity"]) in ("50", "50.0")


def test_response_carries_the_same_boundary_notes_as_the_cli(setup):
    """R-04: MCP uses ``_probe_flips_with_summary`` and returns what was not checked."""
    from ghost.cli import _probe_flips_with_summary

    path, mapping_json, _, code = setup
    payload, is_error = _call(setup, code)
    assert not is_error, payload
    assert isinstance(payload["boundary_notes"], list)
    from ghost.converter.mapping import Mapping

    expected = _probe_flips_with_summary(
        load_workbook(str(path)), Mapping.model_validate(mapping_json), payload["seed"]
    )[1].notes()
    assert payload["boundary_notes"] == expected
