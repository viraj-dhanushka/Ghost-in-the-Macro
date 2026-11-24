"""R-26: formulas that produce text are typed ``string`` in mapping.yaml.

Script-written workbooks have no Excel-saved values, so the type comes from the
formula AST. **Validates: Requirements 1.16, 2.16**
"""

from __future__ import annotations

import openpyxl

from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from samples import make_haunted, make_scenarios


def _types(path) -> dict[str, str]:
    return {k: v.type for k, v in generate_mapping(load_workbook(str(path))).outputs.items()}


def test_scenarios_text_output_is_string(tmp_path):
    types = _types(make_scenarios.build(tmp_path / "s.xlsx"))
    assert types["best_scenario"] == "string"
    assert types["best_net_cost"] == "decimal"


def test_haunted_total_stays_decimal(tmp_path):
    assert set(_types(make_haunted.build(tmp_path / "h.xlsx")).values()) == {"decimal"}


def _tier_workbook(path, body: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"], ws["B1"] = "Order total", 400
    ws["A2"], ws["B2"] = "Tier", body
    wb.save(path)
    return path


def test_if_returning_text_branches_is_string(tmp_path):
    p = _tier_workbook(tmp_path / "t.xlsx", '=IF(B1>=500,"Gold","Standard")')
    assert _types(p) == {"tier": "string"}


def test_concatenation_and_text_function_are_string(tmp_path):
    assert _types(_tier_workbook(tmp_path / "c.xlsx", '="Total: "&B1')) == {"tier": "string"}
    assert _types(_tier_workbook(tmp_path / "f.xlsx", '=TEXT(B1,"0.00")')) == {"tier": "string"}


def test_mixed_branches_keep_the_default(tmp_path):
    p = _tier_workbook(tmp_path / "m.xlsx", '=IF(B1>=500,"Gold",0)')
    assert _types(p) == {"tier": "decimal"}
