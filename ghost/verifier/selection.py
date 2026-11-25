"""Cases that change the winning row of MAX, MIN and MATCH (live-fixes-2026-11-24, L-08).

``MAX``, ``MIN`` and ``MATCH`` (so ``INDEX``/``MATCH``) hide a changed constant when the
row that holds it never wins on the tested inputs. This search finds inputs where the
selected row changes. It needs no knowledge of the workbook: the transpiled Faithful
module is run with ``_max``, ``_min`` and ``_match`` wrapped, and each call reports which
argument it picked (the position of the first extreme value, or the position MATCH
returned). The calls are identified by function, source line and call number.

Method, on the numeric inputs' effective domains (``ghost.verifier.domain``):

1. Evaluate the base point, a ladder of values along each input, and seeded random points.
2. For each call and each pair of positions seen, bisect between the closest two points
   that picked them, until two neighbouring points (one unit apart) pick differently.
   Points met on the way can reveal a third winner, which is then bisected the same way.
3. The cases are the two neighbours of every change point, plus one point for each
   position that never appeared at a change point.

Bounded by ``max_evaluations`` of the module and ``max_cases`` cases; reaching either is
recorded in the ``SelectionSummary`` (shown as report ``boundary_notes``). Same seed, same
cases.
"""
from __future__ import annotations

import random
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from ghost.verifier.domain import DEFAULT_MAX, Domain, to_number

__all__ = ["SelectionSummary", "find_selection_cases", "unpicked_rows_observed", "winner_signature"]

MAX_EVALUATIONS = 3000
MAX_CASES = 60
_RANDOM_POINTS = 600
_MAX_REPS = 40  # points per picked position compared when looking for the closest pair
_LADDER = (0, 1, 5, 20, 50, 100, 250, 500, 750, 900, 1000)  # per mille of the domain width
_SELECTORS = ("_max", "_min", "_match")

Site = tuple[str, int, int]  # (function, source line, call number on that line)
Signature = tuple  # sorted ((site, position), ...)


@dataclass
class SelectionSummary:
    """What the search did not check. Filled in by ``find_selection_cases``."""

    evaluations_used: int = 0
    max_evaluations: int = MAX_EVALUATIONS
    cap_reached: bool = False
    cases_truncated: int | None = None
    selections: int = 0  # MAX/MIN/MATCH calls with a choice to make
    change_points: int = 0
    not_checked_reason: str | None = None
    search_inputs: list[str] = field(default_factory=list)

    def notes(self) -> list[str]:
        if self.not_checked_reason is not None:
            return [f"selection search not checked: {self.not_checked_reason}"]
        out: list[str] = []
        if self.cap_reached:
            out.append(
                f"selection search stopped after {self.max_evaluations} evaluations; "
                "other winning rows may exist"
            )
        if self.cases_truncated is not None:
            out.append(f"selection search kept {self.cases_truncated} cases; the rest were not run")
        return out


class _Budget(Exception):
    pass


def _position(name: str, args: tuple, result: Any) -> Any:
    """The picked position, or None when the call had no choice to make."""
    if name == "_match":
        if len(args) != 2 or not hasattr(args[1], "vals") or len(args[1].vals) < 2:
            return None
        return int(result) if isinstance(result, Decimal) else str(result)
    flat: list[Any] = []
    for a in args:
        flat.extend(a.vals if hasattr(a, "vals") else [a])
    numbers = [x for x in flat if isinstance(x, Decimal)]
    if len(numbers) < 2 or not isinstance(result, Decimal):
        return None
    for i, x in enumerate(flat):
        if isinstance(x, Decimal) and x == result:
            return i
    return None


def _candidates(name: str, args: tuple) -> int:
    if name == "_match":
        return len(args[1].vals)
    return sum(len(a.vals) if hasattr(a, "vals") else 1 for a in args)


def winner_signature(
    compute: Callable[..., dict], inputs: dict[str, Any], sizes: dict[Site, int] | None = None,
) -> dict[Site, Any] | None:
    """Which argument each MAX/MIN/MATCH call of ``compute`` picked at ``inputs``.

    ``None`` when the module fails at ``inputs``. Calls of a module that has none of the
    three helpers give an empty dict. When ``sizes`` is given it receives the number of
    candidates (positions) of each call.
    """
    glob = getattr(compute, "__globals__", None)
    if glob is None:
        return None
    picked: dict[Site, Any] = {}
    counts: dict[tuple[str, int], int] = {}
    originals = {n: glob[n] for n in _SELECTORS if n in glob}

    def wrap(name: str, orig: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any) -> Any:
            result = orig(*args)
            line = sys._getframe(1).f_lineno
            n = counts[(name, line)] = counts.get((name, line), 0) + 1
            pos = _position(name, args, result)
            if pos is not None:
                picked[(name, line, n)] = pos
                if sizes is not None:
                    sizes[(name, line, n)] = _candidates(name, args)
            return result
        return wrapper

    for n, orig in originals.items():
        glob[n] = wrap(n, orig)
    try:
        compute(dict(inputs))
    except Exception:  # noqa: BLE001 - a point outside the module's domain has no winner
        return None
    finally:
        glob.update(originals)
    return picked


def _sig(picked: dict[Site, Any]) -> Signature:
    return tuple(sorted(picked.items(), key=lambda kv: (kv[0], str(kv[1]))))


def _snap(x: Decimal, unit: Decimal, integer: bool) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 60
        return x.to_integral_value(ROUND_HALF_EVEN) if integer else x.quantize(unit, ROUND_HALF_EVEN)


def find_selection_cases(
    compute: Callable[..., dict],
    mapping: Any,
    base_inputs: dict[str, Any],
    domains: dict[str, Domain],
    *,
    seed: int = 0,
    max_evaluations: int = MAX_EVALUATIONS,
    max_cases: int = MAX_CASES,
    summary: SelectionSummary | None = None,
) -> list[dict[str, Any]]:
    """Deterministic cases where the row picked by MAX, MIN or MATCH changes."""
    summary = summary if summary is not None else SelectionSummary()
    summary.max_evaluations = max_evaluations
    base = {n: v for n, v in base_inputs.items() if v is not None and n in mapping.inputs}
    names = sorted(n for n in base if n in domains and to_number(base[n]) is not None)
    summary.search_inputs = names
    if not names:
        return []
    integer = {n: mapping.inputs[n].type == "integer" for n in names}
    unit = Decimal("0.01")
    bounds: dict[str, tuple[Decimal, Decimal]] = {}
    for n in names:
        lo, hi = domains[n]
        b = to_number(base[n])
        bounds[n] = (
            lo if lo is not None else min(Decimal(0), b * 10),
            hi if hi is not None else max(DEFAULT_MAX, b * 10),
        )

    def point(values: dict[str, Decimal]) -> dict[str, Any]:
        p = dict(base)
        p.update(values)
        return p

    seen: dict[tuple, tuple[dict[str, Decimal], dict[Site, Any]]] = {}
    left = [max_evaluations]

    def probe(values: dict[str, Decimal]) -> dict[Site, Any] | None:
        key = tuple(sorted((n, str(v)) for n, v in values.items()))
        if key in seen:
            return seen[key][1]
        if left[0] <= 0:
            raise _Budget
        left[0] -= 1
        picked = winner_signature(compute, point(values))
        if picked is not None:
            seen[key] = (values, picked)
        return picked

    start = {n: _snap(to_number(base[n]), unit, integer[n]) for n in names}
    start = {n: min(max(v, bounds[n][0]), bounds[n][1]) for n, v in start.items()}
    rng = random.Random(seed)
    changes: list[tuple[dict[str, Decimal], dict[str, Decimal]]] = []
    attempted: set[tuple] = set()

    def ladder(n: str) -> list[Decimal]:
        lo, hi = bounds[n]
        return sorted({_snap(lo + (hi - lo) * Decimal(k) / 1000, unit, integer[n]) for k in _LADDER})

    def distance(a: dict[str, Decimal], b: dict[str, Decimal]) -> Decimal:
        total = Decimal(0)
        for n in names:
            width = bounds[n][1] - bounds[n][0]
            total += abs(a[n] - b[n]) / width if width > 0 else Decimal(0)
        return total

    def bisect(p: dict[str, Decimal], q: dict[str, Decimal]) -> None:
        lo_v, hi_v = p, q
        lo_s, hi_s = probe(lo_v), probe(hi_v)
        while lo_s is not None and hi_s is not None and _sig(lo_s) != _sig(hi_s):
            mid = {
                n: _snap((lo_v[n] + hi_v[n]) / 2, unit, integer[n]) for n in names
            }
            if mid == lo_v or mid == hi_v:
                changes.append((lo_v, hi_v))
                return
            mid_s = probe(mid)
            if mid_s is None:
                return
            if _sig(mid_s) == _sig(lo_s):
                lo_v, lo_s = mid, mid_s
            else:
                hi_v, hi_s = mid, mid_s

    try:
        probe(start)
        ladders = {n: ladder(n) for n in names}
        for n in names:  # one input at a time from the base point
            for v in ladders[n]:
                probe({**start, n: v})
        for _ in range(_RANDOM_POINTS):
            p: dict[str, Decimal] = {}
            for n in names:
                lo, hi = bounds[n]
                r = rng.random()
                if r < 0.3:
                    p[n] = rng.choice(ladders[n])
                elif r < 0.5:
                    p[n] = lo
                elif r < 0.75:  # log scale: small values are where a rare row can win
                    p[n] = _snap(lo + (hi - lo) * Decimal(repr(10 ** (-4 * rng.random()))), unit, integer[n])
                else:
                    p[n] = _snap(lo + (hi - lo) * Decimal(repr(rng.random())), unit, integer[n])
                p[n] = min(max(p[n], lo), hi)
            probe(p)
        while True:
            reps: dict[tuple[Site, Any], list[dict[str, Decimal]]] = {}
            for values, picked in seen.values():
                for site, pos in picked.items():
                    reps.setdefault((site, pos), []).append(values)
            todo = None
            by_site: dict[Site, list[Any]] = {}
            for site, pos in reps:
                by_site.setdefault(site, []).append(pos)
            for site in sorted(by_site):
                positions = sorted(by_site[site], key=str)
                for i, a in enumerate(positions):
                    for b in positions[i + 1:]:
                        if (site, str(a), str(b)) not in attempted:
                            todo = (site, a, b)
                            break
                    if todo:
                        break
                if todo:
                    break
            if todo is None:
                break
            site, a, b = todo
            attempted.add((site, str(a), str(b)))
            pa, pb = _thin(reps[(site, a)]), _thin(reps[(site, b)])
            best = min(
                ((x, y) for x in pa for y in pb), key=lambda xy: (distance(*xy), str(xy)),
            )
            bisect(*best)
    except _Budget:
        summary.cap_reached = True
    summary.evaluations_used = max_evaluations - left[0]
    summary.change_points = len(changes)
    summary.selections = len({s for _, picked in seen.values() for s in picked})

    ordered: list[dict[str, Decimal]] = []
    for lo_v, hi_v in changes:
        for v in (lo_v, hi_v):
            if v not in ordered:
                ordered.append(v)
    covered = {(s, str(p)) for v in ordered for s, p in seen[_key(v)][1].items()}
    for (site, pos), pts in sorted(
        ((k, v) for k, v in _reps(seen).items()), key=lambda kv: (kv[0][0], str(kv[0][1]))
    ):
        if (site, str(pos)) not in covered:
            ordered.append(pts[0])
            covered.update((s, str(p)) for s, p in seen[_key(pts[0])][1].items())
    if len(ordered) > max_cases:
        summary.cases_truncated = max_cases
        ordered = ordered[:max_cases]
    cases = []
    for values in ordered:
        case = point(values)
        for n in names:
            if integer[n]:
                case[n] = int(values[n])
        cases.append(case)
    return cases


def _thin(points: list, keep: int = _MAX_REPS) -> list:
    """At most ``keep`` points, evenly spread over the discovery order."""
    if len(points) <= keep:
        return points
    return [points[i * len(points) // keep] for i in range(keep)]


def _key(values: dict[str, Decimal]) -> tuple:
    return tuple(sorted((n, str(v)) for n, v in values.items()))


def _reps(seen: dict[tuple, tuple[dict[str, Decimal], dict[Site, Any]]]) -> dict[tuple[Site, Any], list]:
    out: dict[tuple[Site, Any], list] = {}
    for values, picked in seen.values():
        for site, pos in picked.items():
            out.setdefault((site, pos), []).append(values)
    return out


MIN_ROWS = 3  # a selection among at least this many candidates is a table of rows, not a floor


def unpicked_rows_observed(compute: Callable[..., dict], cases: list[dict[str, Any]]) -> bool:
    """True when, on ``cases``, some MAX/MIN/MATCH call among at least ``MIN_ROWS``
    candidates never picked one of them. Observed by running the module, not inferred."""
    picked: dict[Site, set] = {}
    sizes: dict[Site, int] = {}
    for case in cases:
        sig = winner_signature(compute, case, sizes)
        if sig is None:
            continue
        for site, pos in sig.items():
            picked.setdefault(site, set()).add(str(pos))
    return any(sizes.get(site, 0) >= MIN_ROWS and len(pos) < sizes[site] for site, pos in picked.items())
