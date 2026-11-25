"""Property 3: Excel errors serialise as their text (PBT).

**Validates: Requirements 2.1, 3.12** (live-fixes-2026-11-24, task 3.1; finding L-02)

For any proof report whose mismatch inputs, expected and actual values, mutant
counterexamples (``killed_by``) or boundary cases (``exact_hits``) contain
``ExcelError`` values of any code, mixed with Decimals, strings, booleans and
``None``, ``report_to_json`` succeeds, the result validates against
``proof-report-1.json``, each ``ExcelError`` appears as its ``code`` text at the
place it was held, the HTML report shows the same text in the matching section,
and two calls on the same report give identical bytes.

Errors come from two classes: ``ghost.runtime.excel.ExcelError`` and the
``ExcelError`` of a vendored copy of ``excel.py`` loaded as a separate module.
Generated modules import the sibling ``excel.py`` first (``ghost/cli.py`` copies
it next to ``logic.py``), so the engine can hand the report either class.

Was strict xfail until task 3.2 fixed L-02; the marker is now removed.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Any

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

import ghost.runtime.excel as runtime_excel
from ghost.models import BoundaryResult, Case, Mismatch, Mutant, MutationResult
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_json, validate_report_dict

CODES = ("#DIV/0!", "#VALUE!", "#REF!", "#N/A", "#NUM!", "#NAME?", "#NULL!")
CLASSES = ("translation bug", "original workbook inconsistency", "expected by decision")


@pytest.fixture(scope="module")
def vendored_excel(tmp_path_factory):
    """A vendored copy of excel.py, loaded as its own module (as a generated module does)."""
    folder = tmp_path_factory.mktemp("vendored")
    path = folder / "excel.py"
    shutil.copyfile(runtime_excel.__file__, path)  # same copy step as ghost/cli.py
    name = "ghost_test_vendored_excel"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        assert module.ExcelError is not runtime_excel.ExcelError
        yield module
    finally:
        sys.modules.pop(name, None)


# --------------------------------------------------------------------------
# Strategies: value trees with error markers, materialised inside the test
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Err:
    """Marker for an Excel error; ``origin`` picks the runtime or the vendored class."""

    code: str
    origin: str


errors = st.builds(Err, st.sampled_from(CODES), st.sampled_from(("runtime", "vendored")))
# No '#' in text, so an error code in the output can only come from an ExcelError.
text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ABC0123456789.-", max_size=8)
decimals = st.decimals(min_value=-10**6, max_value=10**6, places=4, allow_nan=False, allow_infinity=False)
scalars = st.one_of(decimals, text, st.booleans(), st.none())
values = st.one_of(errors, scalars)
names = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)


def _dict_with_error(min_size: int = 0):
    """An engine value dict that holds at least one error."""
    return st.tuples(st.dictionaries(names, values, min_size=min_size, max_size=4), names, errors).map(
        lambda t: {**t[0], t[1]: t[2]}
    )


mismatch_specs = st.fixed_dictionaries({
    "inputs": st.dictionaries(names, values, min_size=1, max_size=4),
    "expected": st.dictionaries(names, values, min_size=1, max_size=3),
    "actual": _dict_with_error(),
    "class": st.sampled_from(CLASSES),
})
killed_by_specs = st.fixed_dictionaries({
    "inputs": st.dictionaries(names, values, min_size=1, max_size=4),
    "referee": st.dictionaries(names, values, max_size=3),
    "actual": _dict_with_error(),
})
mutant_specs = st.one_of(killed_by_specs, st.none())  # None: the mutant survived
bracket = st.fixed_dictionaries({"last_unchanged": values, "first_changed": values})
hit = st.fixed_dictionaries({"inputs": _dict_with_error(), "output": st.just("Calc!B5"), "value": values})
boundary_specs = st.lists(st.one_of(bracket, hit), min_size=1, max_size=3).flatmap(
    lambda hits: st.tuples(st.just(hits), errors).map(
        # Make sure each boundary carries at least one error, in a bracket value.
        lambda t: t[0] + [{"last_unchanged": t[1], "first_changed": Decimal("50")}]
    )
)
report_specs = st.fixed_dictionaries({
    "mode": st.sampled_from(("faithful", "intended")),
    "mismatches": st.lists(mismatch_specs, min_size=1, max_size=3),
    "killed": st.lists(killed_by_specs, min_size=1, max_size=2),
    "other_mutants": st.lists(mutant_specs, max_size=2),
    "boundaries": st.lists(boundary_specs, min_size=1, max_size=2),
})


def _materialise(tree: Any, excel_modules: dict[str, Any]) -> Any:
    """Replace each Err marker with an ExcelError of the chosen class."""
    if isinstance(tree, Err):
        return excel_modules[tree.origin].ExcelError(tree.code)
    if isinstance(tree, dict):
        return {k: _materialise(v, excel_modules) for k, v in tree.items()}
    if isinstance(tree, list):
        return [_materialise(v, excel_modules) for v in tree]
    return tree


def _expected_json(tree: Any) -> Any:
    """JSON form the report must hold: errors as code text, Decimals as strings."""
    if isinstance(tree, Err):
        return tree.code
    if isinstance(tree, Decimal):
        return str(tree)
    if isinstance(tree, dict):
        return {k: _expected_json(v) for k, v in tree.items()}
    if isinstance(tree, list):
        return [_expected_json(v) for v in tree]
    return tree


def _codes(tree: Any) -> set[str]:
    if isinstance(tree, Err):
        return {tree.code}
    if isinstance(tree, dict):
        return set().union(*(_codes(v) for v in tree.values())) if tree else set()
    if isinstance(tree, list):
        return set().union(*(_codes(v) for v in tree)) if tree else set()
    return set()


def _html_section(page: str, title: str) -> str:
    start = page.index(f"<h2>{escape(title)}</h2>")
    return page[start:page.index("</section>", start)]


# --------------------------------------------------------------------------
# Property 3
# --------------------------------------------------------------------------


@seed(20261124)
@settings(max_examples=60, deadline=None, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(spec=report_specs)
def test_property_3_excel_errors_serialise_as_text(vendored_excel, spec):
    """Property 3: Excel errors serialise as their text.

    **Validates: Requirements 2.1, 3.12**
    """
    mods = {"runtime": runtime_excel, "vendored": vendored_excel}

    mismatches = [
        Mismatch(
            case=Case(
                inputs=_materialise(m["inputs"], mods),
                referee=_materialise(m["expected"], mods),
                actual=_materialise(m["actual"], mods),
            ),
            output="out", cell=f"Calc!B{i + 2}", mismatch_class=m["class"], minimal=i == 0,
        )
        for i, m in enumerate(spec["mismatches"])
    ]
    mutant_cases = spec["killed"] + spec["other_mutants"]
    mutants = [
        Mutant(
            mutant_id=f"M-{i:08x}", operator="constant_plus_one", location=f"Calc!C{i + 2}",
            killed=k is not None,
            killed_by=None if k is None else Case(
                inputs=_materialise(k["inputs"], mods),
                referee=_materialise(k["referee"], mods),
                actual=_materialise(k["actual"], mods),
            ),
            survivor_reason=None if k is not None else "no difference found on 3 distinct cases",
        )
        for i, k in enumerate(mutant_cases)
    ]
    boundaries = [
        BoundaryResult(cell="Calc!B5", input_name="quantity", threshold=Decimal("50"),
                       exact_hits=_materialise(hits, mods))
        for hits in spec["boundaries"]
    ]
    report = build_report(
        seed=20261204, mode=spec["mode"], cases_tested=len(mismatches), passed=False,
        mismatches=mismatches, boundaries=boundaries,
        mutation=MutationResult(mutants=mutants, killed=sum(m.killed for m in mutants), total=len(mutants)),
        libreoffice_version="test",
    )

    # report_to_json succeeds, is deterministic and validates against the schema.
    text_1 = report_to_json(report)
    text_2 = report_to_json(report)
    assert text_1.encode("utf-8") == text_2.encode("utf-8")
    data = json.loads(text_1)
    validate_report_dict(data)
    assert "ExcelError(" not in text_1

    # Each error appears as its code text, at the place it was held.
    for got, m in zip(data["mismatches"], spec["mismatches"]):
        assert got["inputs"] == _expected_json(m["inputs"])
        assert got["expected"] == _expected_json(m["expected"])
        assert got["actual"] == _expected_json(m["actual"])
    for got, k in zip(data["mutation"]["mutants"], mutant_cases):
        if k is None:
            assert got["killed_by"] is None
        else:
            assert got["killed_by"] == {
                "inputs": _expected_json(k["inputs"]),
                "referee": _expected_json(k["referee"]),
                "actual": _expected_json(k["actual"]),
            }
    for got, hits in zip(data["boundaries"], spec["boundaries"]):
        assert got["exact_hits"] == _expected_json(hits)

    # The HTML report shows the same text, in the matching section, deterministically.
    page = render_html(report)
    assert render_html(report) == page
    assert "ExcelError(" not in page
    sections = {
        "Mismatches": _codes(spec["mismatches"]),
        "Mutation self-check": _codes([k for k in mutant_cases if k is not None]),
        "Boundaries": _codes(spec["boundaries"]),
    }
    for title, codes in sections.items():
        shown = _html_section(page, title)
        for code in codes:
            assert escape(code, quote=True) in shown, (title, code)
