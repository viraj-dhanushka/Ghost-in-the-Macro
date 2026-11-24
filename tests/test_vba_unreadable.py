"""R-13 guardrail: an unreadable VBA container is reported, never silently dropped."""
from __future__ import annotations
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook
from ghost.ingest.workbook import load_workbook
from web.app import create_app


def _corrupt_vba_book(tmp_path: Path) -> Path:
    plain = tmp_path / "plain.xlsx"
    wb = Workbook()
    wb.active["A1"] = 1
    wb.save(plain)
    out = tmp_path / "corrupt.xlsx"
    with zipfile.ZipFile(plain) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("xl/vbaProject.bin", b"this is not an OLE container")
    return out


def test_corrupt_vba_container_is_surfaced_not_dropped(tmp_path):
    wb = load_workbook(str(_corrupt_vba_book(tmp_path)))
    assert wb.vba_present is True
    assert wb.vba_modules == []
    assert wb.vba_error


def test_upload_summary_reports_unreadable_vba(tmp_path):
    path = _corrupt_vba_book(tmp_path)
    app = create_app(session_root=tmp_path / "sessions")
    with TestClient(app) as c:
        r = c.post("/upload", files={"file": ("c.xlsx", path.read_bytes(), "application/octet-stream")})
        assert r.status_code == 200
        wb = r.json()["workbook"]
        assert wb["has_vba"] is True
        assert wb["vba_error"].startswith("VBA present but could not be read:")
