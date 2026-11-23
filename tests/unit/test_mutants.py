"""Unit tests for mutant generation (Requirement 9.1, Property 29 partial)."""
from decimal import Decimal

from ghost.converter.emit_python import emit_python
from ghost.models import Cell, IOSpec, Mapping, Workbook
from ghost.mutation.mutants import generate_mutants


def _source() -> str:
    wb = Workbook(path="x")
    wb.cells = {
        "S!A1": Cell(ref="S!A1", value=3),
        "S!B1": Cell(ref="S!B1", formula="=IF(A1>=50,ROUND(A1*0.03,2),0)"),
        "S!B2": Cell(ref="S!B2", formula="=IF(A1<10,1,2)"),
    }
    m = Mapping(
        inputs={"qty": IOSpec(cell="S!A1")},
        outputs={"a": IOSpec(cell="S!B1"), "b": IOSpec(cell="S!B2")},
    )
    return emit_python(wb, m)


def _run(src: str, qty):
    ns: dict = {"__name__": "g"}
    exec(compile(src, "<m>", "exec"), ns)
    return ns["compute"]({"qty": qty})


def test_all_operators_generated_and_differ_from_source():
    src = _source()
    mutants = generate_mutants(src)
    ops = {m.operator for m in mutants}
    assert ops == {
        "flip_comparison",
        "constant_plus_one",
        "constant_minus_one",
        "rounding_mode",
        "drop_if_then",
        "drop_if_else",
    }
    assert all(m.source != src for m in mutants)
    assert len({m.mutant_id for m in mutants}) == len(mutants)
    assert len({m.source for m in mutants}) == len(mutants)


def test_deterministic():
    src = _source()
    assert generate_mutants(src) == generate_mutants(src)


def test_mutants_compile_and_change_behaviour():
    src = _source()
    base = _run(src, 50)
    by_op = {}
    for m in generate_mutants(src):
        by_op.setdefault(m.operator, []).append(m)
        _run(m.source, 50)  # compiles and runs
    flip = next(m for m in by_op["flip_comparison"] if "xl_ge" in m.description)
    assert _run(flip.source, 50)["a"] != base["a"]  # >= became >
    # 235 * 0.03 = 7.05 -> half up 7.05; use 0.5-boundary: 1.5 style via qty
    assert _run(by_op["rounding_mode"][0].source, 50)["a"] == Decimal("1.5")
    assert all(m.to_model().killed is False for m in generate_mutants(src))
