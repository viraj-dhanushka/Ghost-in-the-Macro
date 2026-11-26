"""Unit tests for the MCP server tools (task 11.1).

Requirements: 12.3, 12.4, 12.5, 12.6, 12.11.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import anyio
import pytest

from mcp_server import server as srv
from ghost.referee.locate import RefereeUnavailable, locate_soffice

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TOOLS = {
    "analyze_workbook", "list_rules", "get_dependencies", "find_inconsistencies",
    "extract_vba", "evaluate_original", "boundary_cases", "check_against_excel_cache",
    "verify_implementation", "mutation_check", "record_decision", "generate_proof_report",
    "recommend_route", "prepare_handoff",
}


def _build_sample(name: str, out: Path) -> Path:
    path = ROOT / "samples" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod.build(out)


@pytest.fixture(scope="module")
def haunted(tmp_path_factory) -> Path:
    return _build_sample("make_haunted", tmp_path_factory.mktemp("mcp") / "haunted.xlsx")


def _have_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


def test_all_fourteen_tools_registered():
    assert set(srv.TOOLS) == EXPECTED_TOOLS


def test_list_tools_via_server_has_schemas():
    tools = anyio.run(srv.build_server().list_tools)
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert all(t.input_schema.get("type") == "object" for t in tools)


def test_mutation_check_requires_migration_dir():
    payload, is_error = srv.call_tool_sync("mutation_check", {})
    assert is_error
    assert payload["error"]["argument"] == "migration_dir"


def test_recommend_route_returns_route_without_command(haunted, tmp_path):
    payload, is_error = srv.call_tool_sync(
        "recommend_route", {"workbook": str(haunted), "migration_dir": str(tmp_path)}
    )
    assert not is_error
    assert payload["route"] == "Ghost converts"
    assert payload["atx_command"] is None and payload["atx_command_executed"] is False
    assert "Ghost converts" in (tmp_path / "design.md").read_text()


def test_invalid_argument_names_the_argument(haunted):
    payload, is_error = srv.call_tool_sync("get_dependencies", {"workbook": str(haunted)})
    assert is_error
    assert payload["error"]["type"] == "invalid_argument"
    assert payload["error"]["argument"] == "cell"


def test_unknown_argument_and_missing_file_are_named(haunted):
    payload, _ = srv.call_tool_sync("find_inconsistencies", {"workbook": str(haunted), "bogus": 1})
    assert payload["error"]["argument"] == "bogus"
    payload, is_error = srv.call_tool_sync("analyze_workbook", {"workbook": "/nonexistent.xlsx"})
    assert is_error and payload["error"]["argument"] == "workbook"


def test_unknown_tool_is_structured_error():
    payload, is_error = srv.call_tool_sync("nope", {})
    assert is_error and payload["error"]["type"] == "unknown_tool"


def test_find_inconsistencies_raises_f001(haunted):
    payload, is_error = srv.call_tool_sync("find_inconsistencies", {"workbook": str(haunted)})
    assert not is_error
    assert [f["finding_id"] for f in payload["findings"]] == ["F-001"]


def test_analyze_and_rules_and_dependencies(haunted):
    payload, is_error = srv.call_tool_sync("analyze_workbook", {"workbook": str(haunted)})
    assert not is_error and payload["metrics"]["formula_count"] > 0
    payload, _ = srv.call_tool_sync("list_rules", {"workbook": str(haunted)})
    assert payload["rules"] and all(r["rule_id"].startswith("R-") for r in payload["rules"])
    json.dumps(payload)  # fully JSON-serialisable


def test_extract_vba_is_read_only(haunted):
    before = Path(haunted).read_bytes()
    payload, is_error = srv.call_tool_sync("extract_vba", {"workbook": str(haunted)})
    assert not is_error and payload["read_only"] is True and payload["modules"] == []
    assert Path(haunted).read_bytes() == before


def test_record_decision_requires_fields_and_writes(tmp_path):
    mdir = tmp_path / "mig"
    mdir.mkdir()
    payload, is_error = srv.call_tool_sync(
        "record_decision",
        {"migration_dir": str(mdir), "behaviour": "x", "reason": "y", "author": "a"},
    )
    assert is_error and payload["error"]["type"] == "invalid_argument"
    assert not (mdir / "decisions.yaml").exists()
    payload, is_error = srv.call_tool_sync(
        "record_decision",
        {"migration_dir": str(mdir), "finding_id": "F-001", "behaviour": "Bulk is 50 or more",
         "reason": "consistency", "author": "tester", "date": "2026-11-30"},
    )
    assert not is_error and payload["decision"]["decision_id"] == "D-001"


def test_verify_implementation_rejects_bad_mapping(haunted):
    payload, is_error = srv.call_tool_sync(
        "verify_implementation",
        {"workbook": str(haunted), "module": "def compute(i): return {}", "mapping": {"inputs": 3}},
    )
    assert is_error and payload["error"]["argument"].startswith("mapping")


@pytest.mark.skipif(not _have_soffice(), reason="LibreOffice not available")
def test_evaluate_original_returns_referee_values(haunted):
    from ghost.cli import _analyse

    an = _analyse(haunted)
    out = sorted(r for r, v in an.roles.items() if v == "OUTPUT")[:1]
    payload, is_error = srv.call_tool_sync(
        "evaluate_original", {"workbook": str(haunted), "inputs": {}, "outputs": out}
    )
    assert not is_error and set(payload["values"]) == set(out)
# Review fix 6.6 (Requirement 12.11): argument errors name the argument, never "referee_error".
@pytest.mark.parametrize("bad", [{"x": 1}, [1, 2], (1, 2)])
def test_evaluate_original_non_scalar_input_names_the_cell(haunted, monkeypatch, bad):
    def _no_referee(*a, **k):
        raise AssertionError("the Referee must not start for an invalid argument")
    monkeypatch.setattr(srv, "RefereeClient", _no_referee)
    from ghost.cli import _analyse
    an = _analyse(haunted)
    cell = sorted(r for r, v in an.roles.items() if v == "INPUT")[0]
    out = sorted(r for r, v in an.roles.items() if v == "OUTPUT")[:1]
    payload, is_error = srv.call_tool_sync(
        "evaluate_original", {"workbook": str(haunted), "inputs": {cell: bad}, "outputs": out}
    )
    assert is_error
    assert payload["error"]["type"] == "invalid_argument"
    assert payload["error"]["argument"] == f"inputs.{cell}"
    assert f"inputs.{cell}" in payload["error"]["message"]
def test_boundary_cases_and_verify_name_bad_arguments(haunted, monkeypatch):
    monkeypatch.setattr(srv, "RefereeClient", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("the Referee must not start for an invalid argument")))
    payload, is_error = srv.call_tool_sync(
        "boundary_cases", {"workbook": str(haunted), "inputs": [{"a": 1}]}
    )
    assert is_error and payload["error"]["type"] == "invalid_argument"
    assert payload["error"]["argument"].startswith("inputs")
    payload, is_error = srv.call_tool_sync(
        "verify_implementation",
        {"workbook": str(haunted), "module": "x", "mapping": {"inputs": {}, "outputs": {}},
         "cases": "many"},
    )
    assert is_error and payload["error"]["type"] == "invalid_argument"
    assert payload["error"]["argument"] == "cases"


def test_jsonable_serialises_excel_errors_in_tool_payloads():
    """L-02 (live-fixes-2026-11-24, task 3.2): MCP payloads holding Excel errors (for
    example verify_implementation's mismatches) serialise them as their code text, for
    the runtime class and for a vendored copy's class (a separate class object)."""
    from decimal import Decimal

    from ghost.models import BoundaryResult, Case, Mismatch
    from ghost.runtime.excel import ExcelError

    class Vendored:
        __slots__ = ("code",)

        def __init__(self, code):
            self.code = code

    Vendored.__name__ = "ExcelError"
    payload = {
        "mismatches": [Mismatch(
            case=Case(inputs={"amount": Decimal("4")}, referee={"y": ExcelError("#VALUE!")},
                      actual={"y": Vendored("#REF!")}),
            output="y", cell="Calc!B3", mismatch_class="translation bug",
        )],
        "boundaries": [BoundaryResult(cell="Calc!B5", input_name="q", threshold=Decimal("50"),
                                      exact_hits=[{"last_unchanged": ExcelError("#N/A"),
                                                   "first_changed": Decimal("50")}])],
        "value": Vendored("#DIV/0!"),
    }
    out = srv.jsonable(payload)
    text = json.dumps(out, sort_keys=True)  # what call_tool / the MCP wiring sends
    assert "ExcelError(" not in text
    case = out["mismatches"][0]["case"]
    assert case == {"inputs": {"amount": "4"}, "referee": {"y": "#VALUE!"}, "actual": {"y": "#REF!"}}
    assert out["boundaries"][0]["exact_hits"] == [{"last_unchanged": "#N/A", "first_changed": "50"}]
    assert out["value"] == "#DIV/0!"


def test_jsonable_still_rejects_unknown_types_inside_models():
    """Only Excel errors get a fallback; other unknown objects are not silently stringified."""
    from ghost.models import Case

    with pytest.raises(Exception, match="not JSON serializable|serialize"):
        srv.jsonable(Case(inputs={"x": object()}))
