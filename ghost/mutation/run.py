"""Run the mutation self-check: verify every Mutant against the Referee.

The question answered is "would the verifier notice a wrong implementation?".
Each Mutant of the (passing) generated module is verified with a reduced case
budget plus targeted boundary cases (``candidate_inputs``: the neighbours of
every Threshold constant). A Mutant is *killed* when verification produces at
least one Mismatch in Faithful mode, and the first counterexample is kept.
The score is killed over total (Requirement 9.3).

Every survivor carries one of three kinds of reason (Requirement 9.4), decided from
what was observed, not guessed:

* ``branch not reachable``: the mutated cell's IF condition was never
  evaluated on any tested input.
* ``not exercised by cases``: the condition was evaluated but only one
  outcome was seen, so the mutated branch never ran.
* ``no difference found on N distinct cases``: the condition was seen both
  ways (or the cell has no IF) and the Mutant produced the same outputs as the
  original on every tested input. The reason lists each input's tested domain
  (type, min, max, decimal places). It is a statement about the cases tried,
  never a claim that the Mutant is equivalent.

The Referee is shared across Mutants through a cache, so each distinct input
is recalculated by LibreOffice once.

Requirements: 9.2, 9.3, 9.4.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from ghost.models import Case, Mapping, Mutant, MutationResult
from ghost.mutation.mutants import GeneratedMutant, generate_mutants
from ghost.verifier.compare import case_key, values_equal
from ghost.verifier.domain import effective_domains, in_domain
from ghost.verifier.selection import unpicked_rows_observed
from ghost.verifier.run import Evaluator, VerifyConfig, load_compute, verify

__all__ = [
    "MutationBaselineFailed",
    "REASON_NOT_EXERCISED",
    "REASON_UNREACHABLE",
    "SURVIVOR_NO_OUTPUT_CHANGE",
    "no_difference_reason",
    "run_mutation",
    "score",
    "tested_domains",
]

DEFAULT_MUTANT_CASES = 100

REASON_UNREACHABLE = "branch not reachable"
REASON_NOT_EXERCISED = "not exercised by cases"
SURVIVOR_NO_OUTPUT_CHANGE = "no_output_change"


class MutationBaselineFailed(Exception):
    """The unmutated module does not pass, so mutants cannot be judged."""


def score(result: MutationResult) -> float:
    return result.killed / result.total if result.total else 0.0


class _CachingReferee:
    """Evaluator wrapper: one Referee evaluation per distinct input."""

    def __init__(self, inner: Evaluator):
        self._inner = inner
        self._cache: dict[tuple, dict[str, Any]] = {}

    def eval(self, inputs: dict[str, Any], outputs: list[str]) -> dict[str, Any]:
        key = (
            tuple(sorted((k, type(v).__name__, str(v)) for k, v in inputs.items())),
            tuple(outputs),
        )
        hit = self._cache.get(key)
        if hit is None:
            hit = self._inner.eval(inputs, outputs)
            self._cache[key] = hit
        return hit


def _hook_outcomes(compute: Callable[..., dict], inputs: Iterable[dict[str, Any]]):
    """Outcomes seen per cell, and the outputs per input, from a traced run."""
    seen: dict[str, set[bool]] = {}

    def trace(hook_id: str, value: Any) -> None:
        seen.setdefault(hook_id.split("#", 1)[0], set()).add(bool(value))

    outs: list[dict[str, Any]] = []
    for inp in inputs:
        try:
            outs.append(compute(dict(inp), trace))
        except Exception as exc:  # noqa: BLE001 - recorded as a differing output
            outs.append({"<error>": type(exc).__name__})
    return seen, outs


def _survivor_reason(
    m: GeneratedMutant,
    mapping: Mapping,
    seen: dict[str, set[bool]],
    base_outs: list[dict[str, Any]],
    mutant_compute: Callable[..., dict],
    tested: list[dict[str, Any]],
    tol: float,
) -> str:
    outcomes = seen.get(m.location)
    if m.operator.startswith("drop_if"):
        if not outcomes:
            return REASON_UNREACHABLE
        # drop_if_then keeps THEN, so it differs only when the condition is false.
        needed = False if m.operator == "drop_if_then" else True
        if needed not in outcomes:
            return REASON_NOT_EXERCISED
    elif outcomes is not None and len(outcomes) < 2:
        return REASON_NOT_EXERCISED
    _, mut_outs = _hook_outcomes(mutant_compute, tested)
    for a, b in zip(base_outs, mut_outs):
        if a.keys() != b.keys() or any(not values_equal(a[k], b[k], tol) for k in a):
            return REASON_NOT_EXERCISED  # differs on a case the verifier did not flag
    return no_difference_reason(mapping, tested)


def _case_key(case: dict[str, Any]) -> tuple:
    return case_key(case)


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


def tested_domains(mapping: Mapping, cases: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Per input: type, min, max and decimal places over the cases actually run."""
    cases = list(cases)
    out: dict[str, str] = {}
    for name, spec in sorted(mapping.inputs.items()):
        values = [c[name] for c in cases if name in c and c[name] is not None]
        if not values:
            out[name] = f"{spec.type}, not tested"
            continue
        nums = [n for n in (_numeric(v) for v in values) if n is not None]
        if spec.type in ("integer", "decimal") and nums:
            places = max(max(0, -n.normalize().as_tuple().exponent) for n in nums)  # type: ignore[operator]
            dp = f"{places} decimal places" if spec.type == "integer" else f"up to {places} decimal places"
            out[name] = f"{spec.type}, min {_fmt(min(nums))}, max {_fmt(max(nums))}, {dp}"
        else:
            out[name] = f"{spec.type}, {len({str(v) for v in values})} distinct values"
    return out


def no_difference_reason(mapping: Mapping, cases: Iterable[dict[str, Any]]) -> str:
    """Survivor reason: what was tried, not a claim that the Mutant is equivalent."""
    cases = list(cases)
    distinct = len({_case_key(c) for c in cases})
    domain = "; ".join(f"{n}: {d}" for n, d in tested_domains(mapping, cases).items())
    return f"no difference found on {distinct} distinct cases; tested domain: {domain}"


def run_mutation(
    module: str,
    mapping: Mapping,
    referee: Evaluator,
    config: VerifyConfig | None = None,
    *,
    cases: int = DEFAULT_MUTANT_CASES,
    targeted: Iterable[dict[str, Any]] = (),
    progress: Callable[[int, int], None] | None = None,
) -> MutationResult:
    """Verify every Mutant of ``module`` (source text) against the Referee.

    ``config`` supplies seed, thresholds, tolerance and overrides; its mode is
    forced to Faithful and its classifier, trace and progress are not used for
    Mutants. ``targeted`` are extra cases (Threshold neighbours) tried first.
    Raises ``MutationBaselineFailed`` when the unmutated module has Mismatches.
    """
    base_cfg = config or VerifyConfig()
    # L-07: a targeted case with a value outside an input's effective domain is not run,
    # so survivor reasons never describe values the verification did not test.
    domains = effective_domains(mapping, base_cfg.sample, base_cfg.default_max, base_cfg.overrides)
    extra = [
        dict(c) for c in targeted
        if all(n not in domains or in_domain(v, domains[n]) for n, v in c.items())
    ]
    cfg = replace(
        base_cfg,
        mode="faithful",
        max_examples=cases,
        classifier=None,
        trace=None,
        progress=None,
        extra_cases=extra,
    )
    shared = _CachingReferee(referee)

    baseline = verify(module, mapping, shared, cfg)
    if not baseline.passed:
        raise MutationBaselineFailed(
            f"the unmutated module has {len(baseline.mismatches)} Mismatch(es); "
            "fix or record a Decision before running the mutation check"
        )
    tested = baseline.cases + [c for c in extra if c not in baseline.cases]
    base_compute = load_compute(module)
    seen, base_outs = _hook_outcomes(base_compute, tested)

    unpicked = unpicked_rows_observed(base_compute, tested)  # L-08, from the traced module
    generated = generate_mutants(module)
    records: list[Mutant] = []
    for i, gm in enumerate(generated, 1):
        mutant_compute = load_compute(gm.source)
        res = verify(mutant_compute, mapping, shared, cfg)
        if res.mismatches:
            first = res.mismatches[0]
            records.append(
                Mutant(
                    mutant_id=gm.mutant_id,
                    operator=gm.operator,
                    location=gm.location,
                    killed=True,
                    killed_by=Case(
                        inputs=first.case.inputs,
                        referee=first.case.referee,
                        actual=first.case.actual,
                    ),
                )
            )
        else:
            reason = _survivor_reason(gm, mapping, seen, base_outs, mutant_compute, tested, cfg.tol)
            records.append(
                Mutant(
                    mutant_id=gm.mutant_id,
                    operator=gm.operator,
                    location=gm.location,
                    killed=False,
                    survivor_reason=reason,
                    survivor_kind=(
                        SURVIVOR_NO_OUTPUT_CHANGE
                        if unpicked and reason.startswith("no difference found on ") else None
                    ),
                )
            )
        if progress:
            progress(i, len(generated))
    killed = sum(1 for r in records if r.killed)
    return MutationResult(mutants=records, killed=killed, total=len(records))


def describe(result: MutationResult, descriptions: dict[str, str] | None = None) -> list[str]:
    """Plain text lines for CLI output."""
    lines = [f"mutation score: {result.killed}/{result.total} killed ({score(result):.0%})"]
    for m in result.mutants:
        if m.killed:
            continue
        what = (descriptions or {}).get(m.mutant_id, m.operator)
        lines.append(f"  survived {m.mutant_id} {m.location} {what}: {m.survivor_reason}")
    return lines
