"""R-17: cell-count cap enforced in the pre-scan, before openpyxl loads anything.

Validates: Requirements 1.17, 2.17.
"""

from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

import ghost.ingest.workbook as ingest_workbook
from ghost.ingest.limits import MAX_CELLS, TooManyCells
from ghost.ingest.workbook import load_workbook
from web.app import create_app


def _big_workbook(path, rows: int, cols: int) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Data")
    for r in range(1, rows + 1):
        ws.append([r * c for c in range(1, cols + 1)])
    wb.save(path)


@pytest.fixture(scope="module")
def big_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("big") / "cells_250k.xlsx"
    _big_workbook(path, rows=5_000, cols=50)  # 250,000 cells
    return path


def test_max_cells_value():
    assert MAX_CELLS == 200_000


def test_oversized_workbook_rejected_fast_before_openpyxl(big_file, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("openpyxl must not load a workbook over MAX_CELLS")

    monkeypatch.setattr(ingest_workbook, "_opx_load", boom)
    start = time.monotonic()
    with pytest.raises(TooManyCells) as exc:
        load_workbook(str(big_file))
    assert time.monotonic() - start < 5.0
    msg = str(exc.value)
    assert "200,000" in msg and "cells" in msg


def test_web_upload_rejects_oversized_workbook(big_file, tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    data = big_file.read_bytes()
    start = time.monotonic()
    r = c.post("/upload", files={"file": ("big.xlsx", io.BytesIO(data), "application/octet-stream")})
    assert time.monotonic() - start < 5.0
    assert r.status_code in (413, 422)
    assert "200,000" in r.json()["error"]


def test_bundled_samples_still_upload_and_analyse(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    for sample in ("discount", "haunted", "scenarios"):
        r = c.post(f"/sample/{sample}")
        assert r.status_code == 200, (sample, r.text[:200])
        assert c.get("/autopsy").status_code == 200
