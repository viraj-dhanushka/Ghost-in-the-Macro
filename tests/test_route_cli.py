"""`ghost route` and the MCP `recommend_route` on a workbook over Ghost's limits (large-workbook-lane,
Requirement 2). Generated workbooks, no LibreOffice."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pytest

from ghost import cli
from ghost.ingest.limits import MAX_CELLS, MAX_FORMULAS, IngestError, TooManyCells, TooManyFormulas

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def many_formulas(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("big") / "formulas.xlsx"
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("S")
    for r in range(1, MAX_FORMULAS + 2):
        ws.append([r, f"=A{r}*2"])
    wb.save(p)
    return p


@pytest.fixture(scope="module")
def many_cells(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("big") / "cells.xlsx"
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("S")
    for r in range(MAX_CELLS // 10 + 1):
        ws.append(list(range(10)))
    ws.append([1, 2])
    wb.save(p)
    return p


def test_the_ingest_error_is_what_the_old_command_would_have_shown(many_formulas):
    from ghost.ingest.workbook import load_workbook
    with pytest.raises(TooManyFormulas):
        load_workbook(str(many_formulas))


def test_route_on_an_over_limit_workbook_exits_0_with_sizes_and_reasons(many_formulas, capsys, monkeypatch):
    def no_load(*a, **k):
        raise AssertionError("the workbook was loaded")

    monkeypatch.setattr(cli, "_load", no_load)
    assert cli.main(["route", str(many_formulas)]) == 0
    out = capsys.readouterr().out
    assert "Route: Over Ghost's limits" in out
    assert f"{MAX_FORMULAS + 1:,} formulas; the limit is {MAX_FORMULAS:,} formulas" in out
    assert f"Formulas: {MAX_FORMULAS + 1:,}, not sent, not converted by Ghost (over the limit)" in out
    assert "VBA: none" in out
    assert "Not checked (the workbook was not loaded)" in out
    assert "atx" not in out  # no AWS command for a workbook with no VBA to send
    assert "AWS Transform converts" not in out


def test_route_on_too_many_cells(many_cells, capsys):
    assert cli.main(["route", str(many_cells)]) == 0
    out = capsys.readouterr().out
    assert "Route: Over Ghost's limits" in out and "cells; the limit is 200,000 cells" in out


def test_mcp_recommend_route_on_an_over_limit_workbook(many_formulas):
    from mcp_server import server as srv
    out = srv.recommend_route(srv.RecommendRouteArgs(workbook=str(many_formulas)))
    assert out["route"] == "Over Ghost's limits"
    assert any("formulas; the limit" in r for r in out["reasons"])
    assert out["atx_command"] is None and out["atx_command_executed"] is False
    assert any(p.startswith("Formulas:") for p in out["parts"])


def test_a_workbook_within_the_limits_gets_the_route_it_always_did(tmp_path, capsys):
    p = tmp_path / "small.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = 2
    wb.active["B1"] = "=A1*3"
    wb.save(p)
    assert cli.main(["route", str(p)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Route: Ghost converts\n")
    assert "  - 0 VBA lines are within the threshold of 2000" in out
    assert "VBA: none" in out and "Formulas: 1, not sent, converted by Ghost" in out


def test_a_file_that_is_not_a_workbook_is_still_an_error(tmp_path, capsys):
    p = tmp_path / "x.xlsx"
    p.write_text("no", encoding="utf-8")
    assert cli.main(["route", str(p)]) == 1
    assert "ghost: error:" in capsys.readouterr().err


def test_the_route_for_every_sample_workbook_is_unchanged(tmp_path, capsys):
    """Ghost converts for the plain samples: the reasons are the old three lines."""
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_discount
    finally:
        sys.path.remove(str(ROOT / "samples"))
    p = make_discount.build(tmp_path / "discount.xlsx")
    assert cli.main(["route", str(p)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Route: Ghost converts\n  - 0 VBA lines are within the threshold of 2000\n"
                          "  - UserForm and Declare counts are within their thresholds\n"
                          "  - batch size 1 is below 10\n")


def test_a_loaded_workbook_with_unreadable_vba_says_so_not_none(tmp_path, capsys):
    import zipfile
    p = tmp_path / "v.xlsm"
    wb = openpyxl.Workbook()
    wb.active["A1"] = 1
    wb.active["B1"] = "=A1+1"
    wb.save(p)
    with zipfile.ZipFile(p, "a") as z:
        z.writestr("xl/vbaProject.bin", b"not an OLE file")
    assert cli.main(["route", str(p)]) == 0
    out = capsys.readouterr().out
    assert "VBA: not readable" in out and "VBA: none" not in out
