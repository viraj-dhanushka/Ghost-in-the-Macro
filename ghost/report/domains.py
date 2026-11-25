"""Tested domain of each input, from the cases a verification actually ran (R-21).

Structured rows for the proof report. ``ghost.mutation.run.tested_domains``
words the same facts as text for survivor reasons.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from ghost.models import Mapping
from ghost.verifier.domain import DEFAULT_MAX


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


def tested_domain_rows(
    mapping: Mapping,
    cases: Iterable[dict[str, Any]],
    sample: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """One row per input, sorted by name: type, min, max, decimal places (or distinct values).

    With ``sample`` (the workbook's own input values), a row whose max was widened to include
    the sample value (it is above the declared or default max) gets ``max_includes_sample``.
    """
    sample = sample or {}
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
            row: dict[str, Any] = {
                "input": name, "type": spec.type,
                "min": _fmt(min(nums)), "max": _fmt(max(nums)), "decimal_places": places,
            }
            s_val = _numeric(sample.get(name))
            cap = spec.max if spec.max is not None else DEFAULT_MAX
            if s_val is not None and s_val > cap:
                row["max_includes_sample"] = _fmt(s_val)
            rows.append(row)
        else:
            rows.append({
                "input": name, "type": spec.type,
                "distinct_values": len({str(v) for v in values}),
            })
    return rows
