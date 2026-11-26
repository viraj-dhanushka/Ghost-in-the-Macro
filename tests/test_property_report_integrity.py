"""Property 30 of the main spec: report integrity (schema, fields unchanged, "not checked" for missing checks).
Validates Requirements 10.2 to 10.5. No LibreOffice."""
from __future__ import annotations

import json
from decimal import Decimal

from hypothesis import given, settings, strategies as st

from ghost.models import Case, Mismatch
from ghost.report.html import build_report
from ghost.report.model import report_to_dict, report_to_json, validate_report_dict

classes = st.sampled_from(["translation bug", "original workbook inconsistency", "expected by decision"])


@st.composite
def results(draw):
    n = draw(st.integers(0, 3))
    mismatches = []
    for i in range(n):
        q = draw(st.integers(0, 500))
        mismatches.append(Mismatch(
            case=Case(inputs={"quantity": q}, referee={"total": Decimal(q) / 2}, actual={"total": Decimal(q)}),
            output="total", cell="Calc!B11", mismatch_class=draw(classes), minimal=draw(st.booleans())))
    generated = draw(st.integers(0, 400))
    targeted = draw(st.integers(0, 20))
    return dict(
        seed=draw(st.integers(0, 2**31)), mode=draw(st.sampled_from(["faithful", "intended"])),
        cases_tested=generated + targeted, cases_generated=generated, cases_targeted=targeted,
        distinct_cases=draw(st.integers(0, generated + targeted)), passed=draw(st.booleans()),
        mismatches=mismatches, libreoffice_version=draw(st.one_of(st.none(), st.just("LibreOffice 26.8.3.1"))),
    )


@settings(max_examples=120, deadline=None)
@given(results())
def test_property_30_the_report_validates_and_keeps_every_engine_field(r):
    report = build_report(**r)
    data = report_to_dict(report)
    validate_report_dict(data)
    validate_report_dict(json.loads(report_to_json(report)))
    assert data["seed"] == r["seed"] and data["mode"] == r["mode"] and data["passed"] is r["passed"]
    assert data["cases_tested"] == r["cases_tested"] and data["cases_generated"] == r["cases_generated"]
    assert data["cases_targeted"] == r["cases_targeted"] and data["distinct_cases"] == r["distinct_cases"]
    assert len(data["mismatches"]) == len(r["mismatches"])
    for got, want in zip(data["mismatches"], r["mismatches"]):
        assert got["inputs"] == {"quantity": want.case.inputs["quantity"]} and got["class"] == want.mismatch_class
        assert got["output"] == "total" and got["cell"] == "Calc!B11"


@settings(max_examples=60, deadline=None)
@given(results())
def test_property_30_a_check_with_no_result_says_not_checked(r):
    data = report_to_dict(build_report(**r))  # no mutation result, no Excel cross-check given
    assert data["mutation"]["status"] == "not checked"
    assert data["sanity"]["status"] in ("not checked", "not cross-checked against Excel")
    if r["libreoffice_version"] is None:
        assert "not checked" in str(data["versions"]["libreoffice"]).lower()
