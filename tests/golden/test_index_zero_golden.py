"""Golden tests for L-03: ``INDEX`` with a 0 row or column (implicit intersection).

live-fixes-2026-11-24, task 3.8. **Validates: Requirements 2.2, 3.14**

Each case is checked twice against a pinned expected value: the value the Referee
(LibreOffice) computes and the value the transpiled module computes. The expected
values come from the measurement in
``.kiro/specs/live-fixes-2026-11-24/measurements-l03.md`` (task 3.5), where
LibreOffice 26.8.3.1 (local) and 7.4.7.2 (live image) gave identical results for
every case used here. Excel was not checked; Excel 365 spills instead of intersecting.

Cases (all formulas use absolute ranges, so they read the same cells wherever they sit):

* single column ``M5:M7`` with row 0, formula on a row inside the range: the element
  on that row, edges included;
* the same formula on a row outside the range: ``#VALUE!``;
* single row ``E20:G20`` with column 0, by the formula's column: inside gives the
  element in that column, outside ``#VALUE!``;
* single cell ``T5`` (R-30): its value from any row;
* the live repro: ``B3`` = ``INDEX(M1:M3,0)`` gives 9.
"""
from __future__ import annotations

import pytest
from openpyxl import Workbook

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute

pytestmark = pytest.mark.golden

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available: golden tests need the Referee", allow_module_level=True)

V = "#VALUE!"

# Formula cell -> (formula, expected). Expected values are the measured Referee results.
CASES: dict[str, tuple[str, object]] = {
    # Single column M5:M7, row 0, formula row inside the range (rule 1).
    "Calc!B5": ("=INDEX($M$5:$M$7,0)", 7.0),    # top edge
    "Calc!B6": ("=INDEX($M$5:$M$7,0)", 8.0),    # middle
    "Calc!B7": ("=INDEX($M$5:$M$7,0)", 9.0),    # bottom edge
    "Calc!X6": ("=INDEX($M$5:$M$7,0)", 8.0),    # row 6, column right of the range
    "Calc!C6": ("=INDEX($M$5:$M$7,0,1)", 8.0),  # column given as 1
    # Same formulas on a row outside the range.
    "Calc!B4": ("=INDEX($M$5:$M$7,0)", V),      # just above
    "Calc!B8": ("=INDEX($M$5:$M$7,0)", V),      # just below
    "Calc!B12": ("=INDEX($M$5:$M$7,0)", V),     # far below
    "Calc!C9": ("=INDEX($M$5:$M$7,0,1)", V),
    # Single row E20:G20, column 0, by the formula's column (rule 2).
    "Calc!E30": ("=INDEX($E$20:$G$20,0)", 21.0),  # left edge
    "Calc!F30": ("=INDEX($E$20:$G$20,0)", 22.0),  # middle
    "Calc!G30": ("=INDEX($E$20:$G$20,0)", 23.0),  # right edge
    "Calc!F15": ("=INDEX($E$20:$G$20,0)", 22.0),  # column F, row above the range
    "Calc!D30": ("=INDEX($E$20:$G$20,0)", V),     # just left
    "Calc!H30": ("=INDEX($E$20:$G$20,0)", V),     # just right
    # Single cell T5 (R-30, rule 6): its value wherever the formula is.
    "Calc!AA5": ("=INDEX($T$5:$T$5,0)", 55.0),
    "Calc!AA9": ("=INDEX($T$5:$T$5,0)", 55.0),
    "Calc!AB9": ("=INDEX($T$5,0)", 55.0),
    "Calc!AC9": ("=INDEX($T$5:$T$5,0,0)", 55.0),
    # The live L-03 repro: row 3 lies in the rows of M1:M3.
    "Calc!B3": ("=INDEX(M1:M3,0)", 9.0),
}

DATA = {"M1": 7, "M2": 8, "M3": 9, "M5": 7, "M6": 8, "M7": 9,
        "E20": 21, "F20": 22, "G20": 23, "T5": 55}


def _plain(v):
    if isinstance(v, dict):
        return v.get("error", v)
    if isinstance(v, ExcelError):
        return v.code
    return v


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    path = tmp_path_factory.mktemp("golden_index0") / "index_zero.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    for ref, value in DATA.items():
        ws[ref] = value
    for cell, (formula, _) in CASES.items():
        ws[cell.split("!")[1]] = formula
    wb.save(path)

    book = load_workbook(str(path))
    mapping = generate_mapping(book, {c: "OUTPUT" for c in CASES})
    emitted = emit_module(book, mapping)
    assert not emitted.not_converted, emitted.not_converted
    got = load_compute(emitted.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    with RefereeClient(None, path) as ref:
        refv = ref.read(list(CASES))
    return {c: (_plain(refv[c]), _plain(got[name_of[c]])) for c in CASES}


@pytest.mark.parametrize("cell", list(CASES))
def test_referee_matches_measured_value(results, cell):
    formula, want = CASES[cell]
    assert values_equal(results[cell][0], want, 1e-6), (cell, formula, results[cell][0])


@pytest.mark.parametrize("cell", list(CASES))
def test_generated_code_matches_measured_value(results, cell):
    formula, want = CASES[cell]
    assert values_equal(results[cell][1], want, 1e-6), (cell, formula, results[cell][1])


def test_every_required_case_is_covered():
    """The four L-03 "Done when" cases are each present with both outcomes."""
    formulas = {f for f, _ in CASES.values()}
    assert "=INDEX($M$5:$M$7,0)" in formulas  # single column: inside and outside
    assert {w for f, w in CASES.values() if f == "=INDEX($M$5:$M$7,0)"} >= {7.0, 8.0, 9.0, V}
    assert {w for f, w in CASES.values() if f == "=INDEX($E$20:$G$20,0)"} >= {22.0, V}
    assert any("$T$5" in f for f in formulas)  # single cell (R-30)
