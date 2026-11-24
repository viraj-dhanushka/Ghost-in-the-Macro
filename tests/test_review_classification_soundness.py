"""Skeptic review of R-01/R-02: a Decision explains a case only when the candidate's
patched comparison is present and right, and its outputs equal the Intended module's.

Uses the real Referee (LibreOffice); skipped with a message when soffice is missing.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from ghost.converter.emit_python import emit_python
from ghost.decisions.store import load_decisions, record
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.classify import explaining_decision
from ghost.verifier.run import verify
from samples import make_haunted
from tests.test_review_proof_strength import _intended_cfg, _mapping, _plant

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available: Referee-backed soundness tests skipped", allow_module_level=True)

VAT_OLD = "'Calculator!E7': Decimal('0.2'),"
VAT_BAD = "'Calculator!E7': Decimal('0.21'),"
B10_AT_50 = (
    "v['Calculator!B10'] = xl_round(",
    "v['Calculator!B10'] = Decimal('0') if v['Calculator!B2']==Decimal('50') else xl_round(",
)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp("sound")
    path = make_haunted.build(d / "haunted.xlsx")
    wb = load_workbook(str(path))
    mig = d / "mig"
    mig.mkdir()
    record(mig, {
        "finding_id": "F-001", "behaviour": "bulk means 50 or more", "reason": "agree with discount",
        "author": "review", "date": "2026-11-24",
        "patch": {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="},
    })
    decisions = load_decisions(mig)
    mapping = _mapping(wb)
    return path, wb, decisions, mapping


def _run(env, code, mode="intended"):
    path, wb, decisions, mapping = env
    with RefereeClient(None, path) as ref:
        return verify(code, mapping, ref, _intended_cfg(wb, mapping, decisions, mode=mode))


def _classes(res):
    return [(m.mismatch_class, m.case.inputs) for m in res.mismatches]


def test_baseline_intended_still_passes_with_one_expected_difference(env):
    path, wb, decisions, mapping = env
    res = _run(env, emit_python(wb, mapping, "intended", decisions))
    assert res.passed
    assert len(res.mismatches) == 1 and res.mismatches[0].mismatch_class == "expected by decision"
    assert Decimal(str(res.mismatches[0].case.inputs["quantity"])) == 50


def test_variant_c_renamed_trace_id_does_not_excuse_vat_bug(env):
    path, wb, decisions, mapping = env
    code = emit_python(wb, mapping, "intended", decisions)
    code = _plant(_plant(code, "'Calculator!B9#1'", "'X9'"), VAT_OLD, VAT_BAD)
    res = _run(env, code)
    assert not res.passed, _classes(res)
    assert all(m.mismatch_class == "translation bug" for m in res.mismatches)


def test_variant_d_untraced_comparison_does_not_excuse_vat_bug(env):
    path, wb, decisions, mapping = env
    code = emit_python(wb, mapping, "intended", decisions)
    code = _plant(code, "_if(trace, 'Calculator!B9#1', ", "_if(None, 'Calculator!B9#1', ")
    code = _plant(code, VAT_OLD, VAT_BAD)
    res = _run(env, code)
    assert not res.passed, _classes(res)


def test_variant_e_wrong_output_at_the_excused_case_is_a_translation_bug(env):
    path, wb, decisions, mapping = env
    code = _plant(emit_python(wb, mapping, "intended", decisions), *B10_AT_50)
    res = _run(env, code)
    assert not res.passed, _classes(res)
    assert any(m.mismatch_class == "translation bug" for m in res.mismatches)


def test_variant_h_faithful_code_bug_is_not_blamed_on_the_workbook(env):
    path, wb, decisions, mapping = env
    code = _plant(emit_python(wb, mapping), *B10_AT_50)
    res = _run(env, code, mode="faithful")
    assert not res.passed
    assert res.mismatches
    assert all(m.mismatch_class == "translation bug" for m in res.mismatches), _classes(res)


def test_module_without_trace_reports_why_nothing_is_explained(env):
    path, wb, decisions, mapping = env
    code = emit_python(wb, mapping, "intended", decisions).replace(
        "def compute(inputs, trace=None):", "def compute(inputs):\n    trace = None"
    )
    res = _run(env, code)
    assert not res.passed
    assert "no trace hook" in (res.explain_unavailable or "")


def test_explaining_decision_requires_present_hook_and_intended_output():
    from ghost.models import Decision

    d = Decision(
        decision_id="D-001", finding_id="F-001", behaviour="b", reason="r", author="a",
        date="2026-11-24", patch={"op": "set_operator", "cell": "S!C1", "from": ">", "to": ">="},
    )
    ref = faith = {"o": 5}
    ft, it = {"S!C1#1": False}, {"S!C1#1": True}
    args = dict(intended={"o": 0}, intended_trace=it)
    assert explaining_decision([d], ["o"], ref, {"o": 0}, it, faith, ft, **args) == "D-001"
    # missing hook in the candidate
    assert explaining_decision([d], ["o"], ref, {"o": 0}, {}, faith, ft, **args) is None
    assert explaining_decision([d], ["o"], ref, {"o": 0}, {"X": True}, faith, ft, **args) is None
    # candidate hook right, but its output differs from the Intended module's
    assert explaining_decision([d], ["o"], ref, {"o": 9}, it, faith, ft, **args) is None
    # candidate hook has the Faithful value
    assert explaining_decision([d], ["o"], ref, {"o": 0}, ft, faith, ft, **args) is None
