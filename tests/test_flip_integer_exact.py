"""L-04 (task 3.10): integer exact hits, confirmed by the module's compared values.

**Validates: Requirements 1.3, 2.3** (live-fixes-2026-11-24)

No LibreOffice needed: workbooks are built with openpyxl (haunted from its committed
generator) and probed through the transpiled module.
"""
from __future__ import annotations

from decimal import Decimal

from openpyxl import Workbook as XlWorkbook

from ghost import cli
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.verifier.flip import FlipSummary, find_flips, flip_boundaries
from ghost.verifier.run import load_compute
from samples import make_haunted


def _haunted(tmp_path):
    wb = load_workbook(str(make_haunted.build(tmp_path / "haunted.xlsx")))
    return wb, generate_mapping(wb)


def test_haunted_quantity_50_is_an_exact_hit_for_b7_and_b9(tmp_path):
    """B7 ``B2>=E2`` (E2 = 50) and B9 ``B2>50``: quantity 50 makes each an equality."""
    wb, mapping = _haunted(tmp_path)
    flips, summary = cli._probe_flips_with_summary(wb, mapping)
    by_cell = {}
    for f in flips:
        if f.input_name == "quantity":
            by_cell.setdefault(f.condition_id, []).append(f)
    for cid in ("Calculator!B7#1", "Calculator!B9#1"):
        assert by_cell.get(cid), (cid, flips)
        assert {f.exact for f in by_cell[cid]} == {Decimal(50)}, by_cell[cid]
        for f in by_cell[cid]:
            assert {f.below, f.above} in ({Decimal(49), Decimal(50)}, {Decimal(50), Decimal(51)})
    assert not summary.exact_not_checked and not summary.exact_cut_short, summary.notes()
    rows = {(b.condition_id, b.input_name): b for b in flip_boundaries(flips)}
    assert rows[("Calculator!B7#1", "quantity")].exact == Decimal(50)
    assert rows[("Calculator!B9#1", "quantity")].exact == Decimal(50)


def _single(tmp_path, condition: str):
    book = XlWorkbook()
    ws = book.active
    ws.title = "S"
    ws["B1"] = 30
    ws["B2"] = f'=IF({condition},"y","n")'
    path = tmp_path / "s.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    mapping = Mapping(
        inputs={"q": IOSpec(cell="S!B1", type="integer", min=Decimal(0), max=Decimal(100))},
        outputs={"o": IOSpec(cell="S!B2", type="string")},
    )
    return wb, mapping


def test_no_exact_hit_when_no_integer_makes_the_sides_equal(tmp_path):
    """``B1*2>=101``: flips between 50 and 51, but 100 and 102 never equal 101."""
    wb, mapping = _single(tmp_path, "B1*2>=101")
    summary = FlipSummary()
    flips = find_flips(load_compute(emit_python(wb, mapping)), mapping, {"q": Decimal(30)},
                       seed=1, summary=summary)
    assert flips and all(f.exact is None for f in flips), flips
    assert not summary.exact_not_checked  # the check ran; it found no equality


def test_hand_written_module_without_compared_values_gets_no_exact_hit(tmp_path):
    """A module that calls ``trace(cid, bool)`` only: flips still found, exact hit
    reported as not checked, never inferred."""
    _, mapping = _single(tmp_path, "B1>=50")

    def compute(inputs, trace=None):
        q = inputs["q"]
        c = q >= 50
        if trace is not None:
            trace("S!B2#1", c)
        return {"o": "y" if c else "n"}

    summary = FlipSummary()
    flips = find_flips(compute, mapping, {"q": Decimal(30)}, seed=1, summary=summary)
    assert flips and all(f.exact is None for f in flips), flips
    assert ("S!B2#1", "q") in summary.exact_not_checked
    assert any(n.startswith("exact hit not checked (the module's trace did not report")
               for n in summary.notes()), summary.notes()


def test_condition_that_is_not_a_single_comparison_is_not_checked(tmp_path):
    """``AND(B1>=50,B1<=100)`` reports no compared values, so no exact hit is claimed."""
    wb, mapping = _single(tmp_path, "AND(B1>=50,B1<=100)")
    summary = FlipSummary()
    flips = find_flips(load_compute(emit_python(wb, mapping)), mapping, {"q": Decimal(30)},
                       seed=1, summary=summary)
    assert flips and all(f.exact is None for f in flips), flips
    assert ("S!B2#1", "q") in summary.exact_not_checked


def test_two_argument_trace_hooks_keep_working(tmp_path):
    """Existing ``trace(cid, bool)`` hooks get exactly two arguments; hooks that ask
    (``compared = True``) also get the two compared values."""
    wb, mapping = _single(tmp_path, "B1>=50")
    code = emit_python(wb, mapping)
    assert code == emit_python(wb, mapping)  # deterministic
    compute = load_compute(code)
    seen = []
    compute({"q": 50}, lambda cid, b: seen.append((cid, b)))
    assert seen == [("S!B2#1", True)]

    asked = []

    def trace(cid, b, *compared):
        asked.append((cid, b, compared))

    trace.compared = True
    compute({"q": 50}, trace)
    assert asked == [("S!B2#1", True, (Decimal(50), Decimal(50)))]


def test_budget_cut_during_the_exact_check_keeps_the_flip_and_says_so(tmp_path):
    """The flip found before the budget ran out is kept with exact None and a note."""
    wb, mapping = _single(tmp_path, "B1>=50")
    compute = load_compute(emit_python(wb, mapping))
    full = FlipSummary()
    find_flips(compute, mapping, {"q": Decimal(30)}, seed=1, summary=full)
    for limit in range(1, full.evaluations_used + 1):
        s = FlipSummary()
        flips = find_flips(compute, mapping, {"q": Decimal(30)}, seed=1, max_evaluations=limit,
                           summary=s)
        assert s.evaluations_used <= limit
        if s.exact_cut_short:
            assert s.cap_reached and flips and flips[-1].exact is None
            assert any("evaluation limit reached" in n for n in s.notes()), s.notes()
            return
    raise AssertionError("no budget limit fell inside the exact-hit check")
