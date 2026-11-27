"""Last fix round, item 2: any other exception from load_workbook becomes the normal 422 "File rejected" card."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import openpyxl
from fastapi.testclient import TestClient

from web.app import create_app

HX = {"hx-request": "true"}


def letters(i: int) -> str:
    """Spreadsheet column letters for any positive index (openpyxl stops at 18,278)."""
    out = ""
    while i:
        i, rem = divmod(i - 1, 26)
        out = chr(65 + rem) + out
    return out


def wide_row_book(tmp_path: Path, cells: int = 18_279) -> bytes:
    """A workbook whose one row has 18,279 cells: columns past XFD (16,384), which openpyxl rejects."""
    src = tmp_path / "w.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = 1
    wb.save(src)
    row = "".join(f'<c r="{letters(i)}1"><v>1</v></c>' for i in range(1, cells + 1)).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                import re
                data = re.sub(rb"<row [^>]*>.*?</row>", b'<row r="1">' + row + b"</row>", data, flags=re.S)
            zout.writestr(info.filename, data)
    return out.getvalue()


def test_a_row_of_18279_cells_gives_the_file_rejected_card_and_no_temp_file(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    r = c.post("/upload", files={"file": ("wide.xlsx", wide_row_book(tmp_path))}, headers=HX)
    assert r.status_code == 422
    assert 'data-kind="file_rejected"' in r.text and "Traceback" not in r.text
    assert not list((tmp_path / "s").rglob("upload.xlsx"))


def test_any_other_exception_from_the_loader_is_a_422_card(tmp_path, monkeypatch):
    import web.app as app_mod

    def boom(path):
        raise RuntimeError("secret internals /Users/x/y")

    monkeypatch.setattr(app_mod, "load_workbook", boom)
    c = TestClient(create_app(session_root=tmp_path / "s"))
    r = c.post("/upload", files={"file": ("a.xlsx", b"PK")}, headers=HX)
    assert r.status_code == 422 and 'data-kind="file_rejected"' in r.text
    assert "secret internals" not in r.text and "/Users/" not in r.text
    assert not list((tmp_path / "s").rglob("upload.xlsx"))
