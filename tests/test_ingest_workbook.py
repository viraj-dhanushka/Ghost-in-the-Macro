"""Unit tests for the workbook loader (task 2.2). Requirements 1.1-1.4, 1.8-1.11."""

from __future__ import annotations

import itertools
import zipfile

import pytest
from openpyxl import Workbook as OpxWorkbook
from openpyxl.workbook.defined_name import DefinedName

from ghost.ingest.limits import (
    Limits,
    ProcessingTimeout,
    TooLarge,
    TooManyFormulas,
    UnsupportedFormat,
)
from ghost.ingest.workbook import extract_references, load_workbook


@pytest.fixture
def book(tmp_path):
    wb = OpxWorkbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"] = 10
    ws["A2"] = 5
    ws["B1"] = "=A1+A2"
    ws["B2"] = "=SUM(A1:A2)*Rate"
    other = wb.create_sheet("Other")
    other["A1"] = "=Calc!B1*2"
    wb.defined_names["Rate"] = DefinedName("Rate", attr_text="Calc!$A$2")
    p = tmp_path / "book.xlsx"
    wb.save(p)
    return str(p)


def test_loads_formulas_names_and_deps(book):
    wb = load_workbook(book)
    assert wb.sheets == ["Calc", "Other"]
    assert wb.cells["Calc!B1"].formula == "=A1+A2"
    assert wb.cells["Calc!A1"].value == 10
    assert wb.named_ranges["Rate"] == "Calc!A2"
    assert wb.deps["Calc!B1"] == {"Calc!A1", "Calc!A2"}
    assert wb.deps["Calc!B2"] == {"Calc!A1", "Calc!A2"}
    assert wb.deps["Other!A1"] == {"Calc!B1"}
    assert wb.excel_saved is False  # openpyxl writes no cached values


def test_rejects_bad_extension(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b")
    with pytest.raises(UnsupportedFormat):
        load_workbook(str(p))


def test_rejects_non_zip_xlsx(tmp_path):
    p = tmp_path / "x.xlsx"
    p.write_text("not a zip")
    with pytest.raises(UnsupportedFormat):
        load_workbook(str(p))


def test_size_limit(book):
    with pytest.raises(TooLarge):
        load_workbook(book, Limits(max_bytes=10))


def test_formula_limit(book):
    with pytest.raises(TooManyFormulas):
        load_workbook(book, Limits(max_formulas=2))


def test_timeout(book):
    ticks = itertools.count(0, 100)
    with pytest.raises(ProcessingTimeout):
        load_workbook(book, Limits(timeout_s=1), clock=lambda: float(next(ticks)))


def test_entity_xml_rejected(book, tmp_path):
    bad = tmp_path / "bad.xlsx"
    with zipfile.ZipFile(book) as src, zipfile.ZipFile(bad, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "xl/workbook.xml":
                data = data.replace(
                    b"<workbook",
                    b'<!DOCTYPE x [<!ENTITY e "boom">]><workbook',
                    1,
                )
            dst.writestr(info.filename, data)
    with pytest.raises(UnsupportedFormat):
        load_workbook(str(bad))


def test_extract_references_ranges_and_quoted_sheets():
    refs = extract_references("=SUM('My Sheet'!A1:A3)+B$2", "S")
    assert refs == {"My Sheet!A1", "My Sheet!A2", "My Sheet!A3", "S!B2"}
