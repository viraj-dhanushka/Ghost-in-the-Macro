"""R-05: a text input of "" is an empty cell, in the Referee and in generated code.

The Referee writes "" with setString, which leaves the cell empty, so INDEX
returns 0 and arithmetic treats it as 0. Generated code must agree.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import Workbook

from ghost.converter.emit_python import emit_python
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.run import load_compute

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)


@pytest.fixture(scope="module")
def sheet(tmp_path_factory):
    path = tmp_path_factory.mktemp("emptytext") / "empty.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"] = "x"
    ws["A2"] = "y"
    ws["B1"] = "=INDEX(A1:A2,1)"
    ws["B2"] = "=A1+1"
    ws["B3"] = '=A1&"z"'
    wb.save(path)
    return path


def _mapping() -> Mapping:
    return Mapping(
        inputs={"label": IOSpec(cell="S!A1", type="string")},
        outputs={
            "indexed": IOSpec(cell="S!B1", type="decimal"),
            "plus_one": IOSpec(cell="S!B2", type="decimal"),
            "joined": IOSpec(cell="S!B3", type="string"),
        },
    )


def test_empty_string_input_is_an_empty_cell_like_the_referee(sheet):
    wb = load_workbook(str(sheet))
    compute = load_compute(emit_python(wb, _mapping()))
    got = compute({"label": ""})
    with RefereeClient(None, sheet) as ref:
        want = ref.eval({"S!A1": ""}, ["S!B1", "S!B2", "S!B3"])
    assert want["S!B1"] == 0 and want["S!B2"] == 1 and want["S!B3"] == "z"
    assert Decimal(got["indexed"]) == 0
    assert Decimal(got["plus_one"]) == 1
    assert got["joined"] == "z"


def test_generated_code_is_deterministic(sheet):
    wb = load_workbook(str(sheet))
    assert emit_python(wb, _mapping()) == emit_python(wb, _mapping())
