"""front-door task 11: Progress_Rail rendered by /run/{id}/panel.

Requirements 7.3-7.5, 8.1-8.8, 9.1-9.4, 9.6, 9.7, 10.11, 10.12.
Jobs run a stand-in command (no LibreOffice); the finished job's status, events
and artifacts are then set by the test, from the recorded haunted fixture or
from hand-built values.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import create_app

HX = {"hx-request": "true"}
FORM = {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"], "outputs": ["Calculator!B11"]}
PATH_RE = re.compile(r"/(Users|home|tmp|var|private|root)/|ghost-sessions|ghost-referee|\.venv")
FIXTURE = Path(__file__).parent / "fixtures" / "front_door" / "haunted_run_events.json"


class _P(HTMLParser):
    VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.nodes: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        n = {"tag": tag, "attrs": dict(attrs), "text": [], "ancestors": [s["tag"] for s in self.stack],
             "anc_attrs": [s["attrs"] for s in self.stack]}
        self.stack.append(n)
        self.nodes.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for s in self.stack:
            s["text"].append(data)


def _parse(body: str) -> _P:
    p = _P()
    p.feed(body)
    return p


def _cls(n) -> list[str]:
    return (n["attrs"].get("class") or "").split()


def _text(n) -> str:
    return " ".join("".join(n["text"]).split())


def _setup(tmp_path, status, events, report=None, error=None):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    app.state.runner._command = lambda mdir, mode, seed, cases: [sys.executable, "-c", "pass"]
    assert c.post("/sample/haunted").status_code == 200
    first = c.post("/verify", data=FORM, headers=HX)
    job_id = first.text.split("/run/")[1].split("/")[0]
    app.state.runner.wait(job_id, 30)
    job = app.state.runner._jobs[job_id]
    job.status = status
    job.events = list(events)
    job.error = error
    job.artifacts.pop("proof-report.json", None)
    if report is not None:
        job.artifacts["proof-report.json"] = json.dumps(report).encode()
    return c, job_id


def _panel(c, job_id) -> str:
    r = c.get(f"/run/{job_id}/panel", headers=HX)
    assert not PATH_RE.search(r.text)
    return r.text


def _mutation(n_killed, n_total):
    return {"total": n_total, "killed": n_killed,
            "mutants": [{"mutant_id": f"m{i}", "operator": "op", "location": f"Calculator!B{i}",
                         "killed": i < n_killed} for i in range(n_total)]}


def _report(mutation=None):
    d = {"passed": True, "mode": "faithful", "seed": 20261204, "cases_tested": 10, "mismatches": []}
    if mutation is not None:
        d["mutation"] = mutation
    else:
        d["mutation"] = {"status": "not checked"}
    return d


def _tombs(p):
    return [n for n in p.nodes if "tombstone" in _cls(n)]


def test_running_neutral_tombstones_and_bar(tmp_path):
    ev = ["Starting verification", "mutation check: mutant 1/4", "mutation check: mutant 2/4"]
    c, jid = _setup(tmp_path, "running", ev)
    body = _panel(c, jid)
    p = _parse(body)
    t = _tombs(p)
    assert len(t) == 4
    assert {n["attrs"].get("data-state") for n in t} == {"neutral"}
    assert all(_text(n) for n in t)  # text label, not colour only
    bars = [n for n in p.nodes if n["tag"] == "progress" or n["attrs"].get("role") == "progressbar"]
    assert len(bars) == 1
    a = bars[0]["attrs"]
    assert (a.get("value") or a.get("aria-valuenow")) == "2"
    assert (a.get("max") or a.get("aria-valuemax")) == "4"
    assert "mutant 2 of 4" in " ".join(_text(n) for n in p.nodes if n["tag"] in ("p", "span", "div", "section"))
    assert "%" not in "".join(bar_t for bar_t in [_text(bars[0])])


def test_single_status_line_outside_polled_root(tmp_path):
    c, jid = _setup(tmp_path, "running", ["Starting verification"])
    p = _parse(_panel(c, jid))
    live = [n for n in p.nodes if "aria-live" in n["attrs"]]
    assert len(live) == 1
    s = live[0]
    assert s["attrs"].get("id") == "status-line"
    assert s["attrs"]["aria-live"] == "polite"
    assert _text(s) == "Verification started"
    root = next(n for n in p.nodes if "job" in _cls(n))
    assert "aria-live" not in root["attrs"]
    assert "hx-get" in root["attrs"]


def test_raw_log_in_details_without_aria_live(tmp_path):
    ev = ["Starting verification"] + [f"  note {i}" for i in range(20)]
    c, jid = _setup(tmp_path, "running", ev)
    p = _parse(_panel(c, jid))
    d = [n for n in p.nodes if n["tag"] == "details"]
    assert len(d) == 1 and "aria-live" not in d[0]["attrs"]
    assert "Raw log" in _text(d[0])
    for i in range(20):
        assert f"note {i}" in _text(d[0])  # full list, not the last 12
    assert not any("aria-live" in a for n in p.nodes if n["tag"] == "pre" for a in n["attrs"])


def test_queued_has_no_bar_or_grid(tmp_path):
    c, jid = _setup(tmp_path, "queued", [])
    p = _parse(_panel(c, jid))
    assert not _tombs(p)
    assert not [n for n in p.nodes if n["tag"] == "progress" or n["attrs"].get("role") == "progressbar"]
    assert next(n for n in p.nodes if n["attrs"].get("id") == "status-line")


def test_done_killed_and_survivors_match_report(tmp_path):
    ev = ["Starting verification"] + [f"mutation check: mutant {i}/5" for i in range(1, 6)] + [
        "[faithful] PASS: x", "Proof report: report.html"]
    c, jid = _setup(tmp_path, "done", ev, _report(_mutation(3, 5)))
    p = _parse(_panel(c, jid))
    t = _tombs(p)
    assert len(t) == 5
    states = [n["attrs"].get("data-state") for n in t]
    assert states.count("killed") == 3
    assert states.count("survived") == 2
    for n in t:
        assert n["attrs"]["data-state"] in _text(n)
    surv = [n for n in p.nodes if "survivors" in _cls(n)]
    assert surv
    items = [n for n in p.nodes if n["tag"] == "li" and "ul" in n["ancestors"] and "survivors" in
             [" ".join(a.get("class", "").split()) for a in n["anc_attrs"]]]
    assert len(items) == 2
    assert "m3" in _text(items[0]) and "m4" in _text(items[1])


def test_done_recorded_fixture_counts(tmp_path):
    data = json.loads(FIXTURE.read_text())
    mb = data["_meta"]["proof_report_mutation"]
    c, jid = _setup(tmp_path, "done", data["events"], _report(_mutation(mb["killed"], mb["total"])))
    p = _parse(_panel(c, jid))
    states = [n["attrs"].get("data-state") for n in _tombs(p)]
    assert states.count("killed") == mb["killed"]
    assert states.count("survived") == mb["total"] - mb["killed"]


def test_done_without_mutation_block_says_not_checked(tmp_path):
    c, jid = _setup(tmp_path, "done", ["Starting verification", "[faithful] PASS: x", "Proof report: r"],
                    _report(None))
    body = _panel(c, jid)
    p = _parse(body)
    assert not _tombs(p)
    assert "Mutation self-check: not checked" in body


def test_failed_keeps_tombstones_neutral(tmp_path):
    ev = ["Starting verification", "mutation check: mutant 1/3"]
    c, jid = _setup(tmp_path, "failed", ev, error="boom")
    p = _parse(_panel(c, jid))
    t = _tombs(p)
    assert len(t) == 3 and {n["attrs"]["data-state"] for n in t} == {"neutral"}


def test_timeout_shows_phase_reached_and_no_later(tmp_path):
    c, jid = _setup(tmp_path, "timeout", ["Starting verification"], error="Verification exceeded the 5 s timeout.")
    body = _panel(c, jid)
    p = _parse(body)
    sl = next(n for n in p.nodes if n["attrs"].get("id") == "status-line")
    assert _text(sl) == "Verification started"
    assert "Proof written" not in body and "Cases compared" not in body
    assert "Verification exceeded the 5 s timeout." in body


def test_timeout_before_any_phase_is_not_started(tmp_path):
    c, jid = _setup(tmp_path, "timeout", [], error="Verification exceeded the 5 s timeout.")
    body = _panel(c, jid)
    p = _parse(body)
    assert any(n["attrs"].get("data-not-started") == "true" for n in p.nodes)
    assert not [n for n in p.nodes if n["attrs"].get("aria-current") == "step" and "phase" in _cls(n)]
    assert "Not started" in body


def test_survivor_reason_shown_in_rail(tmp_path):
    """Guardrail: no hidden or dropped mutants; each survivor shows its reason."""
    mut = _mutation(1, 2)
    mut["mutants"][1]["survivor_reason"] = "boundary not exercised at quantity 50"
    ev = ["Starting verification", "mutation check: mutant 1/2", "mutation check: mutant 2/2",
          "[faithful] PASS: x", "Proof report: report.html"]
    c, jid = _setup(tmp_path, "done", ev, _report(mut))
    p = _parse(_panel(c, jid))
    items = [n for n in p.nodes if n["tag"] == "li" and any(
        "survivors" in (a.get("class") or "").split() for a in n["anc_attrs"])]
    assert len(items) == 1
    assert "m1" in _text(items[0])
    assert "boundary not exercised at quantity 50" in _text(items[0])
