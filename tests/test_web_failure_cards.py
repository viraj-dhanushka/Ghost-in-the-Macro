"""front-door task 4: Failure_Cards and the 404 page (Requirements 10.1-10.10).

Written before the implementation. Selectors the implementation must provide
in ``web/templates/_failure_card.html`` (design.md, "Failure cards"):

* card root: ``class="failure-card"`` with ``data-kind="<kind>"``;
* the Pinned_Error_Text, unchanged, inside the one ``role="alert"`` element;
* ``class="failure-title"`` and ``class="failure-next-step"`` as separate
  elements, outside the alert element;
* a visible severity label ``class="failure-severity"`` (Requirement 10.10).

No LibreOffice is needed: jobs run stand-in commands.
"""
from __future__ import annotations

import html as htmlmod
import re
import sys
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from ghost.ingest.limits import MAX_FILE_BYTES
from web.app import create_app

HX = {"hx-request": "true"}
VERIFY_FORM = {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
               "outputs": ["Calculator!B11"]}
PATH_RE = re.compile(r"/(Users|home|tmp|var|private|root)/|ghost-sessions|ghost-referee|\.venv")


class _Card(HTMLParser):
    """Collects the failure card's parts by class / role, with text and nesting."""

    VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.cards: list[dict] = []
        self.alerts: list[dict] = []
        self.titles: list[dict] = []
        self.nexts: list[dict] = []
        self.severities: list[dict] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in self.VOID:
            return
        classes = (a.get("class") or "").split()
        node = {"tag": tag, "text": [], "attrs": a,
                "in_alert": any(n["alert"] for n in self.stack), "alert": a.get("role") == "alert"}
        self.stack.append(node)
        if "failure-card" in classes:
            self.cards.append(node)
        if node["alert"]:
            self.alerts.append(node)
        if "failure-title" in classes:
            self.titles.append(node)
        if "failure-next-step" in classes:
            self.nexts.append(node)
        if "failure-severity" in classes:
            self.severities.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for n in self.stack:
            n["text"].append(data)


def _text(node) -> str:
    return " ".join("".join(node["text"]).split())


def _parse(body: str) -> _Card:
    p = _Card()
    p.feed(body)
    return p


def _norm(s: str) -> str:
    return " ".join(htmlmod.unescape(s).split())


def _assert_card(body: str, kind: str, pinned: str, tmp_path) -> _Card:
    p = _parse(body)
    assert len(p.cards) == 1, f"expected one .failure-card, got {len(p.cards)}"
    assert p.cards[0]["attrs"].get("data-kind") == kind
    assert len(p.alerts) == 1, "exactly one role=alert element"
    assert _norm(pinned) in _norm(_text(p.alerts[0])), (pinned, _text(p.alerts[0]))
    assert len(p.titles) == 1 and _text(p.titles[0]), "a non-empty failure-title"
    assert len(p.nexts) == 1 and _text(p.nexts[0]), "a non-empty failure-next-step"
    for part in (p.titles[0], p.nexts[0]):
        assert not part["in_alert"] and not part["alert"], "title/next step sit outside the alert"
    assert _norm(pinned) not in _norm(_text(p.titles[0]) + " " + _text(p.nexts[0]))
    assert p.severities and _text(p.severities[0]), "severity label in text (10.10)"
    assert not PATH_RE.search(body) and str(tmp_path) not in body
    return p


def _client(tmp_path, **kw):
    app = create_app(session_root=tmp_path / "s", **kw)
    return TestClient(app), app


def _command(code: str):
    return lambda mdir, mode, seed, cases: [sys.executable, "-c", code]


def _run_job(c, app, command, timeout_s=None):
    app.state.runner._command = command
    if timeout_s is not None:
        app.state.runner.timeout_s = timeout_s
    assert c.post("/sample/haunted").status_code == 200
    first = c.post("/verify", data=VERIFY_FORM, headers=HX)
    assert first.status_code == 200
    job_id = first.text.split("/run/")[1].split("/")[0]
    app.state.runner.wait(job_id, 30)
    panel = c.get(f"/run/{job_id}/panel", headers=HX)
    return job_id, panel


def _job_error(app, job_id) -> str:
    for j in app.state.runner._jobs.values():
        if j.id == job_id:
            return j.error
    raise AssertionError("job not found")


# -- Requirement 10.1 ---------------------------------------------------------
def test_session_expired_card(tmp_path):
    c, _ = _client(tmp_path)
    r = c.get("/autopsy", headers=HX)  # no session cookie
    assert r.status_code == 409
    p = _assert_card(r.text, "session_expired", "Choose a workbook or a sample first.", tmp_path)
    assert "/" in p.links  # link or button to start over


def test_session_expired_card_for_unknown_cookie(tmp_path):
    c, _ = _client(tmp_path)
    c.cookies.set("ghost_session", "not-a-real-token")
    r = c.get("/autopsy", headers=HX)
    _assert_card(r.text, "session_expired", "Choose a workbook or a sample first.", tmp_path)


# -- Requirement 10.2 ---------------------------------------------------------
def test_job_failed_card(tmp_path):
    c, app = _client(tmp_path)
    job_id, panel = _run_job(c, app, _command("import sys; sys.exit(3)"))
    msg = _job_error(app, job_id)
    assert msg == "Verification stopped with exit code 3."
    _assert_card(panel.text, "job_failed", msg, tmp_path)


# -- Requirement 10.3 ---------------------------------------------------------
def test_job_timed_out_card(tmp_path):
    c, app = _client(tmp_path)
    job_id, panel = _run_job(c, app, _command("import time; time.sleep(30)"), timeout_s=0.5)
    msg = _job_error(app, job_id)
    assert msg == "Verification exceeded the 0.5 s timeout."
    _assert_card(panel.text, "job_timed_out", msg, tmp_path)


# -- Requirement 10.4 ---------------------------------------------------------
def test_referee_unavailable_card_from_job_error(tmp_path):
    c, app = _client(tmp_path)
    missing = lambda mdir, mode, seed, cases: ["/nonexistent-dir/soffice"]  # noqa: E731
    job_id, panel = _run_job(c, app, missing)
    msg = _job_error(app, job_id)
    assert "soffice" in msg
    _assert_card(panel.text, "referee_unavailable", msg, tmp_path)


def test_healthz_503_is_still_json_for_referee_unavailable(tmp_path):
    c, app = _client(tmp_path)
    app.state.referee_check = lambda: {"available": False, "reason": "soffice not found"}
    r = c.get("/healthz")
    assert r.status_code == 503 and r.json()["referee"]["available"] is False


# -- Requirement 10.5 ---------------------------------------------------------
def test_file_rejected_card_422(tmp_path):
    c, _ = _client(tmp_path)
    plain = c.post("/upload", files={"file": ("bad.xlsx", b"not a workbook")})
    assert plain.status_code == 422
    msg = plain.json()["error"]
    r = c.post("/upload", files={"file": ("bad.xlsx", b"not a workbook")}, headers=HX)
    assert r.status_code == 422
    _assert_card(r.text, "file_rejected", msg, tmp_path)


def test_file_rejected_card_413(tmp_path):
    c, _ = _client(tmp_path)
    big = b"0" * (MAX_FILE_BYTES + 1)
    r = c.post("/upload", files={"file": ("big.xlsx", big)}, headers=HX)
    assert r.status_code == 413
    _assert_card(r.text, "file_rejected",
                 f"File is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MB limit.", tmp_path)


# -- Requirements 10.6 and 4.3 ------------------------------------------------
def test_unmatched_route_renders_not_found_card_with_link_home(tmp_path):
    c, _ = _client(tmp_path)
    r = c.get("/no/such/page", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    p = _parse(r.text)
    assert len(p.cards) == 1 and p.cards[0]["attrs"].get("data-kind") == "not_found"
    assert len(p.alerts) == 1 and _text(p.alerts[0])
    assert len(p.titles) == 1 and len(p.nexts) == 1
    assert "/" in p.links
    assert not PATH_RE.search(r.text) and str(tmp_path) not in r.text


def test_unknown_sample_renders_not_found_card(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/sample/nope", headers=HX)
    assert r.status_code == 404
    _assert_card(r.text, "not_found", "Unknown sample 'nope'.", tmp_path)


def test_unknown_run_renders_not_found_card_with_pinned_text(tmp_path):
    c, _ = _client(tmp_path)
    c.get("/")  # establish a session
    r = c.get("/run/does-not-exist/panel", headers=HX)
    assert r.status_code == 404
    _assert_card(r.text, "not_found", "Unknown verification run.", tmp_path)
