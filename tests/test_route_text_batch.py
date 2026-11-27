"""Route text at batch size 10 (final round, item 7): unreadable VBA is not "no VBA", and a workbook with no VBA is not
told "The VBA of this workbook...". No LibreOffice."""
from __future__ import annotations

import zipfile
from pathlib import Path

import openpyxl

from ghost.models import Metrics
from ghost.router import explain_route, recommend_route, with_atx_command
from ghost.router.route import NO_VBA_REASON, UNREADABLE_VBA_REASON, route_workbook

UNREADABLE = "VBA is present but could not be read: no command is suggested"


def _book(path: Path, junk_vba: bool) -> Path:
    wb = openpyxl.Workbook()
    wb.active["A1"] = 1
    wb.active["B1"] = "=A1+1"
    wb.save(path)
    if junk_vba:
        with zipfile.ZipFile(path, "a") as z:
            z.writestr("xl/vbaProject.bin", b"not an OLE file")
    return path


def test_unreadable_vba_at_batch_10_says_so_and_suggests_no_command(tmp_path):
    p = _book(tmp_path / "v.xlsm", junk_vba=True)
    route = with_atx_command(route_workbook(str(p), batch_size=10), str(p))
    assert route.route == "AWS Transform custom"  # the batch rule
    assert route.atx_command is None
    assert UNREADABLE in route.reasons and NO_VBA_REASON not in route.reasons
    assert UNREADABLE_VBA_REASON == UNREADABLE
    assert "VBA: not readable" in route.parts


def test_no_vba_at_batch_10_still_says_no_vba(tmp_path):
    p = _book(tmp_path / "n.xlsx", junk_vba=False)
    route = with_atx_command(route_workbook(str(p), batch_size=10), str(p))
    assert route.atx_command is None and NO_VBA_REASON in route.reasons and UNREADABLE not in route.reasons


def test_explain_route_for_a_no_vba_workbook_does_not_open_with_the_vba_of_this_workbook():
    route = with_atx_command(recommend_route(Metrics(formula_count=4), 10))
    text = explain_route(route)
    body = text.split("**Recommended route: AWS Transform custom.**", 1)[1].lstrip()
    assert not body.startswith("The VBA of this workbook")
    assert "no VBA to hand to AWS Transform custom" in body.split("\n\n")[0]
    assert "batch" in body.split("\n\n")[0].lower()
    assert NO_VBA_REASON in text and "atx custom def exec" not in text


def test_explain_route_for_unreadable_vba_says_that_and_not_that_there_is_no_vba(tmp_path):
    p = _book(tmp_path / "v.xlsm", junk_vba=True)
    route = with_atx_command(route_workbook(str(p), batch_size=10), str(p))
    first = explain_route(route).split("**Recommended route: AWS Transform custom.**", 1)[1].lstrip().split("\n\n")[0]
    assert "VBA is present but could not be read" in first
    assert not first.startswith("The VBA of this workbook") and "no VBA" not in first


def test_a_workbook_with_vba_still_opens_with_the_vba_sentence():
    route = with_atx_command(recommend_route(Metrics(userform_count=9, vba_line_count=30, module_count=1)))
    first = explain_route(route).split("**Recommended route: AWS Transform custom.**", 1)[1].lstrip()
    assert first.startswith("The VBA of this workbook is better suited to AWS Transform custom.")
