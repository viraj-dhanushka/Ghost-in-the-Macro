"""Review 2026-11-24: proof-strength gaps found by planting bugs (needs LibreOffice).

Each xfail(strict=True) test describes the behaviour the proof should have and fails
today. When the gap is fixed the test starts passing and strict xfail turns it into a
failure, so the marker must then be removed. See docs/TEST_REPORT_2026-11-24.md.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook as opx_load

from ghost.autopsy.classify import classify
from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.thresholds import extract_thresholds
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.decisions.store import load_decisions, record
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.rules.ears import generate_rules
from ghost.verifier.classify import make_classifier
from ghost.cli import _probe_boundaries, _probe_flips
from ghost.mutation.run import run_mutation
from ghost.verifier.flip import flip_cases
from ghost.verifier.run import VerifyConfig, verify
from samples import make_discount, make_haunted, make_scenarios

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

USER_INPUTS = ("Calculator!B2", "Calculator!B3", "Calculator!B4")


def _mapping(wb, inputs=USER_INPUTS, outputs=("Calculator!B11",)) -> Mapping:
    roles = {r: ("PARAMETER" if v == "INPUT" else v) for r, v in classify(wb, list(outputs)).items()}
    roles.update({r: "INPUT" for r in inputs})
    for r, v in list(roles.items()):
        if v == "OUTPUT" and r not in outputs:
            roles[r] = "INTERMEDIATE"
    return generate_mapping(wb, roles)


def _plant(code: str, old: str, new: str) -> str:
    assert code.count(old) == 1, old
    return code.replace(old, new)


@pytest.fixture(scope="module")
def haunted(tmp_path_factory):
    d = tmp_path_factory.mktemp("haunted")
    path = make_haunted.build(d / "haunted.xlsx")
    wb = load_workbook(str(path))
    mig = d / "mig"
    mig.mkdir()
    record(mig, {
        "finding_id": "F-001", "behaviour": "bulk means 50 or more", "reason": "agree with discount",
        "author": "review", "date": "2026-11-24",
        "patch": {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="},
    })
    return path, wb, load_decisions(mig)


def _intended_cfg(wb, mapping, decisions, mode="intended"):
    thresholds = extract_thresholds(wb)
    findings = detect_inconsistencies(thresholds)
    roles = {s.cell: "INPUT" for s in mapping.inputs.values()} | {s.cell: "OUTPUT" for s in mapping.outputs.values()}
    rules = generate_rules(wb, roles, thresholds)
    return VerifyConfig(mode=mode, thresholds=thresholds,
                        classifier=make_classifier(mode, findings, decisions, rules, wb.deps))


def test_intended_mode_does_not_excuse_unrelated_bug(haunted):
    path, wb, decisions = haunted
    mapping = _mapping(wb)
    code = emit_python(wb, mapping, "intended", decisions)
    buggy = _plant(code, "'Calculator!E7': Decimal('0.2'),", "'Calculator!E7': Decimal('0.21'),")
    with RefereeClient(None, path) as ref:
        res = verify(buggy, mapping, ref, _intended_cfg(wb, mapping, decisions))
    assert not res.passed, [(m.mismatch_class, m.case.inputs) for m in res.mismatches]


def test_faithful_translation_bug_is_labelled_translation_bug(haunted):
    path, wb, decisions = haunted
    mapping = _mapping(wb)
    code = emit_python(wb, mapping)
    buggy = _plant(code, "'Calculator!E7': Decimal('0.2'),", "'Calculator!E7': Decimal('0.21'),")
    with RefereeClient(None, path) as ref:
        res = verify(buggy, mapping, ref, _intended_cfg(wb, mapping, decisions, mode="faithful"))
    assert res.mismatches and res.mismatches[0].mismatch_class == "translation bug"


def test_truncated_distance_is_caught(tmp_path):
    path = make_discount.build(tmp_path / "discount.xlsx")
    wb = load_workbook(str(path))
    mapping = _mapping(wb)
    code = emit_python(wb, mapping)
    buggy = _plant(code, "_inp(inputs.get('delivery_distance_km'))", "_inp(int(inputs.get('delivery_distance_km')))")
    with RefereeClient(None, path) as ref:
        res = verify(buggy, mapping, ref, VerifyConfig(thresholds=extract_thresholds(wb)))
    assert not res.passed


@pytest.fixture(scope="module")
def tier(tmp_path_factory):
    d = tmp_path_factory.mktemp("tier")
    path = make_discount.build(d / "tier.xlsx")
    book = opx_load(path)
    ws = book["Calculator"]
    ws["A12"], ws["B12"] = "Tier", '=IF(B11>=500,"Gold","Standard")'
    book.save(path)
    return path, load_workbook(str(path))


def test_gold_threshold_on_calculated_cell_is_caught(tier):
    path, wb = tier
    mapping = _mapping(wb, outputs=("Calculator!B11", "Calculator!B12"))
    code = emit_python(wb, mapping)
    buggy = _plant(code, "xl_ge(v['Calculator!B11'], Decimal('500'))", "xl_gt(v['Calculator!B11'], Decimal('500'))")
    flips = _probe_flips(wb, mapping)
    with RefereeClient(None, path) as ref:
        res = verify(buggy, mapping, ref,
                     VerifyConfig(thresholds=extract_thresholds(wb), extra_cases=flip_cases(flips, mapping)))
    assert not res.passed


def test_tier_flip_cases_kill_threshold_mutants_and_boundaries_list_b12(tier):
    """R-04: flip and +-1 mutants on the Gold condition are killed; boundaries list B12."""
    path, wb = tier
    mapping = _mapping(wb, outputs=("Calculator!B11", "Calculator!B12"))
    code = emit_python(wb, mapping)
    flips = _probe_flips(wb, mapping)
    extra = flip_cases(flips, mapping)
    assert any(f.condition_id == "Calculator!B12#1" for f in flips)
    with RefereeClient(None, path) as ref:
        boundaries = _probe_boundaries(ref, wb, mapping, extract_thresholds(wb), flips)
        result = run_mutation(code, mapping, ref, VerifyConfig(thresholds=extract_thresholds(wb)),
                              cases=20, targeted=extra)
    assert any(b.cell == "Calculator!B12" and b.kind == "condition flip" for b in boundaries)
    gold = [m for m in result.mutants if m.location == "Calculator!B12"]
    assert gold, "no mutants on the Gold condition"
    assert all(m.killed for m in gold), [(m.mutant_id, m.operator) for m in gold if not m.killed]
    assert {"flip_comparison", "constant_plus_one", "constant_minus_one"} <= {m.operator for m in gold}


def test_order_totalling_500_exists_and_is_gold(tier):
    """Evidence for R-04: such an order exists (1 x 411.67, 0 km gives exactly 500.00, Gold)."""
    path, _ = tier
    with RefereeClient(None, path) as ref:
        v = ref.eval({"Calculator!B2": 1, "Calculator!B3": 411.67, "Calculator!B4": 0}, ["Calculator!B11", "Calculator!B12"])
    assert v["Calculator!B11"] == pytest.approx(500.0) and v["Calculator!B12"] == "Gold"


def test_scenarios_sample_passes_with_default_inputs(tmp_path):
    path = make_scenarios.build(tmp_path / "scenarios.xlsx")
    wb = load_workbook(str(path))
    mapping = generate_mapping(wb)  # the web app's default: every proposed INPUT is checked
    with RefereeClient(None, path) as ref:
        res = verify(emit_python(wb, mapping), mapping, ref, VerifyConfig(thresholds=extract_thresholds(wb)))
    assert res.passed, [(m.output, m.case.referee.get(m.output), m.case.actual.get(m.output)) for m in res.mismatches]


def test_decimal_distance_mutants_are_not_equivalent(tmp_path):
    """Evidence for R-06: two 'equivalent on tested domain' survivors differ at realistic distances."""
    path = make_haunted.build(tmp_path / "haunted.xlsx")
    wb = load_workbook(str(path))
    mapping = Mapping(
        inputs={**_mapping(wb).inputs, "delivery_distance_km": IOSpec(cell="Calculator!B4", type="decimal", min=Decimal(0))},
        outputs=_mapping(wb).outputs,
    )
    code = emit_python(wb, mapping)
    from ghost.verifier.run import load_compute
    one_dp = load_compute(code.replace("v['Calculator!E6'])), Decimal('2')))", "v['Calculator!E6'])), Decimal('1')))"))
    three_dp = load_compute(code.replace("v['Calculator!E6'])), Decimal('2')))", "v['Calculator!E6'])), Decimal('3')))"))
    with RefereeClient(None, path) as ref:
        for km, mutant in ((Decimal("10.3"), one_dp), (Decimal("10.01"), three_dp)):
            inputs = {"quantity": 1, "unit_price": Decimal("1"), "delivery_distance_km": km}
            want = ref.eval({"Calculator!B2": 1, "Calculator!B3": 1, "Calculator!B4": float(km)}, ["Calculator!B11"])["Calculator!B11"]
            got = mutant(dict(inputs))["total"]
            assert abs(float(got) - want) > 1e-6, (km, want, got)
