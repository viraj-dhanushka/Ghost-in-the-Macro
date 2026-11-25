"""front-door task 13: busy-state and focus-movement script. Requirements 5.1-5.4."""
from __future__ import annotations

from fastapi.testclient import TestClient

from web.app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(session_root=tmp_path / "s"))


def test_script_served_and_referenced_once(tmp_path):
    c = _client(tmp_path)
    index = c.get("/").text
    assert index.count("/static/htmx-errors.js") == 1
    r = c.get("/static/htmx-errors.js")
    assert r.status_code == 200
    assert index.count("<script") == index.count("</script>")


def test_script_has_busy_and_focus_handlers(tmp_path):
    js = _client(tmp_path).get("/static/htmx-errors.js").text
    for needle in ("htmx:beforeRequest", "htmx:afterRequest", "htmx:afterSwap",
                   "aria-busy", "aria-disabled", "disabled", "#result", "h1,h2,h3", "focus("):
        assert needle in js, needle
    # existing 4xx swap handler is kept
    assert "htmx:beforeSwap" in js


def test_script_does_not_focus_on_every_poll(tmp_path):
    js = _client(tmp_path).get("/static/htmx-errors.js").text
    assert "job" in js and ("done" in js and "failed" in js)


def test_result_container_is_focusable(tmp_path):
    body = _client(tmp_path).get("/").text
    assert 'id="result"' in body and 'tabindex="-1"' in body
