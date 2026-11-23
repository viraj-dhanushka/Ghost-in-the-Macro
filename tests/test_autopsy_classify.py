"""Tests for ghost.autopsy.classify (Requirements 2.1-2.6, Property 5)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from ghost.autopsy.classify import classify
from ghost.models import Cell, Workbook


def _wb(cells: list[Cell], deps: dict[str, set[str]]) -> Workbook:
    return Workbook(path="x.xlsx", sheets=["S"], cells={c.ref: c for c in cells}, deps=deps)


def test_discount_shape():
    wb = _wb(
        [
            Cell("S!A2", value="Quantity"),
            Cell("S!B2", value=10, fill="FFFFFF00"),
            Cell("S!A3", value="VAT rate"),
            Cell("S!B3", value=0.2),
            Cell("S!A4", value="Base"),
            Cell("S!B4", value=5),
            Cell("S!B5", formula="=B2*B4"),
            Cell("S!B6", formula="=B5*B3"),
        ],
        {"S!B5": {"S!B2", "S!B4"}, "S!B6": {"S!B5", "S!B3"}},
    )
    roles = classify(wb)
    assert roles["S!B2"] == "INPUT"
    assert roles["S!B3"] == "PARAMETER"
    assert roles["S!B4"] == "INPUT"
    assert roles["S!B5"] == "INTERMEDIATE"
    assert roles["S!B6"] == "OUTPUT"
    assert "S!A2" not in roles


def test_user_selected_output_and_shared_fixed_value():
    wb = _wb(
        [
            Cell("S!C1", value=7),
            Cell("S!D1", formula="=C1+1"),
            Cell("S!D2", formula="=C1+D1"),
        ],
        {"S!D1": {"S!C1"}, "S!D2": {"S!C1", "S!D1"}},
    )
    roles = classify(wb, user_outputs=["S!D1"])
    assert roles["S!C1"] == "PARAMETER"
    assert roles["S!D1"] == "OUTPUT"
    assert roles["S!D2"] == "OUTPUT"


def test_validation_makes_input_even_if_shared():
    wb = _wb(
        [
            Cell("S!C1", value=7, validation="whole"),
            Cell("S!D1", formula="=C1+1"),
            Cell("S!D2", formula="=C1*2"),
        ],
        {"S!D1": {"S!C1"}, "S!D2": {"S!C1"}},
    )
    assert classify(wb)["S!C1"] == "INPUT"


@settings(max_examples=50, derandomize=True)
@given(
    n_const=st.integers(1, 5),
    n_form=st.integers(1, 5),
    data=st.data(),
    selected=st.sets(st.integers(0, 4), max_size=2),
)
def test_property_5_role_partition(n_const, n_form, data, selected):
    """Property 5: cell role partition. **Validates: Requirements 2.1, 2.4, 2.5, 2.6**"""
    consts = [Cell(f"S!A{i + 1}", value=i) for i in range(n_const)]
    forms = [Cell(f"S!B{i + 1}", formula="=1") for i in range(n_form)]
    deps = {}
    for i, f in enumerate(forms):
        pool = [c.ref for c in consts] + [g.ref for g in forms[:i]]
        deps[f.ref] = set(data.draw(st.sets(st.sampled_from(pool))))
    wb = _wb(consts + forms, deps)
    sel = {forms[i].ref for i in selected if i < n_form}
    roles = classify(wb, user_outputs=sel)
    used = set().union(*deps.values())
    for f in forms:
        if f.ref in sel or f.ref not in used:
            assert roles[f.ref] == "OUTPUT"
        else:
            assert roles[f.ref] == "INTERMEDIATE"
    for c in consts:
        if c.ref in used:
            assert roles[c.ref] in ("INPUT", "PARAMETER")
