from decimal import Decimal

from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.metrics import metrics
from ghost.autopsy.thresholds import extract_thresholds
from ghost.models import Cell, FeatureFlag, Location, Threshold, VbaModule, Workbook


def _t(cell, op, const, src):
    return Threshold(cell=cell, operator=op, constant=Decimal(const), source=src)


def test_operator_conflict_creates_finding():
    ts = [
        _t("S!B1", ">", "50", Location(cell="S!C1")),
        _t("S!B1", ">=", "50.0", Location(cell="S!C2")),
        _t("S!B1", ">", "50", Location(cell="S!C1")),
        _t("S!B2", ">", "10", Location(cell="S!C3")),
    ]
    findings = detect_inconsistencies(ts)
    assert [f.finding_id for f in findings] == ["F-001"]
    f = findings[0]
    assert f.cell == "S!B1" and f.constant == Decimal("50")
    assert [(loc.cell, op) for loc, op in f.locations] == [("S!C1", ">"), ("S!C2", ">=")]


def test_same_operator_or_different_constant_is_not_a_finding():
    ts = [
        _t("S!B1", ">", "50", Location(cell="S!C1")),
        _t("S!B1", ">", "50", Location(cell="S!C2")),
        _t("S!B1", ">=", "60", Location(cell="S!C3")),
    ]
    assert detect_inconsistencies(ts) == []


def test_ids_sorted_and_cross_vba_formula():
    wb = Workbook(
        path="x",
        sheets=["S"],
        cells={
            "S!C1": Cell(ref="S!C1", formula="=IF(B1>50,1,0)"),
            "S!C2": Cell(ref="S!C2", formula="=IF(A1>=5,1,0)"),
        },
        vba_modules=[
            VbaModule(name="M", source="Sub X()\nIf Range(\"A1\").Value > 5 Then\nEnd If\nEnd Sub", line_count=4)
        ],
    )
    findings = detect_inconsistencies(extract_thresholds(wb))
    assert [f.finding_id for f in findings] == ["F-001"]
    assert findings[0].cell == "S!A1"
    assert any(loc.module == "M" and loc.line == 2 for loc, _ in findings[0].locations)


def test_metrics_counts():
    wb = Workbook(
        path="x",
        cells={
            "S!A1": Cell(ref="S!A1", value=1),
            "S!B1": Cell(ref="S!B1", formula="=A1*2"),
        },
        features=[
            FeatureFlag(kind="volatile", cell="S!B1", detail="NOW", not_verifiable=True),
            FeatureFlag(kind="external_link", cell="S!B1"),
            FeatureFlag(kind="unsupported_function", cell="S!B1", detail="XLOOKUP"),
        ],
    )
    mods = [
        VbaModule(name="M", source='Declare Function Foo Lib "x" ()\nSub A()\nEnd Sub', line_count=3),
        VbaModule(name="F", source="VERSION 5.00\nBegin {C62A69F0-16DC-11CE-9E98-00AA00574A4F} UserForm1\n", line_count=2),
    ]
    m = metrics(wb, mods)
    assert (m.formula_count, m.vba_line_count, m.module_count) == (1, 5, 2)
    assert (m.userform_count, m.declare_count) == (1, 1)
    assert (m.external_link_count, m.volatile_count, m.unsupported_count) == (1, 1, 1)
    assert m.calculator_shape is False


def test_calculator_shape_true_for_plain_formulas():
    wb = Workbook(path="x", cells={"S!B1": Cell(ref="S!B1", formula="=A1*2")})
    m = metrics(wb)
    assert m.calculator_shape is True and m.vba_line_count == 0
