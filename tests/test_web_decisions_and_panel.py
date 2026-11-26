"""Decision_Cards, the remembered author name and the Not_Converted_Panel (readable-proof, Requirements 10 and 11).

Written before the templates change.
"""
from __future__ import annotations

import html as htmlmod
import re
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from fastapi.testclient import TestClient

from web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "web" / "templates"


def _text(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _client(tmp_path):
    return TestClient(create_app(session_root=tmp_path / "s"))


def _haunted_autopsy(tmp_path):
    c = _client(tmp_path)
    c.post("/sample/haunted")
    return c, c.get("/autopsy").text


# -- Decision_Cards --------------------------------------------------------------------------

def test_options_are_radio_cards_with_the_same_attributes_and_the_first_selected(tmp_path):
    _, page = _haunted_autopsy(tmp_path)
    cards = re.findall(r'<label class="choice decision-card">\s*(<input type="radio"[^>]*>)(.*?)</label>', page, re.S)
    assert len(cards) == 3
    for i, (tag, _) in enumerate(cards):
        assert 'name="choice"' in tag and "required" in tag and re.search(r'value="[^"]+"', tag)
        assert ("checked" in tag) == (i == 0)
    assert "Keep the original behaviour" in cards[0][1]


def test_each_card_has_a_title_line_and_the_option_text(tmp_path):
    _, page = _haunted_autopsy(tmp_path)
    t = _text(page)
    assert "Change Calculator!B7 from '>=' to '>'" in t and "Change Calculator!B9 from '>' to '>='" in t


def test_the_reason_is_required_and_empty_when_the_page_is_served(tmp_path):
    _, page = _haunted_autopsy(tmp_path)
    reason = re.search(r"<input[^>]*name=\"reason\"[^>]*>", page).group(0)
    assert "required" in reason and "value=" not in reason
    author = re.search(r"<input[^>]*name=\"author\"[^>]*>", page).group(0)
    assert "required" in author and 'data-remember="author"' in author and 'autocomplete="name"' in author


def test_decision_with_an_empty_reason_is_still_422(tmp_path):
    c, _ = _haunted_autopsy(tmp_path)
    for reason in ("", "   "):
        r = c.post("/decision", data={"finding_id": "F-001", "choice": "keep", "author": "A", "reason": reason})
        assert r.status_code == 422, reason


def test_the_decision_card_has_a_visible_focus_style():
    css = (ROOT / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.decision-card:focus-within", css) and "outline" in css.split(".decision-card:focus-within")[1][:200]


# -- the remembered author name --------------------------------------------------------------

def test_author_script_is_served_once_and_stays_in_the_browser(tmp_path):
    c = _client(tmp_path)
    js = c.get("/static/author-name.js")
    assert js.status_code == 200
    src = js.text
    assert "localStorage" in src and "ghost-author" in src
    assert "reason" not in src.lower()
    for bad in ("fetch(", "XMLHttpRequest", "sendBeacon", "document.cookie", "WebSocket"):
        assert bad not in src, bad
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert index.count("/static/author-name.js") == 1
    assert index.count("<script") == index.count("</script>")


def test_author_script_fills_only_an_empty_author_field_and_handles_storage_errors():
    src = (ROOT / "web" / "static" / "author-name.js").read_text(encoding="utf-8")
    assert "input[name=author]" in src or 'input[name="author"]' in src
    assert "htmx:afterSwap" in src and "try" in src and "catch" in src
    assert ".value" in src and "!" in src  # reads the field before filling it


# -- Not_Converted_Panel ---------------------------------------------------------------------

def _render(**over):
    ctx = {
        "name": "w.xlsx", "sheets": ["S"], "metrics": SimpleNamespace(formula_count=1, vba_line_count=0,
                                                                      module_count=0, calculator_shape=True),
        "excel_saved": False, "vba_error": "", "inputs": [], "outputs": [], "findings": [], "unanswered": 0,
        "decisions": [], "rules": [], "not_converted": [], "not_verifiable": [], "error": None,
    }
    ctx.update(over)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template("_autopsy.html").render(**ctx)


def test_the_panel_is_its_own_section_with_a_heading_and_lists_cell_and_reason():
    page = _render(not_converted=[{"cell": "Calc!C4", "reason": "uses a VBA function"},
                                  {"cell": "Calc!C5", "reason": ""}],
                   not_verifiable=[{"cell": "Calc!D1", "kind": "volatile", "detail": "NOW()"}])
    m = re.search(r'<section class="panel not-converted" aria-labelledby="(not-converted-h)">(.*?)</section>', page, re.S)
    assert m
    assert f'<h3 id="{m.group(1)}"' in m.group(2)
    t = _text(m.group(2))
    assert "Calc!C4" in t and "uses a VBA function" in t
    assert "Calc!C5" in t and "no reason recorded" in t
    assert "Calc!D1" in t and "volatile" in t and "NOW()" in t


def test_no_panel_when_there_is_nothing_to_list():
    assert "not-converted" not in _render()


def test_panel_text_is_escaped():
    page = _render(not_converted=[{"cell": "<b>x</b>", "reason": "<script>1</script>"}])
    assert "<script>1</script>" not in page and "&lt;script&gt;1&lt;/script&gt;" in page


def test_a_real_workbook_with_a_dynamic_construct_shows_the_panel(tmp_path):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"], ws["B1"] = "Qty", 5
    ws["A2"], ws["B2"] = "Today", "=TODAY()"
    ws["A3"], ws["B3"] = "Out", "=B1*2+B2"
    buf = io.BytesIO()
    wb.save(buf)
    c = _client(tmp_path)
    r = c.post("/upload", files={"file": ("w.xlsx", io.BytesIO(buf.getvalue()),
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200
    page = c.get("/autopsy").text
    assert 'class="panel not-converted"' in page and "Calc!B2" in _text(page[page.index('class="panel not-converted"'):])


def test_a_not_verifiable_entry_without_a_cell_or_detail_still_reads_cleanly():
    page = _render(not_verifiable=[{"cell": "", "kind": "volatile", "detail": ""}])
    t = _text(page[page.index('class="panel not-converted"'):])
    t = t.replace(" :", ":")
    assert "no cell recorded: volatile" in t and "volatile ," not in t and "volatile," not in t


def test_the_author_script_refills_after_any_swap_even_a_detached_target():
    src = (ROOT / "web" / "static" / "author-name.js").read_text(encoding="utf-8")
    assert 'addEventListener("htmx:afterSwap", function () { fill(document); })' in src
    assert "htmx:load" in src
