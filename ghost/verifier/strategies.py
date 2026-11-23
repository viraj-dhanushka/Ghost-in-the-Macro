"""Input strategies and type inference for the verifier.

Requirements 8.2, 8.3. Numeric inputs are generated as ``int`` (integer type)
or ``Decimal`` (decimal type). Draws are weighted toward threshold neighbours
(t-1, t, t+1 and, for decimals, t±0.1), zero, negatives where allowed, large
values and decimals.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping as MappingABC, Sequence
from decimal import Decimal

from hypothesis import strategies as st

from ghost.models import IOSpec, Mapping, Threshold

LARGE = Decimal(1_000_000)
_ONE = Decimal(1)
_TENTH = Decimal("0.1")


def _to_decimal(x: object) -> Decimal | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        return Decimal(repr(x))
    if isinstance(x, str):
        try:
            return Decimal(x.strip())
        except Exception:
            return None
    return None


def _is_integral(d: Decimal) -> bool:
    return d.is_finite() and d == d.to_integral_value()


def infer_type(samples: Iterable[object]) -> str:
    """Return "integer" iff all sample values are integers, else "decimal".

    Booleans give "boolean" and non-numeric strings give "string". With no
    usable samples the type defaults to "decimal".
    """
    vals = [s for s in samples if s is not None]
    if not vals:
        return "decimal"
    if all(isinstance(v, bool) for v in vals):
        return "boolean"
    nums = [_to_decimal(v) for v in vals]
    if any(n is None for n in nums):
        return "string"
    return "integer" if all(_is_integral(n) for n in nums if n is not None) else "decimal"


def _validation_type(validation: str | None) -> str | None:
    if not validation:
        return None
    kind = validation.split(":", 1)[0]
    return {"whole": "integer", "decimal": "decimal"}.get(kind)


def infer_spec(
    cell: str,
    samples: Iterable[object] = (),
    validation: str | None = None,
    override: IOSpec | None = None,
) -> IOSpec:
    """Infer an IOSpec from samples and data validation; a user override wins."""
    if override is not None:
        return override
    samples = list(samples)
    vtype = _validation_type(validation)
    typ = vtype or infer_type(samples)
    nums = [d for d in (_to_decimal(s) for s in samples) if d is not None]
    lo = min(nums) if nums and typ in ("integer", "decimal") else None
    hi = max(nums) if nums and typ in ("integer", "decimal") else None
    # Negatives are allowed only if observed; otherwise the lower bound is 0.
    if typ in ("integer", "decimal") and lo is not None and lo >= 0:
        lo = Decimal(0)
    if typ in ("integer", "decimal") and hi is not None:
        hi = None  # upper bound unknown: samples are examples, not limits
    return IOSpec(cell=cell, type=typ, min=lo, max=hi)  # type: ignore[arg-type]


def threshold_neighbours(
    constants: Iterable[Decimal], typ: str = "decimal"
) -> list[Decimal]:
    """t-1, t, t+1 (and t±0.1 for decimals), sorted and de-duplicated."""
    out: set[Decimal] = set()
    for t in constants:
        out.update({t - _ONE, t, t + _ONE})
        if typ == "decimal":
            out.update({t - _TENTH, t + _TENTH})
    return sorted(out)


def _in_range(d: Decimal, spec: IOSpec) -> bool:
    return (spec.min is None or d >= spec.min) and (spec.max is None or d <= spec.max)


def _coerce(d: Decimal, typ: str) -> Decimal | int:
    return int(d) if typ == "integer" else d


def numeric_strategy(
    spec: IOSpec, constants: Sequence[Decimal] = ()
) -> st.SearchStrategy:
    """Threshold-weighted strategy for one numeric input."""
    typ = spec.type
    lo = spec.min
    hi = spec.max
    special: list[Decimal] = [Decimal(0), _ONE, LARGE]
    special += threshold_neighbours(constants, typ)
    if lo is not None:
        special += [lo, lo + _ONE]
    if hi is not None:
        special += [hi, hi - _ONE]
    if lo is None or lo < 0:
        special += [Decimal(-1), -LARGE]
    special = sorted({d for d in special if _in_range(d, spec)})
    if typ == "integer":
        special = sorted({d for d in special if _is_integral(d)})

    if typ == "integer":
        min_v = int(lo) if lo is not None else -(10**9)
        max_v = int(hi) if hi is not None else 10**9
        bulk = st.integers(min_value=min_v, max_value=max_v).map(Decimal)
    else:
        min_v = lo if lo is not None else Decimal(-(10**9))
        max_v = hi if hi is not None else Decimal(10**9)
        bulk = st.decimals(
            min_value=min_v, max_value=max_v, places=2, allow_nan=False, allow_infinity=False
        )
    if not special:
        return bulk.map(lambda d: _coerce(d, typ))
    # Threshold neighbours get most of the weight so 1,000 draws reach them.
    weighted = st.one_of(
        st.sampled_from(special),
        st.sampled_from(special),
        st.sampled_from(special),
        bulk,
    )
    return weighted.map(lambda d: _coerce(d, typ))


def input_strategy(
    spec: IOSpec, thresholds: Iterable[Threshold] = ()
) -> st.SearchStrategy:
    """Strategy for one input given its spec and the thresholds on its cell."""
    if spec.type == "boolean":
        return st.booleans()
    if spec.type == "string":
        return st.text(max_size=12)
    consts = [t.constant for t in thresholds if t.cell == spec.cell]
    return numeric_strategy(spec, consts)


def inputs_strategy(
    mapping: Mapping,
    thresholds: Iterable[Threshold] = (),
    overrides: MappingABC[str, IOSpec] | None = None,
) -> st.SearchStrategy[dict]:
    """Strategy producing a dict of input name -> value for ``compute``."""
    thresholds = list(thresholds)
    overrides = overrides or {}
    parts = {
        name: input_strategy(overrides.get(name, spec), thresholds)
        for name, spec in sorted(mapping.inputs.items())
    }
    return st.fixed_dictionaries(parts)
