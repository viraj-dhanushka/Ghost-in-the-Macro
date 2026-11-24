"""R-27: workbook-scoped defined names that point at one cell or one rectangle.

**Validates: Requirements 1.23, 2.23, 3.7, 3.8**

Resolved across the dependency graph, subset check, emitter, thresholds and rule text.
Dynamic (OFFSET/INDIRECT), sheet-scoped, multi-area and external names stay
"not converted" with a reason. Needs LibreOffice for the Referee comparisons.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from ghost.autopsy.classify import classify
from ghost.autopsy.thresholds import extract_thresholds
from ghost.converter.emit_python import emit_module, emit_python
from ghost.converter.subset import find_not_converted
from ghost.ingest.workbook import classify_name_target, load_workbook
from ghost.models import IOSpec, Mapping
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.rules.ears import generate_rules
from ghost.verifier.run import VerifyConfig, verify


def _build(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A2"], ws["B2"] = "Quantity", 60
    ws["D2"], ws["E2"] = "Bulk threshold", 50
    for i, v in enumerate((1, 2, 3), start=1):
        ws[f"G{i}"] = v
    ws["B4"] = "=Bulk*2"
    ws["B5"] = '=IF(B2>=Bulk,"Y","N")'
    ws["B6"] = "=SUM(Prices)*B2"
    ws["B7"] = "=SUM(Dyn)"
    ws["B8"] = "=B7+1"
    ws["B9"] = "=Local*2"
    wb.defined_names["Bulk"] = DefinedName("Bulk", attr_text="S!$E$2")
    wb.defined_names["Prices"] = DefinedName("Prices", attr_text="S!$G$1:$G$3")
    wb.defined_names["Dyn"] = DefinedName("Dyn", attr_text="OFFSET(S!$G$1,0,0,2,1)")
    ws.defined_names["Local"] = DefinedName("Local", attr_text="S!$E$2")
    wb.save(path)
    return path


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    path = _build(tmp_path_factory.mktemp("names") / "names.xlsx")
    return path, load_workbook(str(path))


def _mapping() -> Mapping:
    return Mapping(
        inputs={"quantity": IOSpec(cell="S!B2", type="decimal", min=Decimal(0), max=Decimal(200))},
        outputs={
            "double": IOSpec(cell="S!B4", type="decimal"),
            "flag": IOSpec(cell="S!B5", type="string"),
            "total": IOSpec(cell="S!B6", type="decimal"),
        },
    )


def test_name_targets_are_classified(book):
    _, wb = book
    assert wb.name_targets == {"Bulk": "S!E2", "Prices": "S!G1:G3"}
    assert "OFFSET" in wb.name_issues["Dyn"] and "dynamic" in wb.name_issues["Dyn"]
    assert "sheet-scoped" in wb.name_issues["Local"]


@pytest.mark.parametrize(
    "text,ok",
    [
        ("S!$E$2", "S!E2"),
        ("'My Sheet'!$A$1:$B$3", "My Sheet!A1:B3"),
        ("OFFSET(S!$A$1,0,0,2,1)", "dynamic"),
        ("INDIRECT(\"A1\")", "dynamic"),
        ("S!$A$1:$A$2,S!$C$1", "multi-area"),
        ("[1]S!$A$1", "external"),
        ("Other!$A$1", "unknown sheet"),
        ("3.5", "not a single cell"),
    ],
)
def test_classify_name_target(text, ok):
    target, reason = classify_name_target(text, ["S", "My Sheet"])
    if "!" in ok:
        assert target == ok and reason is None
    else:
        assert target is None and ok in reason


def test_subset_lists_only_unresolvable_names(book):
    _, wb = book
    listed = {e.cell: e.reason for e in find_not_converted(wb) if not e.dependent}
    assert set(listed) == {"S!B7", "S!B9"}
    assert "Dyn" in listed["S!B7"] and "dynamic" in listed["S!B7"]
    assert "Local" in listed["S!B9"] and "sheet-scoped" in listed["S!B9"]
    dependents = [e.cell for e in find_not_converted(wb) if e.dependent]
    assert dependents == ["S!B8"]


def test_emitter_is_deterministic_and_lists_not_converted(book):
    _, wb = book
    a = emit_python(wb, _mapping())
    assert a == emit_python(wb, _mapping())
    res = emit_module(wb, _mapping())
    assert {e.cell for e in res.not_converted if not e.dependent} == {"S!B7", "S!B9"}


def test_threshold_uses_the_named_cells_value(book):
    _, wb = book
    ts = [t for t in extract_thresholds(wb) if t.source.cell == "S!B5"]
    assert [(t.cell, t.operator, t.constant) for t in ts] == [("S!B2", ">=", Decimal(50))]


def test_input_cell_behind_a_name_is_not_resolved_as_a_threshold(book):
    _, wb = book
    roles = dict(classify(wb))
    roles["S!E2"] = "INPUT"
    assert [t for t in extract_thresholds(wb, roles=roles) if t.source.cell == "S!B5"] == []


def test_named_constant_is_classified(book):
    _, wb = book
    roles = classify(wb)
    assert roles["S!E2"] == "PARAMETER"  # read through the name Bulk, rate-labelled
    assert roles["S!G1"] in ("INPUT", "PARAMETER")  # read through the range name Prices


def test_rule_text_uses_the_name_as_label(book):
    _, wb = book
    rules = {r.cells[0]: r.text for r in generate_rules(wb, classify(wb), extract_thresholds(wb))}
    assert "Bulk [E2]" in rules["S!B4"]
    assert "Bulk [E2]" in rules["S!B5"]
    assert "Prices" in rules["S!B6"]
    assert rules == {r.cells[0]: r.text for r in generate_rules(wb, classify(wb), extract_thresholds(wb))}


def test_names_match_the_referee_and_faithful_passes(book):
    try:
        locate_soffice()
    except RefereeUnavailable:
        pytest.skip("soffice not available")
    path, wb = book
    mapping = _mapping()
    from ghost.verifier.run import load_compute

    compute = load_compute(emit_python(wb, mapping))
    got = compute({"quantity": Decimal(60)})
    with RefereeClient(None, path) as ref:
        want = ref.eval({"S!B2": 60}, ["S!B4", "S!B5", "S!B6"])
        assert want["S!B4"] == 100 and want["S!B5"] == "Y" and want["S!B6"] == 360
        assert got["double"] == Decimal(100) and got["flag"] == "Y" and got["total"] == Decimal(360)
        res = verify(
            emit_python(wb, mapping), mapping, ref,
            VerifyConfig(thresholds=extract_thresholds(wb), max_examples=60),
        )
    assert res.passed, [(m.mismatch_class, m.case.inputs) for m in res.mismatches]
