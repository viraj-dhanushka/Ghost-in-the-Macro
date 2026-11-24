"""R-17: the web app caches the analysis per session and workbook."""
from __future__ import annotations

import ghost.cli as cli
import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.fixture
def counted(monkeypatch):
    calls = {"n": 0}
    real = cli.load_workbook

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(cli, "load_workbook", counting)
    return calls


def _client(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    return TestClient(app), app


def test_repeated_autopsy_parses_once(tmp_path, counted):
    c, _ = _client(tmp_path)
    c.post("/sample/haunted")
    for _ in range(3):
        assert c.get("/autopsy").status_code == 200
    assert counted["n"] == 1


def test_decision_does_not_reparse_and_state_is_fresh(tmp_path, counted):
    c, _ = _client(tmp_path)
    c.post("/sample/haunted")
    assert "D-001" not in c.get("/autopsy").text
    assert counted["n"] == 1
    ok = c.post("/decision", data={"finding_id": "F-001", "choice": "keep",
                                   "author": "Ana", "reason": "Reproduce"})
    assert ok.status_code == 200 and "D-001" in ok.text
    assert "D-001" in c.get("/autopsy").text  # decision state is not stale
    assert counted["n"] == 1


def test_new_upload_or_sample_invalidates(tmp_path, counted):
    c, app = _client(tmp_path)
    c.post("/sample/haunted")
    assert "F-001" in c.get("/autopsy").text
    c.post("/sample/discount")
    r = c.get("/autopsy")
    assert "discount.xlsx" in r.text and "F-001" not in r.text
    assert counted["n"] == 2
    # A new upload of the same path with different bytes is also seen.
    sess = next(iter(app.state.sessions._sessions.values()))
    haunted = (sess.folder / "haunted.xlsx")
    if not haunted.exists():
        c.post("/sample/haunted")
    path = sess.workbook["path"]
    data = open(path, "rb").read()
    c.post("/upload", files={"file": ("x.xlsx", data)})
    c.get("/autopsy")
    assert counted["n"] == 3


def test_changed_inputs_recompute(tmp_path, counted):
    c, app = _client(tmp_path)
    c.post("/sample/haunted")
    c.get("/autopsy")
    sess = next(iter(app.state.sessions._sessions.values()))
    sess.data["inputs"] = "Calculator!B2,Calculator!B3"
    c.get("/autopsy")
    assert counted["n"] == 2
    c.get("/autopsy")
    assert counted["n"] == 2


def test_cache_is_one_entry_and_dropped_with_session(tmp_path, counted):
    c, app = _client(tmp_path)
    c.post("/sample/haunted")
    c.get("/autopsy")
    store = app.state.sessions
    sess = next(iter(store._sessions.values()))
    assert sess.analysis_cache is not None
    c.post("/sample/discount")
    assert sess.analysis_cache is None  # invalidated on new workbook
    c.get("/autopsy")
    assert sess.analysis_cache is not None
    store.delete(sess.sid)
    assert sess.analysis_cache is None
