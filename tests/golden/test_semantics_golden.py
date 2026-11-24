"""Golden semantics tests (R-20): Excel_Semantics_Table rows 1, 2, 5, 7, 8, 9, 10.

Built from samples/make_traps.py. Every formula cell is checked twice against the
table's expected result: the Referee (LibreOffice) value and the value computed by
the transpiled module. Rows 3, 4, 6, 11 (VBA, dates) are not in the traps workbook.
The R-24 LibreOffice-vs-Excel differences are pinned in
tests/test_referee_libreoffice_differences.py and are not repeated here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute

pytestmark = pytest.mark.golden

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available: golden tests need the Referee", allow_module_level=True)


def _load_traps():
    path = Path(__file__).resolve().parents[2] / "samples" / "make_traps.py"
    spec = importlib.util.spec_from_file_location("make_traps", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("make_traps", mod)
    spec.loader.exec_module(mod)
    return mod


traps = _load_traps()

# Expected result per case (same order as traps.CASES), from the table's examples.
# Booleans are written as 1.0 / 0.0 because the Referee returns them that way.
EXPECTED = [
    3.0,  # row 1 ROUND(2.5,0)
    -3.0,  # row 1 ROUND(-2.5,0)
    0.13,  # row 1 ROUND(0.125,2)
    2.68,  # row 2 ROUND(2.675,2)
    2.0,  # row 5 MOD(-7,3)
    -2.0,  # row 5 MOD(7,-3)
    1.0,  # row 7 empty + 1
    "x",  # row 7 empty & "x"
    2.0,  # row 8 TRUE+1
    1.0,  # row 8 FALSE+1
    1.0,  # row 9 "Gold"="GOLD" is TRUE
    0.3,  # row 10 0.1+0.2 vs 0.3 within 1e-6
]


def _norm(v):
    if isinstance(v, dict):
        return v.get("error", v)
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    return v


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    path = tmp_path_factory.mktemp("golden") / "traps.xlsx"
    traps.build().save(path)
    wb = load_workbook(str(path))
    roles = {ref: ("OUTPUT" if c.formula else "PARAMETER") for ref, c in wb.cells.items()}
    mapping = generate_mapping(wb, roles)
    res = emit_module(wb, mapping)
    assert not getattr(res, "not_converted", None), res.not_converted
    got = load_compute(res.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    cells = [f"Traps!E{4 + i}" for i in range(len(traps.CASES))]
    with RefereeClient(None, path) as ref:
        refv = ref.read(cells)
    return [(refv[c], got.get(name_of.get(c))) for c in cells]


def test_expected_list_covers_every_case():
    assert len(EXPECTED) == len(traps.CASES)


@pytest.mark.parametrize("i", range(len(traps.CASES)))
def test_referee_matches_table(results, i):
    row, case = traps.CASES[i][0], traps.CASES[i][1]
    assert values_equal(_norm(results[i][0]), EXPECTED[i], 1e-6), (row, case, results[i][0])


@pytest.mark.parametrize("i", range(len(traps.CASES)))
def test_generated_code_matches_table(results, i):
    row, case = traps.CASES[i][0], traps.CASES[i][1]
    assert values_equal(_norm(results[i][1]), EXPECTED[i], 1e-6), (row, case, results[i][1])


def test_every_p0_row_is_covered():
    assert {c[0] for c in traps.CASES} == {1, 2, 5, 7, 8, 9, 10}
