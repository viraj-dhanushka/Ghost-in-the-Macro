"""Unit tests for rule coverage (Requirements 8.8, 8.9)."""
from decimal import Decimal

from ghost.converter.emit_python import emit_python
from ghost.models import Cell, IOSpec, Mapping, Workbook
from ghost.rules.ears import generate_rules
from ghost.verifier.coverage import CoverageTracker, candidate_inputs, close_gaps


def _setup():
    wb = Workbook(path="x")
    wb.cells = {
        "S!A1": Cell(ref="S!A1", value=3),
        "S!B1": Cell(ref="S!B1", formula="=IF(A1>=50,IF(A1>100,1,2),0)"),
        "S!B2": Cell(ref="S!B2", formula="=IF(A1>50,0,5)"),
    }
    m = Mapping(
        inputs={"qty": IOSpec(cell="S!A1")},
        outputs={"a": IOSpec(cell="S!B1"), "b": IOSpec(cell="S!B2")},
    )
    ns: dict = {"__name__": "g"}
    exec(compile(emit_python(wb, m), "<g>", "exec"), ns)
    return generate_rules(wb), ns["compute"]


def test_hook_ids_map_to_condition_ids_and_report_gaps():
    rules, compute = _setup()
    t = CoverageTracker(rules)
    t.run(compute, {"qty": 3})
    rep = {c.condition_id: c for c in t.report()}
    assert len(rep) == 3
    assert [c.seen_false for c in rep.values()] == [True, False, True]
    assert all(not c.seen_true for c in rep.values())
    assert len(t.uncovered()) == 3


def test_targeted_generation_closes_gaps():
    rules, compute = _setup()
    t = CoverageTracker(rules)
    t.run(compute, {"qty": 3})
    left = close_gaps(t, compute, candidate_inputs({"qty": 3}, [Decimal(50), Decimal(100)]))
    assert left == [] and t.complete


def test_unreachable_condition_stays_uncovered():
    rules, compute = _setup()
    t = CoverageTracker(rules)
    left = close_gaps(t, compute, [{"qty": 3}])
    assert len(left) == 3
    assert t.instrument(compute)({"qty": 60})["b"] == 0
