"""Property 9: Formula fuzzing agrees with the Referee (PBT).

**Validates: Requirements 1.31, 2.31, 3.7** (review-fixes-2026-11-24, task 9.4)

Formulas are drawn from a grammar of the P0 subset and written into one workbook per
example (a batch of formulas, so one Referee call per example). The workbook is
recalculated by one long-lived Referee (module-scoped) and by the transpiled module, and
the results are compared with the verifier's ``values_equal`` (1e-6, exact strings,
errors by type). Hypothesis shrinks a failing batch to the smallest formula.

Grammar exclusions (see .kiro/steering/excel-semantics.md):
- the seven R-24 LibreOffice/Excel differences: ``^`` takes only a literal exponent of 1
  to 3 (no ``0^0``, no negative base with a fractional exponent); comparisons only compare
  like with like (no ``TRUE>1``); text is only built from numbers and text (no
  ``TRUE&""``); SUM/MIN/MAX/AVERAGE take numbers only (no text arguments); no MATCH.
- the R-25 ROUND case with more than 15 significant digits: literals are small and depth
  is at most 3.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st
from openpyxl import Workbook

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

SEED = 20261124
MAX_DEPTH = 3
INPUT_CELLS = ["A1", "A2", "A3"]

# -- grammar ---------------------------------------------------------------

_int_lit = st.integers(-20, 20).map(lambda n: f"({n})" if n < 0 else str(n))
_dec_lit = st.integers(-200, 200).map(lambda n: f"({n / 10})" if n < 0 else str(n / 10))
_num_leaf = st.one_of(_int_lit, _dec_lit, st.sampled_from(INPUT_CELLS))
_text_leaf = st.sampled_from(['""', '"a"', '"B"', '"abc"', '"10"'])
_digits = st.integers(-1, 2)


def _num(depth: int):
    if depth <= 0:
        return _num_leaf
    sub = _num(depth - 1)
    bsub = _bool(depth - 1)
    return st.one_of(
        _num_leaf,
        st.builds(lambda a, op, b: f"({a}{op}{b})", sub, st.sampled_from("+-*/"), sub),
        st.builds(lambda a, e: f"({a}^{e})", sub, st.integers(1, 3)),
        st.builds(lambda c, a, b: f"IF({c},{a},{b})", bsub, sub, sub),
        st.builds(lambda a, b: f"IFERROR({a},{b})", sub, sub),
        st.builds(lambda f, a, d: f"{f}({a},{d})", st.sampled_from(["ROUND", "ROUNDUP", "ROUNDDOWN"]), sub, _digits),
        st.builds(lambda a: f"INT({a})", sub),
        st.builds(lambda a: f"ABS({a})", sub),
        st.builds(lambda a, b: f"MOD({a},{b})", sub, sub),
        st.builds(
            lambda f, args: f"{f}({','.join(args)})",
            st.sampled_from(["MIN", "MAX", "SUM", "AVERAGE"]),
            st.lists(sub, min_size=1, max_size=3),
        ),
    )


def _bool(depth: int):
    nsub = _num(max(depth - 1, 0))
    cmp_ops = st.sampled_from(["=", "<>", "<", ">", "<=", ">="])
    base = st.one_of(
        st.builds(lambda a, op, b: f"({a}{op}{b})", nsub, cmp_ops, nsub),
        st.builds(lambda a, op, b: f"({a}{op}{b})", _text_leaf, cmp_ops, _text_leaf),
    )
    if depth <= 0:
        return base
    sub = _bool(depth - 1)
    return st.one_of(
        base,
        st.builds(lambda a: f"NOT({a})", sub),
        st.builds(lambda f, a, b: f"{f}({a},{b})", st.sampled_from(["AND", "OR"]), sub, sub),
    )


def _text(depth: int):
    if depth <= 0:
        return _text_leaf
    sub = _text(depth - 1)
    nsub = _num(depth - 1)
    return st.one_of(
        _text_leaf,
        st.builds(lambda a, b: f"({a}&{b})", sub, sub),
        st.builds(lambda a, b: f"({a}&{b})", nsub, sub),
        st.builds(lambda c, a, b: f"IF({c},{a},{b})", _bool(depth - 1), sub, sub),
    )


_formula = st.one_of(_num(MAX_DEPTH), _bool(MAX_DEPTH), _text(MAX_DEPTH)).map(lambda f: "=" + f)

_input_value = st.one_of(
    st.integers(-20, 20),
    st.integers(-200, 200).map(lambda n: n / 10),
)
_batch = st.tuples(
    st.lists(_input_value, min_size=3, max_size=3),
    st.lists(_formula, min_size=1, max_size=8),
)

# -- harness ---------------------------------------------------------------


def _write(path, inputs, formulas) -> list[str]:
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    for cell, v in zip(INPUT_CELLS, inputs):
        ws[cell] = v
    cells = []
    for r, f in enumerate(formulas, start=1):
        ws[f"B{r}"] = f
        cells.append(f"S!B{r}")
    wb.save(path)
    return cells


def _ghost_values(path, cells):
    wb = load_workbook(str(path))
    roles = {ref: ("OUTPUT" if c.formula else "PARAMETER") for ref, c in wb.cells.items()}
    mapping = generate_mapping(wb, roles)
    got = load_compute(emit_module(wb, mapping).code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    return [got.get(name_of.get(c)) for c in cells]


@pytest.fixture(scope="module")
def referee(tmp_path_factory):
    d = tmp_path_factory.mktemp("fuzz")
    start = d / "start.xlsx"
    _write(start, [1, 2, 3], ["=1"])
    with RefereeClient(None, start) as ref:
        yield ref, d


@settings(
    max_examples=60,
    deadline=None,
    database=None,
    derandomize=False,
    suppress_health_check=list(HealthCheck),
)
@seed(SEED)
@given(_batch)
def _fuzz(ctx, batch):
    ref, d, counter = ctx
    inputs, formulas = batch
    counter[0] += 1
    path = d / f"fuzz_{counter[0]}.xlsx"
    cells = _write(path, inputs, formulas)
    ref.open(path)
    refv = ref.read(cells)
    ghost = _ghost_values(path, cells)
    bad = []
    for f, c, g in zip(formulas, cells, ghost):
        r = refv[c]
        r = r["error"] if isinstance(r, dict) else r
        if not values_equal(r, g, 1e-6):
            bad.append(f"{f}  inputs={inputs}  Referee={r!r}  Ghost={g!r}")
    assert not bad, "Property 9 mismatch:\n" + "\n".join(bad)


def test_property_9_formula_fuzzing_agrees_with_referee(referee):
    """Property 9: transpiled code equals the Referee for P0-grammar formulas."""
    ref, d = referee
    _fuzz((ref, d, [0]))
