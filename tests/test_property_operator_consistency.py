"""Property 4: Operator consistency (review-fixes-2026-11-24, task 5.1).

**Validates: Requirements 2.11**

For any two comparison operators on the same cell and constant,
`detect_inconsistencies` raises a Finding if and only if their truth sets over
{below, at, above} the constant are neither equal nor complementary (R-09).

Truth sets (docs/KIRO_FIX_PROMPT_2026-11-24.md, R-09):
    >=  {at, above}      >   {above}       <=  {below, at}
    <   {below}          =   {at}          <>  {below, above}

The oracle below is a literal table worked out from those sets, not code that
computes them. Pairs that are equal (same operator) or complementary are
consistent:  >= with <,  > with <=,  = with <>.  Every other pair conflicts.
"""
from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from ghost.autopsy.findings import detect_inconsistencies
from ghost.models import Location, Threshold

PBT_SEED = 20261204

OPERATORS = [">=", ">", "<=", "<", "=", "<>"]

# Literal oracle: unordered operator pairs whose truth sets are complementary.
# (Equal sets means the same operator, which is always consistent.)
COMPLEMENTARY = {
    frozenset({">=", "<"}),
    frozenset({">", "<="}),
    frozenset({"=", "<>"}),
}


def _expect_conflict(a: str, b: str) -> bool:
    if a == b:
        return False
    return frozenset({a, b}) not in COMPLEMENTARY


@seed(PBT_SEED)
@settings(max_examples=100, derandomize=False, database=None, deadline=None,
          suppress_health_check=list(HealthCheck))
@given(
    op_a=st.sampled_from(OPERATORS),
    op_b=st.sampled_from(OPERATORS),
    constant=st.decimals(min_value=-1000, max_value=1000, places=2, allow_nan=False, allow_infinity=False),
)
def test_property_4_operator_consistency(op_a, op_b, constant):
    thresholds = [
        Threshold(cell="S!A1", operator=op_a, constant=constant, source=Location(cell="S!B1")),
        Threshold(cell="S!A1", operator=op_b, constant=constant, source=Location(cell="S!B2")),
    ]
    findings = detect_inconsistencies(thresholds)
    assert (len(findings) == 1) == _expect_conflict(op_a, op_b), (op_a, op_b, Decimal(constant))
    assert len(findings) <= 1
