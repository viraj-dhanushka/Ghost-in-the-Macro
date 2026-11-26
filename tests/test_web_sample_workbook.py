"""GET /sample/{id}/workbook: the sample download route.

Feature: front-door, task 3 (test-first). Validates: Requirements 4.1, 4.2, 4.3,
4.4, 4.5, 4.6, 4.7. Written before the route exists; no LibreOffice needed.
"""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

import web.app as web_app
from web.app import REPO_ROOT, SAMPLES, create_app

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSM_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.12"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(session_root=tmp_path / "s"))


def _cells(content: bytes) -> dict[tuple[str, str], object]:
    wb = openpyxl.load_workbook(io.BytesIO(content))  # formulas kept as text
    return {
        (ws.title, c.coordinate): c.value
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for c in row
        if c.value is not None
    }


@pytest.mark.parametrize("sample_id", list(SAMPLES))
def test_download_returns_workbook_with_filename_and_type(client, sample_id):
    if sample_id == "macros":
        from ghost.referee.locate import RefereeUnavailable, locate_soffice
        try:
            locate_soffice()
        except RefereeUnavailable:
            pytest.skip("the macro sample is built through LibreOffice")
    r = client.get(f"/sample/{sample_id}/workbook")
    assert r.status_code == 200
    fname = SAMPLES[sample_id][1]
    assert r.headers["content-type"].split(";")[0] == (XLSM_TYPE if fname.endswith(".xlsm") else XLSX_TYPE)
    assert fname in r.headers.get("content-disposition", "")
    assert r.content[:2] == b"PK"  # a real xlsx zip, not an error page
    assert _cells(r.content)  # parses and has content


@pytest.mark.parametrize("bad_id", ["nope", "Discount", "..%2Fetc", "discount.xlsx"])
def test_unknown_sample_is_404_failure_card(client, bad_id):
    r = client.get(f"/sample/{bad_id}/workbook")
    assert r.status_code == 404
    assert 'role="alert"' in r.text
    assert "not found" in r.text.lower()


def test_responses_contain_no_server_path(client, tmp_path):
    markers = {str(REPO_ROOT), str(tmp_path), "/tmp/", "/var/folders", "/Users/"}
    responses = [client.get(f"/sample/{i}/workbook") for i in SAMPLES]
    responses.append(client.get("/sample/nope/workbook"))
    for r in responses:
        blob = "\n".join(f"{k}: {v}" for k, v in r.headers.items())
        if r.headers["content-type"].startswith("text/"):
            blob += r.text
        for marker in markers:
            assert marker not in blob, marker


@pytest.mark.parametrize("sample_id", list(SAMPLES))
def test_two_downloads_have_identical_cells_and_formulas(client, sample_id):
    a = client.get(f"/sample/{sample_id}/workbook")
    b = client.get(f"/sample/{sample_id}/workbook")
    assert a.status_code == b.status_code == 200
    ca, cb = _cells(a.content), _cells(b.content)
    assert ca == cb
    assert any(isinstance(v, str) and v.startswith("=") for v in ca.values())


@pytest.mark.parametrize("sample_id", list(SAMPLES))
def test_download_builds_only_in_a_temporary_directory(client, tmp_path, monkeypatch, sample_id):
    calls: list[tuple[str, Path]] = []
    real = web_app._build_sample

    def spy(sid, dest):
        calls.append((sid, Path(dest)))
        return real(sid, dest)

    monkeypatch.setattr(web_app, "_build_sample", spy)
    # Create a session first so a session folder exists that must stay untouched.
    assert client.post("/sample/discount").status_code == 200
    calls.clear()
    session_files = sorted(p for p in (tmp_path / "s").rglob("*"))
    graveyard = REPO_ROOT / "graveyard"
    graveyard_before = sorted(graveyard.rglob("*")) if graveyard.exists() else []
    samples_before = sorted((REPO_ROOT / "samples").rglob("*.xlsx"))

    assert client.get(f"/sample/{sample_id}/workbook").status_code == 200

    assert calls, "route must go through web.app._build_sample"
    forbidden = [(tmp_path / "s").resolve(), (REPO_ROOT / "samples").resolve(), graveyard.resolve()]
    for sid, dest in calls:
        assert sid == sample_id
        resolved = dest.resolve()
        for root in forbidden:
            assert root not in resolved.parents, f"{resolved} is inside {root}"
    assert sorted(p for p in (tmp_path / "s").rglob("*")) == session_files
    assert (sorted(graveyard.rglob("*")) if graveyard.exists() else []) == graveyard_before
    assert sorted((REPO_ROOT / "samples").rglob("*.xlsx")) == samples_before
