"""R-28: cases generated, targeted and distinct are reported separately.

**Validates: Requirements 1.10, 2.10, 3.9**
"""

from __future__ import annotations

from ghost.models import IOSpec, Mapping
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_dict, validate_report_dict
from ghost.verifier.run import VerifyConfig, verify


class _Ref:
    def eval(self, inputs, outputs):
        x = inputs["S!A1"]
        return {"S!B1": x * 2}


def _mapping() -> Mapping:
    return Mapping(
        inputs={"x": IOSpec(cell="S!A1", type="integer", min=0, max=3)},
        outputs={"y": IOSpec(cell="S!B1", type="integer")},
    )


def _compute(inputs):
    return {"y": inputs["x"] * 2}


def test_verify_separates_generated_targeted_and_distinct():
    extra = [{"x": 0}, {"x": 1}, {"x": 1}]
    res = verify(_compute, _mapping(), _Ref(), VerifyConfig(max_examples=40, extra_cases=extra))
    assert res.cases_targeted == 3
    assert res.cases_generated + res.cases_targeted == res.cases_tested
    assert res.cases_generated > 0
    # x is in 0..3, so at most 4 distinct inputs exist among all cases.
    assert 1 <= res.distinct_cases <= 4
    assert res.distinct_cases == len({tuple(sorted(c.items())) for c in res.cases})
    assert res.distinct_cases < res.cases_tested


def test_new_report_json_and_html_show_both_numbers():
    r = build_report(
        seed=1, mode="faithful", cases_tested=309, passed=True,
        cases_generated=300, cases_targeted=9, distinct_cases=176,
    )
    d = report_to_dict(r)
    validate_report_dict(d)
    assert d["cases_tested"] == 309
    assert (d["cases_generated"], d["cases_targeted"], d["distinct_cases"]) == (300, 9, 176)
    assert "300 generated + 9 targeted, 176 distinct" in render_html(r)


def test_old_report_without_new_fields_still_validates_and_renders():
    r = build_report(seed=1, mode="faithful", cases_tested=300, passed=True)
    d = report_to_dict(r)
    assert "distinct_cases" not in d and "cases_generated" not in d
    validate_report_dict(d)
    html = render_html(d)
    assert "300" in html and "distinct" not in html
