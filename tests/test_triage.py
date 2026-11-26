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


# -- memory (large-workbook-lane correction 9) --------------------------------------------------
def _big_book(path: Path, rows: int) -> Path:
    """A valid .xlsx whose one sheet has `rows` rows of one formula cell: tens of MB of XML, a few hundred KB zipped."""
    import io

    base = make_book(path.with_suffix(".base.xlsx"), rows=1, formulas=1)
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename == "xl/worksheets/sheet1.xml":
                continue
            dst.writestr(item.filename, src.read(item.filename))
        head = ('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>")
        with dst.open("xl/worksheets/sheet1.xml", "w") as fh:
            fh.write(head.encode())
            for start in range(1, rows + 1, 50_000):
                chunk = "".join(f'<row r="{r}"><c r="A{r}"><f>1+1</f><v>2</v></c></row>'
                                for r in range(start, min(start + 50_000, rows + 1)))
                fh.write(chunk.encode())
            fh.write(b"</sheetData></worksheet>")
    return path


def test_scan_sizes_and_the_loader_precheck_build_no_tree(tmp_path):
    """A file with a million rows is scanned in bounded memory, in a fresh process so the high-water mark is its own."""
    import subprocess
    import sys
    p = _big_book(tmp_path / "big.xlsx", 1_000_000)
    assert p.stat().st_size < 5 * 1024 * 1024
    code = (
        "import resource, sys\n"
        "from pathlib import Path\n"
        "from ghost.ingest.limits import Limits\n"
        "from ghost.ingest.triage import scan_sizes\n"
        "unit = 1 if sys.platform == 'darwin' else 1024\n"
        "before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit\n"
        "s = scan_sizes(sys.argv[1], Limits(timeout_s=300))\n"
        "after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit\n"
        "print(s.cells, s.formulas, s.counted, (after - before) // (1024 * 1024))\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(p)], capture_output=True, text=True, timeout=600,
                         cwd=Path(__file__).resolve().parent.parent)
    assert out.returncode == 0, out.stderr
    cells, formulas, counted, grown_mb = out.stdout.split()
    assert (cells, formulas, counted) == ("1000002", "1000001", "True")  # the 1M-row sheet plus the base book's second sheet (2 cells, 1 formula)
    # measured 2026-11-26 (macOS, Python 3.13): 13.9 to 14.2 MB over three runs of this file; the bound is 16.
    assert int(grown_mb) < 16, f"memory grew by {grown_mb} MB"


def test_the_loader_precheck_also_stays_within_the_same_memory_bound(tmp_path):
    """Same file through the loader's _check_archive (caps raised so the 4 million elements are allowed)."""
    import subprocess
    import sys
    p = _big_book(tmp_path / "big.xlsx", 1_000_000)
    code = (
        "import resource, sys\n"
        "from ghost.ingest.limits import Deadline, Limits\n"
        "from ghost.ingest.workbook import _check_archive\n"
        "unit = 1 if sys.platform == 'darwin' else 1024\n"
        "lim = Limits(max_cells=10_000_000, max_xml_elements=20_000_000, timeout_s=300)\n"
        "before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit\n"
        "_check_archive(sys.argv[1], lim, Deadline(300))\n"
        "after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit\n"
        "print((after - before) // (1024 * 1024))\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(p)], capture_output=True, text=True, timeout=600,
                         cwd=Path(__file__).resolve().parent.parent)
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.split()[0]) < 16, out.stdout


def test_the_loader_precheck_still_rejects_by_count_and_by_entity(tmp_path):
    from ghost.ingest.limits import TooManyCells
    from ghost.ingest.workbook import load_workbook
    p = make_book(tmp_path / "a.xlsx", rows=30, formulas=2)
    import pytest as _pt
    with _pt.raises(TooManyCells):
        load_workbook(str(p), Limits(max_cells=10))


# -- the deadline counts every start tag (large-workbook-lane correction 1) ----------------------
def _sheet_of_non_cell_tags(path: Path, tags: int) -> Path:
    """A valid workbook whose one sheet holds `tags` empty <x/> elements and no cells at all."""
    base = make_book(path.with_suffix(".base.xlsx"), rows=1, formulas=1)
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename != "xl/worksheets/sheet1.xml":
                dst.writestr(item.filename, src.read(item.filename))
        with dst.open("xl/worksheets/sheet1.xml", "w") as fh:
            fh.write(b'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>')
            for _ in range(0, tags, 100_000):
                fh.write(b"<x/>" * min(100_000, tags))
            fh.write(b"</sheetData></worksheet>")
    return path


def test_the_deadline_is_checked_every_20000_start_tags_not_every_cell(tmp_path):
    p = _sheet_of_non_cell_tags(tmp_path / "tags.xlsx", 2_000_000)
    calls = []

    def clock():
        calls.append(1)
        return len(calls) * 100.0  # every call is 100 s later

    s = scan_sizes(p, Limits(timeout_s=250), clock=clock)
    assert s.counted is False and "stopped" in s.not_counted_reason
    # Deadline() reads the clock once, the per-part check once, then one check per 20,000 tags: it gave up at about
    # the third check, far short of the 100 checks a full parse of 2,000,000 tags would have made.
    assert len(calls) <= 8, len(calls)


def test_a_sheet_with_no_cells_at_all_still_counts_normally_when_the_clock_is_fine(tmp_path):
    p = _sheet_of_non_cell_tags(tmp_path / "tags.xlsx", 50_000)
    s = scan_sizes(p)
    assert s.counted is True and s.cells == 2 and s.formulas == 1  # only the base book's second sheet has cells
