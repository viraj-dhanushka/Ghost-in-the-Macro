"""Upload bounds (last fix round, items 1 and 2): hostile shapes that cost time or memory without many cells.

Each shape is refused by the pre-scan or the dependency cap, or it loads in under 7 s and under 400 MB. The load runs in
a child process so that time and peak memory are the child's. A 1,000-row running total still loads. No LibreOffice.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import openpyxl
import pytest

from ghost.ingest.limits import IngestError, Limits, TooLarge
from ghost.ingest.workbook import load_workbook

ROOT = Path(__file__).resolve().parent.parent
SHEET = "xl/worksheets/sheet1.xml"
WORKBOOK = "xl/workbook.xml"

CHILD = (
    "import sys, time, resource\n"
    "from ghost.ingest.workbook import load_workbook\n"
    "from ghost.ingest.limits import IngestError\n"
    "u = 1 if sys.platform == 'darwin' else 1024\n"
    "t0 = time.monotonic()\n"
    "try:\n"
    "    w = load_workbook(sys.argv[1]); out = 'loaded %d' % len(w.cells)\n"
    "except IngestError as e:\n"
    "    out = 'refused ' + str(e)\n"
    "def peak_mb():\n"
    "    # The child's own peak. On Linux ru_maxrss can carry the parent's peak across fork and exec, so read\n"
    "    # VmHWM (this process's high-water resident set) from /proc/self/status instead.\n"
    "    if sys.platform.startswith('linux'):\n"
    "        for line in open('/proc/self/status'):\n"
    "            if line.startswith('VmHWM:'):\n"
    "                return int(line.split()[1]) // 1024\n"
    "        raise SystemExit('VmHWM not found')\n"
    "    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * u // 1048576\n"
    "print(out, '|', round(time.monotonic() - t0, 2), '|', peak_mb())\n"
)


def run_child(path: Path) -> tuple[str, float, int]:
    r = subprocess.run([sys.executable, "-c", CHILD, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    what, secs, mb = (p.strip() for p in r.stdout.strip().split("|"))
    return what, float(secs), int(mb)


def small(path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for r in range(1, 6):
        ws.cell(r, 1, r)
    ws["B1"] = "=A1+A2"
    wb.save(path)
    return path


def patch_part(src: Path, dst: Path, part: str, edit) -> Path:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            zout.writestr(info.filename, edit(data) if info.filename == part else data)
    return dst


def assert_bounded(path: Path) -> str:
    what, secs, mb = run_child(path)
    print(f"[bounds] {path.name}: {what[:60]} | {secs} s | {mb} MB peak ({sys.platform})")
    assert secs < 7, (what, secs)
    assert mb < 400, (what, mb)
    return what


def test_many_rows_with_heights_are_refused(tmp_path):
    rows = "".join(f'<row r="{i}" ht="20" customHeight="1"/>' for i in range(3, 1_900_000)).encode()
    p = patch_part(small(tmp_path / "a.xlsx"), tmp_path / "rows.xlsx", SHEET,
                   lambda d: d.replace(b"</sheetData>", rows + b"</sheetData>"))
    assert assert_bounded(p).startswith("refused")


def test_many_defined_names_are_refused(tmp_path):
    names = ("<definedNames>" + "".join(f'<definedName name="N{i}">S!$A$1</definedName>' for i in range(1_900_000))
             + "</definedNames>").encode()
    p = patch_part(small(tmp_path / "a.xlsx"), tmp_path / "names.xlsx", WORKBOOK,
                   lambda d: d.replace(b"<calcPr", names + b"<calcPr", 1) if b"<calcPr" in d else d.replace(b"</workbook>", names + b"</workbook>"))
    assert assert_bounded(p).startswith("refused")


def test_100000_data_validations_are_refused(tmp_path):
    dvs = (b'<dataValidations count="100000">'
           + "".join(f'<dataValidation type="whole" sqref="A{i}"><formula1>1</formula1></dataValidation>'
                     for i in range(1, 100_001)).encode()
           + b"</dataValidations>")
    p = patch_part(small(tmp_path / "a.xlsx"), tmp_path / "dv.xlsx", SHEET,
                   lambda d: d.replace(b"</sheetData>", b"</sheetData>" + dvs, 1))
    assert assert_bounded(p).startswith("refused")


def test_one_sqref_of_many_10000_cell_ranges_is_bounded(tmp_path):
    cols = [openpyxl.utils.get_column_letter(c) for c in range(2, 2002)]
    sqref = " ".join(f"{c}1:{c}10000" for c in cols)
    dvs = f'<dataValidations count="1"><dataValidation type="whole" sqref="{sqref}"><formula1>1</formula1></dataValidation></dataValidations>'.encode()
    p = patch_part(small(tmp_path / "a.xlsx"), tmp_path / "sq.xlsx", SHEET,
                   lambda d: d.replace(b"</sheetData>", b"</sheetData>" + dvs, 1))
    assert_bounded(p)  # loads or is refused; either is fine as long as it is quick and small


def running_total(path: Path, n: int) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for i in range(1, n + 1):
        ws.cell(i, 1, i)
        ws.cell(i, 2, f"=SUM(A$1:A{i})")
    wb.save(path)
    return path


def test_a_5000_row_running_total_is_refused_with_the_dependency_message(tmp_path):
    p = running_total(tmp_path / "rt5000.xlsx", 5000)
    assert assert_bounded(p).startswith("refused")
    with pytest.raises(TooLarge, match="Workbook formulas read too many cells in total; rejected."):
        load_workbook(str(p))


def test_a_1000_row_running_total_still_loads(tmp_path):
    p = running_total(tmp_path / "rt1000.xlsx", 1000)
    assert assert_bounded(p).startswith("loaded")


def test_20000_whole_sheet_sums_are_refused_or_bounded(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for i in range(1, 201):
        ws.cell(i, 1, i)
    for i in range(1, 20_001):
        ws.cell(i, 3, "=SUM(A1:A1048576)")
    p = tmp_path / "sums.xlsx"
    wb.save(p)
    assert assert_bounded(p).startswith("refused")


def test_19999_whole_sheet_sums_hit_the_dependency_cap(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for i in range(1, 201):
        ws.cell(i, 1, i)
    for i in range(1, 20_000):
        ws.cell(i, 3, "=SUM(A1:A1048576)")
    p = tmp_path / "sums2.xlsx"
    wb.save(p)
    with pytest.raises(IngestError) as e:
        load_workbook(str(p))
    assert "too many cells in total" in str(e.value)


def test_the_cap_is_10_times_max_cells():
    assert Limits().max_cells * 10 == 2_000_000


def _digest(wb) -> dict:
    h = hashlib.sha256()
    for k, c in wb.cells.items():
        h.update(repr((k, c.value, c.formula, c.fill, c.validation)).encode())
    d = hashlib.sha256(repr([(k, sorted(v)) for k, v in wb.deps.items()]).encode()).hexdigest()
    return {"cells": len(wb.cells), "order_and_content_sha256": h.hexdigest(), "deps_sha256": d, "sheets": wb.sheets,
            "validations": sum(1 for c in wb.cells.values() if c.validation)}


def test_every_sample_loads_identically(tmp_path):
    """The samples are gitignored: build them with their scripts and compare with the pinned baseline."""
    base = json.loads((ROOT / "tests/fixtures/ingest_baseline_ac7035a.json").read_text())
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_discount, make_haunted
    finally:
        sys.path.remove(str(ROOT / "samples"))
    files = {"discount.xlsx": make_discount.build(tmp_path / "discount.xlsx"),
             "haunted.xlsx": make_haunted.build(tmp_path / "haunted.xlsx")}
    for name, path in files.items():
        assert _digest(load_workbook(str(path))) == base[name], name
