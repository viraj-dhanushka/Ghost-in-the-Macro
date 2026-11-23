"""Rule coverage: observe each Rule condition as true and as false.

The generated ``compute(inputs, trace=None)`` calls ``trace(hook_id, bool)`` for
every IF condition it evaluates. Hook ids look like ``"Sheet!B7#1"`` (cell plus
the 1-based IF position in that formula, pre-order). Rule conditions have ids
``"<rule_id>-C<n>"`` and the n-th condition of a rule is the n-th IF of the
rule's own cell (``rule.cells[0]``), so the tracker maps hook ids to condition
ids through that pairing.

Targeted generation (``close_gaps``) tries extra candidate inputs for the gaps
left by the random run; conditions still unobserved are reported as uncovered.
Only observed values are reported.

Requirements: 8.8, 8.9.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping as MappingABC
from decimal import Decimal
from typing import Any

from ghost.models import Rule, RuleCoverage
from ghost.verifier.strategies import threshold_neighbours


class CoverageTracker:
    def __init__(self, rules: Iterable[Rule]):
        self._order: list[tuple[str, str]] = []  # (rule_id, condition_id)
        self._hooks: dict[str, tuple[str, str]] = {}
        self._true: set[str] = set()
        self._false: set[str] = set()
        for rule in rules:
            if not rule.cells:
                continue
            home = rule.cells[0]
            for n, cond in enumerate(rule.conditions, 1):
                self._order.append((rule.rule_id, cond.condition_id))
                self._hooks[f"{home}#{n}"] = (rule.rule_id, cond.condition_id)

    def trace(self, hook_id: str, value: Any) -> None:
        """Trace hook to pass to ``compute``. Unknown hook ids are ignored."""
        hit = self._hooks.get(hook_id)
        if hit is None:
            return
        (self._true if bool(value) else self._false).add(hit[1])

    def run(self, compute: Callable[..., dict], inputs: dict[str, Any]) -> dict:
        """Call ``compute`` with this tracker's hook and return its result."""
        return compute(inputs, trace=self.trace)

    def instrument(self, compute: Callable[..., dict]) -> Callable[[dict], dict]:
        """Wrap ``compute`` so each call records condition outcomes."""
        def wrapped(inputs: dict[str, Any]) -> dict:
            return compute(inputs, trace=self.trace)

        return wrapped

    def report(self) -> list[RuleCoverage]:
        return [
            RuleCoverage(
                rule_id=rid,
                condition_id=cid,
                seen_true=cid in self._true,
                seen_false=cid in self._false,
            )
            for rid, cid in self._order
        ]

    def uncovered(self) -> list[RuleCoverage]:
        return [c for c in self.report() if c.uncovered]

    @property
    def complete(self) -> bool:
        return not self.uncovered()


def candidate_inputs(
    base: MappingABC[str, Any],
    constants: Iterable[Decimal | int | float] = (),
    names: Iterable[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Targeted candidates: vary one numeric input at a time over the neighbours
    (t-1, t, t+1, t±0.1) of each constant, plus zero and negative one.
    Deterministic order."""
    consts = [c if isinstance(c, Decimal) else Decimal(repr(c)) for c in constants]
    values = sorted(set(threshold_neighbours(consts)) | {Decimal(0), Decimal(-1)})
    for name in names if names is not None else sorted(base):
        cur = base[name]
        if isinstance(cur, bool) or not isinstance(cur, (int, float, Decimal)):
            continue
        for v in values:
            if isinstance(cur, int):
                if v != v.to_integral_value():
                    continue
                v = int(v)  # type: ignore[assignment]
            yield {**base, name: v}


def close_gaps(
    tracker: CoverageTracker,
    compute: Callable[..., dict],
    candidates: Iterable[dict[str, Any]],
) -> list[RuleCoverage]:
    """Run candidates until every condition is seen both ways or candidates run
    out. Returns the conditions still uncovered."""
    for inputs in candidates:
        if tracker.complete:
            break
        tracker.run(compute, inputs)
    return tracker.uncovered()
