"""L-08 (task 5.7): cases that change which row MIN / MATCH selects.

**Validates: Requirements 1.7, 2.7, 3.8** (live-fixes-2026-11-24)

The workbook picks the cheapest of three rows with ``MIN`` and ``INDEX``/``MATCH``. Row A
costs 2x, row B costs 600-2x and row C is a flat 290, so C wins only for x = 146..154,
a region of 9 values in 0..10000. Nothing here needs LibreOffice: the mutants are
compared with the transpiled module itself.
"""
from __future__ import annotations

from decimal import Decimal

from openpyxl import Workbook as XlWorkbook

from ghost.converter.emit_python import emit_python
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.mutation.mutants import generate_mutants
from ghost.verifier.domain import effective_domains
from ghost.verifier.run import load_compute
from ghost.verifier.selection import SelectionSummary, find_selection_cases


def _build(tmp_path):
    book = XlWorkbook()
    ws = book.active
    ws.title = "S"
    ws["A1"], ws["B1"] = "x", 0
    for row, (name, cost) in enumerate([("A", "=2*B1"), ("B", "=600-2*B1"), ("C", 290)], start=3):
        ws[f"A{row}"], ws[f"B{row}"] = name, cost
    ws["B6"] = "=MIN(B3:B5)"
    ws["B7"] = "=INDEX(A3:A5,MATCH(B6,B3:B5,0))"
    path = tmp_path / "pick.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    mapping = Mapping(
        inputs={"x": IOSpec(cell="S!B1", type="integer", min=Decimal(0))},
        outputs={"cost": IOSpec(cell="S!B6", type="decimal"), "name": IOSpec(cell="S!B7", type="string")},
    )
    return wb, mapping


def test_search_finds_the_narrow_winning_region_and_kills_the_constant_mutant(tmp_path):
    wb, mapping = _build(tmp_path)
    source = emit_python(wb, mapping)
    compute = load_compute(source)
    base = {"x": 0}
    domains = effective_domains(mapping, base)
    summary = SelectionSummary()
    cases = find_selection_cases(compute, mapping, base, domains, seed=20261204, summary=summary)

    winners = {c["x"] for c in cases if compute(c)["name"] == "C"}
    assert winners and winners <= set(range(146, 155)), (winners, cases)
    # Both sides of the region are covered: the last A row and the first B row beside it.
    assert {compute(c)["name"] for c in cases} == {"A", "B", "C"}
    assert all(0 <= c["x"] <= 10_000 for c in cases)
    assert not summary.cap_reached and summary.notes() == []

    row_c = [m for m in generate_mutants(source) if "B5" in m.location]
    assert row_c, [m.location for m in generate_mutants(source)]
    for m in row_c:
        mutant = load_compute(m.source)
        assert any(mutant(c) != compute(c) for c in cases), m.mutant_id


def test_search_is_deterministic_and_reports_its_cap(tmp_path):
    wb, mapping = _build(tmp_path)
    compute = load_compute(emit_python(wb, mapping))
    domains = effective_domains(mapping, {"x": 0})
    first = find_selection_cases(compute, mapping, {"x": 0}, domains, seed=7)
    assert first == find_selection_cases(compute, mapping, {"x": 0}, domains, seed=7)

    summary = SelectionSummary()
    find_selection_cases(compute, mapping, {"x": 0}, domains, seed=7, max_evaluations=15, summary=summary)
    assert summary.cap_reached and summary.evaluations_used == 15
    assert any("stopped after 15 evaluations" in n for n in summary.notes())


def test_module_without_selection_gives_no_cases(tmp_path):
    book = XlWorkbook()
    ws = book.active
    ws.title = "S"
    ws["B1"], ws["B2"] = 3, "=B1*2"
    path = tmp_path / "plain.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    mapping = Mapping(
        inputs={"x": IOSpec(cell="S!B1", type="integer", min=Decimal(0))},
        outputs={"y": IOSpec(cell="S!B2", type="decimal")},
    )
    compute = load_compute(emit_python(wb, mapping))
    assert find_selection_cases(compute, mapping, {"x": 3}, effective_domains(mapping, {"x": 3})) == []


def test_cli_probe_returns_the_cases_that_reach_verifier_and_mutation(tmp_path):
    """``_probe_selection`` is what ``cmd_verify`` adds to ``extra_cases`` and the mutation
    check's targeted cases (as flip cases are)."""
    from ghost import cli

    wb, mapping = _build(tmp_path)
    cases, summary = cli._probe_selection(wb, mapping, effective_domains(mapping, {"x": 0}), 20261204)
    assert cases and summary.not_checked_reason is None
    assert any(146 <= c["x"] <= 154 for c in cases)
