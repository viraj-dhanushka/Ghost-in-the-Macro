"""VBA source, route and alert on the autopsy screen, and the Macro_Sample (vba-on-screen).

Written before the templates and the sample exist. Hand-made contexts need no LibreOffice; the tests
that build a real macro workbook are skipped when it is not installed.
"""
from __future__ import annotations

import html as htmlmod
import io
import re
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from fastapi.testclient import TestClient

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from web import app as webapp
from web.app import SAMPLES, create_app

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "web" / "templates"


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


needs_soffice = pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")


def _text(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _render(**over):
    ctx = {
        "name": "w.xlsm", "sheets": ["S"], "metrics": SimpleNamespace(formula_count=1, vba_line_count=5,
                                                                      module_count=1, calculator_shape=True),
        "excel_saved": False, "vba_error": "", "inputs": [], "outputs": [], "findings": [], "unanswered": 0,
        "decisions": [], "rules": [], "not_converted": [], "not_verifiable": [], "error": None,
        "vba_blocks": [], "route": None,
    }
    ctx.update(over)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template("_autopsy.html").render(**ctx)


def block(name="Module1.bas", lines=23, text="Sub A()\nEnd Sub", note=None):
    return {"name": name, "line_count": lines, "text": text, "note": note}


# -- the VBA_Panel ---------------------------------------------------------------------------

def test_panel_has_the_heading_and_one_closed_block_per_module():
    page = _render(vba_blocks=[block(), block("Module2.bas", 4, "x")])
    assert re.search(r'<h3 id="vba-h">VBA source: read, never run</h3>', page)
    blocks = re.findall(r"<details\b([^>]*)>\s*<summary>(.*?)</summary>", page, re.S)
    mods = [(a, s) for a, s in blocks if "vba-module" in a]
    assert len(mods) == 2 and all("open" not in a.split() for a, _ in mods)
    assert _text(mods[0][1]) == "Module1.bas, 23 lines" and _text(mods[1][1]) == "Module2.bas, 4 lines"
    assert '<pre class="vba-code"><code>Sub A()\nEnd Sub</code></pre>' in page


def test_module_source_is_escaped():
    hostile = "' <script>alert(1)</script>\nx = \"<img src=x onerror=alert(2)>\""
    page = _render(vba_blocks=[block(text=hostile)], not_converted=[], error=None)
    assert "<script>alert(1)</script>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "&lt;img src=x onerror=alert(2)&gt;" in page


def test_a_hostile_module_name_is_escaped_too():
    page = _render(vba_blocks=[block(name="<b>M</b>.bas")])
    assert "<b>M</b>" not in page and "&lt;b&gt;M&lt;/b&gt;.bas" in page


def test_cut_modules_say_so():
    page = _render(vba_blocks=[block(lines=450, note="Showing the first 400 of 450 lines."),
                               block("Late.bas", 300, text="", note="Not shown: the display limit of 2000 lines was reached. The module has 300 lines.")])
    t = _text(page)
    assert "Showing the first 400 of 450 lines." in t
    assert "Not shown: the display limit of 2000 lines was reached. The module has 300 lines." in t


def test_the_panel_states_what_ghost_does_and_does_not_do():
    t = _text(_render(vba_blocks=[block()]))
    assert ("Ghost reads this VBA without running it. It does not translate VBA to Python, and a cell that "
            "calls a VBA function is listed as not converted.") in t


def test_no_panel_without_modules_and_without_inventing_one():
    page = _render()
    assert "VBA source" not in page and "vba-source" not in page


def test_an_unreadable_vba_shows_the_error_and_no_panel():
    page = _render(vba_error="VBA present but could not be read: bad stream")
    assert "VBA source" not in page
    m = re.search(r'<li class="error" role="alert">(.*?)</li>', page, re.S)
    assert m and _text(m.group(1)) == "VBA present but could not be read: bad stream (VBA: not checked)"


def test_every_element_with_class_error_carries_role_alert():
    page = _render(vba_error="VBA present but could not be read: x", error="Choose a workbook first.")
    tags = re.findall(r'<[a-z0-9]+\b[^>]*class="[^"]*\berror\b[^"]*"[^>]*>', page)
    assert len(tags) >= 2
    assert all('role="alert"' in t for t in tags), tags


# -- the Route_Panel -------------------------------------------------------------------------

def route(name, reasons, command=None):
    return {"route": name, "reasons": reasons, "command": command}


def test_ghost_converts_has_no_command_and_no_label():
    page = _render(route=route("Ghost converts", ["23 VBA lines are within the threshold of 2000", "batch size 1 is below 10"]))
    m = re.search(r'<section class="panel route" aria-labelledby="route-h">(.*?)</section>', page, re.S)
    assert m and re.search(r'<h3 id="route-h">Migration route</h3>', m.group(1))
    t = _text(m.group(1))
    assert "Ghost converts" in t and "23 VBA lines are within the threshold of 2000" in t
    assert "suggested command" not in t and "atx" not in t
    assert "recommendation computed from counts in the workbook; no command was run." in t
    assert "nothing was run" not in t


@pytest.mark.parametrize("name", ["Split", "AWS Transform custom"])
def test_aws_routes_show_the_command_labelled_not_run(name):
    cmd = "atx custom def exec -n excel-vba-to-python -p '<workbook-directory>' -c 'python3 -m compileall -q .' -x -t"
    page = _render(route=route(name, ["2500 VBA lines exceed the threshold of 2000"], cmd))
    sec = re.search(r'<section class="panel route".*?</section>', page, re.S).group(0)
    assert name in _text(sec) and "suggested command, not run" in _text(sec)
    assert re.search(r"<code class=\"route-command\">atx custom def exec .*&lt;workbook-directory&gt;", sec)
    assert "/tmp" not in sec and "/private" not in sec


def test_ghost_converts_with_vba_says_the_vba_is_not_translated():
    r = route("Ghost converts", ["23 VBA lines are within the threshold of 2000"])
    r["vba_note"] = "Ghost converts the formulas; it does not translate the VBA."
    t = _text(_render(route=r))
    assert "Ghost converts the formulas; it does not translate the VBA." in t
    assert "does not translate the VBA" not in _text(_render(route=route("Ghost converts", ["x"])))


def test_the_command_flags_are_explained_as_aws_transform_options_not_ghost_trust():
    cmd = "atx custom def exec -n excel-vba-to-python -p '<workbook-directory>' -x -t"
    t = _text(_render(route=route("Split", ["r"], cmd)))
    assert "-x -t are AWS Transform options (non-interactive, trust all tools). Ghost never runs this command." in t


def test_no_route_panel_when_the_route_is_not_available():
    assert "panel route" not in _render()


# -- the Macro_Sample ------------------------------------------------------------------------

def test_the_fourth_sample_is_registered_with_a_one_sentence_blurb():
    script, fname, label = SAMPLES["macros"]
    assert (script, fname, label) == ("make_xlsm.py", "discount_vba.xlsm", "Macro workbook (generated)")
    blurb = webapp.SAMPLE_BLURBS["macros"]
    assert blurb.count(".") == 1 and blurb.endswith(".")
    # Skeptic review: "converts the formulas" and "routes the macro logic" claimed more than the engine does
    # (Calculator!B13 is not converted; the router only recommends a route from counts).
    for word in ("reads the VBA", "finds thresholds in it", "converts the formulas it supports",
                 "recommends a migration route", "does not translate VBA to Python"):
        assert word in blurb, word
    assert "routes the macro logic" not in blurb and "converts the formulas," not in blurb
    assert not re.search(r"\b(correct|proven|proved|verified)\b", blurb, re.I)


def test_the_landing_page_shows_the_fourth_card(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    page = c.get("/").text
    assert 'hx-post="/sample/macros"' in page and "Macro workbook (generated)" in page
    assert "/sample/macros/workbook" in page


def _fake_generator(counter, delay=0.0):
    def run(sample_id, dest):
        counter.append(sample_id)
        time.sleep(delay)
        Path(dest).write_bytes(b"PK-fake")
    return run


def test_the_macro_sample_is_built_once_per_process(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webapp, "_SAMPLE_CACHE", {})
    monkeypatch.setattr(webapp, "_run_generator", _fake_generator(calls))
    for i in range(3):
        d = tmp_path / f"d{i}.xlsm"
        webapp._build_sample("macros", d)
        assert d.read_bytes() == b"PK-fake"
    assert calls == ["macros"]


def test_two_requests_at_once_start_one_build(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webapp, "_SAMPLE_CACHE", {})
    monkeypatch.setattr(webapp, "_run_generator", _fake_generator(calls, delay=0.3))
    threads = [threading.Thread(target=webapp._build_sample, args=("macros", tmp_path / f"t{i}.xlsm")) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert calls == ["macros"]
    assert all((tmp_path / f"t{i}.xlsm").read_bytes() == b"PK-fake" for i in range(4))


def test_a_failed_build_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "_SAMPLE_CACHE", {})
    state = {"n": 0}
    def flaky(sample_id, dest):
        state["n"] += 1
        if state["n"] == 1:
            raise RefereeUnavailable("soffice not found")
        Path(dest).write_bytes(b"ok")
    monkeypatch.setattr(webapp, "_run_generator", flaky)
    with pytest.raises(RefereeUnavailable):
        webapp._build_sample("macros", tmp_path / "a.xlsm")
    webapp._build_sample("macros", tmp_path / "b.xlsm")
    assert (tmp_path / "b.xlsm").read_bytes() == b"ok"


def test_the_other_samples_are_not_cached(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(webapp, "_SAMPLE_CACHE", {})
    monkeypatch.setattr(webapp, "_run_generator", _fake_generator(calls))
    webapp._build_sample("discount", tmp_path / "x.xlsx")
    webapp._build_sample("discount", tmp_path / "y.xlsx")
    assert calls == ["discount", "discount"]


def test_a_missing_referee_gives_503_and_the_other_samples_still_work(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "_SAMPLE_CACHE", {})
    def no_referee(sample_id, dest):
        if sample_id == "macros":
            raise RefereeUnavailable("soffice not found. Searched: /somewhere/soffice")
        return webapp.__dict__["_real_run_generator"](sample_id, dest)
    monkeypatch.setitem(webapp.__dict__, "_real_run_generator", webapp._run_generator)
    monkeypatch.setattr(webapp, "_run_generator", no_referee)
    c = TestClient(create_app(session_root=tmp_path / "s"))
    r = c.post("/sample/macros", headers={"hx-request": "true"})
    assert r.status_code == 503
    assert 'data-kind="referee_unavailable"' in r.text and "/somewhere" not in r.text
    assert c.post("/sample/discount").status_code == 200


@needs_soffice
def test_the_download_is_a_macro_enabled_workbook(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    r = c.get("/sample/macros/workbook")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.ms-excel.sheet.macroEnabled.12")
    assert 'filename="discount_vba.xlsm"' in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert "xl/vbaProject.bin" in z.namelist()


@needs_soffice
def test_the_macro_sample_loads_and_the_autopsy_shows_its_vba(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    assert c.post("/sample/macros").status_code == 200
    page = c.get("/autopsy").text
    assert "VBA source: read, never run" in page
    assert re.search(r"<summary>\s*Module1\.bas, 23 lines\s*</summary>", page)
    assert "Function DeliveryFee(quantity As Double, distanceKm As Double) As Double" in htmlmod.unescape(page)
    t = _text(page)
    assert "Calculator!B13" in t and "function DELIVERYFEE is outside the P0 subset" in t
    assert "Migration route" in t and "Ghost converts" in t and "23 VBA lines are within the threshold of 2000" in t
    assert "suggested command" not in t
    assert "Not converted" in t


@needs_soffice
def test_the_macro_sample_passes_a_faithful_run_with_its_default_cells(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    c.post("/sample/macros")
    page = c.get("/autopsy").text
    boxes = {"inputs": [], "outputs": []}
    for kind, value, rest in re.findall(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>', page):
        if "checked" in rest:
            boxes[kind].append(htmlmod.unescape(value))
    assert boxes == {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"], "outputs": ["Calculator!B11"]}
    r = c.post("/verify", data=boxes)
    assert r.status_code == 200, r.text
    jid = r.text.split("/run/")[1].split("/")[0]
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        panel = c.get(f"/run/{jid}/panel").text
        if 'hx-trigger="every 1s"' not in panel and "Proof report" in panel:
            break
        time.sleep(1)
    else:
        pytest.fail("verification did not finish")
    assert 'class="verdict pass"' in panel
    assert "Passed: no difference found on" in _text(panel)


@needs_soffice
def test_a_hostile_module_in_an_upload_is_shown_escaped(tmp_path):
    from ghost.referee.client import RefereeClient
    import openpyxl
    base = tmp_path / "base.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"], ws["B1"] = "Qty", 5
    ws["A2"], ws["B2"] = "Out", "=B1*2"
    wb.save(base)
    target = tmp_path / "evil.xlsm"
    src = "' <script>alert(1)</script>\nSub Evil()\n    MsgBox \"<img src=x onerror=alert(2)>\"\nEnd Sub\n"
    with RefereeClient(None, base, run_macros=False, job_dir=str(tmp_path)) as ref:
        ref.open(base)
        ref.save_with_vba(target, {"Evil": src})
    c = TestClient(create_app(session_root=tmp_path / "s"))
    r = c.post("/upload", files={"file": ("evil.xlsm", io.BytesIO(target.read_bytes()), "application/octet-stream")})
    assert r.status_code == 200, r.text
    page = c.get("/autopsy").text
    assert "VBA source: read, never run" in page
    assert "<script>alert(1)</script>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


@needs_soffice
def test_the_macro_sample_shows_no_false_finding_and_no_decision_form(tmp_path):
    # Engine fix (2026-11-26): `If extraKm < 0 Then extraKm = 0` was read as an operator conflict.
    c = TestClient(create_app(session_root=tmp_path / "s"))
    assert c.post("/sample/macros").status_code == 200
    page = c.get("/autopsy").text
    assert "No operator conflicts found." in page
    assert 'class="finding"' not in page and 'hx-post="/decision"' not in page and "F-001" not in page
    assert "Record decision" not in page
