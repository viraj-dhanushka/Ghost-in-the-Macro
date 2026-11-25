"""Unit tests for the proof report model and schema (task 8.1)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ghost.models import Case, Mismatch, RuleCoverage
from ghost.report.model import (
    ProofReport,
    ReportValidationError,
    make_versions,
    report_to_dict,
    report_to_json,
    validate_report_dict,
)


def _report(**kw) -> ProofReport:
    base = dict(
        ghost_version="0.1.0",
        seed=7,
        versions=make_versions("7.6.0"),
        mode="faithful",
        cases_tested=300,
        passed=True,
    )
    base.update(kw)
    return ProofReport(**base)


def test_absent_checks_are_not_checked():
    d = report_to_dict(_report())
    assert d["mutation"] == {"status": "not checked"}
    assert d["sanity"] == {"status": "not checked"}
    validate_report_dict(d)


def test_missing_libreoffice_version_is_not_checked():
    assert make_versions(None).libreoffice == "not checked"


def test_full_report_validates_and_is_deterministic():
    m = Mismatch(
        case=Case(inputs={"quantity": 50, "p": Decimal("1.10")}, referee={"t": 1}, actual={"t": 2}),
        output="t",
        cell="Calc!B11",
        mismatch_class="translation bug",
    )
    r = _report(
        passed=False,
        mismatches=[m],
        rule_coverage=[RuleCoverage(rule_id="R-1", condition_id="c1", seen_true=True, seen_false=False)],
    )
    text = report_to_json(r)
    assert text == report_to_json(r)
    data = json.loads(text)
    assert data["mismatches"][0]["inputs"]["p"] == "1.10"
    assert data["mismatches"][0]["class"] == "translation bug"


def test_schema_rejects_bad_report():
    d = report_to_dict(_report())
    d["mode"] = "bogus"
    with pytest.raises(ReportValidationError):
        validate_report_dict(d)
    d = report_to_dict(_report())
    del d["seed"]
    with pytest.raises(ReportValidationError):
        validate_report_dict(d)
    d = report_to_dict(_report())
    d["sanity"] = {"status": "pass"}
    with pytest.raises(ReportValidationError):
        validate_report_dict(d)


# L-02 (live-fixes-2026-11-24, task 3.2): Excel errors serialise as their code text.


class _VendoredExcelError:
    """Stands in for the ExcelError of a vendored excel.py copy: a separate class object."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code


_VendoredExcelError.__name__ = "ExcelError"


def test_excel_error_code_is_duck_typed():
    from ghost.report.model import excel_error_code
    from ghost.runtime.excel import ExcelError

    assert excel_error_code(ExcelError("#REF!")) == "#REF!"
    assert excel_error_code(_VendoredExcelError("#N/A")) == "#N/A"
    assert excel_error_code("#REF!") is None  # text is not an error
    assert excel_error_code(Decimal("1")) is None
    assert excel_error_code(_VendoredExcelError("hello")) is None  # not an error code

    class Other:
        code = "#REF!"

    assert excel_error_code(Other()) is None  # another class name is not an Excel error


def test_report_serialises_excel_errors_from_both_classes():
    from ghost.runtime.excel import ExcelError

    m = Mismatch(
        case=Case(inputs={"q": _VendoredExcelError("#VALUE!")}, referee={"y": ExcelError("#DIV/0!")},
                  actual={"y": _VendoredExcelError("#REF!")}),
        output="y", cell="Calc!B3", mismatch_class="translation bug", minimal=True,
    )
    data = json.loads(report_to_json(_report(passed=False, mismatches=[m])))
    got = data["mismatches"][0]
    assert (got["inputs"], got["expected"], got["actual"]) == (
        {"q": "#VALUE!"}, {"y": "#DIV/0!"}, {"y": "#REF!"}
    )
