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
from ghost.verifier.classify import explaining_decision, verdict
from ghost.verifier.compare import DEFAULT_TOL, case_key, values_equal
from ghost.verifier.domain import DEFAULT_MAX, effective_domains
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
    default_max: Decimal | None = DEFAULT_MAX
    # The workbook's own input values (name -> value). An input whose sample is above its
    # max is generated up to the sample, so the effective domain (ghost.verifier.domain)
    # includes it. Empty: the domain is the declared range plus ``default_max``.
    sample: dict[str, Any] = field(default_factory=dict)
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
    # Transpiled Faithful ``compute`` (no patch) for the Intended-mode three-condition
    # test. When None it is built from the Referee's workbook.
    faithful: Callable[..., dict] | None = None
    # Transpiled Intended ``compute`` (Faithful + the Decision patches). When None it is
    # built from the Referee's workbook and the classifier's Decisions.
    intended: Callable[..., dict] | None = None


@dataclass
class VerifyResult:
    seed: int
    mode: Mode
    cases_tested: int  # generated + targeted, repeats included
    passed: bool
    mismatches: list[Mismatch]
    # Generated inputs in order, up to and including the first failing Case.
    cases: list[dict[str, Any]]
    max_examples: int
    # Intended mode: distinct cases explained by each Decision (decision_id -> count).
    expected_counts: dict[str, int] = field(default_factory=dict)
    # R-28: Hypothesis-generated cases, targeted extra cases, distinct inputs among all.
    cases_generated: int = 0
    cases_targeted: int = 0
    distinct_cases: int = 0
    # Intended mode: why Decisions could not explain any mismatch (else None).
    explain_unavailable: str | None = None


def _build_faithful(
    referee: Any, mapping: Mapping, mode: str = "faithful", decisions: Any = None
) -> Callable[..., dict] | None:
    """Transpile the Referee's workbook (Faithful, or Intended with the Decisions' patches).

    None if the workbook is not fully convertible or a patch cannot be applied."""
    path = getattr(referee, "workbook_path", None)
    if path is None:
        return None
    try:
        from ghost.converter.emit_python import emit_module
        from ghost.ingest.workbook import load_workbook

        res = emit_module(load_workbook(str(path)), mapping, mode, list(decisions or []))
        if res.not_converted:
            return None
        return load_compute(res.code)
    except Exception:  # noqa: BLE001 - unconvertible means "cannot explain"
        return None


def _accepts_trace(fn: Callable[..., dict]) -> bool:
    import inspect

    try:
        return "trace" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


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

    classifier = cfg.classifier
    decisions = list(getattr(classifier, "decisions", []) or [])
    three_cond = (
        cfg.mode == "intended" and bool(decisions) and getattr(classifier, "mode", None) == "intended"
    )
    faithful = None
    if three_cond:
        faithful = cfg.faithful or _build_faithful(referee, mapping)
    intended = None
    if three_cond:
        intended = cfg.intended or _build_faithful(referee, mapping, "intended", decisions)
    can_explain = (
        faithful is not None and intended is not None
        and _accepts_trace(compute) and _accepts_trace(faithful) and _accepts_trace(intended)
    )
    explain_unavailable: str | None = None
    if three_cond and not can_explain:
        if not _accepts_trace(compute):
            explain_unavailable = "module has no trace hook, so Decisions cannot explain mismatches"
        else:
            explain_unavailable = (
                "workbook is not fully convertible, so Decisions cannot explain mismatches"
            )

    def explain(inputs: dict[str, Any], ref: dict[str, Any], got: dict[str, Any]) -> str | None:
        if not can_explain:
            return None
        try:
            ct: dict[str, bool] = {}
            ft: dict[str, bool] = {}
            it: dict[str, bool] = {}
            cand = compute(dict(inputs), lambda h, v: ct.__setitem__(h, v))
            faith = faithful(dict(inputs), lambda h, v: ft.__setitem__(h, v))  # type: ignore[misc]
            inten = intended(dict(inputs), lambda h, v: it.__setitem__(h, v))  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            return None
        return explaining_decision(
            decisions, out_names, ref, cand, ct, faith, ft, cfg.tol, intended=inten, intended_trace=it
        )

    cache: dict[tuple, tuple[dict[str, Any], dict[str, Any], list[str], str | None]] = {}
    generated: list[dict[str, Any]] = []
    state: dict[str, Any] = {"failed": False, "last_fail": None, "done": 0}
    expected: dict[str, dict[tuple, tuple]] = {}

    def evaluate(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str], str | None]:
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
        got_o = {n: got.get(n) for n in out_names}
        by = explain(inputs, ref, got) if (diffs and three_cond) else None
        res = (ref, got_o, diffs, by)
        cache[key] = res
        state["done"] += 1
        if cfg.progress:
            cfg.progress(min(state["done"], cfg.max_examples), cfg.max_examples)
        return res

    def check(inputs: dict[str, Any]) -> None:
        ref, got, diffs, by = evaluate(inputs)
        if not state["failed"]:
            generated.append(dict(inputs))
        if diffs and by:
            # Explained by a Decision: record it and keep generating.
            k = case_key(inputs)
            expected.setdefault(by, {}).setdefault(k, (dict(inputs), ref, got, diffs))
            return
        if diffs:
            state["failed"] = True
            state["last_fail"] = (dict(inputs), ref, got, diffs)
            raise _Failed(f"mismatch on {diffs}")

    targeted = 0
    for extra in cfg.extra_cases:
        try:
            targeted += 1
            check(dict(extra))
        except _Failed:
            break

    overrides = dict(cfg.overrides)
    for n, (_lo, hi) in effective_domains(mapping, cfg.sample, cfg.default_max, cfg.overrides).items():
        spec = overrides.get(n, mapping.inputs[n])
        if hi is not None and spec.max != hi:
            overrides[n] = spec.model_copy(update={"max": hi})
    strat = inputs_strategy(mapping, cfg.thresholds, overrides)

    def run_search(body: Callable[[dict[str, Any]], None]) -> None:
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
        prepared()

    if not state["failed"]:

        def body(inputs: dict[str, Any]) -> None:
            check(inputs)

        try:
            run_search(body)
        except BaseException:  # noqa: BLE001
            if state["last_fail"] is None:
                raise

    # One shrunk example per Decision that explained at least one case.
    shrunk: dict[str, tuple] = {}
    def finder(did: str, found: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
        def body_d(inputs: dict[str, Any]) -> None:
            ref, got, diffs, by = evaluate(inputs)
            if diffs and by == did:
                found["hit"] = (dict(inputs), ref, got, diffs)
                raise _Failed(f"explained by {did}")

        return body_d

    for did in sorted(expected):
        found: dict[str, Any] = {}
        body_d = finder(did, found)
        try:
            run_search(body_d)
        except BaseException:  # noqa: BLE001
            pass
        if "hit" in found:
            shrunk[did] = found["hit"] + (True,)
        else:
            shrunk[did] = next(iter(expected[did].values())) + (False,)

    def case_trace(m: Mismatch) -> dict[str, bool]:
        """Comparison trace to blame the workbook with, or {} (nothing to blame).

        The workbook is blamed only when the transpiled Faithful module itself disagrees
        with the Referee on this case: a Faithful module must reproduce the quirk, so a
        mismatch that the transpiler does not share is a bug in the module under test.
        """
        if "faithful" not in state:
            state["faithful"] = cfg.faithful or _build_faithful(referee, mapping)
        fn = state["faithful"]
        if fn is None or not _accepts_trace(fn):
            return {}
        tr: dict[str, bool] = {}
        try:
            out = fn(dict(m.case.inputs), lambda h, v: tr.__setitem__(h, v))
        except Exception:  # noqa: BLE001
            return {}
        agrees = all(
            n in out and values_equal(m.case.referee.get(n), out[n], cfg.tol) for n in out_names
        )
        return {} if agrees else tr

    use_trace = (
        classifier is not None
        and not three_cond
        and bool(getattr(classifier, "findings", None))
    )

    def _classify(m: Mismatch, by: str | None) -> Mismatch:
        if classifier is None:
            return m
        if three_cond:
            return classifier(m, explained_by=by)  # type: ignore[call-arg]
        if use_trace:
            return classifier(m, trace=case_trace(m))  # type: ignore[call-arg]
        return classifier(m)

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
            mismatches.append(_classify(m, None))
    for did, (inputs, ref, got, diffs, minimal) in shrunk.items():
        for name in diffs:
            m = Mismatch(
                case=Case(inputs=inputs, referee=ref, actual=got),
                output=name,
                cell=out_cells[name],
                mismatch_class="translation bug",
                minimal=minimal,
            )
            m = _classify(m, did)
            if m.mismatch_class == "expected by decision":
                m = m.model_copy(update={"cases": len(expected[did])})
            mismatches.append(m)

    passed = verdict(cfg.mode, mismatches)
    n_targeted = min(targeted, len(generated))
    distinct = {case_key(c) for c in generated}
    return VerifyResult(
        seed=cfg.seed,
        mode=cfg.mode,
        cases_tested=len(generated),
        cases_generated=len(generated) - n_targeted,
        cases_targeted=n_targeted,
        distinct_cases=len(distinct),
        explain_unavailable=explain_unavailable,
        passed=passed,
        mismatches=mismatches,
        cases=generated,
        max_examples=cfg.max_examples,
        expected_counts={d: len(v) for d, v in sorted(expected.items())},
    )


def _given(strategy, body):
    from hypothesis import given

    return given(strategy)(body)
