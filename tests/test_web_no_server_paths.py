"""R-21 (paths): job events and error text never show absolute server paths.

Validates: Requirements 1.18, 2.18 (review-fixes-2026-11-24).
"""
from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from web.app import create_app
from web.paths import scrub_paths

REPO = Path(__file__).resolve().parent.parent


def test_scrub_run_dir_and_other_paths():
    run = Path("/tmp/ghost-sessions-ab/sid/run-1")
    assert scrub_paths(f"Wrote {run}/logic_intended.py (intended)", run) == "Wrote ./logic_intended.py (intended)"
    assert scrub_paths(f"Proof report: {run}", run) == "Proof report: ."
    assert scrub_paths("cwd /app/ghost/cli.py failed", run) == "cwd cli.py failed"
    assert scrub_paths("in /Users/someone/x/y.xlsx.", run) == "in y.xlsx."
    assert scrub_paths(r"C:\Users\me\file.xlsx broke") == "file.xlsx broke"


def test_scrub_keeps_ordinary_text():
    s = "cases 300/300, and/or ratio 1/2, https://example.com/a, ./rel/path.py, Calculator!B2"
    assert scrub_paths(s, Path("/tmp/x")) == s


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


def _assert_clean(text: str, banned: list[str]) -> None:
    for b in banned:
        assert b not in text, f"{b!r} leaked in: {text[:500]}"
    assert not re.search(r"(?<![\w./:~-])/(?:tmp|var|private|app|home|Users|root)\b", text), text[:500]


def test_failure_text_has_no_paths(tmp_path):
    import sys
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    c.post("/sample/haunted")
    code = "import sys; print('Wrote /tmp/ghost-x/run-1/logic.py'); print('boom /app/ghost/cli.py', file=sys.stderr); sys.exit(2)"
    app.state.runner._command = lambda m, mode, seed, cases: [sys.executable, "-c", code]
    r = c.post("/verify", data={"inputs": ["Calculator!B2"], "outputs": ["Calculator!B11"]})
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, 30)
    text = json.dumps(job.snapshot())
    _assert_clean(text, [tempfile.gettempdir(), str(REPO)])
    assert "logic.py" in text


def test_422_and_500_bodies_have_no_paths(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    r = c.post("/upload", files={"file": ("bad.xlsx", b"not a zip", "application/octet-stream")})
    assert r.status_code == 422
    _assert_clean(r.text, [tempfile.gettempdir(), str(tmp_path), str(REPO)])
    app.state.referee_check = lambda: {"available": False, "reason": "x"}


@pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")
def test_real_haunted_job_has_no_paths(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    assert c.post("/sample/haunted").status_code == 200
    r = c.post("/verify", data={
        "inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
        "outputs": ["Calculator!B11"],
    })
    assert r.status_code == 200, r.text
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, 240)
    assert job.status in ("done", "failed")
    folder = str(next(iter(app.state.sessions._sessions.values())).folder)
    banned = [folder, str(tmp_path), tempfile.gettempdir(), str(REPO)]
    snap = c.get(f"/jobs/{job_id}").json()
    assert snap["events"], "expected job output"
    _assert_clean(json.dumps(snap), banned)
    sse = c.get(f"/jobs/{job_id}/events").text
    _assert_clean(sse, banned)
    _assert_clean(c.get(f"/run/{job_id}/panel").text, banned)
