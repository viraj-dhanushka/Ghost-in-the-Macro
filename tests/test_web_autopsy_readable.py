"""The readable autopsy (readable-proof, Requirements 8 and 9). Written before the templates change.

Workbooks are built inside the tests. The haunted sample is the generated one from samples/.
"""
from __future__ import annotations

import html as htmlmod
import io
import re
from pathlib import Path
from types import SimpleNamespace

import jinja2
import openpyxl
import pytest
from fastapi.testclient import TestClient

from web.app import SAMPLES, create_app

TEMPLATES = Path(__file__).resolve().parent.parent / "web" / "templates"
_BOX = re.compile(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>')
_BOX_WITH_TEXT = re.compile(
    r'<label class="cell"><input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>(.*?)</label>', re.S)


def _client(tmp_path):
    return TestClient(create_app(session_root=tmp_path / "s"))


def _text(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _flat(fragment):
    """Text with the tags removed and nothing put in their place (a marked operator stays inside its formula)."""
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", fragment))


def _autopsy(tmp_path, sample="haunted"):
    c = _client(tmp_path)
    assert c.post(f"/sample/{sample}").status_code == 200
    return c.get("/autopsy").text


# -- labelled checkboxes ---------------------------------------------------------------------

DEFAULTS = {
    "discount": (["Calculator!B2", "Calculator!B3", "Calculator!B4"], ["Calculator!B11"]),
    "haunted": (["Calculator!B2", "Calculator!B3", "Calculator!B4"], ["Calculator!B11"]),
    "scenarios": (["Model!B2", "Model!B3", "Model!E2"], ["Model!B19", "Model!B20"]),
    "macros": (["Calculator!B2", "Calculator!B3", "Calculator!B4"], ["Calculator!B11"]),
}


@pytest.mark.parametrize("sample_id", list(SAMPLES))
def test_default_selection_and_markup_are_unchanged(tmp_path, sample_id):
    if sample_id == "macros":
        from ghost.referee.locate import RefereeUnavailable, locate_soffice
        try:
            locate_soffice()
        except RefereeUnavailable:
            pytest.skip("the macro sample is built through LibreOffice")
    page = _autopsy(tmp_path, sample_id)
    checked = {"inputs": [], "outputs": []}
    for kind, value, rest in _BOX.findall(page):
        assert rest.strip() in ("", "checked"), rest  # only `checked` may follow `value`
        if "checked" in rest:
            checked[kind].append(htmlmod.unescape(value))
    assert (checked["inputs"], checked["outputs"]) == DEFAULTS[sample_id]


def test_haunted_labels_values_and_formulas(tmp_path):
    page = _autopsy(tmp_path)
    boxes = {(k, htmlmod.unescape(v)): _text(t) for k, v, _, t in _BOX_WITH_TEXT.findall(page)}
    assert boxes[("inputs", "Calculator!B2")] == "Quantity (Calculator!B2), value in the workbook: 10"
    assert boxes[("inputs", "Calculator!B3")] == "Unit price (Calculator!B3), value in the workbook: 19.95"
    assert boxes[("inputs", "Calculator!E2")] == "Bulk threshold (units) (Calculator!E2), value in the workbook: 50"
    assert boxes[("outputs", "Calculator!B11")] == "Total (Calculator!B11), formula: =B8+B9+B10"
    assert boxes[("outputs", "Calculator!B9")].startswith("Delivery fee (Calculator!B9), formula: =IF(B2>50,0,")


def test_a_cell_without_a_label_shows_the_address_alone(tmp_path):
    page = _autopsy(tmp_path, "scenarios")
    boxes = {htmlmod.unescape(v): _text(t) for k, v, _, t in _BOX_WITH_TEXT.findall(page)}
    assert boxes["Model!C6"].startswith("Model!C6, value in the workbook: ")
    assert "()" not in boxes["Model!C6"]


def _upload(c, build):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calc"
    build(ws)
    buf = io.BytesIO()
    wb.save(buf)
    r = c.post("/upload", files={"file": ("evil.xlsx", io.BytesIO(buf.getvalue()),
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    return c.get("/autopsy").text


def test_markup_in_labels_values_and_formulas_is_escaped(tmp_path):
    def build(ws):
        ws["A2"], ws["B2"] = "<script>alert(1)</script>", 5
        ws["A3"], ws["B3"] = "Note <b>bold</b>", "<i>v</i>"
        ws["A4"], ws["B4"] = "Result", '=IF(B2<5,LEN(B3),"<img src=x onerror=alert(2)>")'
    page = _upload(_client(tmp_path), build)
    assert "<script>alert(1)</script>" not in page and "<i>v</i>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; (Calc!B2), value in the workbook: 5" in page
    assert "&lt;i&gt;v&lt;/i&gt;" in page
    assert "&lt;img src=x onerror=alert(2)&gt;" in page


# -- the Finding_Card ------------------------------------------------------------------------

def test_haunted_finding_card_shows_each_location_with_its_formula(tmp_path):
    page = _autopsy(tmp_path)
    card = page[page.index('<article class="finding"'):page.index("</article>")]
    t = _text(card)
    assert re.search(r"<h4[^>]*>F-001: Operator conflict on Calculator!B2 against 50</h4>", card)
    flat = _flat(card)
    assert "=IF(B2>=E2,ROUND(B6*E3,2),0)" in flat and "=IF(B2>50,0,ROUND(E4+MAX(0,B4-E5)*E6,2))" in flat
    assert '<mark class="op">&gt;=</mark>' in card and '<mark class="op">&gt;</mark>' in card
    assert "uses >=" in t and "uses >" in t  # the words carry the operator without the colour
    assert "at exactly 50, B7 uses >= and B9 uses >" in t


def test_finding_card_has_no_computed_outcome(tmp_path):
    page = _autopsy(tmp_path)
    t = _text(page[page.index('<article class="finding"'):page.index("<form")])
    sentence = re.search(r"at exactly 50[^.]*", t).group(0)
    assert not re.search(r"\b(result|returns|gives|total|fee|discount|equals)\b", sentence, re.I)
    assert not re.search(r"\d+\.\d+", sentence)


def _ctx(**over):
    ctx = {
        "name": "w.xlsx", "sheets": ["S"], "metrics": SimpleNamespace(formula_count=1, vba_line_count=5,
                                                                      module_count=1, calculator_shape=True),
        "excel_saved": False, "vba_error": "", "inputs": [], "outputs": [], "findings": [], "unanswered": 0,
        "decisions": [], "rules": [], "not_converted": [], "not_verifiable": [], "error": None,
    }
    ctx.update(over)
    return ctx


def _render_autopsy(**over):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template("_autopsy.html").render(**_ctx(**over))


def _finding(locations):
    return {"id": "F-009", "kind": "operator_conflict", "title": "Operator conflict", "cell": "S!B2",
            "constant": "50", "locations": locations, "options": [{"value": "keep", "label": "Keep"}],
            "decision": None, "consequence": "at exactly 50, Module1:12 uses >"}


def test_a_macro_location_shows_module_and_line_and_no_formula():
    macro = {"where": "Module1:12", "op": ">", "cell": None, "module": "Module1", "line": 12,
             "formula": None, "segments": None}
    page = _render_autopsy(findings=[_finding([macro])])
    card = page[page.index('<article class="finding"'):page.index("</article>")]
    assert "Module1" in card and "line 12" in card
    assert 'class="formula"' not in card


def test_a_cell_location_with_formula_marks_the_operator():
    loc = {"where": "S!B7", "op": ">=", "cell": "S!B7", "module": None, "line": None,
           "formula": "=IF(B2>=E2,1,0)", "segments": [("=IF(B2", False), (">=", True), ("E2,1,0)", False)]}
    page = _render_autopsy(findings=[_finding([loc])])
    assert '=IF(B2<mark class="op">&gt;=</mark>E2,1,0)' in page


def test_the_finding_title_comes_from_the_finding_not_the_template():
    f = _finding([])
    f["title"] = "Some other kind"
    page = _render_autopsy(findings=[f])
    assert "F-009: Some other kind on S!B2 against 50" in page and "operator conflict" not in page.lower()


def test_a_workbook_with_no_finding_says_no_operator_conflicts_not_no_inconsistencies(tmp_path):
    page = _autopsy(tmp_path, "discount")
    assert "No operator conflicts found." in page and "No inconsistencies found." not in page
