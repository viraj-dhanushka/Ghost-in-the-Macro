"""Condition-flip probing (R-04, R-10 expressions; Property 6).

For every IF condition the transpiled Faithful module evaluates, each numeric input
is searched for the points where the condition changes truth value, with the other
inputs held at the base values and at a few seeded random base points. The module's
``trace(condition_id, bool)`` hook reports each condition, so the search works for
thresholds on calculated cells (``B11>=500``) and on expressions (``A2*A3>=500``)
alike, and needs no knowledge of the formula.

``find_flips`` returns a ``Flip`` per change point: a value on each side, within
``tolerance`` (integers: adjacent values), plus ``exact`` when the condition flips
between a value on the input's grid and a neighbour 1e-6 of a grid step away. That is
where the compared value equals the threshold, as far as the trace can show; it is
``None`` for integer inputs (both neighbours are already cases) and when the
threshold is not reachable on the grid.

All arithmetic is ``decimal.Decimal``. The work is bounded by ``max_evaluations``
calls of ``compute``. The result is a pure function of the arguments and ``seed``.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Callable

__all__ = [
    "Flip", "FlipSummary", "find_flips", "flip_cases", "flip_boundaries",
    "literals_from_workbook",
]

_GRID_POINTS = 9  # coarse scan points per input, endpoints and base value included
_MAX_FLIPS_PER_SEARCH = 3  # per condition, input and base point
_RANDOM_BASES = 2
_FINE_FACTOR = 6  # fine refinement is 10**-6 of a grid step
_MAX_LITERAL_POINTS = 60  # extra grid points seeded from formula literals, per search


@dataclass
class FlipSummary:
    """What flip probing did not check. Filled in by ``find_flips`` and ``flip_cases``.

    Everything here is engine output; ``notes()`` is the only wording shown to users.
    """

    max_evaluations: int = 0
    evaluations_used: int = 0
    cap_reached: bool = False
    conditions: list[str] = field(default_factory=list)
    not_completed: list[tuple[str, str]] = field(default_factory=list)  # (condition, input)
    no_flip: list[tuple[str, str, str]] = field(default_factory=list)  # (condition, input, domain)
    not_probed: list[tuple[str, str]] = field(default_factory=list)  # (input, type)
    flips_truncated: list[tuple[str, str]] = field(default_factory=list)
    literal_points_truncated: list[str] = field(default_factory=list)  # input names
    cases_truncated: int | None = None  # the limit, when more cases existed
    not_checked_reason: str | None = None
    partial_reason: str | None = None

    def notes(self) -> list[str]:
        """Deterministic user-facing lines; empty when nothing was left unchecked."""
        if self.not_checked_reason is not None:
            return [f"flip probing not checked: {self.not_checked_reason}"]
        out: list[str] = []
        if self.partial_reason:
            out.append(f"flip probing partial: {self.partial_reason}")
        if self.cap_reached:
            out.append(
                f"flip probing stopped at {self.evaluations_used} evaluations; "
                f"{len(self.not_completed)} condition/input pairs not checked"
            )
        if self.flips_truncated:
            pairs = ", ".join(f"{c} on {n}" for c, n in sorted(self.flips_truncated))
            out.append(
                f"flip probing kept only the first {_MAX_FLIPS_PER_SEARCH} change points "
                f"per search for: {pairs}"
            )
        if self.literal_points_truncated:
            out.append(
                f"flip probing seeded only {_MAX_LITERAL_POINTS} formula-literal points "
                f"per search for inputs: {', '.join(sorted(set(self.literal_points_truncated)))}"
            )
        if self.cases_truncated is not None:
            out.append(
                f"flip probing found more cases than the limit of {self.cases_truncated}; "
                "the rest were not added to verification"
            )
        by_cond: dict[str, list[str]] = {}
        for c, n, dom in self.no_flip:
            by_cond.setdefault(c, []).append(f"{n} {dom}")
        for c in sorted(by_cond):
            out.append(f"no flip found for {c} on {', '.join(sorted(by_cond[c]))}")
        for n, t in sorted(self.not_probed):
            out.append(f"not probed: {t} input {n}")
        return out


@dataclass(frozen=True)
class Flip:
    condition_id: str
    input_name: str
    others: dict[str, Any] = field(compare=True)
    below: Decimal
    above: Decimal
    exact: Decimal | None = None

    def cases(self) -> list[dict[str, Any]]:
        """Full input dicts: below, above and (if not None) exact."""
        values = [self.below, self.above]
        if self.exact is not None:
            values.append(self.exact)
        return [{**self.others, self.input_name: v} for v in values]


MAX_FLIP_CASES = 200  # cap on extra cases fed to verification and mutation


def flip_cases(
    flips: list[Flip], mapping: Any, limit: int = MAX_FLIP_CASES,
    summary: FlipSummary | None = None,
) -> list[dict[str, Any]]:
    """Deterministic, de-duplicated extra cases (integer inputs as ``int``).

    When more than ``limit`` distinct cases exist the rest are dropped and
    ``summary.cases_truncated`` records the limit.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for f in flips:
        for case in f.cases():
            for n, v in list(case.items()):
                spec = mapping.inputs.get(n)
                if spec is not None and spec.type == "integer" and isinstance(v, Decimal):
                    case[n] = int(v)
            key = tuple(sorted((n, str(v)) for n, v in case.items()))
            if key not in seen:
                if len(out) >= limit:
                    if summary is not None:
                        summary.cases_truncated = limit
                    return out
                seen.add(key)
                out.append(case)
    return out


def flip_boundaries(flips: list[Flip]) -> list[Any]:
    """One BoundaryResult per (condition, input): the first flip found (base values first)."""
    from ghost.models import BoundaryResult  # local: keep this module importable alone

    out: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for f in flips:
        if (f.condition_id, f.input_name) in seen:
            continue
        seen.add((f.condition_id, f.input_name))
        point = f.exact if f.exact is not None else f.above
        out.append(
            BoundaryResult(
                cell=f.condition_id.split("#")[0],
                input_name=f.input_name,
                threshold=point,
                change_point=point,
                kind="condition flip",
                condition_id=f.condition_id,
                below=f.below,
                above=f.above,
                exact=f.exact,
            )
        )
    return sorted(out, key=lambda b: (b.condition_id or "", b.input_name))


class _Budget(Exception):
    pass


_NUMBER = re.compile(r"(?<![A-Za-z_$!.\d\"'])(\d+(?:\.\d+)?)(%?)")


def literals_from_workbook(wb: Any) -> list[Decimal]:
    """Numeric literals written in the workbook's formulas, sorted, de-duplicated.

    Used to seed the probe grid so narrow windows (``AND(B1>10,B1<20)``) and equality
    tests (``B3=777``) are not missed between grid points. ``50%`` is 0.5.
    """
    found: set[Decimal] = set()
    for cell in wb.cells.values():
        f = getattr(cell, "formula", None)
        if not f:
            continue
        for num, pct in _NUMBER.findall(f):
            v = Decimal(num)
            found.add(v / 100 if pct else v)
    return sorted(found)


def _dec(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(x)


def _is_numeric(spec: Any) -> bool:
    return spec.type in ("integer", "decimal")


class _Prober:
    def __init__(self, compute: Callable[..., dict], max_evaluations: int) -> None:
        self.compute = compute
        self.left = max_evaluations

    def truths(self, inputs: dict[str, Any]) -> dict[str, bool]:
        if self.left <= 0:
            raise _Budget
        self.left -= 1
        seen: dict[str, bool] = {}

        def trace(cid: str, value: Any) -> None:
            seen[cid] = bool(value)

        try:
            self.compute(dict(inputs), trace)
        except Exception:  # noqa: BLE001 - a point outside the module's domain has no truth
            return {}
        return seen


def _snap(x: Decimal, unit: Decimal, integer: bool) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 60
        if integer:
            return x.to_integral_value(ROUND_HALF_EVEN)
        return x.quantize(unit, rounding=ROUND_HALF_EVEN)


def _bounds(spec: Any, base: Decimal) -> tuple[Decimal, Decimal]:
    lo = _dec(spec.min) if spec.min is not None else min(Decimal(0), base * 10)
    hi = _dec(spec.max) if spec.max is not None else max(Decimal(1000), base * 10)
    return lo, hi


def _literal_points(
    literals: list[Decimal], lo: Decimal, hi: Decimal, tol: Decimal, unit: Decimal, integer: bool
) -> tuple[list[Decimal], bool]:
    """Each literal, its +-1 and (decimals) +-tolerance, inside [lo, hi]; capped."""
    pts: set[Decimal] = set()
    for lit in literals:
        offsets = (Decimal(-1), Decimal(0), Decimal(1))
        if not integer:
            offsets += (-tol, tol)
        for o in offsets:
            p = _snap(lit + o, unit, integer)
            if lo <= p <= hi:
                pts.add(p)
    ordered = sorted(pts)
    return ordered[:_MAX_LITERAL_POINTS], len(ordered) > _MAX_LITERAL_POINTS


def _grid(
    lo: Decimal, hi: Decimal, base: Decimal, unit: Decimal, integer: bool,
    extra: list[Decimal] | tuple = (),
) -> list[Decimal]:
    points = {lo, hi, *extra}
    step = (hi - lo) / (_GRID_POINTS - 1)
    for i in range(1, _GRID_POINTS - 1):
        points.add(_snap(lo + step * i, unit, integer))
    if lo <= base <= hi:
        points.add(_snap(base, unit, integer))
    return sorted(p for p in points if lo <= p <= hi)


def _bisect(
    prober: _Prober,
    cid: str,
    inputs: dict[str, Any],
    name: str,
    lo: Decimal,
    hi: Decimal,
    lo_truth: bool,
    stop: Decimal,
    unit: Decimal,
    integer: bool,
) -> tuple[Decimal, Decimal] | None:
    """Narrow (lo, hi), whose truths differ, to an interval of width <= stop."""
    while hi - lo > stop:
        with localcontext() as ctx:
            ctx.prec = 60
            mid = (lo + hi) // 2 if integer else _snap((lo + hi) / 2, unit, False)
        if not lo < mid < hi:
            break
        value = prober.truths({**inputs, name: mid}).get(cid)
        if value is None:
            return None
        if value == lo_truth:
            lo = mid
        else:
            hi = mid
    return lo, hi


def _exact_hit(
    prober: _Prober,
    cid: str,
    inputs: dict[str, Any],
    name: str,
    below: Decimal,
    above: Decimal,
    below_truth: bool,
    unit: Decimal,
) -> Decimal | None:
    fine = unit.scaleb(-_FINE_FACTOR)
    refined = _bisect(prober, cid, inputs, name, below, above, below_truth, fine, fine, False)
    if refined is None:
        return None
    on_grid = [
        v for v in refined
        if below <= v <= above and v == _snap(v, unit, False)
    ]
    return on_grid[0] if len(on_grid) == 1 else None


def _search(
    prober: _Prober,
    inputs: dict[str, Any],
    name: str,
    spec: Any,
    tolerance: Decimal,
    unit: Decimal,
    found: dict[tuple, int],
    bases_key: tuple,
    out: list[Flip],
    summary: FlipSummary,
    literals: list[Decimal],
    domains: dict[str, str],
) -> None:
    integer = spec.type == "integer"
    base = _dec(inputs[name])
    lo, hi = _bounds(spec, base)
    if integer:
        lo, hi = lo.to_integral_value(ROUND_FLOOR), hi.to_integral_value(ROUND_FLOOR)
    domains.setdefault(name, f"[{lo}, {hi}]")
    if hi <= lo:
        return
    extra, cut = _literal_points(literals, lo, hi, tolerance, unit, integer)
    if cut:
        summary.literal_points_truncated.append(name)
    points = _grid(lo, hi, base, unit, integer, extra)
    states = [(p, prober.truths({**inputs, name: p})) for p in points]
    others = {k: v for k, v in inputs.items() if k != name}
    cids = sorted({c for _, t in states for c in t})
    for c in cids:
        if c not in summary.conditions:
            summary.conditions.append(c)
    for cid in cids:
        for (p0, t0), (p1, t1) in zip(states, states[1:]):
            a, b = t0.get(cid), t1.get(cid)
            if a is None or b is None or a == b:
                continue
            key = (cid, name, bases_key)
            if found.get(key, 0) >= _MAX_FLIPS_PER_SEARCH:
                if (cid, name) not in summary.flips_truncated:
                    summary.flips_truncated.append((cid, name))
                break
            narrowed = _bisect(prober, cid, inputs, name, p0, p1, a, tolerance if not integer else Decimal(1), unit, integer)
            if narrowed is None:
                continue
            below, above = narrowed
            exact = None if integer else _exact_hit(prober, cid, inputs, name, below, above, a, unit)
            found[key] = found.get(key, 0) + 1
            out.append(Flip(cid, name, dict(others), below, above, exact))


def find_flips(
    compute: Callable[..., dict],
    mapping: Any,
    base_inputs: dict[str, Any],
    *,
    tolerance: Decimal = Decimal("0.001"),
    seed: int = 0,
    max_evaluations: int = 6000,
    literals: list[Decimal] | None = None,
    summary: FlipSummary | None = None,
) -> list[Flip]:
    """Binary-search every numeric input for each IF condition's change points.

    ``compute`` is the transpiled Faithful ``compute(inputs, trace=None)``. Other inputs
    stay at ``base_inputs`` and at ``_RANDOM_BASES`` seeded random points inside their
    ``min``/``max``. ``literals`` (see ``literals_from_workbook``) seed the first base's
    grid. Stops when ``max_evaluations`` calls of ``compute`` are used; whatever was not
    checked is recorded in ``summary`` (pass a ``FlipSummary`` to receive it).
    """
    summary = summary if summary is not None else FlipSummary()
    summary.max_evaluations = max_evaluations
    literal_list = sorted(set(_dec(x) for x in (literals or ())))
    tolerance = _dec(tolerance)
    places = max(0, -tolerance.as_tuple().exponent) if tolerance.is_finite() else 3
    unit = Decimal(1).scaleb(-places)
    numeric = sorted(n for n, s in mapping.inputs.items() if _is_numeric(s) and n in base_inputs)
    base = {n: (_dec(v) if n in numeric else v) for n, v in base_inputs.items() if n in mapping.inputs}

    rng = random.Random(seed)
    bases: list[dict[str, Any]] = [dict(base)]
    for _ in range(_RANDOM_BASES):
        point = dict(base)
        for n in numeric:
            spec = mapping.inputs[n]
            lo, hi = _bounds(spec, base[n])
            integer = spec.type == "integer"
            if integer:
                point[n] = Decimal(rng.randint(int(lo), int(hi))) if hi >= lo else base[n]
            else:
                steps = int((hi - lo) / unit)
                point[n] = lo + unit * rng.randint(0, max(steps, 0)) if steps > 0 else base[n]
        if point not in bases:
            bases.append(point)

    prober = _Prober(compute, max_evaluations)
    out: list[Flip] = []
    found: dict[tuple, int] = {}
    domains: dict[str, str] = {}
    finished: dict[str, int] = {n: 0 for n in numeric}
    try:
        for i, inputs in enumerate(bases):
            for name in numeric:
                key = tuple(sorted((k, str(v)) for k, v in inputs.items() if k != name))
                _search(
                    prober, inputs, name, mapping.inputs[name], tolerance, unit, found, key,
                    out, summary, literal_list if i == 0 else [], domains,
                )
                finished[name] += 1
    except _Budget:
        summary.cap_reached = True
    summary.evaluations_used = max_evaluations - prober.left
    flipped = {(f.condition_id, f.input_name) for f in out}
    for name in numeric:
        for cid in summary.conditions:
            if finished[name] < len(bases):
                summary.not_completed.append((cid, name))
            elif (cid, name) not in flipped:
                summary.no_flip.append((cid, name, domains.get(name, "")))
    for n, spec in sorted(mapping.inputs.items()):
        if not _is_numeric(spec):
            summary.not_probed.append((n, "text" if spec.type == "string" else spec.type))
    return out
