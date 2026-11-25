"""Preservation tests for ``.kiro/specs/live-fixes-2026-11-24`` (task 2).

**Property 2: Preservation** - behaviour outside the L-02 to L-08 bug conditions
stays as it is on the unfixed code.
**Validates: Requirements 3.9, 3.10**

The demo storyline and mutation floors (clauses 3.1 to 3.5) are in
``tests/test_demo_invariants.py``; the sample default boxes (clause 3.11) in
``tests/test_web_samples.py``; R-30 single-cell ``INDEX`` cases in
``tests/test_review_semantics.py``. This file adds what none of them pins.

Real output on the unfixed code (24 Nov 2026, LibreOffice 26.8.3):

* ``=10/B1`` with input B1 = 0: Referee ``#DIV/0!``, Ghost ``#DIV/0!``; ``verify``
  with that case added passes with 0 mismatches.
* ``INDEX`` from formula cells in column B, rows 10 to 15, outside the rows and
  columns of ``M1:O3``: ``INDEX(M1:N3,2,2)`` 18, ``INDEX(M1:M3,3)`` 9, and
  ``INDEX(M1:M3,0)``, ``INDEX(M1:O1,0)``, ``INDEX(M1:N3,0,1)``,
  ``INDEX(M1:O1,1,0)`` all ``#VALUE!`` on both sides. The positions are explicit
  here because L-03 makes the result of a 0 index depend on where the formula is.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import Workbook

from ghost.converter.emit_python import emit_module, emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import values_equal
from ghost.verifier.run import VerifyConfig, load_compute, verify

try:
    locate_soffice()
    _SOFFICE_MSG = None
except RefereeUnavailable as exc:
    _SOFFICE_MSG = f"LibreOffice (soffice) not installed: the Referee is unavailable ({exc})"

pytestmark = pytest.mark.skipif(_SOFFICE_MSG is not None, reason=_SOFFICE_MSG or "")

SEED = 20261204


def _referee_value(v):
    return v["error"] if isinstance(v, dict) else v


def test_excel_error_on_both_sides_passes(tmp_path):
    """Clause 3.9: ``=10/B1`` at B1 = 0 is ``#DIV/0!`` on both sides, and the case passes."""
    path = tmp_path / "div.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"], ws["B1"] = "Amount", 2
    ws["A2"], ws["B2"] = "Ratio", "=10/B1"
    wb.save(path)

    book = load_workbook(str(path))
    mapping = generate_mapping(book, {"Calc!B1": "INPUT", "Calc!B2": "OUTPUT"})
    (in_name,) = mapping.inputs
    (out_name,) = mapping.outputs
    source = emit_python(book, mapping)
    ghost = load_compute(source)({in_name: 0})[out_name]
    assert isinstance(ghost, ExcelError) and ghost.code == "#DIV/0!"
    with RefereeClient(None, path) as ref:
        assert _referee_value(ref.eval({"Calc!B1": 0}, ["Calc!B2"])["Calc!B2"]) == "#DIV/0!"
        res = verify(source, mapping, ref,
                     VerifyConfig(seed=SEED, max_examples=20, extra_cases=[{in_name: 0}]))
    assert {in_name: 0} in res.cases, "the B1 = 0 case must have been run"
    assert res.passed is True and res.mismatches == []


# Formula cell -> (formula, value measured on the Referee and Ghost, unfixed code).
INDEX_PINNED = {
    "B10": ("=INDEX(M1:N3,2,2)", Decimal(18)),
    "B11": ("=INDEX(M1:M3,3)", Decimal(9)),
    "B12": ("=INDEX(M1:M3,0)", "#VALUE!"),    # row 0, single column, row 12 outside 1-3
    "B13": ("=INDEX(M1:O1,0)", "#VALUE!"),    # column 0, single row, column B outside M-O
    "B14": ("=INDEX(M1:N3,0,1)", "#VALUE!"),  # row 0, multi-row range, row 14 outside 1-3
    "B15": ("=INDEX(M1:O1,1,0)", "#VALUE!"),  # column 0, single row, column B outside M-O
}


@pytest.fixture(scope="module")
def index_results(tmp_path_factory):
    path = tmp_path_factory.mktemp("idx") / "index_pinned.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    for i, v in enumerate((7, 8, 9), start=1):
        ws[f"M{i}"] = v
    for i, v in enumerate((17, 18, 19), start=1):
        ws[f"N{i}"] = v
    ws["O1"] = 27
    for cell, (formula, _) in INDEX_PINNED.items():
        ws[cell] = formula
    wb.save(path)

    book = load_workbook(str(path))
    roles = {ref: ("OUTPUT" if c.formula else "PARAMETER") for ref, c in book.cells.items()}
    mapping = generate_mapping(book, roles)
    got = load_compute(emit_module(book, mapping).code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    refs = [f"Calc!{cell}" for cell in INDEX_PINNED]
    with RefereeClient(None, path) as ref:
        refv = ref.read(refs)
    return {cell: (_referee_value(refv[f"Calc!{cell}"]), got.get(name_of[f"Calc!{cell}"]))
            for cell in INDEX_PINNED}


@pytest.mark.parametrize("cell", sorted(INDEX_PINNED))
def test_index_pinned_cases_keep_their_results(index_results, cell):
    """Clause 3.10: non-zero indexes give the element; a 0 from outside the range gives #VALUE!."""
    formula, want = INDEX_PINNED[cell]
    referee, ghost = index_results[cell]
    assert values_equal(referee, want, 1e-6), (cell, formula, "referee", referee)
    assert values_equal(ghost, want, 1e-6), (cell, formula, "ghost", ghost)
