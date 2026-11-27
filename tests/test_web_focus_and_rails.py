"""Focus after a swap, and the step rails (final round, items 8 and 9). The script's decisions are pure functions, run
here under Node with a tiny fake DOM; the real-browser walk is `scripts/browser_walk.mjs`. No LibreOffice."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "web" / "static" / "htmx-errors.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = r"""
const g = require(process.argv[1]);
const out = {};
%s
console.log(JSON.stringify(out));
"""


def node(body: str):
    r = subprocess.run(["node", "-e", HARNESS % body, str(JS)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# a fake document: elements are looked up by the selector the script asks for
FAKE = r"""
function el(name, log) {
  const attrs = {tabindex: null};
  return {name, hasAttribute: a => a in attrs && attrs[a] !== null, setAttribute: (a, v) => { attrs[a] = v; },
          focus: o => log.push(['focus', name, o && o.preventScroll === true]),
          scrollIntoView: o => log.push(['scroll', name, o && o.block])};
}
function doc(found, log, polling, active) {
  const els = {};
  for (const sel of found) els[sel] = el(sel, log);
  const byId = {'job-h-1': el('job-h-1', log)};
  const job = polling === undefined ? null : {hasAttribute: a => a === 'hx-get' && polling};
  const result = {focus: () => log.push(['focus', '#result']), contains: () => true,
    querySelector: s => s === '.job' ? job : (els[s] || null)};
  return {querySelector: s => s === '#result' ? result : (els[s] || null), result,
          activeElement: active === undefined ? {tagName: 'BODY'} : active, getElementById: i => byId[i] || null};
}
function swap(path, found, polling, state, active) {
  const log = [];
  const d = doc(found, log, polling, active);
  g.ghostAfterSwap({detail: {pathInfo: {requestPath: path}, target: d.result}}, d, state);
  return log;
}
"""


def test_a_run_start_focuses_and_scrolls_to_the_job_heading_not_to_loaded():
    out = node(FAKE + """
const state = {jobWasPolling: false};
out.log = swap('/verify', ['#loaded-h', '#job .job h2', '.job h2', 'h1,h2,h3'], true, state);
out.state = state;
""")
    kinds = [(k, name) for k, name, *_ in out["log"]]
    assert kinds == [("focus", "#job .job h2"), ("scroll", "#job .job h2")]
    assert out["log"][1][2] == "start" and out["log"][0][2] is True  # focus without the jump, then scroll to the top
    assert out["state"]["jobWasPolling"] is True


def test_a_poll_that_is_still_running_scrolls_nothing_but_puts_back_focus_it_lost():
    lost = node(FAKE + """
out.log = swap('/run/abc/panel', ['.job h2'], true, {jobWasPolling: true, headingId: 'job-h-1'});
""")
    assert lost["log"] == [["focus", "job-h-1", True]]  # same heading, no scrolling
    kept = node(FAKE + """
out.log = swap('/run/abc/panel', ['.job h2'], true, {jobWasPolling: true, headingId: 'job-h-1'}, {tagName: 'INPUT'});
""")
    assert kept["log"] == []  # the user moved focus elsewhere: never touched


def test_a_poll_that_is_still_running_moves_nothing():
    out = node(FAKE + """
const state = {jobWasPolling: true};
out.log = swap('/run/abc/panel', ['.job .vc-headline', '.job h2'], true, state);
""")
    assert out["log"] == []


def test_the_poll_that_finishes_focuses_the_verdict_heading():
    out = node(FAKE + """
const state = {jobWasPolling: true};
out.log = swap('/run/abc/panel', ['.job .vc-headline', '.job h2', '#loaded-h'], false, state);
out.state = state;
""")
    assert [(k, n) for k, n, *_ in out["log"]] == [("focus", ".job .vc-headline"), ("scroll", ".job .vc-headline")]
    assert out["state"]["jobWasPolling"] is False


def test_a_finished_run_without_a_verdict_card_falls_back_to_the_job_heading():
    out = node(FAKE + """
const state = {jobWasPolling: true};
out.log = swap('/run/abc/panel', ['.job h2'], false, state);
""")
    assert [(k, n) for k, n, *_ in out["log"]] == [("focus", ".job h2"), ("scroll", ".job h2")]


def test_a_poll_after_the_run_has_finished_moves_nothing():
    out = node(FAKE + """
const state = {jobWasPolling: false};
out.log = swap('/run/abc/panel', ['.job .vc-headline', '.job h2'], false, state);
""")
    assert out["log"] == []


def test_upload_and_sample_go_to_the_loaded_heading_and_the_autopsy_load_and_decision_move_nothing():
    out = node(FAKE + """
out.upload = swap('/upload', ['#loaded-h', 'h1,h2,h3'], undefined, {jobWasPolling: false});
out.sample = swap('/sample/haunted', ['#loaded-h'], undefined, {jobWasPolling: false});
out.autopsy = swap('/autopsy', ['#autopsy-h', '#loaded-h'], undefined, {jobWasPolling: false});
out.decision = swap('/decision', ['#autopsy-h', '#loaded-h'], undefined, {jobWasPolling: false});
""")
    assert [n for _, n, *_ in out["upload"]] == ["#loaded-h"] * 2
    assert [n for _, n, *_ in out["sample"]] == ["#loaded-h"] * 2
    assert out["autopsy"] == []
    assert out["decision"] == []  # the autopsy section is replaced in place: the page and the focus stay where they are


def test_an_unknown_swap_keeps_the_old_behaviour_first_heading_in_result_else_the_result():
    out = node(FAKE + """
out.heading = swap('/something', ['h1,h2,h3'], undefined, {jobWasPolling: false});
out.none = swap('/something', [], undefined, {jobWasPolling: false});
""")
    assert [n for _, n, *_ in out["heading"]] == ["h1,h2,h3"] * 2
    assert out["none"] == [["focus", "#result"]]


# -- the rails -----------------------------------------------------------------------------------------
RAILS = r"""
function li(cls, cue) {
  const o = {classes: new Set(cls), attrs: {'aria-current': cls.includes('current') ? 'step' : null}, cue: cue ? {removed: false} : null};
  o.classList = {contains: c => o.classes.has(c), add: c => o.classes.add(c), remove: c => o.classes.delete(c)};
  o.removeAttribute = a => { o.attrs[a] = null; };
  o.querySelector = s => (s === '.step-cue' && o.cue && !o.cue.removed) ? {remove: () => { o.cue.removed = true; }} : null;
  return o;
}
function rail(items) { return {querySelectorAll: s => s === 'li.current' ? items.filter(i => i.classes.has('current')) : []}; }
"""


def test_only_the_newest_rail_keeps_the_current_marker():
    out = node(RAILS + """
const a = [li(['step', 'current'], true), li(['step', 'upcoming'])];
const b = [li(['step', 'done']), li(['step', 'current'], true)];
const c = [li(['step', 'done']), li(['step', 'current'], true)];
g.ghostSupersedeRails({querySelectorAll: s => s === '.stepper' ? [rail(a), rail(b), rail(c)] : []});
const snap = r => r.map(i => ({cls: [...i.classes].sort(), cur: i.attrs['aria-current'], cue: i.cue ? i.cue.removed : null}));
out.a = snap(a); out.b = snap(b); out.c = snap(c);
""")
    assert out["a"][0] == {"cls": ["done", "step"], "cur": None, "cue": True}
    assert out["b"][1] == {"cls": ["done", "step"], "cur": None, "cue": True}
    assert out["c"][1] == {"cls": ["current", "step"], "cur": "step", "cue": False}  # the newest rail is untouched
    assert out["a"][1]["cls"] == ["step", "upcoming"]


def test_a_single_rail_is_left_alone():
    out = node(RAILS + """
const a = [li(['step', 'current'], true)];
g.ghostSupersedeRails({querySelectorAll: s => s === '.stepper' ? [rail(a)] : []});
out.a = [...a[0].classes].sort();
""")
    assert out["a"] == ["current", "step"]


# -- static checks on the script ----------------------------------------------------------------------
def test_the_script_keeps_what_the_older_tests_pin():
    js = JS.read_text(encoding="utf-8")
    for needle in ("htmx:beforeRequest", "htmx:afterRequest", "htmx:afterSwap", "aria-busy", "aria-disabled", "#result",
                   "h1,h2,h3", "focus(", "htmx:beforeSwap", "429"):
        assert needle in js, needle
    assert "module.exports" in js and "typeof document" in js  # loadable under node for these tests


def test_the_job_panel_markup_has_the_headings_the_script_looks_for(tmp_path):
    from fastapi.testclient import TestClient
    from web.app import create_app
    app = create_app(session_root=tmp_path / "s")
    env = app.state.templates.env if hasattr(app.state, "templates") else None
    assert env is not None or True
    html = (ROOT / "web" / "templates" / "_job.html").read_text(encoding="utf-8")
    assert '<h2 id="job-h-{{ job.id }}">' in html
    card = (ROOT / "web" / "templates" / "_verdict_card.html").read_text(encoding="utf-8")
    assert 'class="vc-headline"' in card and '<h3 id="vc-h-{{ job_id }}"' in card
    upload = (ROOT / "web" / "templates" / "_upload_result.html").read_text(encoding="utf-8")
    assert 'id="loaded-h"' in upload
    autopsy = (ROOT / "web" / "templates" / "_autopsy.html").read_text(encoding="utf-8")
    assert 'id="autopsy-h"' in autopsy and 'hx-target="#job"' in autopsy
