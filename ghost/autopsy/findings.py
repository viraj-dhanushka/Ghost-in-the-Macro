"""Inconsistency detection (requirement 2.8).

The same cell compared with the same constant is an operator conflict when two
operators disagree about the constant. Each operator has a truth set over
{below, at, above}; two operators are consistent when their sets are equal or
complementary (R-09). Finding ids are assigned in sorted (cell, constant) order,
so identical input gives identical ids.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ghost.models import Finding, Location, Threshold


_ALL = frozenset({"below", "at", "above"})
_TRUTH: dict[str, frozenset[str]] = {
    ">=": frozenset({"at", "above"}),
    ">": frozenset({"above"}),
    "<=": frozenset({"below", "at"}),
    "<": frozenset({"below"}),
    "=": frozenset({"at"}),
    "<>": frozenset({"below", "above"}),
}


def _consistent(a: str, b: str) -> bool:
    if a == b:
        return True
    ta, tb = _TRUTH.get(a), _TRUTH.get(b)
    if ta is None or tb is None:
        return False  # unknown operator: do not guess, keep the Finding
    return ta == tb or (not (ta & tb) and (ta | tb) == _ALL)


def _has_conflict(operators: set[str]) -> bool:
    ops = sorted(operators)
    return any(not _consistent(a, b) for i, a in enumerate(ops) for b in ops[i + 1:])


def _location_key(loc: Location) -> tuple[str, str, int]:
    return (loc.cell or "", loc.module or "", loc.line or 0)


def detect_inconsistencies(thresholds: list[Threshold]) -> list[Finding]:
    groups: dict[tuple[str, Decimal], list[Threshold]] = defaultdict(list)
    for t in thresholds:
        groups[(t.cell, t.constant)].append(t)

    findings: list[Finding] = []
    for cell, constant in sorted(groups):
        members = groups[(cell, constant)]
        if not _has_conflict({t.operator for t in members}):
            continue
        unique = {(t.source, t.operator) for t in members}
        locations = sorted(unique, key=lambda lo: (_location_key(lo[0]), lo[1]))
        findings.append(
            Finding(
                finding_id=f"F-{len(findings) + 1:03d}",
                kind="operator_conflict",
                cell=cell,
                constant=constant,
                locations=locations,
            )
        )
    return findings
