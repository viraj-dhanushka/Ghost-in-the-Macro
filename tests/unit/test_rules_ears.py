from hypothesis import given, strategies as st

from ghost.models import Cell, Workbook
from ghost.rules.ears import generate_rules
from ghost.rules.ids import normalise_formula, rule_id


def _wb() -> Workbook:
    wb = Workbook(path="x", sheets=["S"])
    wb.cells["S!A1"] = Cell(ref="S!A1", value="Quantity")
    wb.cells["S!B1"] = Cell(ref="S!B1", value=60)
    wb.cells["S!B2"] = Cell(ref="S!B2", value=5)
    wb.cells["S!B3"] = Cell(ref="S!B3", formula="=IF(B1>=50,B1*0.9,B1)")
    wb.cells["S!B4"] = Cell(ref="S!B4", formula="=ROUND(B2*0.03,2)")
    wb.cells["S!B5"] = Cell(ref="S!B5", formula="=INDEX(B1:B2,1)")
    return wb


def test_if_round_lookup_and_labels():
    rules = {r.cells[0]: r for r in generate_rules(_wb())}
    t = rules["S!B3"].text
    assert t.startswith("WHEN Quantity [B1] is at least 50 THE SYSTEM SHALL set")
    assert "OTHERWISE THE SYSTEM SHALL set" in t
    assert "rounded to 2 decimals (half away from zero)" in rules["S!B4"].text
    assert "B2" in rules["S!B4"].text and "[B2]" not in rules["S!B4"].text
    assert "look up" in rules["S!B5"].text
    assert rules["S!B3"].conditions[0].condition_id == rules["S!B3"].rule_id + "-C1"


def test_deterministic():
    assert generate_rules(_wb()) == generate_rules(_wb())


def test_rule_id_normalisation():
    assert rule_id("S!B3", "=if( $B$1 >= 50 , 1 , 0 )") == rule_id("S!B3", "=IF(B1>=50,1,0)")
    assert rule_id("S!B3", "=1").startswith("R-") and len(rule_id("S!B3", "=1")) == 10
    assert normalise_formula('=a("x y")') == 'A("x y")'


@given(st.text(alphabet="ab 1$+", max_size=12))
def test_id_stable(f):
    assert rule_id("S!A1", f) == rule_id("S!A1", f)
