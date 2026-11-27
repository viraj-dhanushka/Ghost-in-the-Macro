"""Hostile workbook shapes against the upload path (final round, Part 1, items 1 to 5).

Written before the fix. A reviewer's tested patch was read and re-implemented, not copied. Each shape is either
refused by the pre-scan or loads fast with small memory. No LibreOffice.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import openpyxl
import pytest

from ghost.ingest.limits import Deadline, Limits, MAX_CELLS, TooLarge, TooManyCells
from ghost.ingest.triage import scan_sizes
from ghost.ingest.workbook import _check_archive, load_workbook

ROOT = Path(__file__).resolve().parent.parent
SHEET = "xl/worksheets/sheet1.xml"


def small_book(path: Path, rows: int = 12, cols: int = 10) -> Path:
    """A valid workbook of rows x cols numeric cells and a few formulas (120 cells by default)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            ws.cell(r, c, r * c)
    ws["L1"] = "=A1+B1"
    ws["L2"] = "=A2*2"
    wb.save(path)
    return path


def rewrite(src: Path, dst: Path, edit) -> Path:
    """Copy a zip, letting `edit(name, data) -> (name, data)` change each part."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            name, data = edit(info.filename, zin.read(info.filename))
            zout.writestr(name, data)
    return dst


def move_sheet(src: Path, dst: Path, new_name: str) -> Path:
    """Move the sheet part to `new_name` and fix the relationship and the content type so openpyxl still reads it."""
    rel_target = new_name[len("xl/"):]

    def edit(name, data):
        if name == SHEET:
            return new_name, data
        if name == "xl/_rels/workbook.xml.rels":
            return name, data.replace(b"worksheets/sheet1.xml", rel_target.encode())
        if name == "[Content_Types].xml":
            return name, data.replace(b"/xl/worksheets/sheet1.xml", ("/" + new_name).encode())
        return name, data

    return rewrite(src, dst, edit)


def inject_into_sheet(src: Path, dst: Path, xml: str) -> Path:
    def edit(name, data):
        if name == SHEET:
            return name, data.replace(b"</sheetData>", b"</sheetData>" + xml.encode())
        return name, data

    return rewrite(src, dst, edit)


def keys_and_content(wb) -> list:
    return [(k, c.value, c.formula, c.fill, c.validation) for k, c in wb.cells.items()]


# -- 1. a part is scanned whatever its name; cells are counted by structure -----------------------------
RENAMES = [
    ("xl/ws/sheet1.xml", "a moved sheet"),
    ("xl/worksheets/sheet1.XML", "an upper-case extension"),
    ("xl/worksheets/sheet1.dat", "an unknown extension"),
    ("xl/data/s1.bin", "a binary-looking name"),
]


@pytest.mark.parametrize("new_name", [n for n, _ in RENAMES], ids=[w for _, w in RENAMES])
def test_a_renamed_sheet_hits_the_cell_cap(tmp_path, new_name):
    original = small_book(tmp_path / "a.xlsx")
    renamed = move_sheet(original, tmp_path / "r.xlsx", new_name)
    lim = Limits(max_cells=50)
    with pytest.raises(TooManyCells):
        _check_archive(str(renamed), lim, Deadline(60))
    with pytest.raises(TooManyCells):
        load_workbook(str(renamed), lim)


@pytest.mark.parametrize("new_name", [n for n, _ in RENAMES], ids=[w for _, w in RENAMES])
def test_a_renamed_sheet_hits_the_element_cap(tmp_path, new_name):
    renamed = move_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "r.xlsx", new_name)
    with pytest.raises(TooLarge, match="too many XML elements"):
        _check_archive(str(renamed), Limits(max_xml_elements=100), Deadline(60))


@pytest.mark.parametrize("new_name", [n for n, _ in RENAMES], ids=[w for _, w in RENAMES])
def test_a_renamed_sheet_loads_identically_when_within_limits(tmp_path, new_name):
    original = small_book(tmp_path / "a.xlsx")
    renamed = move_sheet(original, tmp_path / "r.xlsx", new_name)
    a, b = load_workbook(str(original)), load_workbook(str(renamed))
    assert keys_and_content(a) == keys_and_content(b) and a.deps == b.deps


def test_cells_are_counted_by_structure_not_by_file_name(tmp_path):
    """A `c` element that is not under a row (a stray tag in a non-sheet part) is not a cell; one after a row is."""
    p = small_book(tmp_path / "a.xlsx")
    stray = rewrite(p, tmp_path / "stray.xlsx", lambda n, d: (n, d.replace(b"</sheetData>", b"</sheetData>") if n != "docProps/app.xml"
                                                              else d.replace(b"</Properties>", b"<c/><c/><c/></Properties>")))
    _check_archive(str(stray), Limits(max_cells=130), Deadline(60))  # 120 real cells + 3 stray tags: not counted as cells


def test_triage_counts_a_renamed_sheet_too(tmp_path):
    original = small_book(tmp_path / "a.xlsx")
    base = scan_sizes(original)
    for new_name, _ in RENAMES:
        renamed = move_sheet(original, tmp_path / "r.xlsx", new_name)
        s = scan_sizes(renamed)
        assert (s.cells, s.formulas) == (base.cells, base.formulas), new_name


# -- 2. only stored cells are walked --------------------------------------------------------------------
def test_two_cells_far_apart_do_not_create_four_million(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "=OJ10000*2"
    ws["OJ10000"] = 21
    p = tmp_path / "sparse.xlsx"
    wb.save(p)
    t0 = time.monotonic()
    loaded = load_workbook(str(p))
    assert time.monotonic() - t0 < 2.0
    assert list(loaded.cells) == ["Sheet!A1", "Sheet!OJ10000"]
    assert loaded.cells["Sheet!A1"].formula == "=OJ10000*2"


def test_sparse_cells_stay_small_in_memory(tmp_path):
    wb = openpyxl.Workbook()
    wb.active["A1"] = 1
    wb.active["OJ10000"] = 2
    p = tmp_path / "sparse.xlsx"
    wb.save(p)
    code = (
        "import resource, sys, time\n"
        "from ghost.ingest.workbook import load_workbook\n"
        "u = 1 if sys.platform == 'darwin' else 1024\n"
        "load_workbook(sys.argv[1])  # warm-up: imports\n"
        "b0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u\n"
        "t0 = time.monotonic()\n"
        "w = load_workbook(sys.argv[1])\n"
        "print(len(w.cells), round(time.monotonic() - t0, 2), (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u - b0) // 1048576)\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(p)], capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    n, secs, grown = out.stdout.split()
    assert n == "2" and float(secs) < 2.0 and int(grown) < 50, out.stdout


def test_validation_only_positions_are_not_stored_now_and_were_not_before(tmp_path):
    """The old loader stored a cell only if it had a value or a formula, so empty positions that a data validation
    covers were never stored (the three validations of the discount sample sit on cells that have values, and are in
    the pinned baseline). The new walk does not create them either."""
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = 5
    ws["B3"] = 7
    dv = DataValidation(type="whole", operator="between", formula1="0", formula2="9")
    dv.add("B2:B4")
    ws.add_data_validation(dv)
    p = tmp_path / "v.xlsx"
    wb.save(p)
    loaded = load_workbook(str(p))
    assert list(loaded.cells) == ["Sheet!A1", "Sheet!B3"]
    assert loaded.cells["Sheet!B3"].validation and not loaded.cells["Sheet!A1"].validation


# -- 3. ranged elements are capped in the pre-scan ------------------------------------------------------
def test_one_large_merge_is_refused_quickly(tmp_path):
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "m.xlsx",
                          '<mergeCells count="1"><mergeCell ref="A1:ZZ50000"/></mergeCells>')
    t0 = time.monotonic()
    with pytest.raises(TooLarge, match="merged, hyperlinked or commented"):
        load_workbook(str(p))
    assert time.monotonic() - t0 < 2.0


def test_one_ranged_hyperlink_is_refused_quickly(tmp_path):
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "h.xlsx",
                          '<hyperlinks><hyperlink ref="A1:ZZ50000" display="x" location="S!A1"/></hyperlinks>')
    t0 = time.monotonic()
    with pytest.raises(TooLarge, match="merged, hyperlinked or commented"):
        load_workbook(str(p))
    assert time.monotonic() - t0 < 2.0


def test_one_ranged_comment_is_refused_quickly(tmp_path):
    comments = ('<?xml version="1.0"?><comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<authors><author>a</author></authors><commentList><comment ref="A1:ZZ50000" authorId="0">'
                '<text><r><t>x</t></r></text></comment></commentList></comments>')
    src = small_book(tmp_path / "a.xlsx")
    dst = tmp_path / "c.xlsx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, zin.read(info.filename))
        zout.writestr("xl/comments/comment1.xml", comments)  # the part is scanned whatever refers to it
    t0 = time.monotonic()
    with pytest.raises(TooLarge, match="merged, hyperlinked or commented"):
        load_workbook(str(dst))
    assert time.monotonic() - t0 < 2.0


def test_an_unreasonable_number_of_merges_is_refused_even_when_each_is_small(tmp_path):
    merges = "".join(f'<mergeCell ref="A{i}:B{i}"/>' for i in range(1, 20_002))
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "many.xlsx", f"<mergeCells>{merges}</mergeCells>")
    with pytest.raises(TooLarge, match="merged, hyperlinked or commented"):
        _check_archive(str(p), Limits(), Deadline(60))


def test_an_unreasonable_number_of_hyperlinks_is_refused_even_when_each_is_small(tmp_path):
    links = "".join(f'<hyperlink ref="A{i}" location="S!A1"/>' for i in range(1, 20_002))
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "many.xlsx", f"<hyperlinks>{links}</hyperlinks>")
    with pytest.raises(TooLarge, match="merged, hyperlinked or commented"):
        _check_archive(str(p), Limits(), Deadline(60))


def test_a_data_validation_over_a_whole_column_still_loads(tmp_path):
    """A whole-column validation is common and creates no cells, so it is not a ranged element in the sense of the cap."""
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "dv.xlsx",
                          '<dataValidations count="1"><dataValidation type="whole" sqref="A1:A1048576">'
                          "<formula1>0</formula1></dataValidation></dataValidations>")
    _check_archive(str(p), Limits(), Deadline(60))


def test_small_ranged_elements_are_fine(tmp_path):
    p = inject_into_sheet(small_book(tmp_path / "a.xlsx"), tmp_path / "ok.xlsx",
                          '<mergeCells count="1"><mergeCell ref="A1:C2"/></mergeCells>')
    _check_archive(str(p), Limits(), Deadline(60))
    assert load_workbook(str(p)).sheets == ["S"]


# -- 4. nothing legitimate changed ---------------------------------------------------------------------
BASELINE = json.loads((ROOT / "tests" / "fixtures" / "ingest_baseline_ac7035a.json").read_text(encoding="utf-8"))


def _digest(wb) -> dict:
    h = hashlib.sha256()
    for k, c in wb.cells.items():
        h.update(repr((k, c.value, c.formula, c.fill, c.validation)).encode())
    d = hashlib.sha256(repr([(k, sorted(v)) for k, v in wb.deps.items()]).encode()).hexdigest()
    return {"cells": len(wb.cells), "order_and_content_sha256": h.hexdigest(), "deps_sha256": d, "sheets": wb.sheets,
            "validations": sum(1 for c in wb.cells.values() if c.validation)}


def test_every_sample_loads_with_identical_cells_order_content_and_dependencies(tmp_path):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_discount, make_haunted, make_scenarios, make_traps
    finally:
        sys.path.remove(str(ROOT / "samples"))
    files = {"discount.xlsx": make_discount.build(tmp_path / "discount.xlsx"),
             "haunted.xlsx": make_haunted.build(tmp_path / "haunted.xlsx"),
             "scenarios.xlsx": make_scenarios.build(tmp_path / "scenarios.xlsx"),
             "graveyard_haunted.xlsx": ROOT / "graveyard" / "haunted.xlsx"}
    make_traps.build().save(tmp_path / "traps.xlsx")
    files["traps.xlsx"] = tmp_path / "traps.xlsx"
    for name, path in files.items():
        assert _digest(load_workbook(str(path))) == BASELINE[name], name
    assert BASELINE["discount.xlsx"]["validations"] == 3  # the validation cells are part of what is pinned


def test_the_macro_sample_loads_identically():
    pytest.importorskip("ghost.referee.locate")
    from ghost.referee.locate import RefereeUnavailable, locate_soffice
    try:
        locate_soffice()
    except RefereeUnavailable:
        pytest.skip("LibreOffice not installed")
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_xlsm
    finally:
        sys.path.remove(str(ROOT / "samples"))
    with tempfile.TemporaryDirectory() as t:
        p = make_xlsm.build(Path(t) / "discount_vba.xlsm")
        assert _digest(load_workbook(str(p))) == BASELINE["discount_vba.xlsm"]


def _reference_cells(path: Path) -> list:
    """The old loader's walk, reduced to what it kept: every position of each sheet's bounding box, in row then column
    order, skipping positions with nothing to store."""
    wb = openpyxl.load_workbook(path, data_only=False)
    out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    out.append((f"{ws.title}!{c.coordinate}", c.value))
    return out


def test_a_legitimate_workbook_at_the_cell_limit_loads_with_the_same_cells_in_the_same_order(tmp_path):
    rows, cols = 20_000, 10  # exactly MAX_CELLS (200,000) stored cells
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Big")
    for r in range(1, rows + 1):
        row = [r * c for c in range(1, cols)]
        row.append(f"=A{r}+B{r}" if r <= 5_000 else r)
        ws.append(row)
    p = tmp_path / "big.xlsx"
    wb.save(p)
    assert rows * cols == MAX_CELLS
    loaded = load_workbook(str(p))
    got = [(k, c.formula or c.value) for k, c in loaded.cells.items()]
    want = [(k, v) for k, v in _reference_cells(p)]
    assert len(got) == MAX_CELLS and got == want
    assert len(loaded.deps) == 5_000


def test_one_cell_over_the_limit_is_still_refused(tmp_path):
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Big")
    for _ in range(20_000):
        ws.append(list(range(10)))
    ws.append([1])
    p = tmp_path / "over.xlsx"
    wb.save(p)
    with pytest.raises(TooManyCells):
        load_workbook(str(p))


# -- 5. memory: warm up once, then measure ------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "darwin", reason="measured on macOS only")
def test_the_scan_stays_under_8_mb_after_a_warm_up(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_triage import _big_book
    big = _big_book(tmp_path / "big.xlsx", 1_000_000)
    tiny = small_book(tmp_path / "tiny.xlsx")
    code = (
        "import resource, sys\n"
        "from ghost.ingest.limits import Limits\n"
        "from ghost.ingest.triage import scan_sizes\n"
        "u = 1 if sys.platform == 'darwin' else 1024\n"
        "scan_sizes(sys.argv[2])  # warm-up on a tiny workbook: the imports and parser set-up are a one-time cost\n"
        "b0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u\n"
        "s = scan_sizes(sys.argv[1], Limits(timeout_s=300))\n"
        "b1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u\n"
        "print(s.cells, round((b1 - b0) / 1048576, 1))\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(big), str(tiny)], capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    cells, grown = out.stdout.split()
    assert cells == "1000002" and float(grown) < 8.0, out.stdout


@pytest.mark.skipif(sys.platform != "darwin", reason="measured on macOS only")
def test_the_loader_prescan_stays_under_8_mb_after_a_warm_up(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_triage import _big_book
    big = _big_book(tmp_path / "big.xlsx", 1_000_000)
    tiny = small_book(tmp_path / "tiny.xlsx")
    code = (
        "import resource, sys\n"
        "from ghost.ingest.limits import Deadline, Limits\n"
        "from ghost.ingest.workbook import _check_archive\n"
        "u = 1 if sys.platform == 'darwin' else 1024\n"
        "lim = Limits(max_cells=10_000_000, max_xml_elements=20_000_000, timeout_s=300)\n"
        "_check_archive(sys.argv[2], lim, Deadline(300))\n"
        "b0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u\n"
        "_check_archive(sys.argv[1], lim, Deadline(300))\n"
        "print(round((resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u - b0) / 1048576, 1))\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(big), str(tiny)], capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert float(out.stdout.split()[0]) < 8.0, out.stdout
