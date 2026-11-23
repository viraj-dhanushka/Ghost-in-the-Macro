"""Verification run: Hypothesis cases, Referee as oracle, shrunk counterexamples.

``verify`` generates Cases with Hypothesis (explicit ``seed``, no example
database), evaluates each on the Referee (one long-lived process, results
cached per distinct input so shrinking never repeats an eval) and on the
generated ``compute``, and compares every mapped output with
``values_equal``. The first failing Case is shrunk by Hypothesis to a minimal
counterexample, which is reported as a ``Mismatch`` with ``minimal=True`` (one
Mismatch per differing output).

Mismatch classification (Requirement 8.10 to 8.12) is a separate task. A
``classifier`` callable may be passed in the config; without one every
Mismatch is reported as "translation bug", the only claim the engine can make
without Findings and Decisions. ``passed`` follows Requirement 8.13/8.14.

Requirements: 8.1, 8.6, 8.7.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Protocol

from hypothesis import HealthCheck, Phase, seed as hyp_seed, settings

from ghost.models import Case, IOSpec, Mapping, Mismatch, Mode, Threshold
from ghost.verifier.classify import verdict
from ghost.verifier.compare import DEFAULT_TOL, values_equal
from ghost.verifier.strategies import inputs_strategy

__all__ = ["VerifyConfig", "VerifyResult", "load_compute", "verify"]

DEFAULT_SEED = 20261204
DEFAULT_CASES = 300


class Evaluator(Protocol):
    def eval(self, inputs: dict[str, Any], outputs: list[str]) -> dict[str, Any]: ...


@dataclass
class VerifyConfig:
    seed: int = DEFAULT_SEED
    max_examples: int = DEFAULT_CASES
    mode: Mode = "faithful"
    tol: float = DEFAULT_TOL
    # Upper bound applied to numeric inputs whose mapping has no max. The
    # Referee computes in binary doubles, so very large products cannot meet
    # the 1e-6 absolute tolerance; this keeps clean workbooks at zero Mismatches.
    default_max: Decimal | None = Decimal(10_000)
    thresholds: list[Threshold] = field(default_factory=list)
    overrides: dict[str, IOSpec] = field(default_factory=dict)
    # progress(cases_done, cases_total) after each new Referee evaluation.
    progress: Callable[[int, int], None] | None = None
    # Optional condition trace passed to compute(inputs, trace) (rule coverage).
    trace: Callable[[str, bool], None] | None = None
    # Optional Mismatch -> Mismatch hook (classify.py).
    classifier: Callable[[Mismatch], Mismatch] | None = None
    # Cases evaluated before Hypothesis' own generation, e.g. targeted cases.
    extra_cases: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class VerifyResult:
    seed: int
    mode: Mode
    cases_tested: int
    passed: bool
    mismatches: list[Mismatch]
    # Generated inputs in order, up to and including the first failing Case.
    cases: list[dict[str, Any]]
    max_examples: int


def load_compute(source: str | Path | Callable[..., dict]) -> Callable[..., dict]:
    """Return ``compute`` from a callable, a module path, or module source."""
    if callable(source):
        return source
    text = str(source)
    p = Path(text) if "\n" not in text and len(text) < 4096 else None
    if p is not None and p.is_file():
        text = p.read_text(encoding="utf-8")
    ns: dict[str, Any] = {"__name__": "ghost_generated_logic"}
    mod = types.ModuleType("ghost_generated_logic")
    mod.__dict__.update(ns)
    exec(compile(text, "<ghost-logic>", "exec"), mod.__dict__)
    fn = mod.__dict__.get("compute")
    if not callable(fn):
        raise ValueError("module does not define compute(inputs)")
    return fn


def _wire(value: Any) -> Any:
    """Referee wire value: Decimal becomes int or float, others unchanged."""
    if isinstance(value, bool) or not isinstance(value, Decimal):
        return value
    return int(value) if value == value.to_integral_value() else float(value)


def _referee_value(v: Any) -> Any:
    if isinstance(v, dict) and "error" in v:
        return v["error"]
    return v


class _Failed(AssertionError):
    """Raised inside the Hypothesis test body when a Case mismatches."""


def verify(
    module: str | Path | Callable[..., dict],
    mapping: Mapping,
    referee: Evaluator,
    config: VerifyConfig | None = None,
) -> VerifyResult:
    cfg = config or VerifyConfig()
    compute = load_compute(module)
    in_cells = {n: s.cell for n, s in mapping.inputs.items()}
    out_cells = {n: s.cell for n, s in mapping.outputs.items()}
    out_names = sorted(out_cells)
    out_refs = [out_cells[n] for n in out_names]

    cache: dict[tuple, tuple[dict[str, Any], dict[str, Any], list[str]]] = {}
    generated: list[dict[str, Any]] = []
    state: dict[str, Any] = {"failed": False, "last_fail": None, "done": 0}

    def evaluate(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        key = tuple((n, type(inputs[n]).__name__, str(inputs[n])) for n in sorted(inputs))
        hit = cache.get(key)
        if hit is not None:
            return hit
        wire = {in_cells[n]: _wire(v) for n, v in inputs.items()}
        ref_raw = referee.eval(wire, out_refs)
        ref = {n: _referee_value(ref_raw.get(out_cells[n])) for n in out_names}
        try:
            got = compute(dict(inputs), cfg.trace) if cfg.trace else compute(dict(inputs))
        except Exception as exc:  # a crashing implementation is a mismatch
            got = {n: f"<compute raised {type(exc).__name__}: {exc}>" for n in out_names}
        diffs = [
            n for n in out_names
            if n not in got or not values_equal(ref[n], got[n], cfg.tol)
        ]
        res = (ref, {n: got.get(n) for n in out_names}, diffs)
        cache[key] = res
        state["done"] += 1
        if cfg.progress:
            cfg.progress(state["done"], cfg.max_examples)
        return res

    def check(inputs: dict[str, Any]) -> None:
        ref, got, diffs = evaluate(inputs)
        if not state["failed"]:
            generated.append(dict(inputs))
        if diffs:
            state["failed"] = True
            state["last_fail"] = (dict(inputs), ref, got, diffs)
            raise _Failed(f"mismatch on {diffs}")

    for extra in cfg.extra_cases:
        try:
            check(dict(extra))
        except _Failed:
            break

    if not state["failed"]:
        overrides = dict(cfg.overrides)
        if cfg.default_max is not None:
            for n, spec in mapping.inputs.items():
                spec = overrides.get(n, spec)
                if spec.type in ("integer", "decimal") and spec.max is None:
                    overrides[n] = spec.model_copy(update={"max": cfg.default_max})
        strat = inputs_strategy(mapping, cfg.thresholds, overrides)

        def body(inputs: dict[str, Any]) -> None:
            check(inputs)

        prepared = hyp_seed(cfg.seed)(
            settings(
                max_examples=cfg.max_examples,
                derandomize=False,
                database=None,
                deadline=None,
                phases=(Phase.generate, Phase.shrink),
                suppress_health_check=list(HealthCheck),
                print_blob=False,
            )(_given(strat, body))
        )
        try:
            prepared()
        except BaseException as exc:  # noqa: BLE001
            if state["last_fail"] is None:
                raise exc

    mismatches: list[Mismatch] = []
    if state["last_fail"] is not None:
        inputs, ref, got, diffs = state["last_fail"]
        for name in diffs:
            m = Mismatch(
                case=Case(inputs=inputs, referee=ref, actual=got),
                output=name,
                cell=out_cells[name],
                mismatch_class="translation bug",
                minimal=True,
            )
            mismatches.append(cfg.classifier(m) if cfg.classifier else m)

    passed = verdict(cfg.mode, mismatches)
    return VerifyResult(
        seed=cfg.seed,
        mode=cfg.mode,
        cases_tested=len(generated),
        passed=passed,
        mismatches=mismatches,
        cases=generated,
        max_examples=cfg.max_examples,
    )


def _given(strategy, body):
    from hypothesis import given

    return given(strategy)(body)
