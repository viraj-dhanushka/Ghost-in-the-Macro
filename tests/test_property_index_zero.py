"""Property 4: INDEX with 0 follows implicit intersection (PBT).

**Validates: Requirements 2.2, 3.10** (live-fixes-2026-11-24, task 3.6; finding L-03)

For random range shapes and positions and random formula-cell positions, in scalar
context, Ghost's generated ``INDEX`` gives what the Referee gives. The expected
value comes from ``referee_rule`` below, a small function written from the rules
measured in task 3.5 (``.kiro/specs/live-fixes-2026-11-24/measurements-l03.md``,
rules 1 to 3 and 5 to 8). It does not call into ``ghost.converter``.

Drawn cases:

* single column, row 0 (column omitted, 1 or 0), and ``INDEX(col,k,0)`` (rule 5)
* single row, column 0 (row omitted, 1 or 0), and ``INDEX(row,0,k)`` (rule 5)
* grid with exactly one index 0 and the other non-zero (rule 3)
* single cell (R-30, rule 6)
* range on another sheet (rule 7), the 0 read from a cell holding 0, and ``+0``
  on the result (rule 8)

The formula cell is never inside the range's rectangle, on its own sheet or the
other one: on the same sheet that is a circular reference, and across sheets it
was not measured.

Not drawn: ``INDEX`` inside ``SUM``/``AVERAGE`` (rule 9, aggregate context; task 3.7
implemented it, pinned by ``tests/test_index_zero_measurement.py`` and
``tests/test_index_zero_contexts.py``), a grid with both indexes 0 or a single 0 (rule 4, pinned by
``tests/test_index_zero_measurement.py``), and the cases listed as "Not checked" in
the measurement file.

Checks:

1. ``test_rule_reproduces_measured_table``: the oracle gives the measured Referee
   value for every scalar case in the measurement table (no LibreOffice needed).
2. ``test_property_4_generated_index_follows_measured_rule``: Hypothesis, explicit
   seed; each draw is its own workbook, converted with Ghost and compared with the
   oracle.
3. ``test_rule_matches_referee_on_sample`` and
   ``test_property_4_generated_index_matches_referee_on_sample``: a seeded sample
   covering every shape, inside and outside, same and other sheet, laid out one
   draw per sheet pair in one workbook, read from one module-scoped Referee.
   Skipped with a message when soffice is not installed.

The Ghost checks were strict xfail until task 3.7 fixed L-03; the markers are gone.
"""
from __future__ import annotations

import itertools
import random
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st
from openpyxl import Workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute
from tests.index_zero_probe import _DATA as PROBE_DATA

SEED = 20261124
V = "#VALUE!"
TOL = 1e-6
MAX_ROW = 40
MAX_COL = 26  # A..Z for ranges and formula cells
ZERO_COL = 30  # AD: the cell holding 0 lives here, clear of every range and formula
SHAPES = ("column", "row", "grid_row0", "grid_col0", "cell")
MEASUREMENTS = (Path(__file__).resolve().parent.parent
                / ".kiro/specs/live-fixes-2026-11-24/measurements-l03.md")


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


needs_referee = pytest.mark.skipif(
    not _has_soffice(), reason="LibreOffice (soffice) not installed: the Referee is unavailable")


# --------------------------------------------------------------------------
# Case model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexCase:
    """One ``INDEX`` formula with a 0 argument, in scalar context."""

    shape: str
    top: int
    left: int
    rows: int
    cols: int
    values: tuple[int, ...]  # row-major
    args: tuple[str, ...]  # "0" or a positive whole number, as written
    formula_sheet: str  # "Calc" or "Data"
    range_sheet: str
    f_row: int
    f_col: int
    zero_from_cell: bool  # every "0" argument is a reference to a cell holding 0
    zero_row: int  # row of that cell, column ZERO_COL, formula sheet
    plus0: bool  # formula is INDEX(...)+0
    single_ref: bool  # INDEX($T$5,0) rather than INDEX($T$5:$T$5,0)


def referee_rule(c: IndexCase) -> int | str:
    """Referee value for ``c``, from the rules in measurements-l03.md.

    Rule 8: a 0 read from a cell and a ``+0`` on the result behave like the bare
    literal, so ``zero_from_cell`` and ``plus0`` are not consulted. Rule 7: the
    formula's own row and column numbers are compared with the range's, whatever
    the sheets, so the sheets are not consulted either.
    """
    if c.rows == 1 and c.cols == 1:  # rule 6 (R-30): the cell, wherever the formula is
        return c.values[0]
    nums = [int(a) for a in c.args]
    if len(nums) == 1:
        if nums[0] == 0 and c.rows > 1 and c.cols > 1:
            return V  # rule 4: one argument 0 on a grid
        ri, ci = (1, nums[0]) if c.rows == 1 else (nums[0], 1)
    else:
        ri, ci = nums
    if ri == 0 and c.rows == 1:  # rule 5: a 0 on a length-1 dimension selects it
        ri = 1
    if ci == 0 and c.cols == 1:
        ci = 1
    if ri == 0 and ci == 0:
        return V  # rule 4: both 0 on a grid
    if ri == 0:  # rules 1 and 3: intersect with the formula's row, edges included
        if not c.top <= c.f_row <= c.top + c.rows - 1:
            return V
        ri = c.f_row - c.top + 1
    if ci == 0:  # rules 2 and 3: intersect with the formula's column
        if not c.left <= c.f_col <= c.left + c.cols - 1:
            return V
        ci = c.f_col - c.left + 1
    return c.values[(ri - 1) * c.cols + (ci - 1)]


# --------------------------------------------------------------------------
# Drawing cases: one generator, driven by Hypothesis or by a seeded Random
# --------------------------------------------------------------------------


class _HypothesisChooser:
    def __init__(self, draw):
        self._draw = draw

    def int(self, lo: int, hi: int) -> int:
        return self._draw(st.integers(lo, hi))

    def choice(self, seq):
        return self._draw(st.sampled_from(list(seq)))

    def flag(self) -> bool:
        return self._draw(st.booleans())

    def distinct(self, n: int) -> tuple[int, ...]:
        return tuple(self._draw(st.lists(st.integers(1, 999), min_size=n, max_size=n, unique=True)))


class _RandomChooser:
    def __init__(self, rng: random.Random):
        self._rng = rng

    def int(self, lo: int, hi: int) -> int:
        return self._rng.randint(lo, hi)

    def choice(self, seq):
        return self._rng.choice(list(seq))

    def flag(self) -> bool:
        return self._rng.random() < 0.5

    def distinct(self, n: int) -> tuple[int, ...]:
        return tuple(self._rng.sample(range(1, 1000), n))


def make_case(ch, shape: str | None = None, inside: bool | None = None,
              other_sheet: bool | None = None, zero_from_cell: bool | None = None) -> IndexCase:
    """Draw one case. ``inside``: the formula shares the intersected row (or column)."""
    shape = shape or ch.choice(SHAPES)
    if shape == "column":
        rows, cols = ch.int(2, 6), 1
        args = ch.choice([("0",), ("0", "1"), ("0", "0"), (str(ch.int(1, rows)), "0")])
        axis = "row"
    elif shape == "row":
        rows, cols = 1, ch.int(2, 6)
        args = ch.choice([("0",), ("1", "0"), ("0", "0"), ("0", str(ch.int(1, cols)))])
        axis = "col"
    elif shape == "grid_row0":
        rows, cols = ch.int(2, 5), ch.int(2, 5)
        args = ("0", str(ch.int(1, cols)))
        axis = "row"
    elif shape == "grid_col0":
        rows, cols = ch.int(2, 5), ch.int(2, 5)
        args = (str(ch.int(1, rows)), "0")
        axis = "col"
    else:  # single cell
        rows, cols = 1, 1
        args = ch.choice([("0",), ("0", "0")])
        axis = ch.choice(("row", "col"))
    single_ref = shape == "cell" and args == ("0",) and ch.flag()
    top = ch.int(1, MAX_ROW - rows + 1)
    left = ch.int(1, MAX_COL - cols + 1)
    inside = ch.flag() if inside is None else inside
    row_span = range(top, top + rows)
    col_span = range(left, left + cols)
    rows_out = [r for r in range(1, MAX_ROW + 1) if r not in row_span]
    cols_out = [c for c in range(1, MAX_COL + 1) if c not in col_span]
    if axis == "row":
        f_row = ch.choice(row_span) if inside else ch.choice(rows_out)
        f_col = ch.choice(cols_out) if inside else ch.int(1, MAX_COL)
    else:
        f_col = ch.choice(col_span) if inside else ch.choice(cols_out)
        f_row = ch.choice(rows_out) if inside else ch.int(1, MAX_ROW)
    values = ch.distinct(rows * cols)
    other_sheet = ch.flag() if other_sheet is None else other_sheet
    formula_sheet = ch.choice(("Calc", "Data"))
    range_sheet = ({"Calc": "Data", "Data": "Calc"}[formula_sheet] if other_sheet
                   else formula_sheet)
    zero_from_cell = ch.flag() if zero_from_cell is None else zero_from_cell
    return IndexCase(
        shape=shape, top=top, left=left, rows=rows, cols=cols, values=values, args=args,
        formula_sheet=formula_sheet, range_sheet=range_sheet, f_row=f_row, f_col=f_col,
        zero_from_cell=zero_from_cell, zero_row=ch.int(1, MAX_ROW), plus0=ch.flag(),
        single_ref=single_ref,
    )


@st.composite
def index_cases(draw) -> IndexCase:
    return make_case(_HypothesisChooser(draw))


def referee_sample() -> list[IndexCase]:
    """Seeded sample for the Referee: every shape x inside/outside x same/other sheet, twice."""
    ch = _RandomChooser(random.Random(SEED))
    return [
        make_case(ch, shape=shape, inside=inside, other_sheet=other,
                  zero_from_cell=True if rep else None)
        for rep in (0, 1)
        for shape in SHAPES
        for inside in (True, False)
        for other in (False, True)
    ]


# --------------------------------------------------------------------------
# Workbooks
# --------------------------------------------------------------------------


def _a1(row: int, col: int) -> str:
    return f"{get_column_letter(col)}{row}"


def formula_text(c: IndexCase, sheet_name: dict[str, str]) -> str:
    first = f"${get_column_letter(c.left)}${c.top}"
    last = f"${get_column_letter(c.left + c.cols - 1)}${c.top + c.rows - 1}"
    rng = first if c.single_ref else f"{first}:{last}"
    if c.range_sheet != c.formula_sheet:
        rng = f"{sheet_name[c.range_sheet]}!{rng}"
    zero = f"${get_column_letter(ZERO_COL)}${c.zero_row}" if c.zero_from_cell else "0"
    args = ",".join(zero if a == "0" else a for a in c.args)
    return f"=INDEX({rng},{args})" + ("+0" if c.plus0 else "")


def _place(sheets: dict, c: IndexCase, sheet_name: dict[str, str]) -> str:
    """Write ``c`` into the workbook; return the formula cell reference."""
    rs = sheets[sheet_name[c.range_sheet]]
    for i, v in enumerate(c.values):
        rs.cell(row=c.top + i // c.cols, column=c.left + i % c.cols, value=v)
    fs = sheets[sheet_name[c.formula_sheet]]
    if c.zero_from_cell:
        fs.cell(row=c.zero_row, column=ZERO_COL, value=0)
    fs.cell(row=c.f_row, column=c.f_col, value=formula_text(c, sheet_name))
    return f"{sheet_name[c.formula_sheet]}!{_a1(c.f_row, c.f_col)}"


def build_workbook(path: Path, cases: list[IndexCase]) -> tuple[Path, list[str]]:
    """One case per sheet pair (``C<i>`` for Calc, ``D<i>`` for Data), so cases never collide."""
    wb = Workbook()
    wb.remove(wb.active)
    sheets: dict = {}
    refs = []
    for i, c in enumerate(cases):
        names = {"Calc": f"C{i:02d}", "Data": f"D{i:02d}"} if len(cases) > 1 else {
            "Calc": "Calc", "Data": "Data"}
        for logical in ("Calc", "Data"):
            sheets[names[logical]] = wb.create_sheet(names[logical])
        refs.append(_place(sheets, c, names))
    wb.save(path)
    return path, refs


def _plain(v: object) -> object:
    """Referee ``{"error": ...}`` and ``ExcelError`` as their text; other values unchanged."""
    if isinstance(v, dict) and "error" in v:
        return v["error"]
    if isinstance(v, ExcelError):
        return v.code
    return v


def ghost_values(path: Path, refs: list[str]) -> dict[str, object]:
    """Ghost's generated code on ``path``: one value per formula cell (no inputs)."""
    book = load_workbook(str(path))
    mapping = generate_mapping(book, {r: "OUTPUT" for r in refs})
    emitted = emit_module(book, mapping)
    not_converted = {nc.cell: nc.reason for nc in emitted.not_converted}
    out = load_compute(emitted.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    return {r: (f"not converted: {not_converted[r]}" if r in not_converted
                else _plain(out.get(name_of[r]))) for r in refs}


def _describe(c: IndexCase, ref: str) -> str:
    return (f"{ref} {formula_text(c, {'Calc': 'Calc', 'Data': 'Data'})} "
            f"range {c.range_sheet} rows {c.top}-{c.top + c.rows - 1} "
            f"cols {c.left}-{c.left + c.cols - 1} values {c.values}")


# --------------------------------------------------------------------------
# 1. The oracle reproduces the measured table
# --------------------------------------------------------------------------

_PROBE_FORMULA = re.compile(
    r"^=INDEX\((?:(\w+)!)?\$([A-Z]+)\$(\d+)(?::\$([A-Z]+)\$(\d+))?,([^,()]+)(?:,([^,()]+))?\)(\+0)?$")


def _measured_scalar_rows() -> list[tuple[str, IndexCase, object]]:
    """Scalar rows of the measurement table as (case id, IndexCase, Referee value)."""
    rows = []
    for line in MEASUREMENTS.read_text(encoding="utf-8").splitlines():
        cells = [x.strip() for x in line.split("|")]
        if len(cells) < 9 or not cells[3].startswith("`="):
            continue
        cid, ref, formula, lo26, lo74 = cells[1], cells[2], cells[3].strip("`"), cells[5], cells[6]
        assert lo26 == lo74, (cid, lo26, lo74)
        m = _PROBE_FORMULA.match(formula)
        if m is None:  # SUM / AVERAGE rows: aggregate context, rule 9, not in Property 4
            assert formula.startswith(("=SUM(", "=AVERAGE(")), formula
            continue
        rsheet, c1, r1, c2, r2, a, b, plus0 = m.groups()
        fsheet, faddr = ref.split("!")
        fm = re.fullmatch(r"([A-Z]+)(\d+)", faddr)
        left, top = column_index_from_string(c1), int(r1)
        right, bottom = (column_index_from_string(c2), int(r2)) if c2 else (left, top)
        rsheet = rsheet or fsheet
        data = PROBE_DATA[rsheet]
        values = tuple(data[_a1(r, c)] for r in range(top, bottom + 1)
                       for c in range(left, right + 1))
        args = tuple(x for x in (a, b) if x is not None)
        zero_cells = [x for x in args if x.startswith("$")]
        assert all(PROBE_DATA[fsheet][x.replace("$", "")] == 0 for x in zero_cells), zero_cells
        case = IndexCase(
            shape="measured", top=top, left=left, rows=bottom - top + 1, cols=right - left + 1,
            values=values, args=tuple("0" if x.startswith("$") else x for x in args),
            formula_sheet=fsheet, range_sheet=rsheet, f_row=int(fm.group(2)),
            f_col=column_index_from_string(fm.group(1)), zero_from_cell=bool(zero_cells),
            zero_row=0, plus0=bool(plus0), single_ref=c2 is None,
        )
        rows.append((cid, case, lo26 if lo26.startswith("#") else int(lo26)))
    return rows


def test_rule_reproduces_measured_table():
    rows = _measured_scalar_rows()
    assert len(rows) == 59, len(rows)  # 69 measured, less the 10 SUM/AVERAGE rows
    wrong = [(cid, expected, referee_rule(c)) for cid, c, expected in rows
             if not values_equal(expected, referee_rule(c), TOL)]
    assert not wrong, wrong


# --------------------------------------------------------------------------
# 2. Property 4 on Ghost's generated code
# --------------------------------------------------------------------------

_counter = itertools.count()


@pytest.fixture(scope="module")
def workdir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("property4")


@seed(SEED)
@settings(max_examples=120, deadline=None, derandomize=True, database=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(case=index_cases())
def test_property_4_generated_index_follows_measured_rule(case, workdir):
    """Property 4: INDEX with 0 follows implicit intersection.

    **Validates: Requirements 2.2, 3.10**
    """
    path, (ref,) = build_workbook(workdir / f"case_{next(_counter)}.xlsx", [case])
    ghost = ghost_values(path, [ref])[ref]
    expected = referee_rule(case)
    assert values_equal(expected, ghost, TOL), {
        "case": _describe(case, ref), "expected (measured rule)": expected, "ghost": ghost}


# --------------------------------------------------------------------------
# 3. Cross-check a seeded sample against the real Referee (one batched workbook)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def batch(tmp_path_factory):
    """The sample workbook and one Referee for the module, with every formula cell read."""
    if not _has_soffice():
        pytest.skip("LibreOffice (soffice) not installed: the Referee is unavailable")
    cases = referee_sample()
    path, refs = build_workbook(tmp_path_factory.mktemp("property4_batch") / "batch.xlsx", cases)
    with RefereeClient(None, path) as referee:
        values = {r: _plain(v) for r, v in referee.read(refs).items()}
        yield cases, refs, path, values


def test_referee_sample_covers_every_shape_and_placement():
    cases = referee_sample()
    combos = {(c.shape, c.formula_sheet != c.range_sheet) for c in cases}
    assert combos == {(s, o) for s in SHAPES for o in (False, True)}
    assert any(c.zero_from_cell for c in cases) and any(c.plus0 for c in cases)
    # Each non-cell shape has cases the unfixed code gets wrong (inside) and right (outside).
    for shape in SHAPES[:-1]:
        kinds = {referee_rule(c) == V for c in cases if c.shape == shape}
        assert kinds == {True, False}, shape


@needs_referee
def test_rule_matches_referee_on_sample(batch):
    """The oracle agrees with the real Referee on the seeded sample."""
    cases, refs, _, referee = batch
    wrong = [(_describe(c, r), "rule", referee_rule(c), "referee", referee[r])
             for c, r in zip(cases, refs) if not values_equal(referee_rule(c), referee[r], TOL)]
    assert not wrong, wrong


@needs_referee
def test_property_4_generated_index_matches_referee_on_sample(batch):
    """Property 4 against the real Referee: Ghost's value equals LibreOffice's.

    **Validates: Requirements 2.2, 3.10**
    """
    cases, refs, path, referee = batch
    ghost = ghost_values(path, refs)
    wrong = [(_describe(c, r), "referee", referee[r], "ghost", ghost[r])
             for c, r in zip(cases, refs) if not values_equal(referee[r], ghost[r], TOL)]
    assert not wrong, wrong
