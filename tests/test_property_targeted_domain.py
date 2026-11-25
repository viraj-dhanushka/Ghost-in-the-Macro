"""Property 7: Targeted values stay inside the effective domain (PBT).

**Validates: Requirements 1.6, 2.6** (live-fixes-2026-11-24, task 5.3; finding L-07)

Definition used (design.md, Glossary "Effective domain" and Property 7, as changed by the
OWNER DECISION of task 5.4). The effective domain of a numeric input is
``[min, max]`` where ``min`` is the declared ``IOSpec`` min (none: no lower bound, so -1 is
allowed there and not where ``min`` is 0) and ``max`` is the largest of the declared
``IOSpec`` max, ``VerifyConfig.default_max`` (10,000) when there is no declared max, and the
workbook's own sample value. The owner chose this widening over plain clamping: the
scenarios sample has ``gross_income = 60000``, above ``default_max``, and its domain is
therefore 0..60,000. Before this decision the domain was the ``IOSpec`` range with
``default_max`` filled in, and the sample was not part of it. The assertions are unchanged;
only the definition of the domain the helpers compute gained the sample. Every base value
this file generates is inside the domain by construction, so the sample widening does not
change what the property-based tests draw.

My reading of the design, stated because it does not pin everything down:

* "Targeted values" are the values the targeted cases give to the input they vary:
  ``candidate_inputs`` (``ghost/verifier/coverage.py``), the flip cases
  (``ghost/verifier/flip.py``: ``below``, ``above``, ``exact`` and the cases built from
  them) and the mutation check's targeted list, which ``ghost/cli.py`` builds as
  ``candidate_inputs(...) + flip_cases(...)`` and ``ghost/mutation/run.py`` runs.
* The generated base value is always drawn INSIDE the effective domain. The sample-level
  test below asserts the design's statement
  ``survivorDomains(result) ⊆ testedDomainsTable(result)`` and also accepts a clearly
  labelled survivor domain ("mutation cases"). It checks containment, as the design says,
  and not strict equality: the mutation baseline runs its own case count, so equal minima
  and maxima are not promised.
* ``candidate_inputs`` takes the domain as ``domains`` (input name -> (min, max), task 5.4),
  so ``_candidate_inputs`` passes it through that parameter, computed with the base value as
  the sample. ``find_flips`` is called with the raw mapping, exactly as ``ghost/cli.py``
  does.

The strict xfail ``L-07`` markers were removed by task 5.4 (all five tests pass).
Hypothesis runs with an explicit seed. The sample test needs the Referee (real
LibreOffice) and skips when ``soffice`` is not installed.
"""
from __future__ import annotations

import inspect
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, example, given, seed, settings
from hypothesis import strategies as st

from ghost import cli
from ghost.models import IOSpec, Mapping
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.coverage import candidate_inputs
from ghost.verifier.flip import find_flips, flip_cases
from ghost.verifier.run import VerifyConfig

from samples import make_discount, make_haunted, make_scenarios

SEED = 20261204
DEFAULT_MAX = VerifyConfig().default_max  # Decimal(10_000), the effective max when the IOSpec has none
assert DEFAULT_MAX == Decimal(10_000)

# --------------------------------------------------------------------------
# Effective domain
# --------------------------------------------------------------------------
def effective_domain(spec: IOSpec, sample: Any = None) -> tuple[Decimal | None, Decimal]:
    """(min or None for no lower bound, max): the largest of the declared max (or
    ``default_max`` where the spec has none) and the workbook's sample value."""
    hi = spec.max if spec.max is not None else DEFAULT_MAX
    if sample is not None and not isinstance(sample, bool):
        hi = max(hi, sample if isinstance(sample, Decimal) else Decimal(repr(sample)))
    return spec.min, hi


def _inside(value: Any, spec: IOSpec, sample: Any = None) -> bool:
    lo, hi = effective_domain(spec, sample)
    d = value if isinstance(value, Decimal) else Decimal(repr(value))
    return (lo is None or d >= lo) and d <= hi


def _outside(
    case: dict[str, Any], mapping: Mapping, names: list[str] | None = None,
    base: dict[str, Any] | None = None,
) -> list[str]:
    bad = []
    base = base or {}
    for n in names if names is not None else sorted(case):
        spec = mapping.inputs.get(n)
        if spec is None or spec.type not in ("integer", "decimal") or isinstance(case[n], bool):
            continue
        if not _inside(case[n], spec, base.get(n)):
            lo, hi = effective_domain(spec, base.get(n))
            bad.append(f"{n}={case[n]} outside [{lo}, {hi}]")
    return bad


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------
@st.composite
def numeric_specs(draw, index: int) -> IOSpec:
    """Integer or decimal input; min absent, negative, zero or positive; max absent or given."""
    typ = draw(st.sampled_from(["integer", "decimal"]))
    lo = draw(st.sampled_from([None, -50, 0, 5]))
    if lo is None:
        hi = draw(st.sampled_from([None, 100, 5000]))
    else:
        hi = draw(st.sampled_from([None, lo + 100, lo + 5000]))
    return IOSpec(
        cell=f"S!B{index + 1}", type=typ,
        min=None if lo is None else Decimal(lo), max=None if hi is None else Decimal(hi),
    )


@st.composite
def mappings_with_base(draw, max_inputs: int = 2):
    """A mapping of 1..max_inputs numeric inputs and a base value inside each effective domain."""
    n = draw(st.integers(1, max_inputs))
    inputs = {f"x{i}": draw(numeric_specs(i)) for i in range(n)}
    base: dict[str, Any] = {}
    for name, spec in inputs.items():
        lo, hi = effective_domain(spec)
        low = int(lo) if lo is not None else -200
        high = int(min(hi, Decimal(9000)))
        if spec.type == "integer":
            base[name] = draw(st.integers(low, max(low, high)))
        else:
            base[name] = Decimal(draw(st.integers(low * 10, max(low * 10, high * 10)))) / 10
    return Mapping(inputs=inputs), base


constants_st = st.lists(
    st.integers(-60, 12_000).map(Decimal), min_size=0, max_size=3, unique=True
)


# --------------------------------------------------------------------------
# candidate_inputs
# --------------------------------------------------------------------------
def _candidate_inputs(mapping: Mapping, base: dict[str, Any], constants: list[Decimal]):
    params = inspect.signature(candidate_inputs).parameters
    kwargs: dict[str, Any] = {}
    if "mapping" in params:
        kwargs["mapping"] = mapping
    else:
        for key in ("effective_domains", "domains"):
            if key in params:
                kwargs[key] = {n: effective_domain(s, base.get(n)) for n, s in mapping.inputs.items()}
                break
    return list(candidate_inputs(base, constants, **kwargs))


@seed(SEED)
@settings(max_examples=40, deadline=None, derandomize=False, suppress_health_check=list(HealthCheck))
@example(  # the haunted shape: integer, min 0, no max; 0 and -1 are always added today
    mb=(Mapping(inputs={"x0": IOSpec(cell="S!B1", type="integer", min=Decimal(0))}), {"x0": 1}),
    constants=[Decimal(50)],
)
@given(mb=mappings_with_base(max_inputs=3), constants=constants_st)
def test_property_7_candidate_inputs_stay_inside_effective_domain(mb, constants):
    """**Property 7** (``candidate_inputs``): every varied value is inside the effective domain.

    **Validates: Requirements 1.6, 2.6**
    """
    mapping, base = mb
    for case in _candidate_inputs(mapping, base, constants):
        varied = [n for n in case if case[n] != base[n]]
        assert not _outside(case, mapping, varied, base), (case, base, _outside(case, mapping, varied, base))


# --------------------------------------------------------------------------
# Flip cases (below, above, exact hit and small-value retries)
# --------------------------------------------------------------------------
def _module(threshold: Decimal, op: str, two_inputs: bool):
    """A pure-Python stand-in for a transpiled module: ``x0 [*x1] <op> threshold``.

    Honours the trace protocol of ``ghost/converter/emit_python.py``: ``trace(id, truth)``
    and, when ``trace.compared`` is set, ``trace(id, truth, left, right)``.
    """
    def compute(inputs, trace=None):
        left = Decimal(inputs["x0"])
        if two_inputs:
            left = left * Decimal(inputs["x1"])
        truth = left >= threshold if op == ">=" else left > threshold
        if trace is not None:
            if getattr(trace, "compared", False):
                trace("S!B9#1", truth, left, threshold)
            else:
                trace("S!B9#1", truth)
        return {"out": 1 if truth else 0}

    return compute


@seed(SEED)
@settings(max_examples=25, deadline=None, derandomize=False, suppress_health_check=list(HealthCheck))
@example(  # base above 1000: today's search range is max(1000, base * 10), above default_max
    mb=(Mapping(inputs={"x0": IOSpec(cell="S!B1", type="decimal")}), {"x0": Decimal(2000)}),
    threshold=Decimal(50), op=">=",
)
@given(
    mb=mappings_with_base(max_inputs=2),
    threshold=st.integers(1, 3000).map(Decimal),
    op=st.sampled_from([">=", ">"]),
)
def test_property_7_flip_cases_stay_inside_effective_domain(mb, threshold, op):
    """**Property 7** (flips): every below, above, exact-hit and retry case is inside the domain.

    Every numeric value of every case is checked: the generated base is inside the domain,
    so any value outside it was introduced by the search.

    **Validates: Requirements 1.6, 2.6**
    """
    mapping, base = mb
    compute = _module(threshold, op, two_inputs=len(mapping.inputs) == 2)
    flips = find_flips(compute, mapping, dict(base), seed=SEED, literals=[threshold])
    for f in flips:
        for label, v in (("below", f.below), ("above", f.above), ("exact", f.exact)):
            if v is None:
                continue
            spec = mapping.inputs[f.input_name]
            assert _inside(v, spec, base.get(f.input_name)), (f.condition_id, f.input_name, label, v, base)
    for case in flip_cases(flips, mapping):
        assert not _outside(case, mapping, base=base), (case, base, _outside(case, mapping, base=base))


# --------------------------------------------------------------------------
# Samples: survivor reasons against the "Tested domains" table (needs the Referee)
# --------------------------------------------------------------------------
try:
    locate_soffice()
    _SOFFICE_MSG = None
except RefereeUnavailable as exc:
    _SOFFICE_MSG = f"LibreOffice (soffice) not available: {exc}"

_DOMAIN_ITEM = re.compile(r"(\w+): (?:integer|decimal), min (-?[\d.]+), max (-?[\d.]+)")
_CASES = 40
_MUTANT_CASES = 20


def _report_for(module, tmp_path: Path) -> dict:
    xlsx = module.build(tmp_path / "s.xlsx")
    mdir = tmp_path / "m"
    assert cli.main(["convert", str(xlsx), "--migration", str(mdir)]) == 0
    assert cli.main([
        "mutate", str(mdir), "--mode", "faithful", "--seed", str(SEED),
        "--cases", str(_CASES), "--mutant-cases", str(_MUTANT_CASES),
    ]) == 0
    return json.loads((mdir / "reports" / "faithful" / "proof-report.json").read_text("utf-8"))


@pytest.mark.skipif(_SOFFICE_MSG is not None, reason=_SOFFICE_MSG or "")
@pytest.mark.parametrize(
    "module", [make_haunted, make_discount, make_scenarios], ids=["haunted", "discount", "scenarios"]
)
def test_property_7_survivor_domains_match_tested_domains(module, tmp_path):
    """**Property 7** (report): no survivor reason names a value outside the "Tested domains" table.

    Passes when each survivor's min and max per input lie within the table's row, or when
    the reason is labelled as describing "mutation cases" (the design's labelling option).

    **Validates: Requirements 1.6, 2.6**
    """
    report = _report_for(module, tmp_path)
    mutation = report["mutation"]
    assert isinstance(mutation, dict) and mutation.get("mutants"), "mutation check did not run"
    table = {r["input"]: r for r in report["tested_domains"] if "min" in r}
    assert table, "report has no numeric 'Tested domains' rows"
    survivors = [m for m in mutation["mutants"] if not m["killed"]]
    assert survivors, "sample has no survivors; the property would be vacuous"
    problems = []
    for m in survivors:
        reason = m["survivor_reason"]
        if "mutation cases" in reason:
            continue
        for name, lo, hi in _DOMAIN_ITEM.findall(reason):
            row = table.get(name)
            if row is None:
                continue
            if Decimal(lo) < Decimal(row["min"]) or Decimal(hi) > Decimal(row["max"]):
                problems.append(
                    f"{m['mutant_id']} {name}: survivor min {lo} max {hi}, "
                    f"table min {row['min']} max {row['max']}"
                )
    assert not problems, problems[:5]
