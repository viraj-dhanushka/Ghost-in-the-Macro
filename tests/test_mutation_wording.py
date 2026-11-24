"""R-06: honest survivor wording, and the ROUND-digit mutants of the haunted sample.

**Validates: Requirements 2.9** (review-fixes-2026-11-24). A surviving mutant is
reported as "no difference found on N distinct cases" plus the tested domain of
every input, derived from the cases actually run. Ghost never claims equivalence.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ghost.models import IOSpec, Mapping
from ghost.mutation import run as mutation_run
from ghost.mutation.run import no_difference_reason
from ghost.mutation.run import tested_domains as domains_of

_MAPPING = Mapping(
    inputs={
        "quantity": IOSpec(cell="S!B1", type="integer"),
        "distance": IOSpec(cell="S!B2", type="decimal"),
        "label": IOSpec(cell="S!B3", type="string"),
    },
    outputs={"total": IOSpec(cell="S!B4", type="decimal")},
)

_CASES = [
    {"quantity": 0, "distance": Decimal("10.3"), "label": "a"},
    {"quantity": 7, "distance": Decimal("0.125"), "label": "b"},
    {"quantity": 50, "distance": Decimal("12"), "label": "a"},
]


def test_domains_come_from_the_cases_actually_run():
    d = domains_of(_MAPPING, _CASES)
    assert d["quantity"] == "integer, min 0, max 50, 0 decimal places"
    assert d["distance"] == "decimal, min 0.125, max 12, up to 3 decimal places"
    assert d["label"] == "string, 2 distinct values"


def test_reason_states_distinct_count_and_domain_without_claiming_equivalence():
    cases = _CASES + [dict(_CASES[0])]  # a repeat must not be counted twice
    reason = no_difference_reason(_MAPPING, cases)
    assert reason.startswith("no difference found on 3 distinct cases")
    assert "quantity: integer, min 0, max 50" in reason
    assert "distance: decimal, min 0.125, max 12" in reason
    assert "equivalen" not in reason.lower()


def test_old_wording_is_gone_from_the_module():
    assert not hasattr(mutation_run, "REASON_EQUIVALENT")
    assert "equivalent on tested domain" not in Path(mutation_run.__file__).read_text(encoding="utf-8")


def test_no_claim_of_equivalence_in_code_templates_or_skills():
    root = Path(__file__).resolve().parents[1]
    hits = []
    for folder in ("ghost", "web", "mcp_server", "plugin"):
        for p in (root / folder).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".html", ".md", ".json", ".yaml", ".js"}:
                if "equivalent on tested domain" in p.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(str(p.relative_to(root)))
    assert not hits, hits


def test_haunted_round_digit_mutants_are_killed(tmp_path):
    """Done when (R-06): the constant +-1 mutants on the ROUND digits of Calculator!B9 die."""
    from ghost.cli import _probe_flips
    from ghost.autopsy.thresholds import extract_thresholds
    from ghost.converter.emit_python import emit_python
    from ghost.ingest.workbook import load_workbook
    from ghost.mutation.run import run_mutation
    from ghost.referee.client import RefereeClient
    from ghost.referee.locate import RefereeUnavailable, locate_soffice
    from ghost.verifier.coverage import candidate_inputs
    from ghost.verifier.flip import flip_cases
    from ghost.verifier.run import VerifyConfig
    from tests.test_review_proof_strength import USER_INPUTS, _mapping
    from samples import make_haunted

    try:
        locate_soffice()
    except RefereeUnavailable:
        pytest.skip("soffice not available")
    path = make_haunted.build(tmp_path / "haunted.xlsx")
    wb = load_workbook(str(path))
    mapping = _mapping(wb, inputs=USER_INPUTS)
    assert mapping.inputs["delivery_distance_km"].type == "decimal"
    code = emit_python(wb, mapping)
    thresholds = extract_thresholds(wb)
    base = {n: (Decimal(repr(wb.cells[s.cell].value)) if isinstance(wb.cells[s.cell].value, float)
                else wb.cells[s.cell].value) for n, s in mapping.inputs.items()}
    extra = flip_cases(_probe_flips(wb, mapping), mapping)
    with RefereeClient(None, path) as ref:
        res = run_mutation(
            code, mapping, ref, VerifyConfig(seed=20261204, max_examples=300, thresholds=thresholds),
            cases=100, targeted=list(candidate_inputs(base, [t.constant for t in thresholds])) + extra,
        )
    b9 = [m for m in res.mutants if m.location == "Calculator!B9" and m.operator.startswith("constant_")]
    assert b9, "no constant +-1 mutants on Calculator!B9"
    assert all(m.killed for m in b9), [(m.mutant_id, m.operator, m.survivor_reason) for m in b9 if not m.killed]
    for m in res.mutants:
        if not m.killed:
            assert "equivalen" not in (m.survivor_reason or "").lower()
