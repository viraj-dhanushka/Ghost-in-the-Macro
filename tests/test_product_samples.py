"""Product tests on the generated samples against the real LibreOffice Referee.

**Validates: Requirements 8.15, 19.7, 19.8, 20.5** (task 7.10; exercises
Properties 16, 24, 28 end to end).
Skipped when soffice is not available.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook as XlWorkbook

from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.thresholds import extract_thresholds
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.models import Decision
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.rules.ears import generate_rules
from ghost.verifier.boundary import probe
from ghost.verifier.classify import make_classifier
from ghost.verifier.run import VerifyConfig, load_compute, verify

from samples import make_discount, make_haunted, make_scenarios

try:
    locate_soffice()
    _HAVE_SOFFICE = True
except RefereeUnavailable:
    _HAVE_SOFFICE = False

pytestmark = pytest.mark.skipif(not _HAVE_SOFFICE, reason="soffice not available")

CASES = 300


@pytest.mark.parametrize("module", [make_discount, make_scenarios], ids=["a-discount", "c-scenarios"])
def test_clean_samples_zero_mismatches_faithful(module, tmp_path):
    path = module.build(tmp_path / "clean.xlsx")
    wb = load_workbook(str(path))
    # Autopsy defaults, the same mapping the web app pre-checks.
    mapping = generate_mapping(wb)
    thresholds = extract_thresholds(wb)
    with RefereeClient(None, path) as ref:
        r = verify(
            emit_python(wb, mapping),
            mapping,
            ref,
            VerifyConfig(max_examples=CASES, thresholds=thresholds),
        )
    assert r.mode == "faithful"
    assert r.cases_tested >= CASES
    assert r.mismatches == [] and r.passed


def _haunted(tmp_path):
    path = make_haunted.build(tmp_path / "haunted.xlsx")
    wb = load_workbook(str(path))
    mapping = generate_mapping(wb)
    thresholds = extract_thresholds(wb)
    findings = detect_inconsistencies(thresholds)
    return path, wb, mapping, thresholds, findings


def test_haunted_autopsy_raises_f001(tmp_path):
    _, _, _, _, findings = _haunted(tmp_path)
    f001 = [f for f in findings if f.finding_id == "F-001"]
    assert len(f001) == 1
    assert f001[0].constant == Decimal(50)
    assert {op for _, op in f001[0].locations} == {">", ">="}


def test_haunted_faithful_passes(tmp_path):
    path, wb, mapping, thresholds, findings = _haunted(tmp_path)
    with RefereeClient(None, path) as ref:
        r = verify(
            emit_python(wb, mapping),
            mapping,
            ref,
            VerifyConfig(max_examples=CASES, thresholds=thresholds),
        )
    assert r.passed and r.mismatches == [] and r.cases_tested >= CASES


def test_haunted_intended_one_expected_difference_at_quantity_50(tmp_path):
    path, wb, mapping, thresholds, findings = _haunted(tmp_path)
    (f001,) = [f for f in findings if f.finding_id == "F-001"]
    d001 = Decision(
        decision_id="D-001",
        finding_id="F-001",
        behaviour="bulk means 50 or more",
        reason="Free delivery should start at the same quantity as the bulk discount",
        author="test",
        date=date(2026, 12, 1),
        patch={"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="},
    )
    rules = generate_rules(wb, thresholds=thresholds)
    classifier = make_classifier(
        "intended", findings=findings, decisions=[d001], rules=rules, deps=wb.deps
    )
    module = emit_python(wb, mapping, "intended", [d001])
    with RefereeClient(None, path) as ref:
        r = verify(
            load_compute(module),
            mapping,
            ref,
            VerifyConfig(
                mode="intended", max_examples=CASES, thresholds=thresholds, classifier=classifier
            ),
        )
    assert r.mismatches, "Intended module must differ from the original at quantity 50"
    assert {m.mismatch_class for m in r.mismatches} == {"expected by decision"}
    assert {m.decision_id for m in r.mismatches} == {"D-001"}
    assert {m.finding_id for m in r.mismatches} == {"F-001"}
    assert all(m.minimal for m in r.mismatches)
    assert all(m.case.inputs["quantity"] == 50 for m in r.mismatches)
    assert r.passed


def _gold_fixture(path, threshold: int):
    wb = XlWorkbook()
    ws = wb.active
    ws.title = "Loyalty"
    ws["A1"], ws["B1"] = "Spend", 100
    ws["A2"], ws["B2"] = "Gold bonus", f"=IF(B1>={threshold},ROUND(B1*0.1,2),0)"
    wb.save(path)
    return path


@pytest.mark.parametrize("threshold", [500, 250])
def test_boundary_probe_lands_exactly_on_threshold(threshold, tmp_path):
    path = _gold_fixture(tmp_path / "gold.xlsx", threshold)
    with RefereeClient(None, path) as ref:
        res = probe(
            ref,
            {"Loyalty!B1": 100},
            "Loyalty!B1",
            "Loyalty!B2",
            0,
            1000,
            threshold=threshold,
            step="0.01",
        )
    assert res.change_point == Decimal(threshold)
    assert res.change_point == Decimal(f"{threshold}.00")
    assert res.operator_includes == "at"
    assert res.exact_hits == [
        {"last_unchanged": threshold - 0.01, "first_changed": threshold}
    ]


@pytest.mark.parametrize("module", [make_discount, make_haunted], ids=["a-discount", "b-haunted"])
def test_autopsy_defaults_equal_demo_inputs_and_outputs(module, tmp_path):
    """The demo hard-codes no mapping; the autopsy defaults are the demo's mapping.

    **Validates: Requirements 2.1, 3.6**
    """
    wb = load_workbook(str(module.build(tmp_path / "s.xlsx")))
    mapping = generate_mapping(wb)
    assert [s.cell for s in mapping.inputs.values()] == [
        "Calculator!B2", "Calculator!B3", "Calculator!B4",
    ]
    assert [s.cell for s in mapping.outputs.values()] == ["Calculator!B11"]
