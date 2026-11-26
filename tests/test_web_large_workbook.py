"""The web app and a workbook over Ghost's limits (large-workbook-lane, Requirement 3). No LibreOffice."""
from __future__ import annotations

import ast
import io
import re
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from ghost.ingest.limits import MAX_FILE_BYTES, MAX_FORMULAS
from web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
HX = {"hx-request": "true"}


def _client(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    return TestClient(app), app


@pytest.fixture(scope="module")
def many_formulas(tmp_path_factory) -> bytes:
    p = tmp_path_factory.mktemp("big") / "formulas.xlsx"
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("S")
    for r in range(1, MAX_FORMULAS + 2):
        ws.append([r, f"=A{r}*2"])
    wb.save(p)
    assert p.stat().st_size < MAX_FILE_BYTES
    return p.read_bytes()


def test_an_over_limit_upload_shows_a_route_card_where_the_error_was(tmp_path, many_formulas):
    c, _ = _client(tmp_path)
    r = c.post("/upload", files={"file": ("big.xlsx", io.BytesIO(many_formulas))}, headers=HX)
    assert r.status_code == 422
    t = r.text
    assert 'class="route-card"' in t
    assert "Over Ghost&#39;s limits" in t or "Over Ghost's limits" in t
    assert f"{MAX_FORMULAS + 1:,} formulas; the limit is {MAX_FORMULAS:,} formulas" in t
    assert f"Formulas: {MAX_FORMULAS + 1:,}, not converted by Ghost (over the limit)" in t
    assert "not in it" in t and "never" not in t.lower().replace("never executed", "")
    assert "VBA: none" in t
    assert "does not convert" in t.lower()
    assert "atx" not in t  # no VBA to send: no command
    assert not re.search(r"/(Users|home|tmp|var|private)/", t)


def test_the_web_path_counts_under_a_short_deadline(tmp_path, many_formulas, monkeypatch):
    seen = {}
    import ghost.ingest.triage as tri
    real = tri.scan_sizes

    def spy(path, limits=None, clock=None):
        seen["timeout"] = limits.timeout_s if limits else None
        return real(path, limits, clock)

    monkeypatch.setattr(tri, "scan_sizes", spy)
    c, _ = _client(tmp_path)
    assert c.post("/upload", files={"file": ("big.xlsx", io.BytesIO(many_formulas))}).status_code == 422
    assert seen["timeout"] is not None and seen["timeout"] <= 10


def test_the_json_answer_carries_the_route(tmp_path, many_formulas):
    c, _ = _client(tmp_path)
    r = c.post("/upload", files={"file": ("big.xlsx", io.BytesIO(many_formulas))})
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False and body["error"]
    assert body["route"]["route"] == "Over Ghost's limits"
    assert any("formulas; the limit" in x for x in body["route"]["reasons"])
    assert any(p.startswith("Formulas:") for p in body["route"]["parts"])


def test_a_file_over_5_mb_says_run_ghost_locally_and_the_cap_is_unchanged(tmp_path):
    assert MAX_FILE_BYTES == 5 * 1024 * 1024
    c, _ = _client(tmp_path)
    r = c.post("/upload", files={"file": ("big.xlsx", b"0" * (MAX_FILE_BYTES + 1))}, headers=HX)
    assert r.status_code == 413
    assert "too large for the public demo; run Ghost locally" in r.text
    assert "ghost route &lt;file&gt;" in r.text or "ghost route <file>" in r.text


def test_the_web_app_does_not_touch_challenge_handoff_receipt_or_atx():
    bad = []
    for py in (ROOT / "web").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            if any(n.startswith(("ghost.challenge", "ghost.handoff", "ghost.receipt")) or n in ("challenge", "handoff", "receipt")
                   for n in names):
                bad.append(f"{py.name}:{node.lineno}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(("atx ", "aws ")):
                if "suggested" not in py.read_text(encoding="utf-8").lower():
                    bad.append(f"{py.name}:{node.lineno}")
    assert bad == []
