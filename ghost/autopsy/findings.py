"""Inconsistency detection (requirement 2.8).

The same cell compared with the same constant using different operators is an
operator conflict. Finding ids are assigned in sorted (cell, constant) order,
so identical input gives identical ids.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ghost.models import Finding, Location, Threshold


def _location_key(loc: Location) -> tuple[str, str, int]:
    return (loc.cell or "", loc.module or "", loc.line or 0)


def detect_inconsistencies(thresholds: list[Threshold]) -> list[Finding]:
    groups: dict[tuple[str, Decimal], list[Threshold]] = defaultdict(list)
    for t in thresholds:
        groups[(t.cell, t.constant)].append(t)

    findings: list[Finding] = []
    for cell, constant in sorted(groups):
        members = groups[(cell, constant)]
        if len({t.operator for t in members}) < 2:
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
