"""Tested domain of each input, from the cases a verification actually ran (R-21).

Structured rows for the proof report. ``ghost.mutation.run.tested_domains``
words the same facts as text for survivor reasons.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from ghost.models import Mapping


def _numeric(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    return None


def _fmt(d: Decimal) -> str:
    return format(d.normalize(), "f")


def tested_domain_rows(mapping: Mapping, cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per input, sorted by name: type, min, max, decimal places (or distinct values)."""
    cases = list(cases)
    rows: list[dict[str, Any]] = []
    for name, spec in sorted(mapping.inputs.items()):
        values = [c[name] for c in cases if name in c and c[name] is not None]
        if not values:
            rows.append({"input": name, "type": spec.type, "not_tested": True})
            continue
        nums = [n for n in (_numeric(v) for v in values) if n is not None]
        if spec.type in ("integer", "decimal") and nums:
            places = max(max(0, -n.normalize().as_tuple().exponent) for n in nums)  # type: ignore[operator]
            rows.append({
                "input": name, "type": spec.type,
                "min": _fmt(min(nums)), "max": _fmt(max(nums)), "decimal_places": places,
            })
        else:
            rows.append({
                "input": name, "type": spec.type,
                "distinct_values": len({str(v) for v in values}),
            })
    return rows
