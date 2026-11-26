"""Pure helpers of web/autopsy_view.py (readable-proof, Requirements 8 and 9). Written before the module."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from web.autopsy_view import checkbox_text, consequence, finding_title, formula_segments, short_ref


def test_finding_title_comes_from_the_kind():
    assert finding_title("operator_conflict") == "Operator conflict"
    assert finding_title("range_gap") == "Range gap"


def test_short_ref_drops_the_sheet_only_on_the_same_sheet():
    assert short_ref("Calculator!B7", "Calculator!B2") == "B7"
    assert short_ref("Other!B7", "Calculator!B2") == "Other!B7"


def cell(ref, op):
    return {"cell": ref, "module": None, "line": None, "op": op}


def test_consequence_for_two_locations_has_no_outcome():
    s = consequence("50", "Calculator!B2", [cell("Calculator!B7", ">="), cell("Calculator!B9", ">")])
    assert s == "at exactly 50, B7 uses >= and B9 uses >"


def test_consequence_for_three_locations_and_a_macro_location():
    locs = [cell("S!B7", ">="), cell("S!B9", ">"), {"cell": None, "module": "Module1", "line": 12, "op": "<"}]
    assert consequence("50", "S!B2", locs) == "at exactly 50, B7 uses >=, B9 uses > and Module1:12 uses <"


def test_consequence_for_one_location_is_still_a_sentence():
    assert consequence("7", "S!B2", [cell("S!B7", "=")]) == "at exactly 7, B7 uses ="


def seg(formula, op, const):
    return formula_segments(formula, op, const)


def marked(segments):
    return [t for t, is_op in segments if is_op]


@pytest.mark.parametrize("formula, op, const", [
    ("=IF(B2>=E2,ROUND(B6*E3,2),0)", ">=", "50"),
    ("=IF(B2>50,0,ROUND(E4,2))", ">", "50"),
    ("=IF(A1>=50,IF(B1>=50,1,2),3)", ">=", "50"),
    ("=IF(A1<>50,1,0)", "<>", "50"),
    ("=A1+B1", ">", "50"),
    ("", ">", "50"),
])
def test_segments_always_rebuild_the_formula(formula, op, const):
    assert "".join(t for t, _ in seg(formula, op, const)) == formula


def test_segments_fall_back_to_the_first_matching_operator():
    s = seg("=IF(B2>=E2,ROUND(B6*E3,2),0)", ">=", "50")
    assert marked(s) == [">="] and s[0] == ("=IF(B2", False)


def test_segments_prefer_the_operator_next_to_the_constant():
    s = seg("=IF(X>=7,1,IF(Y>=50,1,2))", ">=", "50")
    assert marked(s) == [">="]
    assert s[0][0] == "=IF(X>=7,1,IF(Y" and s[1] == (">=", True)


def test_segments_do_not_mistake_parts_of_longer_operators():
    assert marked(seg("=IF(A1>=50,1,0)", ">", "50")) == []
    assert marked(seg("=IF(A1<>50,1,0)", "<", "50")) == []
    assert marked(seg("=IF(A1<>50,1,0)", "<>", "50")) == ["<>"]


def test_segments_skip_the_leading_equals_of_the_formula():
    assert marked(seg("=IF(A1=50,1,0)", "=", "50")) == ["="]
    assert seg("=IF(A1=50,1,0)", "=", "50")[0] == ("=IF(A1", False)
    assert marked(seg("=A1+1", "=", "50")) == []


def test_segments_with_no_such_operator_are_one_plain_piece():
    assert seg("=A1+B1", ">", "50") == [("=A1+B1", False)]


def test_checkbox_text_forms():
    assert checkbox_text("Calculator!B2", "Quantity", value=10) == "Quantity (Calculator!B2), value in the workbook: 10"
    assert checkbox_text("Calculator!B11", "Total", formula="=B8+B9+B10") == "Total (Calculator!B11), formula: =B8+B9+B10"
    assert checkbox_text("Calculator!E3", None, value=0.1) == "Calculator!E3, value in the workbook: 0.1"
    assert checkbox_text("Calculator!B2", "Quantity") == "Quantity (Calculator!B2)"
    assert checkbox_text("Calculator!B2", None) == "Calculator!B2"
    assert checkbox_text("Calculator!B2", "", value="") == "Calculator!B2, value in the workbook: "


def test_module_is_pure():
    src = Path(__file__).resolve().parent.parent / "web" / "autopsy_view.py"
    names = set()
    for n in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module.split(".")[0])
    assert not names & {"ghost", "fastapi", "starlette", "jinja2", "os", "sys", "time", "pathlib", "subprocess"}
