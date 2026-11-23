"""Web skeleton tests (task 12.1). Validates: Requirements 13.9, 13.10, 13.12, 13.14."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from web.app import PRIVACY_NOTE, create_app
from web.sessions import COOKIE_NAME


def _client(tmp_path, **kw):
    app = create_app(session_root=tmp_path / "s", **kw)
    return TestClient(app), app


def test_healthz_and_privacy_note(tmp_path):
    c, app = _client(tmp_path)
    app.state.referee_check = lambda: {"available": True}
    assert c.get("/healthz").json() == {"status": "ok", "referee": {"available": True}}
    r = c.get("/")
    assert r.status_code == 200 and PRIVACY_NOTE[:40] in r.text
    assert "run_macros" not in r.text and "trust" not in r.text.lower()
    assert COOKIE_NAME in c.cookies


def test_upload_rejection_shows_ingestor_error(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/upload", files={"file": ("evil.exe", io.BytesIO(b"nope"), "application/octet-stream")})
    assert r.status_code == 422
    assert "Accepted formats" in r.json()["error"]
    r = c.post("/upload", files={"file": ("a.xlsx", io.BytesIO(b"not a zip"), "application/octet-stream")})
    assert r.status_code == 422 and r.json()["error"]


def test_upload_too_large(tmp_path, monkeypatch):
    monkeypatch.setattr("web.app.MAX_FILE_BYTES", 10)
    c, _ = _client(tmp_path)
    r = c.post("/upload", files={"file": ("a.xlsx", io.BytesIO(b"x" * 100), "application/octet-stream")})
    assert r.status_code == 413


def test_sample_flow_and_session_folder_deleted(tmp_path):
    c, app = _client(tmp_path)
    r = c.post("/sample/haunted")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["workbook"]["formulas"] > 0
    assert "run_macros" not in r.text
    store = app.state.sessions
    assert len(store) == 1
    folder = next(store.root.iterdir())
    assert any(folder.iterdir())
    assert c.delete("/session").json()["ok"]
    assert not folder.exists()


def test_unknown_sample_404(tmp_path):
    c, _ = _client(tmp_path)
    assert c.post("/sample/nope").status_code == 404


def test_tampered_cookie_gets_new_session(tmp_path):
    c, app = _client(tmp_path)
    r = c.post("/sample/discount", headers={"cookie": f"{COOKIE_NAME}=abc.deadbeef"})
    assert r.status_code == 200
    assert len(app.state.sessions) == 1
    assert "abc.deadbeef" not in r.headers.get("set-cookie", "")
    assert COOKIE_NAME in r.headers.get("set-cookie", "")


def test_idle_sweep_removes_folder(tmp_path):
    t = [0.0]
    from web.sessions import SessionStore

    store = SessionStore(root=tmp_path / "x", idle_timeout_s=10, clock=lambda: t[0])
    s = store.create()
    assert s.folder.exists()
    t[0] = 5
    assert store.sweep() == []
    t[0] = 20
    assert store.sweep() == [s.sid]
    assert not s.folder.exists()
