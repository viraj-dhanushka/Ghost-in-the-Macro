"""Property tests for web/verdict.py (readable-proof, Properties 1 to 5; Property 6 is added with the
optional tasks). Hypothesis, explicit seed 20261204, over generated schema-valid Proof_Reports.
Each test checks the dict that build_verdict returns, not text scraped from HTML.
"""
from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, seed, settings, strategies as st
from jsonschema import Draft202012Validator

from web.verdict import build_verdict

SEED = 20261204
SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "ghost" / "report" / "schema"
                     / "proof-report-1.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

CLASSES = ["translation bug", "original workbook inconsistency", "expected by decision"]
_ids = st.sampled_from(["D-001", "D-002", "F-001", "F-002", "R-aaaa0001", "M-0000000a", "M-0000000b"])
_text = st.text(alphabet="abcXYZ 0123-_.:", max_size=14)
_scalar = st.one_of(st.integers(-5, 600), st.floats(-5, 600, allow_nan=False, allow_infinity=False), _text)
_values = st.dictionaries(st.sampled_from(["quantity", "unit_price", "delivery_distance_km", "total"]),
                          _scalar, max_size=3)


@st.composite
def _mismatch(draw):
    m = {"inputs": draw(_values), "expected": draw(_values), "actual": draw(_values),
         "class": draw(st.sampled_from(CLASSES))}
    for key, strat in (("output", st.sampled_from(["total", "net", "nope"])), ("cell", _text),
                       ("rule_id", st.one_of(st.none(), _ids)), ("finding_id", st.one_of(st.none(), _ids)),
                       ("decision_id", st.one_of(st.none(), _ids)), ("minimal", st.booleans()),
                       ("cases", st.integers(1, 40))):
        if draw(st.booleans()):
            m[key] = draw(strat)
    return m


@st.composite
def _mutation(draw):
    if draw(st.booleans()):
        return {"status": "not checked"}
    flags = draw(st.lists(st.booleans(), max_size=8))
    mutants = []
    for i, f in enumerate(flags):
        rec = {"mutant_id": f"M-{i:08x}", "killed": f}
        if not f and draw(st.booleans()):
            rec["survivor_reason"] = draw(_text)
        mutants.append(rec)
    block = {"mutants": mutants, "killed": sum(flags), "total": len(flags)}
    if draw(st.integers(0, 4)) == 0:  # the schema does not tie the numbers to the list
        block["killed"], block["total"] = draw(st.integers(0, 12)), draw(st.integers(0, 12))
    if draw(st.booleans()):
        block["survivor_explanation"] = draw(_text)
    return block


@st.composite
def reports(draw):
    d = {
        "schema_version": "1", "ghost_version": "0.1.0", "seed": draw(st.integers(0, 10**9)),
        "versions": {"libreoffice": "LO", "python": "3", "ghost": "0.1.0"},
        "mode": draw(st.sampled_from(["faithful", "intended"])),
        "cases_tested": draw(st.integers(0, 600)), "passed": draw(st.booleans()),
        "mismatches": draw(st.lists(_mismatch(), max_size=4)),
        "boundaries": [], "findings": [], "decisions": [],
        "rule_coverage": draw(st.lists(st.fixed_dictionaries({
            "rule_id": _ids, "condition_id": _ids, "seen_true": st.booleans(), "seen_false": st.booleans()}),
            max_size=4)),
        "mutation": draw(_mutation()),
        "sanity": draw(st.one_of(
            st.just({"status": "not checked"}),
            st.fixed_dictionaries({"status": st.sampled_from(
                ["matched", "differences", "not cross-checked against Excel"]),
                "matched": st.integers(0, 5), "total": st.integers(0, 5), "differences": st.just([])}))),
    }
    for key, strat in (("cases_generated", st.integers(0, 600)), ("cases_targeted", st.integers(0, 60)),
                       ("distinct_cases", st.integers(0, 600)),
                       ("boundary_notes", st.lists(_text, max_size=3)),
                       ("not_converted", st.lists(st.fixed_dictionaries({"cell": _text, "reason": _text}), max_size=3)),
                       ("tested_domains", st.lists(st.fixed_dictionaries({"input": _text, "type": _text}, optional={
                           "not_tested": st.booleans(), "distinct_values": st.integers(0, 50)}), max_size=3))):
        if draw(st.booleans()):
            d[key] = draw(strat)
    return d


_SETTINGS = dict(max_examples=200, deadline=None, derandomize=False)


@seed(SEED)
@settings(max_examples=100, deadline=None, derandomize=False)
@given(reports())
def test_every_generated_report_is_schema_valid(report):
    assert not list(VALIDATOR.iter_errors(report))


# Feature: readable-proof, Property 1: The Headline claims agreement only for a passed report with no mismatches
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_1_claims_agreement_only_for_passed_and_no_mismatches(report):
    """**Validates: Requirements 2.2, 2.3, 13.2**"""
    v = build_verdict(report)
    holds = report["passed"] is True and report["mismatches"] == []
    assert v["claims_agreement"] is holds
    if holds:
        assert v["headline"].startswith("Passed: no difference found")
    else:
        assert not v["headline"].startswith("Passed: no difference found")


_MISSING = object()


def allowed_numbers(report: dict) -> set[int]:
    """Numbers Requirement 12.5 allows, computed from the report alone."""
    ok = {0}
    for key in ("cases_tested", "cases_generated", "cases_targeted", "distinct_cases"):
        if isinstance(report.get(key), int):
            ok.add(report[key])
    mut = report.get("mutation") or {}
    for key in ("killed", "total"):
        if isinstance(mut.get(key), int):
            ok.add(mut[key])
    arrays = [v for v in report.values() if isinstance(v, list)]
    if isinstance(mut.get("mutants"), list):
        arrays.append(mut["mutants"])
    for arr in arrays:
        ok.add(len(arr))
        records = [e for e in arr if isinstance(e, dict)]
        for e in records:
            for key in ("cases", "distinct_values"):
                if isinstance(e.get(key), int):
                    ok.add(e[key])
        for key in {k for e in records for k in e}:
            vals = [e.get(key, _MISSING) for e in records]
            for v in {x for x in vals if isinstance(x, (str, int, float, bool, type(None)))}:
                same = sum(1 for x in vals if x == v and type(x) is type(v))
                ok |= {same, len(arr) - same}
    return ok


# Feature: readable-proof, Property 2: Every number is traceable
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_2_every_number_is_traceable(report):
    """**Validates: Requirements 1.7, 12.5, 13.3**"""
    v = build_verdict(report)
    stray = {k: n for k, n in v["numbers"].items() if n not in allowed_numbers(report)}
    assert not stray, stray


# Feature: readable-proof, Property 3: A mutation block that was not run reads "not checked"
@seed(SEED)
@settings(**_SETTINGS)
@given(reports().map(lambda d: {**d, "mutation": {"status": "not checked"}}))
def test_property_3_mutation_not_run_reads_not_checked(report):
    """**Validates: Requirements 3.5, 13.4**"""
    tile = build_verdict(report)["tiles"]["planted_bugs"]
    assert tile["text"] == "not checked" and tile["bar"] is None and tile["survivors"] == []


# Feature: readable-proof, Property 4: No surviving mutant is hidden
@seed(SEED)
@settings(**_SETTINGS)
@given(reports().filter(lambda d: "mutants" in d["mutation"]))
def test_property_4_every_surviving_mutant_is_listed(report):
    """**Validates: Requirements 3.7, 13.5**"""
    listed = build_verdict(report)["tiles"]["planted_bugs"]["survivors"]
    survivors = [m["mutant_id"] for m in report["mutation"]["mutants"] if m["killed"] is not True]
    assert [s["mutant_id"] for s in listed] == survivors
    assert all(s["reason"] for s in listed)


# Feature: readable-proof, Property 5: "Excel" never appears in a sentence that claims agreement unless the cross-check matched
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_5_excel_only_with_a_matched_cross_check(report):
    """**Validates: Requirements 5.7, 13.6**"""
    v = build_verdict(report)
    if v["claims_agreement"] and report["sanity"].get("status") != "matched":
        assert "Excel" not in v["headline"]


# Feature: readable-proof, Property 6: build_verdict is deterministic and does not modify its argument
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_6_deterministic_and_does_not_modify_its_argument(report):
    """**Validates: Requirements 1.3, 1.4, 13.7**"""
    import copy
    before = copy.deepcopy(report)
    first = build_verdict(report)
    assert report == before
    assert build_verdict(report) == first


# Feature: readable-proof, Property 2 (named): each number equals its definition, not just some allowed value
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_2_named_numbers_equal_their_definition(report):
    """**Validates: Requirements 1.7, 12.5**"""
    n = build_verdict(report)["numbers"]
    ms = report["mismatches"]
    explained = sum(1 for m in ms if m["class"] == "expected by decision")
    assert n["mismatches"] == len(ms) and n["expected_by_decision"] == explained
    assert n["differences"] == len(ms) - explained
    for cls in ("translation bug", "original workbook inconsistency", "expected by decision"):
        assert n["mismatches_" + cls.replace(" ", "_")] == sum(1 for m in ms if m["class"] == cls)
    if report["cases_tested"] > 0:
        assert n["cases_tested"] == report["cases_tested"]
    for key in ("cases_generated", "cases_targeted", "distinct_cases"):
        assert (n.get(key) == report[key]) if key in report else (key not in n)
    mut = report["mutation"]
    if "total" in mut:
        assert (n["killed"], n["total"]) == (mut["killed"], mut["total"])
        assert n["survivors"] == sum(1 for m in mut["mutants"] if m["killed"] is not True)
    else:
        assert "killed" not in n and "total" not in n
    assert n["boundary_notes"] == len(report.get("boundary_notes", []))
    assert n["not_converted"] == len(report.get("not_converted", []))
    assert n["domains_not_tested"] == sum(1 for r in report.get("tested_domains", []) if r.get("not_tested") is True)


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _strings(v)


# Feature: readable-proof, Property 5 (strengthened): "Excel" appears only in the cross-check sentence, which follows sanity.status
@seed(SEED)
@settings(**_SETTINGS)
@given(reports())
def test_property_5_excel_only_in_the_cross_check_sentence(report):
    """**Validates: Requirements 5.1, 5.5, 5.7, 13.6**"""
    v = build_verdict(report)
    status = report["sanity"].get("status")
    expected = ("Not cross-checked against Excel." if status == "not cross-checked against Excel"
                else f"Excel cross-check: {status}.")
    assert v["not_proven"]["excel"] == expected
    outside = {**v, "not_proven": {k: x for k, x in v["not_proven"].items() if k != "excel"}}
    assert not [s for s in _strings(outside) if "Excel" in s]
    if status == "not cross-checked against Excel":
        assert v["not_proven"]["excel"].count("Excel") == 1


# Feature: readable-proof, Property 4 (strengthened): each survivor carries its recorded reason
@seed(SEED)
@settings(**_SETTINGS)
@given(reports().filter(lambda d: "mutants" in d["mutation"]))
def test_property_4_survivor_reasons_are_the_recorded_ones(report):
    """**Validates: Requirements 3.7, 3.8**"""
    listed = build_verdict(report)["tiles"]["planted_bugs"]["survivors"]
    survivors = [m for m in report["mutation"]["mutants"] if m["killed"] is not True]
    assert [s["reason"] for s in listed] == [
        m["survivor_reason"] if m.get("survivor_reason", "").strip() else "no reason recorded" for m in survivors]
