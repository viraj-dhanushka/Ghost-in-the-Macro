"""R-24 Referee fidelity: pin where LibreOffice differs from Excel.

Each formula below gives a different result in LibreOffice than in Excel (see the
"Where LibreOffice differs from Excel" table in .kiro/steering/excel-semantics.md).
The tests pin what the installed LibreOffice returns today, so an upgrade that changes
any of them fails here and prompts a look at the table. They do not claim these are
correct Excel results.

Measured 2026-11-24 through the Referee: local 26.8.3.1 and the live image
(ghost-local:cp4, Debian bookworm) 7.4.7.2 gave identical results for all seven, so
both major versions share one expectation. If they diverge in a future version, add
a new major-version key to EXPECTED.
"""
from __future__ import annotations

import re
import subprocess

import pytest
from openpyxl import Workbook

from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice

try:
    _SOFFICE = locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

FORMULAS = {
    "pow_zero_zero": "=0^0",
    "cube_root_neg": "=(-8)^(1/3)",
    "match_text_in_numbers": '=MATCH("2",M1:M3,0)',
    "match_bool_in_numbers": "=MATCH(TRUE,M1:M3,0)",
    "true_gt_one": "=TRUE>1",
    "sum_text_arg": '=SUM("5",1)',
    "true_concat": '=TRUE&""',
}

# What LibreOffice returns. Booleans come back from the Referee as 1.0 / 0.0.
_SAME = {
    "pow_zero_zero": 1.0,  # Excel: #NUM!
    "cube_root_neg": -2.0,  # Excel: #NUM!
    "match_text_in_numbers": 2.0,  # Excel: #N/A
    "match_bool_in_numbers": 1.0,  # Excel: #N/A
    "true_gt_one": 0.0,  # FALSE; Excel: TRUE
    "sum_text_arg": {"error": "#VALUE!"},  # Excel: 6
    "true_concat": "1",  # Excel: "TRUE"
}
EXPECTED: dict[int, dict] = {7: _SAME, 26: _SAME}


def _major_version() -> int:
    out = subprocess.run([_SOFFICE, "--version"], capture_output=True, text=True, timeout=60).stdout
    m = re.search(r"LibreOffice\s+(\d+)\.", out)
    if not m:  # pragma: no cover
        pytest.skip(f"cannot read the LibreOffice version from {out!r}")
    return int(m.group(1))


@pytest.fixture(scope="module")
def referee_values(tmp_path_factory):
    path = tmp_path_factory.mktemp("lo_diff") / "differences.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    for i, v in enumerate((1, 2, 3), start=1):
        ws[f"M{i}"] = v
    cells = {}
    for r, (cid, formula) in enumerate(FORMULAS.items(), start=1):
        ws[f"B{r}"] = formula
        cells[cid] = f"S!B{r}"
    wb.save(path)
    with RefereeClient(None, path) as ref:
        got = ref.read(list(cells.values()))
    return {cid: got[cell] for cid, cell in cells.items()}


@pytest.mark.parametrize("cid", sorted(FORMULAS))
def test_libreoffice_result_is_pinned(referee_values, cid):
    major = _major_version()
    if major not in EXPECTED:
        pytest.skip(f"LibreOffice {major} has no pinned expectations; measure and add them to EXPECTED")
    assert referee_values[cid] == EXPECTED[major][cid], (
        f"LibreOffice {major} changed its result for {FORMULAS[cid]}; "
        "update EXPECTED and the table in .kiro/steering/excel-semantics.md"
    )
