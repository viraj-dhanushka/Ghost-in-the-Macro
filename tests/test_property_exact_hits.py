"""Property 5: Exact hits are found and confirmed for product and integer thresholds (PBT).

**Validates: Requirements 2.3** (live-fixes-2026-11-24, task 3.9; finding L-04)

No LibreOffice needed: each workbook is built with openpyxl into ``tmp_path``,
transpiled with ``emit_python`` and probed through the generated module.

API under test. ``design.md`` (L-04, "Fix Implementation") names the functions to
change (``_search``, ``_exact_hit``, ``find_flips`` in ``ghost/verifier/flip.py``) but
no new public names, so this test uses only the API that exists today:

    find_flips(compute, mapping, base_inputs, *, tolerance=Decimal("0.001"), seed=0,
               max_evaluations=6000, literals=None, summary=None) -> list[Flip]
    Flip.exact            # exact hit: the input value where the compared sides are equal
    Flip.others           # the other inputs during the search (after the fix this
                          # includes the small-values retry, e.g. {"price": 1})
    FlipSummary.max_evaluations, .evaluations_used, .cap_reached
    FlipSummary.notes()   # becomes the report's ``boundary_notes`` (ghost/cli.py)

The fix tasks add, inside ``find_flips``/``_search``: the small-values retry (design
L-04 step 3: each other numeric input set in turn to 1, 2, 4, 5, 10 inside its
domain), integer exact hits checked on ``below`` and ``above`` (step 1, replacing
``exact = None if integer`` at ``flip.py:370``), and capped extra evaluations with a
``boundary_notes`` entry when a cap is reached (step 4). The cap constants are not
named by the design; this test checks only their visible effect.

How an exact hit is confirmed (never inferred from ``find_flips``'s own word): the
module is evaluated at ``{**flip.others, flip.input_name: flip.exact}`` with a
probing ``trace`` hook.

* Each workbook has a probe output ``B6`` holding the compared side (``=B2*B3`` or
  ``=B2``). The module's value for it must equal the threshold ``T`` exactly.
* The trace hook must report the condition, with the truth an equality gives for
  the operator (``>=`` and ``<=`` true, ``>`` and ``<`` false).
* Design L-04 step 2 lets the fix extend the hook to pass the two compared values.
  If the hook receives exactly two extra positional values, they must be equal.

Sample values are chosen so a one-input-at-a-time search from them cannot hit ``T``
(the ``tier`` repro has quantity 3, price 25.5): the base quantity is coprime with 10
and does not divide ``T`` (so ``T / quantity`` has no finite decimal form), and the
base price is ``k + 0.5`` with ``2k + 1`` not dividing ``T`` (so ``T / price`` is not
a whole number). The seeded random bases could still hit ``T`` by chance; the
property needs at least one hit, wherever it comes from.

Strict xfail until tasks 3.10 to 3.12 land (L-04). The existing Property 6 test in
``tests/test_property_condition_flip.py`` is unchanged.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, seed, settings
from hypothesis import strategies as st
from openpyxl import Workbook as XlWorkbook

from ghost.converter.emit_python import emit_python
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.verifier.flip import FlipSummary, find_flips
from ghost.verifier.run import load_compute

CID = "Calc!B5#1"
OPS = (">=", ">", "<=", "<")
TOL = Decimal("0.001")


def _build(tmp_path: Path, name: str, condition: str, probe: str, inputs: dict[str, IOSpec]):
    """Sheet Calc: B2 quantity = 3, B3 price = 25.5, B5 = IF(<condition>, ...), B6 = probe."""
    book = XlWorkbook()
    ws = book.active
    ws.title = "Calc"
    ws["A2"], ws["B2"] = "Quantity", 3
    ws["A3"], ws["B3"] = "Price", 25.5
    ws["A5"], ws["B5"] = "Tier", f'=IF({condition},"Gold","Standard")'
    ws["A6"], ws["B6"] = "Compared", f"={probe}"
    path = tmp_path / f"{name}.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    mapping = Mapping(
        inputs=inputs,
        outputs={
            "tier": IOSpec(cell="Calc!B5", type="string"),
            "compared": IOSpec(cell="Calc!B6", type="decimal"),
        },
    )
    return load_compute(emit_python(wb, mapping)), mapping


def _confirmed(compute, case: dict, op: str, threshold: int) -> tuple[bool, object]:
    """Evaluate the module at ``case``; True when its probe shows the two sides equal."""
    seen: list[tuple] = []

    def trace(cid, truth, *compared, **_):
        seen.append((cid, bool(truth), compared))

    out = compute(dict(case), trace)
    calls = [s for s in seen if s[0] == CID]
    equal_truth = op in (">=", "<=")
    ok = (
        Decimal(str(out["compared"])) == Decimal(threshold)
        and len(calls) == 1
        and calls[0][1] == equal_truth
    )
    compared = calls[0][2] if calls else ()
    if ok and len(compared) == 2:
        ok = Decimal(str(compared[0])) == Decimal(str(compared[1]))
    return ok, {"case": case, "compared_output": out.get("compared"), "trace": seen}


def _check_flips(compute, flips, summary: FlipSummary, op: str, threshold: int) -> None:
    """Shared assertions: a confirmed exact hit, no unconfirmed one, budget respected."""
    assert summary.evaluations_used <= summary.max_evaluations, summary
    if summary.cap_reached:
        assert summary.notes(), "budget cut the search short but no boundary note says so"
    hits = []
    for f in flips:
        if f.exact is None:
            continue
        ok, evidence = _confirmed(compute, {**f.others, f.input_name: f.exact}, op, threshold)
        assert ok, ("exact hit not confirmed by the module", f, evidence)
        hits.append(f)
    assert any(f.condition_id == CID for f in hits), (
        "no exact hit", [(f.condition_id, f.input_name, f.others, f.below, f.above, f.exact)
                         for f in flips], summary.notes(),
    )


def test_fixture_probe_is_sound(tmp_path):
    """Not xfail: guards the probe so the xfail below cannot hide a mistake in the setup."""
    inputs = {
        "quantity": IOSpec(cell="Calc!B2", type="integer", min=Decimal(1), max=Decimal(1000)),
        "price": IOSpec(cell="Calc!B3", type="decimal", min=Decimal(0), max=Decimal(1000)),
    }
    for op in OPS:
        compute, _ = _build(tmp_path, f"sound_{OPS.index(op)}", f"B2*B3{op}500", "B2*B3", inputs)
        at = {"quantity": Decimal(1), "price": Decimal(500)}
        assert _confirmed(compute, at, op, 500)[0], op
        off = {"quantity": Decimal(3), "price": Decimal("25.5")}
        assert not _confirmed(compute, off, op, 500)[0], op


@st.composite
def _product_case(draw):
    qmax = draw(st.integers(min_value=100, max_value=2000))
    pmax = draw(st.integers(min_value=100, max_value=2000))
    threshold = draw(st.integers(min_value=2, max_value=min(qmax, pmax) - 1))
    q0 = draw(st.sampled_from([3, 7, 9, 11, 13]))
    k = draw(st.integers(min_value=1, max_value=50))
    p0 = Decimal(k) + Decimal("0.5")
    # one-input-at-a-time from the samples cannot reach T exactly
    assume(threshold % q0 != 0)
    assume(threshold % (2 * k + 1) != 0)
    assume(p0 < threshold)
    op = draw(st.sampled_from(OPS))
    return op, threshold, qmax, pmax, q0, p0


@seed(20261124)
@settings(max_examples=30, deadline=None, derandomize=True, suppress_health_check=list(HealthCheck))
@given(case=_product_case())
def test_property_5_product_threshold_exact_hit_confirmed(tmp_path, case):
    """``IF(B2*B3 op T, ...)``, quantity integer in [1, qmax], price decimal in [0, pmax].

    **Validates: Requirements 2.3** (Property 5)
    """
    op, threshold, qmax, pmax, q0, p0 = case
    inputs = {
        "quantity": IOSpec(cell="Calc!B2", type="integer", min=Decimal(1), max=Decimal(qmax)),
        "price": IOSpec(cell="Calc!B3", type="decimal", min=Decimal(0), max=Decimal(pmax)),
    }
    name = f"product_{OPS.index(op)}_{threshold}_{qmax}_{pmax}_{q0}_{p0}"
    compute, mapping = _build(tmp_path, name, f"B2*B3{op}{threshold}", "B2*B3", inputs)
    summary = FlipSummary()
    flips = find_flips(compute, mapping, {"quantity": Decimal(q0), "price": p0},
                       tolerance=TOL, seed=1, summary=summary)
    _check_flips(compute, flips, summary, op, threshold)


@pytest.mark.parametrize("op", OPS)
def test_property_5_integer_single_input_exact_hit_at_50(tmp_path, op):
    """``IF(B2 op 50, ...)`` with quantity integer in [0, 100]: exact hit at 50.

    **Validates: Requirements 2.3** (Property 5, integer exact hits)
    """
    inputs = {"quantity": IOSpec(cell="Calc!B2", type="integer", min=Decimal(0), max=Decimal(100))}
    compute, mapping = _build(tmp_path, f"single_{OPS.index(op)}", f"B2{op}50", "B2", inputs)
    summary = FlipSummary()
    flips = find_flips(compute, mapping, {"quantity": Decimal(30)}, tolerance=TOL, seed=1,
                       summary=summary)
    _check_flips(compute, flips, summary, op, 50)
    assert {f.exact for f in flips if f.exact is not None} == {Decimal(50)}, flips
