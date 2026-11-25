"""Effective domain (L-07, task 5.4): declared range, default cap, and the workbook's sample."""
from __future__ import annotations

from decimal import Decimal

from ghost.models import IOSpec, Mapping
from ghost.verifier.coverage import candidate_inputs
from ghost.verifier.domain import DEFAULT_MAX, effective_domain, effective_domains


def test_max_is_largest_of_declared_default_and_sample():
    nomax = IOSpec(cell="S!B1", type="integer", min=Decimal(0))
    assert effective_domain(nomax) == (Decimal(0), DEFAULT_MAX)
    assert effective_domain(nomax, 60000) == (Decimal(0), Decimal(60000))
    assert effective_domain(nomax, 50) == (Decimal(0), DEFAULT_MAX)
    declared = IOSpec(cell="S!B1", type="integer", min=Decimal(0), max=Decimal(100))
    assert effective_domain(declared, 5) == (Decimal(0), Decimal(100))
    assert effective_domain(declared, 500) == (Decimal(0), Decimal(500))
    assert effective_domain(IOSpec(cell="S!B1", type="decimal"))[0] is None


def test_candidates_drop_negative_one_and_stay_in_domain():
    mapping = Mapping(inputs={"q": IOSpec(cell="S!B1", type="integer", min=Decimal(0))})
    domains = effective_domains(mapping, {"q": 60000})
    cases = list(candidate_inputs({"q": 60000}, [Decimal(50), Decimal(70000)], domains=domains))
    values = {c["q"] for c in cases}
    assert -1 not in values and 0 in values and 50 in values
    assert max(values) == 60000  # 70000 and its neighbours are clamped to the maximum
    assert any(c["q"] == -1 for c in candidate_inputs({"q": 60000}, [Decimal(50)]))  # no domain


def test_report_says_max_includes_sample_value():
    from ghost.report.domains import tested_domain_rows
    from ghost.report.html import render_html
    mapping = Mapping(inputs={"g": IOSpec(cell="S!B1", type="integer", min=Decimal(0))})
    cases = [{"g": 0}, {"g": 60000}]
    rows = tested_domain_rows(mapping, cases, sample={"g": 60000})
    assert rows[0]["max_includes_sample"] == "60000"
    assert "max_includes_sample" not in tested_domain_rows(mapping, cases, sample={"g": 50})[0]
    assert "max_includes_sample" not in tested_domain_rows(mapping, cases)[0]
    from ghost.report.html import build_report, write_report
    report = build_report(seed=1, mode="faithful", cases_tested=2, passed=True, tested_domains=rows)
    html = render_html(report)
    assert "includes the workbook" in html and "60000" in html
