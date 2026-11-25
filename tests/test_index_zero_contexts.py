"""L-03 (task 3.7): ``INDEX`` contexts measured while fixing implicit intersection.

The task 3.5 table (``tests/test_index_zero_measurement.py``) lists as "not checked"
several contexts the fix touches. Task 3.7 measured them with
``tests/index_zero_contexts_probe.py`` on 2026-11-24, on LibreOffice 26.8.3.1 (local)
and 7.4.7.2 (Docker image ``ghost-local:l03``, not pushed). This file pins the Referee
result per major version and checks Ghost's generated code against it.

What the measurement showed (both versions unless stated):

* A direct ``INDEX`` argument of ``SUM``, ``AVERAGE``, ``MIN``, ``MAX``, ``AND`` or
  ``OR`` is a reference: the whole selected row, column, grid or cell, with text
  skipped (``SUM(INDEX(N5:N7,1))`` with "x" in N5 is 0), wherever the formula is. A
  computed 0 behaves like a literal 0. Ghost: ``_index_area``.
* Inside ``IF``, ``ROUND``, ``IFERROR``, ``CHOOSE`` at the top level, and inside
  arithmetic within ``SUM`` (``SUM(INDEX(...)+1)``), ``INDEX`` intersects like a bare
  formula. Ghost: ``_index`` with the formula cell's position.
* A grid with the column omitted selects the whole row: ``INDEX(Q5:R7,2)`` is 32 in
  column Q, 42 in column R, ``#VALUE!`` elsewhere, and 74 inside ``SUM``.
* Error order: a negative index is ``#VALUE!``; then an index past the end is
  ``#REF!`` on 26.8.3.1 and ``#VALUE!`` on 7.4.7.2 (``PAST_END``); then a 0 on a
  longer dimension intersects. Ghost gives ``#REF!`` for an index past the end (as
  before this task, for example ``INDEX(M1:M3,5)``), so these cases match 26.8.3.1
  and not 7.4.7.2. Fractions truncate (``0.5`` is 0, ``1.9`` is 1); ``"0"``, FALSE
  and an empty cell are 0; TRUE is 1.
* ``INDEX`` passed through ``IF``, ``IFERROR`` or ``CHOOSE`` inside ``SUM`` stays a
  reference (24 from row 9) and ``IFERROR`` differs by position (24 on row 6, 0 on
  row 9). Ghost cannot reproduce this, so such cells are "not converted" with the
  reason ``INDEX_PASSED_THROUGH`` (``ghost/converter/subset.py``). An ``INDEX`` whose
  indexes are literal whole numbers of 1 or more stays converted (``AZ9``, 8).

Excel was not checked. Excel 365 spills instead of intersecting.

**Validates: Requirements 2.2, 3.10**
"""
from __future__ import annotations

import re

import pytest

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.converter.subset import INDEX_PASSED_THROUGH, find_not_converted
from ghost.ingest.workbook import load_workbook
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute
from tests.index_zero_contexts_probe import CASES, build_workbook, measure_referee

V, R = "#VALUE!", "#REF!"

# Formula cell -> Referee result, identical on LibreOffice 7.4.7.2 and 26.8.3.1.
_SAME: dict[str, object] = {
    "Calc!B6": 24, "Calc!C6": 7, "Calc!D6": 9, "Calc!E6": False, "Calc!F6": True,
    "Calc!G6": 1, "Calc!H6": 8, "Calc!I6": 25, "Calc!J6": 4, "Calc!K6": 8,
    "Calc!L6": 8, "Calc!O6": 24, "Calc!S6": 8, "Calc!T6": 8, "Calc!U6": 222,
    "Calc!V6": "#DIV/0!", "Calc!W6": 222, "Calc!X6": -8, "Calc!Y6": 8, "Calc!AA6": 24,
    "Calc!AB6": 8, "Calc!AC6": 7, "Calc!AD6": 8, "Calc!AE6": 8,
    "Calc!AG6": V, "Calc!AH6": V, "Calc!AN6": V,
    "Calc!B9": 24, "Calc!C9": 7, "Calc!D9": 9, "Calc!E9": False, "Calc!F9": True,
    "Calc!G9": V, "Calc!H9": V, "Calc!I9": V, "Calc!J9": 4, "Calc!K9": 4,
    "Calc!L9": V, "Calc!O9": 24, "Calc!S9": -1, "Calc!T9": 24, "Calc!U9": 0,
    "Calc!V9": 7, "Calc!W9": 74, "Calc!X9": V, "Calc!Q9": 32, "Calc!R9": 42,
    "Calc!Y9": 222, "Calc!AA9": 24, "Calc!AB9": 66, "Calc!AE9": 43, "Calc!AF9": 24,
    "Calc!AG9": 7, "Calc!AH9": 24, "Calc!AI9": 8,
    "Calc!AN9": V, "Calc!AO9": V, "Calc!AP9": V, "Calc!AQ9": 16, "Calc!AR9": V,
    "Calc!AS9": V, "Calc!AT9": V, "Calc!AV9": V, "Calc!Q12": 31,
    "Calc!AW6": 24, "Calc!AX6": 24, "Calc!AY6": 24,
    "Calc!AW9": 24, "Calc!AX9": 0, "Calc!AY9": 24, "Calc!AZ9": 8,
}
# An index past the end: #REF! on 26.8.3.1, #VALUE! on 7.4.7.2.
PAST_END = ("Calc!AF6", "Calc!AI6", "Calc!AC9", "Calc!AD9", "Calc!AJ9", "Calc!AK9",
            "Calc!AL9", "Calc!Q10", "Calc!AM9", "Calc!F30", "Calc!AU9")
EXPECTED: dict[int, dict[str, object]] = {
    26: _SAME | {c: R for c in PAST_END},
    7: _SAME | {c: V for c in PAST_END},
}
NOT_CONVERTED = ("Calc!AW6", "Calc!AX6", "Calc!AY6", "Calc!AW9", "Calc!AX9", "Calc!AY9")
CELLS = [ref for ref, _ in CASES]
FORMULA = dict(CASES)


def _plain(v: object) -> object:
    return v.code if isinstance(v, ExcelError) else v


@pytest.fixture(scope="module")
def book_path(tmp_path_factory):
    return build_workbook(tmp_path_factory.mktemp("l03ctx") / "index_zero_contexts.xlsx")


@pytest.fixture(scope="module")
def ghost(book_path):
    book = load_workbook(str(book_path))
    mapping = generate_mapping(book, {r: "OUTPUT" for r in CELLS})
    emitted = emit_module(book, mapping)
    out = load_compute(emitted.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    nc = {e.cell: e.reason for e in emitted.not_converted}
    return {r: (f"not converted: {nc[r]}" if r in nc else _plain(out.get(name_of[r])))
            for r in CELLS}, book, emitted


@pytest.fixture(scope="module")
def referee(tmp_path_factory):
    try:
        locate_soffice()
    except RefereeUnavailable as exc:  # pragma: no cover
        pytest.skip(f"LibreOffice (soffice) not installed: the Referee is unavailable ({exc})")
    result = measure_referee(tmp_path_factory.mktemp("l03ctx_ref"))
    m = re.match(r"(\d+)\.", result["libreoffice"])
    if not m:  # pragma: no cover
        pytest.skip(f"cannot read the LibreOffice version from {result['libreoffice']!r}")
    return int(m.group(1)), result["referee"]


def test_every_case_has_an_expectation():
    assert set(CELLS) == set(_SAME) | set(PAST_END)
    assert not set(_SAME) & set(PAST_END)
    assert set(NOT_CONVERTED) <= set(CELLS)


@pytest.mark.parametrize("cell", CELLS)
def test_referee_result_is_pinned(referee, cell):
    major, values = referee
    if major not in EXPECTED:
        pytest.skip(f"LibreOffice {major} has no pinned expectations; run the probe")
    assert values_equal(values[cell], EXPECTED[major][cell], 1e-6), (
        f"LibreOffice {major} changed {FORMULA[cell]} at {cell}: {values[cell]!r}")


@pytest.mark.parametrize("cell", [c for c in CELLS if c not in NOT_CONVERTED])
def test_ghost_matches_measured_result(ghost, cell):
    """Ghost equals the Referee (26.8.3.1 for an index past the end, see ``PAST_END``)."""
    got, _, _ = ghost
    want = EXPECTED[26][cell]
    assert values_equal(want, got[cell], 1e-6), (cell, FORMULA[cell], "want", want, "ghost", got[cell])


@pytest.mark.parametrize("cell", [c for c in CELLS if c not in NOT_CONVERTED and c not in PAST_END])
def test_ghost_matches_installed_referee(ghost, referee, cell):
    """Ghost equals whichever Referee is installed, on every case both versions agree on."""
    got, _, _ = ghost
    _, values = referee
    assert values_equal(values[cell], got[cell], 1e-6), (
        cell, FORMULA[cell], "referee", values[cell], "ghost", got[cell])


@pytest.mark.parametrize("cell", NOT_CONVERTED)
def test_index_passed_through_inside_aggregate_is_not_converted(ghost, cell):
    """INDEX through IF/IFERROR/CHOOSE inside SUM is listed with cell and reason, never guessed."""
    got, book, emitted = ghost
    listed = {(e.cell, e.reason) for e in find_not_converted(book)}
    assert (cell, INDEX_PASSED_THROUGH) in listed
    assert got[cell] == f"not converted: {INDEX_PASSED_THROUGH}"
    assert f"#   {cell}: {INDEX_PASSED_THROUGH}" in emitted.code


def test_generated_code_is_deterministic_and_carries_the_position(book_path, ghost):
    _, _, emitted = ghost
    book = load_workbook(str(book_path))
    again = emit_module(book, generate_mapping(book, {r: "OUTPUT" for r in CELLS}))
    assert again.code == emitted.code
    # The formula cell's own sheet, row and column, and the range origin, are constants.
    assert ("v['Calc!G9'] = _if(trace, 'Calc!G9#1', xl_gt(_index(_Rng(3, 1, "
            "[v['Calc!M5'], v['Calc!M6'], v['Calc!M7']], 5, 13), Decimal('0'), None, "
            "at=('Calc', 9, 7)), Decimal('7'))") in emitted.code
    assert ("_sum(_index_area(_Rng(3, 1, [v['Calc!M5'], v['Calc!M6'], v['Calc!M7']]), "
            "v['Calc!Z1']))") in emitted.code
