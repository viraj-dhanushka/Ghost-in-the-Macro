"""Mutation self-check on samples and fixtures, against the real Referee.

**Validates: Requirements 20.7** (and 9.1, 9.3, 9.4: Property 29 end to end).
Skipped with a clear message when soffice is not installed. Nothing is faked:
every Case is recalculated by headless LibreOffice.

Hand-checked arithmetic used below:

* Gold fixture: Total = Quantity * Unit price; flag = IF(Total>=500,...).
  Random cases (explicit seed) essentially never land on Total = 500.00 because
  the threshold sits on a derived cell, not on an input. Boundary probing
  (``targeted`` cases = Threshold neighbours, as the CLI passes them) varies
  one input at a time over 499, 500, 501, ... so Unit price = 500 with
  Quantity = 1 gives Total = 500.00 exactly, where ``>=`` and ``>`` differ.
* Rounding fixture: the task's 235 x 0.03 is 7.05 exactly, which needs no
  rounding at 2 places (half-even and half-away agree), so the fixture uses
  ROUND(Quantity*0.03, 1). Then 235 * 0.03 = 7.05 sits exactly on a .x5
  boundary with an even digit before it: half away from zero gives 7.1,
  half even gives 7.0.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import Workbook as XlWorkbook

from ghost.autopsy.thresholds import extract_thresholds
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.mutation.run import describe, run_mutation, score
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.coverage import candidate_inputs
from ghost.verifier.run import VerifyConfig

from samples import make_discount, make_haunted

try:
    locate_soffice()
    _SOFFICE_MSG = None
except RefereeUnavailable as exc:
    _SOFFICE_MSG = f"LibreOffice (soffice) not available, mutation tests need the real Referee: {exc}"

pytestmark = pytest.mark.skipif(_SOFFICE_MSG is not None, reason=_SOFFICE_MSG or "")

SEED = 20261204
CASES = 40


def _base_inputs(wb, mapping):
    base = {}
    for name, spec in mapping.inputs.items():
        v = wb.cells[spec.cell].value
        base[name] = Decimal(repr(v)) if isinstance(v, float) else v
    return base


def _prepare(path, user_outputs=()):
    wb = load_workbook(str(path))
    mapping = generate_mapping(wb, user_outputs=list(user_outputs))
    thresholds = extract_thresholds(wb)
    return wb, mapping, thresholds, emit_python(wb, mapping)


@pytest.mark.parametrize("module", [make_discount, make_haunted], ids=["discount", "haunted"])
def test_flip_comparison_mutants_on_bulk_thresholds_are_killed(module, tmp_path):
    """Requirements 20.7, 9.1, 9.3: every ``>=``/``>`` flip on a bulk Threshold dies."""
    path = module.build(tmp_path / "s.xlsx")
    wb, mapping, thresholds, source = _prepare(path)
    constants = [t.constant for t in thresholds]
    base = _base_inputs(wb, mapping)
    cfg = VerifyConfig(seed=SEED, max_examples=CASES, thresholds=thresholds)
    with RefereeClient(None, path) as ref:
        result = run_mutation(
            source, mapping, ref, cfg, cases=CASES,
            targeted=list(candidate_inputs(base, constants)),
        )

    bulk_cells = {t.source.cell for t in thresholds if t.constant == 50}
    assert bulk_cells, "sample must have a bulk Threshold at 50"
    flips = [m for m in result.mutants if m.operator == "flip_comparison" and m.location in bulk_cells]
    assert {m.location for m in flips} == bulk_cells
    survivors = [(m.location, m.survivor_reason) for m in flips if not m.killed]
    assert not survivors, f"flip_comparison mutants survived: {survivors}"
    for m in flips:
        assert m.killed_by is not None and m.killed_by.inputs["quantity"] in (49, 50, 51)

    # Score is reported as killed/total (Requirement 9.3).
    assert result.total == len(result.mutants) > 0
    assert result.killed == sum(m.killed for m in result.mutants)
    assert score(result) == result.killed / result.total
    assert describe(result)[0].startswith(f"mutation score: {result.killed}/{result.total} killed")
    assert all(m.survivor_reason for m in result.mutants if not m.killed)


def _gold_fixture(path):
    wb = XlWorkbook()
    ws = wb.active
    ws.title = "Loyalty"
    ws["A1"], ws["B1"] = "Quantity", 1
    ws["A2"], ws["B2"] = "Unit price", 1.25
    ws["A3"], ws["B3"] = "Total", "=B1*B2"
    ws["A4"], ws["B4"] = "Tier", '=IF(B3>=500,"Gold","Standard")'
    wb.save(path)
    return path


def test_gold_ge_to_gt_mutant_killed_only_by_boundary_probing(tmp_path):
    """Requirement 20.7: ``>=`` -> ``>`` at Total = 500.00 needs boundary probing."""
    path = _gold_fixture(tmp_path / "gold.xlsx")
    wb, mapping, thresholds, source = _prepare(path, user_outputs=["Loyalty!B3"])
    assert [(t.cell, t.operator, t.constant) for t in thresholds] == [("Loyalty!B3", ">=", Decimal(500))]
    constants = [t.constant for t in thresholds]
    base = _base_inputs(wb, mapping)
    cfg = VerifyConfig(seed=SEED, max_examples=CASES, thresholds=thresholds)

    def flip(result):
        (m,) = [m for m in result.mutants if m.operator == "flip_comparison" and m.location == "Loyalty!B4"]
        return m

    with RefereeClient(None, path) as ref:
        random_only = run_mutation(source, mapping, ref, cfg, cases=CASES, targeted=[])
        probed = run_mutation(
            source, mapping, ref, cfg, cases=CASES,
            targeted=list(candidate_inputs(base, constants)),
        )

    survived = flip(random_only)
    assert not survived.killed, "random cases alone must not hit Total = 500.00 exactly"
    assert survived.survivor_reason

    killed = flip(probed)
    assert killed.killed and killed.killed_by is not None
    total_name = next(n for n, s in mapping.outputs.items() if s.cell == "Loyalty!B3")
    tier_name = next(n for n, s in mapping.outputs.items() if s.cell == "Loyalty!B4")
    assert Decimal(repr(killed.killed_by.referee[total_name])) == Decimal("500")
    assert killed.killed_by.referee[tier_name] == "Gold"
    assert killed.killed_by.actual[tier_name] == "Standard"


def test_half_even_rounding_mutant_killed_at_235_times_0_03(tmp_path):
    """Requirement 20.7: ROUND half up -> half even differs at 235 * 0.03 = 7.05."""
    path = tmp_path / "round.xlsx"
    wb = XlWorkbook()
    ws = wb.active
    ws.title = "Fee"
    ws["A1"], ws["B1"] = "Quantity", 1
    ws["A2"], ws["B2"] = "Fee", "=ROUND(B1*0.03,1)"
    wb.save(path)

    wbk, mapping, thresholds, source = _prepare(path)
    cfg = VerifyConfig(seed=SEED, max_examples=CASES, thresholds=thresholds)
    with RefereeClient(None, path) as ref:
        # Baseline sanity on the Referee itself: half away from zero, 7.05 -> 7.1.
        assert Decimal(repr(ref.eval({"Fee!B1": 235}, ["Fee!B2"])["Fee!B2"])) == Decimal("7.1")
        result = run_mutation(source, mapping, ref, cfg, cases=CASES, targeted=[{"quantity": 235}])

    (m,) = [m for m in result.mutants if m.operator == "rounding_mode"]
    assert m.killed and m.killed_by is not None
    assert m.killed_by.inputs["quantity"] == 235
    out = next(iter(mapping.outputs))
    assert Decimal(repr(m.killed_by.referee[out])) == Decimal("7.1")
    assert Decimal(str(m.killed_by.actual[out])) == Decimal("7.0")
