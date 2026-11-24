"""Property 6: Condition-flip probing finds the boundary (PBT).

**Validates: Requirements 2.8** (review-fixes-2026-11-24, task 4.7; R-04 and R-10 expressions)

No LibreOffice needed: the workbook is built with openpyxl, transpiled with
``emit_python`` and probed through the module's ``trace`` hook.

API that task 4.8 must implement (design.md names ``ghost/verifier/flip.py`` but fixes no
signature, so it is fixed here):

    # ghost/verifier/flip.py
    @dataclass(frozen=True)
    class Flip:
        condition_id: str               # trace id, e.g. "Calculator!B5#1"
        input_name: str                 # the numeric input that was searched
        others: dict[str, Decimal]      # values of every other input during the search
        below: Decimal                  # value on one side of the flip
        above: Decimal                  # value on the other side (condition truth differs)
        exact: Decimal | None           # input value where the compared value equals the
                                        # threshold, when one exists in the domain
        def cases(self) -> list[dict[str, Decimal]]:
            '''Full input dicts: below, above and (if not None) exact, others filled in.'''

    def find_flips(compute, mapping, base_inputs: dict[str, Decimal], *,
                   tolerance: Decimal = Decimal("0.001"), seed: int = 0) -> list[Flip]

``compute`` is the transpiled Faithful ``compute(inputs, trace=None)``. For each IF
condition that fires, each numeric input of ``mapping`` is binary-searched between its
``min`` and ``max`` (the test sets both) with the other inputs at ``base_inputs`` plus
a few seeded random base points. Guarantees tested here: ``|above - below| <= tolerance``,
the condition truth differs at ``below`` and ``above``, and ``exact`` is the true
threshold crossing (``T / k``) with that value included in ``cases()``.
"""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st
from openpyxl import Workbook as XlWorkbook

from ghost.converter.emit_python import emit_python
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.verifier.run import load_compute

TOL = Decimal("0.001")
FACTORS = (1, 2, 4, 5, 10)  # T / k always terminates, so the exact hit is representable


def _build(op: str, threshold: int, calculated_cell: bool):
    """Workbook: B2 qty, B3 price; B5 = IF(<qty*price> op T, "Gold", "Std")."""
    book = XlWorkbook()
    ws = book.active
    ws.title = "Calculator"
    ws["B2"], ws["B3"] = 2, 3
    if calculated_cell:
        ws["B4"] = "=B2*B3"
        ws["B5"] = f'=IF(B4{op}{threshold},"Gold","Std")'
    else:
        ws["B5"] = f'=IF(B2*B3{op}{threshold},"Gold","Std")'
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "flip.xlsx"
        book.save(path)
        wb = load_workbook(str(path))
    mapping = Mapping(
        inputs={
            "qty": IOSpec(cell="Calculator!B2", type="decimal", min=Decimal(0), max=Decimal(2000)),
            "price": IOSpec(cell="Calculator!B3", type="decimal", min=Decimal(0), max=Decimal(2000)),
        },
        outputs={"tier": IOSpec(cell="Calculator!B5", type="string")},
    )
    return load_compute(emit_python(wb, mapping)), mapping


def _holds(op: str, qty: Decimal, price: Decimal, threshold: int) -> bool:
    return qty * price >= threshold if op == ">=" else qty * price > threshold


@pytest.mark.parametrize("calculated_cell", [False, True])
@pytest.mark.parametrize("op", [">=", ">"])
def test_flip_fixture_is_sound(op, calculated_cell):
    """Not xfail: guards the test's own setup so the xfail below cannot hide a mistake in it."""
    compute, _ = _build(op, 20, calculated_cell)
    seen = []
    at = compute({"qty": Decimal(4), "price": Decimal(5)}, trace=lambda cid, b: seen.append((cid, b)))
    assert seen == [("Calculator!B5#1", op == ">=")] and at["tier"] == ("Gold" if op == ">=" else "Std")
    over = compute({"qty": Decimal(5), "price": Decimal(5)})
    assert over["tier"] == "Gold"
    assert _holds(op, Decimal(4), Decimal(5), 20) == (op == ">=")


@seed(20261124)
@settings(max_examples=40, deadline=None, derandomize=True, suppress_health_check=list(HealthCheck))
@given(
    op=st.sampled_from([">=", ">"]),
    calculated_cell=st.booleans(),
    threshold=st.integers(min_value=1, max_value=1000),
    qty=st.sampled_from(FACTORS),
    price=st.sampled_from(FACTORS),
)
def test_property_6_condition_flip_probing_finds_boundary(op, calculated_cell, threshold, qty, price):
    from ghost.verifier.flip import find_flips

    compute, mapping = _build(op, threshold, calculated_cell)
    base = {"qty": Decimal(qty), "price": Decimal(price)}
    flips = find_flips(compute, mapping, base, tolerance=TOL, seed=1)

    for name, other in (("qty", "price"), ("price", "qty")):
        k = base[other]
        matches = [f for f in flips if f.input_name == name and f.others == {other: k}]
        assert len(matches) == 1, (name, flips)
        f = matches[0]
        assert f.condition_id == "Calculator!B5#1"

        def holds(x: Decimal) -> bool:
            return _holds(op, x * k, Decimal(1), threshold)

        # opposite sides, within tolerance
        assert holds(f.below) != holds(f.above)
        assert abs(f.above - f.below) <= TOL
        # exact hit T / k exists in the domain, is reported and is among the extra cases
        exact = Decimal(threshold) / k
        assert f.exact == exact
        values = [c[name] for c in f.cases() if all(c[o] == v for o, v in f.others.items())]
        assert f.below in values and f.above in values and exact in values
