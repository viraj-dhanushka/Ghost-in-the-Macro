"""The effective domain of a numeric input (live-fixes-2026-11-24, L-07).

One definition, used by the Hypothesis strategies, the targeted cases
(``candidate_inputs``), flip probing, the mutation check's targeted list and the
report's "Tested domains" table, so they all describe the same set of values.

Owner decision (task 5.4), for each numeric input:

* ``min``: the declared ``IOSpec`` min, or no lower bound when there is none (an
  input the mapping says cannot be negative has ``min`` 0 and so keeps 0 as its floor).
* ``max``: the largest of the declared ``IOSpec`` max, ``default_max`` when there is no
  declared max, and the workbook's own sample value. A sample above the default cap
  (scenarios: ``gross_income`` 60,000) therefore widens the domain instead of being
  dropped.

A targeted value is clamped into the domain. ``None`` as a bound means unbounded.
"""
from __future__ import annotations

from collections.abc import Mapping as MappingABC
from decimal import Decimal
from typing import Any

from ghost.models import IOSpec, Mapping

__all__ = [
    "DEFAULT_MAX",
    "Domain",
    "clamp",
    "effective_domain",
    "effective_domains",
    "in_domain",
    "is_numeric_spec",
    "to_number",
]

DEFAULT_MAX = Decimal(10_000)

# (min or None for no lower bound, max or None for no upper bound)
Domain = tuple["Decimal | None", "Decimal | None"]


def is_numeric_spec(spec: IOSpec) -> bool:
    return spec.type in ("integer", "decimal")


def to_number(value: Any) -> Decimal | None:
    """``value`` as a Decimal (floats through ``repr``), or None for non-numbers and booleans."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        d = Decimal(repr(value))
        return d if d.is_finite() else None
    return None


def effective_domain(
    spec: IOSpec, sample: Any = None, default_max: Decimal | None = DEFAULT_MAX
) -> Domain:
    """The domain of one numeric input; see the module docstring."""
    lo = spec.min
    candidates: list[Decimal] = []
    if spec.max is not None:
        candidates.append(spec.max)
    elif default_max is not None:
        candidates.append(default_max)
    s = to_number(sample)
    if s is not None and candidates:
        candidates.append(s)
    hi = max(candidates) if candidates else None  # no declared max and no cap: unbounded
    return lo, hi


def effective_domains(
    mapping: Mapping,
    sample: MappingABC[str, Any] | None = None,
    default_max: Decimal | None = DEFAULT_MAX,
    overrides: MappingABC[str, IOSpec] | None = None,
) -> dict[str, Domain]:
    """The domain of every numeric input of ``mapping``, by input name."""
    sample = sample or {}
    overrides = overrides or {}
    return {
        name: effective_domain(overrides.get(name, spec), sample.get(name), default_max)
        for name, spec in sorted(mapping.inputs.items())
        if is_numeric_spec(overrides.get(name, spec))
    }


def in_domain(value: Any, domain: Domain) -> bool:
    d = to_number(value)
    if d is None:
        return True  # not a number: nothing to bound
    lo, hi = domain
    return (lo is None or d >= lo) and (hi is None or d <= hi)


def clamp(value: Decimal, domain: Domain) -> Decimal:
    lo, hi = domain
    if lo is not None and value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value
