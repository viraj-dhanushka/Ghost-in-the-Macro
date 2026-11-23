"""Unit tests for the Python emitter (Requirements 7.1 to 7.4, 7.7, 7.8, 7.11)."""
from datetime import date
from decimal import Decimal

from ghost.converter.emit_python import emit_module, emit_python
from ghost.models import Cell, Decision, IOSpec, Mapping, Workbook
from ghost.runtime.excel import DIV0


def _wb() -> Workbook:
    wb = Workbook(path="x")
    cells = {
        "S!A1": Cell(ref="S!A1", value=3),  # qty (input)
        "S!A2": Cell(ref="S!A2", value=0.1),  # rate constant
        "S!B1": Cell(ref="S!B1", formula="=IF(A1>=50,ROUND(A1*A2,2),A1)"),
        "S!B2": Cell(ref="S!B2", formula="=IF(A1>50,0,5)"),
        "S!B3": Cell(ref="S!B3", formula="=SUM(A1:A2)+MOD(-7,3)"),
        "S!B4": Cell(ref="S!B4", formula="=A1/0"),
        "S!B5": Cell(ref="S!B5", formula="=VLOOKUP(A1,A1:A2,1,FALSE)"),
        "S!B6": Cell(ref="S!B6", formula="=B5+1"),
    }
    wb.cells = cells
    wb.deps = {"S!B6": {"S!B5"}}
    return wb


def _mapping() -> Mapping:
    return Mapping(
        inputs={"qty": IOSpec(cell="S!A1")},
        outputs={
            "disc": IOSpec(cell="S!B1"),
            "ship": IOSpec(cell="S!B2"),
            "tot": IOSpec(cell="S!B3"),
            "bad": IOSpec(cell="S!B4"),
            "lookup": IOSpec(cell="S!B6"),
        },
    )


def _run(code: str, inputs: dict, trace=None) -> dict:
    ns: dict = {"__name__": "gen_logic"}
    exec(compile(code, "<gen>", "exec"), ns)
    return ns["compute"](inputs, trace)


def test_faithful_module_computes_and_traces():
    code = emit_python(_wb(), _mapping())
    seen = []
    out = _run(code, {"qty": 50}, lambda cid, b: seen.append((cid, b)))
    assert out["disc"] == Decimal("5.0")
    assert out["ship"] == 5  # quirk: > 50 is False at exactly 50
    assert out["tot"] == Decimal("50") + Decimal("0.1") + 2  # MOD(-7,3)=2
    assert out["bad"] == DIV0
    assert ("S!B1#1", True) in seen and ("S!B2#1", False) in seen


def test_unsupported_cells_get_no_code_and_dependents_are_omitted():
    res = emit_module(_wb(), _mapping())
    assert "VLOOKUP" not in res.code.split("def compute")[1]
    assert "S!B5" not in res.code.split("def compute")[1]
    assert [e.cell for e in res.not_converted] == ["S!B5", "S!B6"]
    assert res.omitted_outputs == ("lookup",)
    assert "lookup" not in _run(res.code, {"qty": 1})


def test_output_is_deterministic_and_intended_without_decisions_matches():
    a = emit_python(_wb(), _mapping())
    assert a == emit_python(_wb(), _mapping())
    assert a == emit_python(_wb(), _mapping(), "intended", [])


def test_intended_mode_applies_set_operator_patch():
    d = Decision(
        decision_id="D-001",
        behaviour="bulk means 50 or more",
        reason="r",
        author="a",
        date=date(2026, 1, 1),
        patch={"op": "set_operator", "cell": "B2", "to": ">="},
    )
    faithful = emit_python(_wb(), _mapping(), "faithful", [d])
    intended = emit_python(_wb(), _mapping(), "intended", [d])
    assert _run(faithful, {"qty": 50})["ship"] == 5
    assert _run(intended, {"qty": 50})["ship"] == 0


def _dec(**patch):
    return Decision(
        decision_id="D-002", behaviour="b", reason="r", author="a",
        date=date(2026, 1, 1), patch=patch,
    )


def test_intended_mode_rejects_unusable_patches():
    import pytest
    from ghost.converter.emit_python import InvalidPatch

    for patch in (
        {"op": "replace_formula", "cell": "B2"},
        {"op": "set_operator", "cell": "B2", "to": "=>"},
        {"op": "set_operator", "cell": "B9", "to": ">="},  # matches nothing
    ):
        with pytest.raises(InvalidPatch):
            emit_python(_wb(), _mapping(), "intended", [_dec(**patch)])
    # record-only decision (no patch) changes nothing
    assert emit_python(_wb(), _mapping(), "intended", [_dec()]) == emit_python(_wb(), _mapping())
    # faithful mode ignores patches entirely
    emit_python(_wb(), _mapping(), "faithful", [_dec(op="bogus")])
