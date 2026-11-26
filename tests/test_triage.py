"""Size triage without loading the workbook (large-workbook-lane, Requirement 1 and Property 1).
Written before `ghost/ingest/triage.py` exists. No LibreOffice needed.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import openpyxl
import pytest

from ghost.ingest.limits import Limits, UnsupportedFormat
from ghost.ingest.triage import SizeProfile, scan_sizes


def make_book(path: Path, rows: int = 4, formulas: int = 2) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for r in range(1, rows + 1):
        ws.cell(r, 1, r)
    for r in range(1, formulas + 1):
        ws.cell(r, 2, f"=A{r}*2")
    ws2 = wb.create_sheet("Other")
    ws2["A1"] = "x"
    ws2["B1"] = "=Sheet1!A1+1"
    wb.save(path)
    return path


def add_junk_vba(path: Path) -> Path:
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("xl/vbaProject.bin", b"this is not an OLE file")
    return path


def test_counts_cells_and_formulas_by_streaming(tmp_path):
    p = make_book(tmp_path / "a.xlsx", rows=4, formulas=2)
    s = scan_sizes(p)
    assert isinstance(s, SizeProfile)
    assert s.file_bytes == p.stat().st_size
    assert s.cells == 4 + 2 + 2  # Sheet1: A1:A4, B1:B2; Other: A1, B1
    assert s.formulas == 3
    assert s.counted is True and s.not_counted_reason is None
    assert s.exceeded(Limits()) == ()


def test_the_formula_count_equals_what_the_ingest_loader_counts(tmp_path):
    from ghost.ingest.workbook import load_workbook
    p = make_book(tmp_path / "a.xlsx", rows=30, formulas=25)
    wb = load_workbook(str(p))
    assert scan_sizes(p).formulas == sum(1 for c in wb.cells.values() if c.formula)


def test_triage_never_loads_the_workbook(tmp_path, monkeypatch):
    p = make_book(tmp_path / "a.xlsx")
    import ghost.ingest.workbook as ingest

    def boom(*a, **k):
        raise AssertionError("the workbook was loaded")

    monkeypatch.setattr(openpyxl, "load_workbook", boom)
    monkeypatch.setattr(ingest, "_opx_load", boom)
    monkeypatch.setattr(ingest, "load_workbook", boom)
    assert scan_sizes(p).formulas == 3


def test_every_limit_exceeded_is_listed_in_order(tmp_path):
    p = make_book(tmp_path / "a.xlsx")
    s = scan_sizes(p, Limits(max_bytes=10, max_cells=5, max_formulas=1))
    assert s.exceeded(Limits(max_bytes=10, max_cells=5, max_formulas=1)) == ("file size", "cells", "formulas")
    assert s.exceeded(Limits(max_cells=5)) == ("cells",)
    assert s.cells == 8 and s.formulas == 3  # exact: counting does not stop at the limit


def test_a_file_over_the_byte_limit_is_still_measured(tmp_path):
    p = make_book(tmp_path / "a.xlsx")
    s = scan_sizes(p, Limits(max_bytes=10))
    assert s.cells == 8 and "file size" in s.exceeded(Limits(max_bytes=10))


def test_a_bomb_is_not_counted_and_says_why(tmp_path):
    p = make_book(tmp_path / "a.xlsx")
    s = scan_sizes(p, Limits(max_uncompressed_bytes=10))
    assert s.cells is None and s.formulas is None and s.counted is False
    assert "expands" in s.not_counted_reason


def test_a_timeout_gives_a_lower_bound_and_says_so(tmp_path):
    p = make_book(tmp_path / "a.xlsx", rows=50, formulas=20)
    ticks = iter(range(0, 10_000, 100))
    s = scan_sizes(p, Limits(timeout_s=250), clock=lambda: next(ticks))
    assert s.counted is False
    assert "stopped" in s.not_counted_reason and "at least" in s.not_counted_reason
    assert s.cells is None or s.cells <= 8 + 100


def test_a_non_workbook_is_still_an_error(tmp_path):
    p = tmp_path / "a.xlsx"
    p.write_text("not a zip", encoding="utf-8")
    with pytest.raises(UnsupportedFormat):
        scan_sizes(p)


def test_an_unreadable_vba_project_is_reported_not_raised(tmp_path):
    p = add_junk_vba(make_book(tmp_path / "a.xlsm"))
    s = scan_sizes(p)
    assert s.vba_present is True
    assert s.vba_error and s.vba_lines == 0
    assert s.cells == 8  # the rest of the profile is intact


def test_a_workbook_without_vba_has_no_vba_figures(tmp_path):
    s = scan_sizes(make_book(tmp_path / "a.xlsx"))
    assert (s.vba_present, s.vba_lines, s.vba_modules, s.userforms, s.declares, s.vba_error) == (False, 0, 0, 0, 0, None)
