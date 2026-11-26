"""Property 9 of the main spec (ghost-in-the-macro): rule determinism and stable identifiers.
Validates Requirements 3.6 and 3.7. No LibreOffice."""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

from ghost import cli
from ghost.rules.ids import normalise_formula, rule_id

ROOT = Path(__file__).resolve().parent.parent

cells = st.builds(lambda s, c, r: f"{s}!{c}{r}", st.sampled_from(["Sheet1", "Calc", "Data"]),
                  st.sampled_from(list("ABCDE")), st.integers(1, 50))
formulas = st.builds(lambda a, op, b: f"={a}{op}{b}", st.sampled_from(["A1", "B2", "C3", "D4"]),
                     st.sampled_from(["+", "-", "*", "/", ">", ">="]), st.sampled_from(["A1", "B2", "50", "0.1", "C3"]))


@settings(max_examples=200, deadline=None)
@given(cells, formulas)
def test_property_9_rule_id_is_stable_and_has_the_documented_shape(cell, formula):
    assert rule_id(cell, formula) == rule_id(cell, formula)
    assert rule_id(cell, formula).startswith("R-") and len(rule_id(cell, formula)) == 10


@settings(max_examples=200, deadline=None)
@given(cells, formulas, st.sampled_from(["", " ", "  "]))
def test_property_9_formulas_equal_after_normalisation_share_an_id(cell, formula, pad):
    spaced = formula.replace("+", f"{pad}+{pad}").replace("*", f"{pad}*{pad}")
    assert normalise_formula(spaced) == normalise_formula(formula)
    assert rule_id(cell, spaced) == rule_id(cell, formula)


@settings(max_examples=300, deadline=None)
@given(cells, formulas, cells, formulas)
def test_property_9_different_cell_or_formula_gives_a_different_id(c1, f1, c2, f2):
    if (c1, normalise_formula(f1)) != (c2, normalise_formula(f2)):
        assert rule_id(c1, f1) != rule_id(c2, f2)


def test_property_9_generating_rules_twice_gives_identical_text_and_ids(tmp_path):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_haunted
    finally:
        sys.path.remove(str(ROOT / "samples"))
    book = make_haunted.build(tmp_path / "h.xlsx")
    first = cli._analyse(book).rules
    second = cli._analyse(book).rules
    assert [(r.rule_id, r.text) for r in first] == [(r.rule_id, r.text) for r in second]
    assert len({r.rule_id for r in first}) == len(first)
