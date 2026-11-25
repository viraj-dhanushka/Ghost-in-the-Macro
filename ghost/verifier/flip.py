"""Condition-flip probing (R-04, R-10 expressions; Property 6).

For every IF condition the transpiled Faithful module evaluates, each numeric input
is searched for the points where the condition changes truth value, with the other
inputs held at the base values and at a few seeded random base points. The module's
``trace(condition_id, bool)`` hook reports each condition, so the search works for
thresholds on calculated cells (``B11>=500``) and on expressions (``A2*A3>=500``)
alike, and needs no knowledge of the formula.

``find_flips`` returns a ``Flip`` per change point: a value on each side, within
``tolerance`` (integers: adjacent values), plus ``exact``:

* decimal inputs: when the condition flips between a value on the input's grid and
  a neighbour 1e-6 of a grid step away, where the compared value equals the
  threshold as far as the trace can show; ``None`` when the threshold is not
  reachable on the grid.
* integer inputs (L-04): ``below`` or ``above``, whichever makes the two compared
  sides equal. Each is evaluated again with a hook that asks for the compared
  values (``trace.compared = True``, see ``ghost/converter/emit_python.py``), and
  the hit is recorded only when the module reports two equal numbers. It is never
  inferred from the operator. When the module does not report the values (a
  hand-written module, or a condition that is not a single comparison) and no hit
  is confirmed, ``FlipSummary.exact_not_checked`` records the pair.

All arithmetic is ``decimal.Decimal``. The work is bounded by ``max_evaluations``
calls of ``compute``. The result is a pure function of the arguments and ``seed``.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Callable

from ghost.verifier.domain import DEFAULT_MAX, effective_domain, in_domain

__all__ = [
    "Flip", "FlipSummary", "find_flips", "flip_cases", "flip_boundaries",
    "literals_from_workbook",
]

_GRID_POINTS = 9  # coarse scan points per input, endpoints and base value included
_MAX_FLIPS_PER_SEARCH = 3  # per condition, input and base point
_RANDOM_BASES = 2
_FINE_FACTOR = 6  # fine refinement is 10**-6 of a grid step
_MAX_LITERAL_POINTS = 60  # extra grid points seeded from formula literals, per search
_SMALL_VALUES = (Decimal(1), Decimal(2), Decimal(4), Decimal(5), Decimal(10))  # L-04 retry
_RETRY_EVALS_PER_CONDITION = 600  # extra evaluations the small-values retry may use per condition
_RETRY_EVALS_TOTAL = 2000  # ... and per run


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
    # (condition, input): integer flips whose compared values the module did not report
    exact_not_checked: list[tuple[str, str]] = field(default_factory=list)
    # (condition, input): integer flips found, exact hit not checked, budget used up
    exact_cut_short: list[tuple[str, str]] = field(default_factory=list)
    # (condition, input): small-values retry stopped by its evaluation cap
    retry_cut_short: list[tuple[str, str]] = field(default_factory=list)
    # exact-hit cases found but dropped by the case limit: (condition, input, others, exact)
    exact_not_run: list[tuple] = field(default_factory=list)
    # (condition, input) searched from some but not all base points when the budget ran out
    partly_checked: list[tuple[str, str]] = field(default_factory=list)
    finer_literals: list[Decimal] = field(default_factory=list)  # formula literals below the probe step
    probe_step: Decimal = Decimal("0.001")
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
            if not self.conditions:
                out.append(
                    f"flip probing stopped at {self.evaluations_used} evaluations before "
                    "any condition was found; no condition was checked"
                )
            elif self.not_completed:
                out.append(
                    f"flip probing stopped at {self.evaluations_used} evaluations; "
                    f"{len(self.not_completed)} condition/input pairs not checked"
                )
            else:
                out.append(
                    f"flip probing stopped at {self.evaluations_used} evaluations; every "
                    "condition/input pair found was searched from at least one base point"
                )
            if self.conditions:
                if self.partly_checked:
                    pairs = ", ".join(f"{c} on {n}" for c, n in sorted(self.partly_checked))
                    out.append(
                        "flip probing searched only some of the base points for: " + pairs
                    )
                out.append(
                    "flip probing stopped before all conditions were found; "
                    "conditions it had not reached are not listed"
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
        if self.exact_not_checked:
            pairs = ", ".join(f"{c} on {n}" for c, n in sorted(set(self.exact_not_checked)))
            out.append(
                "exact hit not checked (the module's trace did not report the two "
                f"compared values) for: {pairs}"
            )
        if self.exact_cut_short:
            pairs = ", ".join(f"{c} on {n}" for c, n in sorted(set(self.exact_cut_short)))
            out.append(f"exact hit not checked (evaluation limit reached) for: {pairs}")
        if self.retry_cut_short:
            pairs = ", ".join(f"{c} on {n}" for c, n in sorted(set(self.retry_cut_short)))
            out.append(
                "exact hit search with small values for the other inputs stopped at its "
                f"evaluation limit for: {pairs}"
            )
        if self.cases_truncated is not None:
            out.append(
                f"flip probing found more cases than the limit of {self.cases_truncated}; "
                "the rest were not added to verification"
            )
        if self.exact_not_run:
            out.append(
                f"{len(self.exact_not_run)} exact hits found but not run: case limit of "
                f"{self.cases_truncated}; their boundary rows are marked"
            )
        if self.finer_literals:
            shown = ", ".join(str(x) for x in self.finer_literals[:3])
            out.append(
                f"decimal thresholds finer than the {self.probe_step} probe step are not "
                f"checked (formula literals: {shown})"
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
    # L-06: the constant the condition compares against, or ``calculated`` when the
    # compared threshold moves with an input; both unset when it could not be told.
    threshold_constant: Decimal | None = field(default=None, compare=False)
    threshold_calculated: bool | None = field(default=None, compare=False)

    def exact_ident(self) -> tuple:
        """Identity of this flip's exact hit (condition, input, other values, value)."""
        return (
            self.condition_id, self.input_name,
            tuple(sorted((n, str(v)) for n, v in self.others.items())), str(self.exact),
        )

    def cases(self) -> list[dict[str, Any]]:
        """Full input dicts: below, above and (if not None) exact."""
        values = [self.below, self.above]
        if self.exact is not None:
            values.append(self.exact)
        return [{**self.others, self.input_name: v} for v in values]


MAX_FLIP_CASES = 200  # cap on extra cases fed to verification and mutation


def flip_cases(
    flips: list[Flip], mapping: Any, limit: int = MAX_FLIP_CASES,
    summary: FlipSummary | None = None, domains: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic, de-duplicated extra cases (integer inputs as ``int``).

    ``domains`` (input name -> effective domain, ``ghost.verifier.domain``) is a guard:
    a case with a numeric value outside its input's domain is dropped. The search already
    stays inside the domain, so nothing is dropped in practice.

    When more than ``limit`` distinct cases exist the rest are dropped and
    ``summary.cases_truncated`` records the limit. Truncation keeps the cases of
    confirmed exact hits first, then the others in flip order. An exact-hit case that
    still does not fit is recorded in ``summary.exact_not_run``; its boundary row is
    marked by ``flip_boundaries``.
    """
    distinct: list[dict[str, Any]] = []
    index: dict[tuple, int] = {}
    exact_of: dict[int, list[tuple]] = {}  # case position -> exact idents it serves
    for f in flips:
        for which, case in enumerate(f.cases()):
            if domains and any(
                n in domains and not in_domain(v, domains[n]) for n, v in case.items()
            ):
                continue
            for n, v in list(case.items()):
                spec = mapping.inputs.get(n)
                if spec is not None and spec.type == "integer" and isinstance(v, Decimal):
                    case[n] = int(v)
            key = tuple(sorted((n, str(v)) for n, v in case.items()))
            if key not in index:
                index[key] = len(distinct)
                distinct.append(case)
            if which == 2:  # the exact-hit case
                exact_of.setdefault(index[key], []).append(f.exact_ident())
    if len(distinct) <= limit:
        return distinct
    if summary is not None:
        summary.cases_truncated = limit
    order = sorted(range(len(distinct)), key=lambda i: (i not in exact_of, i))
    kept = sorted(order[:limit])
    if summary is not None:
        kept_set = set(kept)
        for i in sorted(exact_of):
            if i not in kept_set:
                summary.exact_not_run.extend(exact_of[i])
    return [distinct[i] for i in kept]


def flip_boundaries(flips: list[Flip], summary: FlipSummary | None = None) -> list[Any]:
    """One BoundaryResult per (condition, input): the first flip found (base values first).

    ``summary`` (the one given to ``flip_cases``) marks rows whose exact-hit case was
    dropped by the case limit; a flip whose exact case ran is preferred over one whose
    case did not.
    """
    from ghost.models import BoundaryResult  # local: keep this module importable alone

    out: list[Any] = []
    seen: set[tuple[str, str]] = set()
    not_run = set(summary.exact_not_run) if summary is not None else set()
    # A confirmed exact hit (including one from the small-values retry) is preferred over
    # the first bracket-only flip for the same condition and input.
    ordered = sorted(
        flips, key=lambda f: (f.exact is None, f.exact is not None and f.exact_ident() in not_run)
    )  # stable: search order kept
    for f in ordered:
        if (f.condition_id, f.input_name) in seen:
            continue
        seen.add((f.condition_id, f.input_name))
        point = f.exact if f.exact is not None else f.above
        dropped = f.exact is not None and f.exact_ident() in not_run
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
                exact_others=(
                    {k: str(v) for k, v in sorted(f.others.items())}
                    if f.exact is not None and f.others else None
                ),
                exact_note="found but not run: case limit" if dropped else None,
                threshold_constant=f.threshold_constant,
                threshold_calculated=f.threshold_calculated,
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
        self.retried: set[tuple[str, str]] = set()  # (condition, input) already retried
        self.retry_spent: dict[str, int] = {}  # evaluations used by retries, per condition
        self.retry_total = 0

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

    def compared(self, inputs: dict[str, Any], cid: str) -> tuple[Any, ...] | None:
        """The two values ``cid`` compared at ``inputs``, as the module reports them.

        ``None`` when the module did not report them (its trace call carried only the
        truth value, or the condition was not evaluated). One evaluation of the budget.
        """
        if self.left <= 0:
            raise _Budget
        self.left -= 1
        seen: dict[str, tuple[Any, ...]] = {}

        def trace(c: str, value: Any, *sides: Any) -> None:
            seen[c] = sides

        trace.compared = True  # type: ignore[attr-defined]  # ask for the compared values
        try:
            self.compute(dict(inputs), trace)
        except Exception:  # noqa: BLE001 - nothing reported at a failing point
            return None
        sides = seen.get(cid)
        return sides if sides is not None and len(sides) == 2 else None


def _equal_numbers(left: Any, right: Any) -> bool:
    """True only for two numbers (not booleans) with exactly the same Decimal value."""
    for x in (left, right):
        if isinstance(x, bool) or not isinstance(x, (int, float, Decimal)):
            return False
    a, b = _dec(left), _dec(right)
    return a.is_finite() and b.is_finite() and a == b


def _integer_exact_hit(
    prober: _Prober, cid: str, inputs: dict[str, Any], name: str,
    below: Decimal, above: Decimal,
) -> tuple[Decimal | None, bool]:
    """``below`` or ``above`` where the module reports equal compared values (L-04).

    Returns (exact hit or None, whether the module reported the values at both points).
    A hit is recorded only when exactly one of the two points is confirmed equal.
    """
    hits: list[Decimal] = []
    reported = True
    for value in (below, above):
        sides = prober.compared({**inputs, name: value}, cid)
        if sides is None:
            reported = False
        elif _equal_numbers(*sides):
            hits.append(value)
    return (hits[0] if len(hits) == 1 else None), reported


def _snap(x: Decimal, unit: Decimal, integer: bool) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 60
        if integer:
            return x.to_integral_value(ROUND_HALF_EVEN)
        return x.quantize(unit, rounding=ROUND_HALF_EVEN)


def _bounds(spec: Any, base: Decimal) -> tuple[Decimal, Decimal]:
    """Search range of one input: its effective domain (``ghost.verifier.domain``).

    The upper end is the domain's maximum (declared max, else the default cap, and never
    below the value the workbook holds). With no declared min the domain has no lower
    bound; the search then starts at 0, or at ten times a negative value."""
    dmin, dmax = effective_domain(spec, base)
    lo = _dec(dmin) if dmin is not None else min(Decimal(0), base * 10)
    hi = _dec(dmax) if dmax is not None else max(DEFAULT_MAX, base * 10)
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


def _confirmed_exact(
    prober: _Prober, cid: str, inputs: dict[str, Any], name: str, value: Decimal
) -> bool:
    """True when the module reports two equal compared numbers for ``cid`` at ``value``."""
    sides = prober.compared({**inputs, name: value}, cid)
    return sides is not None and _equal_numbers(*sides)


def _small_value_variants(
    inputs: dict[str, Any], name: str, mapping_inputs: dict[str, Any]
) -> list[dict[str, Any]]:
    """Variants of ``inputs`` with every OTHER numeric input at one small value (L-04).

    For each value in ``_SMALL_VALUES``, each other numeric input whose effective
    domain (type, min, max) contains it and that does not already hold it is set to
    it; the others keep their current value. Variants that change nothing are skipped.
    """
    variants: list[dict[str, Any]] = []
    for s in _SMALL_VALUES:
        variant = dict(inputs)
        changed = False
        for other in sorted(mapping_inputs):
            spec = mapping_inputs[other]
            if other == name or not _is_numeric(spec) or other not in inputs:
                continue
            lo, hi = _bounds(spec, _dec(inputs[other]))
            if spec.type == "integer":
                lo, hi = lo.to_integral_value(ROUND_FLOOR), hi.to_integral_value(ROUND_FLOOR)
            if lo <= s <= hi and _dec(inputs[other]) != s:
                variant[other] = s
                changed = True
        if changed:
            variants.append(variant)
    return variants


def _retry_small_values(
    prober: _Prober,
    cid: str,
    inputs: dict[str, Any],
    name: str,
    mapping_inputs: dict[str, Any],
    tolerance: Decimal,
    unit: Decimal,
    literals: list[Decimal],
    out: list[Flip],
    summary: FlipSummary,
) -> None:
    """Search ``name`` again for ``cid`` with the other inputs at small values (L-04).

    Stops at the first confirmed exact hit. Only a hit confirmed by the compared-values
    trace is kept, as a Flip whose ``others`` hold the retry's values. Bounded by
    ``_RETRY_EVALS_PER_CONDITION`` for the condition and ``_RETRY_EVALS_TOTAL`` for the
    run; reaching either is recorded in ``summary.retry_cut_short``.
    """
    spec = mapping_inputs[name]
    integer = spec.type == "integer"
    for variant in _small_value_variants(inputs, name, mapping_inputs):
        if (
            prober.retry_spent.get(cid, 0) >= _RETRY_EVALS_PER_CONDITION
            or prober.retry_total >= _RETRY_EVALS_TOTAL
        ):
            if (cid, name) not in summary.retry_cut_short:
                summary.retry_cut_short.append((cid, name))
            return
        start = prober.left
        try:
            hit = _retry_one(
                prober, cid, variant, name, spec, integer, tolerance, unit, literals, out
            )
        finally:
            spent = start - prober.left
            prober.retry_spent[cid] = prober.retry_spent.get(cid, 0) + spent
            prober.retry_total += spent
        if hit:
            return


def _retry_one(
    prober: _Prober, cid: str, inputs: dict[str, Any], name: str, spec: Any,
    integer: bool, tolerance: Decimal, unit: Decimal, literals: list[Decimal],
    out: list[Flip],
) -> bool:
    base = _dec(inputs[name])
    lo, hi = _bounds(spec, base)
    if integer:
        lo, hi = lo.to_integral_value(ROUND_FLOOR), hi.to_integral_value(ROUND_FLOOR)
    if hi <= lo:
        return False
    extra, _cut = _literal_points(literals, lo, hi, tolerance, unit, integer)
    points = _grid(lo, hi, base, unit, integer, extra)
    states = [(p, prober.truths({**inputs, name: p})) for p in points]
    kept = 0
    for (p0, t0), (p1, t1) in zip(states, states[1:]):
        a, b = t0.get(cid), t1.get(cid)
        if a is None or b is None or a == b:
            continue
        kept += 1
        if kept > _MAX_FLIPS_PER_SEARCH:
            break
        narrowed = _bisect(
            prober, cid, inputs, name, p0, p1, a, tolerance if not integer else Decimal(1),
            unit, integer,
        )
        if narrowed is None:
            continue
        below, above = narrowed
        if integer:
            exact, _reported = _integer_exact_hit(prober, cid, inputs, name, below, above)
        else:
            exact = _exact_hit(prober, cid, inputs, name, below, above, a, unit)
            if exact is not None and not _confirmed_exact(prober, cid, inputs, name, exact):
                exact = None
        if exact is not None:
            others = {k: v for k, v in inputs.items() if k != name}
            flip = Flip(cid, name, others, below, above, exact)
            # One Flip per (condition, input, other values): a retry that lands on a point
            # already searched upgrades a Flip without an exact hit, never duplicates it.
            same = [
                i for i, f in enumerate(out)
                if (f.condition_id, f.input_name, f.others) == (cid, name, others)
            ]
            if not same:
                out.append(flip)
                return True
            if out[same[0]].exact is None:
                out[same[0]] = flip
                return True
            return False
    return False


_CLASSIFY_EVALS = 1500  # evaluations for threshold classification, per run


def _is_number(x: Any) -> bool:
    return not isinstance(x, bool) and isinstance(x, (int, float, Decimal))


def _classify_one(
    prober: _Prober, f: Flip, mapping_inputs: dict[str, Any]
) -> tuple[Decimal | None, bool] | None:
    """(constant, False) or (None, True) for ``f``'s condition; ``None`` when unknown.

    The module reports the two compared values at ``below`` and ``above``. A side that is
    the same at both points and does not move when any other numeric input is changed is
    the constant. If neither side stays put, or the steady side moves with another input,
    the threshold is calculated. Anything the trace does not show is left unknown.
    """
    cid, name = f.condition_id, f.input_name
    low = prober.compared({**f.others, name: f.below}, cid)
    high = prober.compared({**f.others, name: f.above}, cid)
    if low is None or high is None or not all(_is_number(x) for x in (*low, *high)):
        return None
    steady = [i for i in (0, 1) if _dec(low[i]) == _dec(high[i])]
    if not steady:
        return None, True
    if len(steady) == 2:
        return None  # the condition does not depend on this input here
    i = steady[0]
    value = _dec(high[i])
    for other in sorted(f.others):
        spec = mapping_inputs.get(other)
        if spec is None or not _is_numeric(spec):
            continue
        cur = _dec(f.others[other])
        lo, hi = _bounds(spec, cur)
        alt = hi if cur != hi else lo
        if alt == cur:
            continue
        moved = prober.compared({**f.others, other: alt, name: f.above}, cid)
        if moved is None or not all(_is_number(x) for x in moved):
            return None
        if _dec(moved[i]) != value:
            return None, True
    return value, False


def _classify_thresholds(
    prober: _Prober, out: list[Flip], mapping_inputs: dict[str, Any]
) -> None:
    """Set ``threshold_constant`` / ``threshold_calculated`` on every flip (L-06).

    One classification per (condition, input), made on the flip the boundary table shows
    (a confirmed exact hit first, as ``flip_boundaries`` orders them) and copied to the
    others. Stops quietly when the allowance is used up: those flips stay unclassified.
    """
    from dataclasses import replace

    result: dict[tuple[str, str], tuple[Decimal | None, bool] | None] = {}
    order = sorted(range(len(out)), key=lambda i: (out[i].exact is None, i))
    try:
        for i in order:
            key = (out[i].condition_id, out[i].input_name)
            if key not in result:
                result[key] = _classify_one(prober, out[i], mapping_inputs)
    except _Budget:
        pass
    for i, f in enumerate(out):
        got = result.get((f.condition_id, f.input_name))
        if got is not None:
            out[i] = replace(f, threshold_constant=got[0], threshold_calculated=got[1])


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
    mapping_inputs: dict[str, Any],
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
            if integer:
                try:
                    exact, reported = _integer_exact_hit(prober, cid, inputs, name, below, above)
                except _Budget:
                    # Keep the flip already found; its exact hit was not checked.
                    found[key] = found.get(key, 0) + 1
                    out.append(Flip(cid, name, dict(others), below, above, None))
                    summary.exact_cut_short.append((cid, name))
                    raise
                if exact is None and not reported:
                    summary.exact_not_checked.append((cid, name))
            else:
                exact = _exact_hit(prober, cid, inputs, name, below, above, a, unit)
                if exact is not None:
                    # The bisection only infers the hit; keep it only when the module's
                    # compared values confirm it (the same rule as for integers).
                    try:
                        sides = prober.compared({**inputs, name: exact}, cid)
                    except _Budget:
                        found[key] = found.get(key, 0) + 1
                        out.append(Flip(cid, name, dict(others), below, above, None))
                        summary.exact_cut_short.append((cid, name))
                        raise
                    if sides is None:
                        summary.exact_not_checked.append((cid, name))
                    if sides is None or not _equal_numbers(*sides):
                        exact = None
            found[key] = found.get(key, 0) + 1
            out.append(Flip(cid, name, dict(others), below, above, exact))
            if exact is None and (cid, name) not in prober.retried:
                prober.retried.add((cid, name))
                _retry_small_values(
                    prober, cid, inputs, name, mapping_inputs, tolerance, unit, literals,
                    out, summary,
                )


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
                    out, summary, literal_list if i == 0 else [], domains, mapping.inputs,
                )
                finished[name] += 1
    except _Budget:
        summary.cap_reached = True
    summary.evaluations_used = max_evaluations - prober.left
    # L-06 threshold classification has its own small allowance, not counted above.
    prober.left = _CLASSIFY_EVALS
    _classify_thresholds(prober, out, mapping.inputs)
    summary.probe_step = unit
    if any(_is_numeric(mapping.inputs[n]) and mapping.inputs[n].type == "decimal" for n in numeric):
        summary.finer_literals = [x for x in literal_list if -x.as_tuple().exponent > places]
    flipped = {(f.condition_id, f.input_name) for f in out}
    for name in numeric:
        for cid in summary.conditions:
            if finished[name] == 0:
                summary.not_completed.append((cid, name))
            elif finished[name] < len(bases):
                summary.partly_checked.append((cid, name))
            elif (cid, name) not in flipped:
                summary.no_flip.append((cid, name, domains.get(name, "")))
    for n, spec in sorted(mapping.inputs.items()):
        if not _is_numeric(spec):
            summary.not_probed.append((n, "text" if spec.type == "string" else spec.type))
    return out
