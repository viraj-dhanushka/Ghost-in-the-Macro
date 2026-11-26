"""Unit tests for web/verdict.py (readable-proof, Part A).

Written before the module exists (test first). Reports are built inside the tests; the haunted
Intended mismatch copies the shape of a real recorded run (quantity 50, Referee 6.0, new code 0).
Validates: Requirements 1 to 6 and 12.8 of .kiro/specs/readable-proof/requirements.md.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from web.verdict import build_verdict, verdict_text

BANNED = re.compile(r"\b(correct|proven|proved|verified)\b", re.I)


def report(**over):
    d = {
        "schema_version": "1", "ghost_version": "0.1.0", "seed": 20261204, "versions": {},
        "mode": "faithful", "cases_tested": 311, "cases_generated": 300, "cases_targeted": 11,
        "distinct_cases": 200, "passed": True, "mismatches": [], "boundaries": [],
        "rule_coverage": [], "mutation": {"status": "not checked"},
        "sanity": {"status": "not cross-checked against Excel", "matched": 0, "total": 0, "differences": []},
        "findings": [], "decisions": [], "boundary_notes": [], "tested_domains": [],
    }
    d.update(over)
    return d


def explained(**over):
    m = {"actual": {"total": "0"}, "cases": 26, "cell": "Calculator!B11", "class": "expected by decision",
         "decision_id": "D-001", "expected": {"total": 6.0}, "finding_id": "F-001",
         "inputs": {"delivery_distance_km": "0", "quantity": 50, "unit_price": "0"},
         "minimal": True, "output": "total", "rule_id": "R-794f519c"}
    m.update(over)
    return m


def bug(**over):
    return explained(**{"class": "translation bug", "decision_id": None, "finding_id": None, "cases": 1,
                        "minimal": False, **over})


def intended_explained(n=1):
    return report(mode="intended", passed=True, mismatches=[explained() for _ in range(n)])


def mutation(killed_flags, **extra):
    mutants = [{"mutant_id": f"M-{i:08x}", "killed": f, **({} if f else {"survivor_reason": f"reason {i}"})}
               for i, f in enumerate(killed_flags)]
    return {"mutants": mutants, "killed": sum(killed_flags), "total": len(killed_flags), **extra}


# -- verdict_text: every state ---------------------------------------------------------------

def test_agreement():
    assert verdict_text(report()) == "Passed: no difference found on 311 cases"


def test_intended_all_explained_names_the_decisions():
    d = report(mode="intended", mismatches=[explained(decision_id="D-002"), explained(decision_id="D-001")])
    assert verdict_text(d) == ("Passed: no unexplained difference found on 311 cases; "
                               "2 expected by decision D-001, D-002")


@pytest.mark.parametrize("mode", ["faithful", "auto", None, "other"])
def test_explained_mismatches_without_mode_intended_are_the_bare_label(mode):
    # Requirement 2.4: the "no unexplained difference" state needs the mode to be exactly intended.
    d = report(mismatches=[explained()])
    if mode is None:
        del d["mode"]
    else:
        d["mode"] = mode
    assert verdict_text(d) == "Passed"


def test_unexplained_mismatch_with_passed_true_is_the_bare_label():
    assert verdict_text(report(mode="intended", mismatches=[bug()])) == "Passed"


def test_not_passed_counts_only_unexplained():
    d = report(passed=False, mode="intended", mismatches=[explained(), bug(), bug()])
    assert verdict_text(d) == "Not passed: 2 difference(s) found"
    assert verdict_text(report(passed=False)) == "Not passed"


@pytest.mark.parametrize("passed", [None, "yes", 1, 0])
def test_passed_missing_or_not_boolean(passed):
    d = report(passed=passed)
    assert verdict_text(d) == "Verdict not available"
    del d["passed"]
    assert verdict_text(d) == "Verdict not available"


@pytest.mark.parametrize("bad", ["x", 3, ["x"], [1], [bug(), "x"]])
def test_uncountable_mismatches_are_the_bare_label(bad):
    assert verdict_text(report(mismatches=bad)) == "Passed"
    assert verdict_text(report(mismatches=bad, passed=False)) == "Not passed"


@pytest.mark.parametrize("n", [None, 0, -3, "311", True, 3.5])
def test_cases_not_a_positive_integer_reads_not_checked(n):
    assert verdict_text(report(cases_tested=n)) == "Passed: no difference found; number of cases: not checked"


# -- headline, flag and state ----------------------------------------------------------------

@pytest.mark.parametrize("d, state, claims", [
    (report(), "agreement", True),
    (intended_explained(), "explained", False),
    (report(passed=False, mismatches=[bug()]), "not_passed", False),
    (report(passed=None), "unavailable", False),
    (report(mismatches=[bug()]), "unsupported", False),
])
def test_headline_flag_and_state(d, state, claims):
    v = build_verdict(d)
    assert v["headline"] == verdict_text(d)
    assert v["state"] == state
    assert v["claims_agreement"] is claims


def test_claims_agreement_needs_passed_true_and_no_mismatches():
    assert build_verdict(report())["claims_agreement"] is True
    assert build_verdict(report(mode="intended"))["claims_agreement"] is True
    assert build_verdict(intended_explained())["claims_agreement"] is False
    assert build_verdict(report(passed=False))["claims_agreement"] is False


def test_headline_numbers_are_in_the_numbers_field():
    v = build_verdict(intended_explained(2))
    assert v["numbers"]["cases_tested"] == 311
    assert v["numbers"]["expected_by_decision"] == 2
    v = build_verdict(report(passed=False, mismatches=[bug(), bug(), explained()], mode="intended"))
    assert v["numbers"]["differences"] == 2


# -- tiles -----------------------------------------------------------------------------------

def test_inputs_tile_counts_and_not_checked():
    t = build_verdict(report())["tiles"]["inputs"]
    assert [t[k]["text"] for k in ("generated", "targeted", "distinct")] == ["300", "11", "200"]
    assert t["distinct"]["value"] == 200
    d = report()
    for k in ("cases_generated", "cases_targeted", "distinct_cases"):
        del d[k]
    t = build_verdict(d)["tiles"]["inputs"]
    assert [t[k]["text"] for k in ("generated", "targeted", "distinct")] == ["not checked"] * 3
    assert t["generated"]["value"] is None


def test_disagreements_tile_counts_each_class():
    d = report(passed=False, mode="intended", mismatches=[bug(), explained(), explained(),
                                                         bug(**{"class": "original workbook inconsistency"})])
    t = build_verdict(d)["tiles"]["disagreements"]
    assert t["total"]["value"] == 4
    assert {c["class"]: c["count"]["value"] for c in t["by_class"]} == {
        "translation bug": 1, "original workbook inconsistency": 1, "expected by decision": 2}
    assert [c["class"] for c in t["by_class"]][:3] == [
        "translation bug", "original workbook inconsistency", "expected by decision"]
    z = build_verdict(report())["tiles"]["disagreements"]
    assert z["total"]["value"] == 0 and all(c["count"]["value"] == 0 for c in z["by_class"])


def test_planted_bugs_k_of_t_with_bar():
    t = build_verdict(report(mutation=mutation([True, True, False])))["tiles"]["planted_bugs"]
    assert t["text"] == "2 of 3"
    assert t["bar"] == {"killed": 2, "total": 3}
    assert t["survivors"] == [{"mutant_id": "M-00000002", "reason": "reason 2"}]


def test_planted_bugs_zero_of_zero_has_no_bar():
    t = build_verdict(report(mutation={"mutants": [], "killed": 0, "total": 0}))["tiles"]["planted_bugs"]
    assert t["text"] == "0 of 0" and t["bar"] is None and t["survivors"] == []


def test_planted_bugs_not_checked_has_no_bar():
    t = build_verdict(report())["tiles"]["planted_bugs"]
    assert t["text"] == "not checked" and t["bar"] is None and t["survivors"] == []
    assert "killed" not in build_verdict(report())["numbers"]


def test_disagreeing_numbers_are_shown_as_recorded():
    m = mutation([True, False])
    m["killed"], m["total"] = 5, 8
    v = build_verdict(report(mutation=m))
    assert v["tiles"]["planted_bugs"]["text"] == "5 of 8"
    assert v["tiles"]["planted_bugs"]["bar"] == {"killed": 5, "total": 8}
    assert len(v["tiles"]["planted_bugs"]["survivors"]) == 1
    assert v["numbers"]["killed"] == 5 and v["numbers"]["total"] == 8 and v["numbers"]["survivors"] == 1


def test_every_survivor_is_listed_with_reason_or_none_recorded():
    m = mutation([False, True, False, False])
    del m["mutants"][2]["survivor_reason"]
    s = build_verdict(report(mutation=m))["tiles"]["planted_bugs"]["survivors"]
    assert [x["mutant_id"] for x in s] == ["M-00000000", "M-00000002", "M-00000003"]
    assert [x["reason"] for x in s] == ["reason 0", "no reason recorded", "reason 3"]


def test_a_record_without_a_killed_flag_is_listed_not_counted_as_killed():
    m = mutation([True, True])
    del m["mutants"][1]["killed"]
    s = build_verdict(report(mutation=m))["tiles"]["planted_bugs"]["survivors"]
    assert [x["mutant_id"] for x in s] == ["M-00000001"]


def test_survivor_explanation_is_shown():
    v = build_verdict(report(mutation=mutation([False], survivor_explanation="no difference found on 3 cases")))
    assert v["tiles"]["planted_bugs"]["explanation"] == "no difference found on 3 cases"
    assert build_verdict(report(mutation=mutation([True])))["tiles"]["planted_bugs"]["explanation"] is None


# -- counterexample --------------------------------------------------------------------------

def test_no_mismatch_no_counterexample():
    assert build_verdict(report())["counterexample"] is None


def test_haunted_intended_counterexample():
    c = build_verdict(intended_explained())["counterexample"]
    assert {"name": "quantity", "value": "50"} in c["inputs"]
    assert c["output"] == "total"
    assert c["workbook_says"] == [{"key": None, "value": "6.0"}]
    assert c["new_code_says"] == [{"key": None, "value": "0"}]
    assert c["class"] == "expected by decision" and c["plain"] == "expected by decision"
    assert c["decision_id"] == "D-001" and c["finding_id"] == "F-001"


def test_counterexample_is_the_minimal_one_else_the_first():
    a, b, c = bug(output="a", minimal=False), bug(output="b", minimal=True), bug(output="c", minimal=True)
    assert build_verdict(report(passed=False, mismatches=[a, b, c]))["counterexample"]["output"] == "b"
    a2, b2 = bug(output="a", minimal=False), bug(output="b", minimal=False)
    assert build_verdict(report(passed=False, mismatches=[a2, b2]))["counterexample"]["output"] == "a"


def test_counterexample_without_a_usable_output_lists_every_differing_entry():
    m = bug(expected={"a": 1, "b": 2, "c": 3}, actual={"a": 1, "b": 9, "c": 3})
    del m["output"]
    c = build_verdict(report(passed=False, mismatches=[m]))["counterexample"]
    assert c["workbook_says"] == [{"key": "b", "value": "2"}]
    assert c["new_code_says"] == [{"key": "b", "value": "9"}]
    assert c["output"] == "Calculator!B11"  # falls back to the cell
    m2 = bug(expected={"total": 6.0}, actual={"other": 1}, output="total")
    c2 = build_verdict(report(passed=False, mismatches=[m2]))["counterexample"]
    assert c2["workbook_says"] == [{"key": "total", "value": "6.0"}]
    assert c2["new_code_says"] == [{"key": "other", "value": "1"}]


def test_counterexample_values_are_copied_as_recorded():
    m = bug(expected={"total": 6.0}, actual={"total": {"a": [1, 2]}}, output="total")
    c = build_verdict(report(passed=False, mismatches=[m]))["counterexample"]
    assert c["workbook_says"][0]["value"] == "6.0"
    assert c["new_code_says"][0]["value"] == '{"a":[1,2]}'


@pytest.mark.parametrize("cls, finding, plain", [
    ("translation bug", None,
     "the new code differs from the workbook, and no Finding or Decision accounts for it"),
    ("original workbook inconsistency", "F-002",
     "the new code differs from the workbook where the workbook's own formulas disagree (Finding F-002)"),
    ("original workbook inconsistency", None,
     "the new code differs from the workbook where the workbook's own formulas disagree"),
    ("expected by decision", "F-001", "expected by decision"),
])
def test_plain_words_for_each_class(cls, finding, plain):
    c = build_verdict(report(passed=False, mismatches=[bug(**{"class": cls, "finding_id": finding})]))["counterexample"]
    assert c["class"] == cls and c["plain"] == plain


def test_unknown_class_has_no_plain_words():
    c = build_verdict(report(passed=False, mismatches=[bug(**{"class": "something new"})]))["counterexample"]
    assert c["class"] == "something new" and c["plain"] is None


# -- not proven strip ------------------------------------------------------------------------

def test_not_proven_lists_notes_domains_rules_and_not_converted():
    d = report(
        boundary_notes=["no flip found for B7#1", "second note"],
        tested_domains=[{"input": "quantity", "type": "integer"},
                        {"input": "unit_price", "type": "decimal", "not_tested": True},
                        {"input": "delivery", "type": "decimal", "not_tested": False}],
        rule_coverage=[{"rule_id": "R-1", "condition_id": "R-1-C1", "seen_true": True, "seen_false": True},
                       {"rule_id": "R-2", "condition_id": "R-2-C1", "seen_true": True, "seen_false": False},
                       {"rule_id": "R-3", "condition_id": "R-3-C1", "seen_true": False, "seen_false": True},
                       {"rule_id": "R-4", "condition_id": "R-4-C1", "seen_true": False, "seen_false": False}],
        not_converted=[{"cell": "Calc!C4", "reason": "VBA call"}, {"cell": "Calc!C5", "reason": ""}],
    )
    n = build_verdict(d)["not_proven"]
    assert n["boundary_notes"] == ["no flip found for B7#1", "second note"]
    assert n["domains_not_tested"] == ["unit_price"]
    assert n["rules_not_seen"] == [
        {"rule_id": "R-2", "condition_id": "R-2-C1", "side": "false"},
        {"rule_id": "R-3", "condition_id": "R-3-C1", "side": "true"},
        {"rule_id": "R-4", "condition_id": "R-4-C1", "side": "true and false"}]
    assert n["not_converted"] == [{"cell": "Calc!C4", "reason": "VBA call"},
                                  {"cell": "Calc!C5", "reason": "no reason recorded"}]
    v = build_verdict(d)["numbers"]
    assert v["boundary_notes"] == 2 and v["domains_not_tested"] == 1 and v["not_converted"] == 2


@pytest.mark.parametrize("sanity, sentence", [
    ({"status": "not cross-checked against Excel"}, "Not cross-checked against Excel."),
    ({"status": "matched", "matched": 3, "total": 3}, "Excel cross-check: matched."),
    ({"status": "differences"}, "Excel cross-check: differences."),
    ({"status": "not checked"}, "Excel cross-check: not checked."),
    (None, "Excel cross-check: not checked."),
])
def test_excel_sentence(sanity, sentence):
    d = report()
    if sanity is None:
        del d["sanity"]
    else:
        d["sanity"] = sanity
    assert build_verdict(d)["not_proven"]["excel"] == sentence


def test_excel_phrase_does_not_double():
    s = build_verdict(report())["not_proven"]["excel"]
    assert s.count("Excel") == 1 and "Excel cross-check:" not in s


# -- reproduce line and glossary -------------------------------------------------------------

def test_reproduce_line_has_no_cases_and_a_fixed_caption():
    r = build_verdict(report())["reproduce"]
    assert r["command"] == "python -m ghost.cli verify <migration-dir> --mode faithful --seed 20261204"
    assert "--cases" not in r["command"]
    assert r["caption"] == "Run from the migration folder; add --mutation-cases to repeat the planted-bug check."


def test_reproduce_line_with_missing_mode_or_seed():
    d = report()
    del d["mode"]
    d["seed"] = True
    assert build_verdict(d)["reproduce"]["command"] == (
        "python -m ghost.cli verify <migration-dir> --mode not checked --seed not checked")


def test_reproduce_line_has_no_server_path_or_ids():
    d = report(versions={"python": "3.13"}, ghost_version="0.1.0")
    cmd = build_verdict(d)["reproduce"]["command"]
    assert "/" not in cmd.replace("<migration-dir>", "") and "job" not in cmd.lower() and "session" not in cmd.lower()


def test_glossary_has_the_four_terms_and_no_correctness_claim():
    g = build_verdict(report())["glossary"]
    assert [x["term"] for x in g] == ["Referee", "Mutant", "Faithful", "Intended"]
    assert all(x["text"].strip() for x in g)
    assert not any(BANNED.search(x["text"]) for x in g)


# -- purity and robustness -------------------------------------------------------------------

def test_module_imports_only_the_standard_library_and_nothing_with_io():
    src = Path(__file__).resolve().parent.parent / "web" / "verdict.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    forbidden = {"ghost", "fastapi", "starlette", "jinja2", "os", "sys", "time", "datetime", "random",
                 "pathlib", "subprocess", "socket", "urllib", "threading", "asyncio", "io", "shutil",
                 "tempfile", "web"}
    assert not names & forbidden, names & forbidden


JUNK = [
    {}, {"passed": None}, {k: None for k in report()},
    report(mismatches="x", mutation=5, tested_domains=3, boundary_notes="abc", sanity=[], seed=True,
           rule_coverage={"a": 1}, not_converted="x", cases_generated="300", mode=7),
    report(mismatches=[None, 3, {"inputs": 5, "expected": "x", "actual": None, "class": 9}]),
    report(mutation={"mutants": "x", "killed": "a", "total": None}),
    report(mutation={"mutants": [None, 3, {"killed": False}], "killed": 1, "total": 3}),
    report(rule_coverage=[None, {"rule_id": 1}], tested_domains=[None, {"not_tested": True}],
           not_converted=[None, {"cell": 5}]),
]


@pytest.mark.parametrize("d", JUNK)
def test_missing_or_mistyped_fields_never_raise(d):
    v = build_verdict(d)
    assert isinstance(v, dict) and isinstance(v["headline"], str) and isinstance(v["numbers"], dict)
    assert all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in v["numbers"].values())


def test_empty_report_reads_verdict_not_available():
    v = build_verdict({})
    assert v["headline"] == "Verdict not available" and v["claims_agreement"] is False
    assert v["state"] == "unavailable" and v["counterexample"] is None


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


@pytest.mark.parametrize("d", [
    report(), intended_explained(), report(passed=False, mismatches=[bug()]), report(passed=None),
    report(mismatches=[bug()]), report(mutation=mutation([True, False])), {},
])
def test_no_banned_word_in_any_string_the_card_produces(d):
    assert not [s for s in _strings(build_verdict(d)) if BANNED.search(s)]


# -- optional criteria (Requirements 4.5 and 5.6) ----------------------------------------------

@pytest.mark.parametrize("cases, expected", [(26, 26), (2, 2), (1, None), (0, None)])
def test_counterexample_says_how_many_generated_cases_it_stands_for(cases, expected):
    v = build_verdict(report(passed=False, mismatches=[bug(cases=cases)]))
    assert v["counterexample"]["cases"] == expected
    assert v["numbers"].get("counterexample_cases") == expected


def test_counterexample_without_a_cases_field_has_no_cases_line():
    m = bug()
    del m["cases"]
    v = build_verdict(report(passed=False, mismatches=[m]))
    assert v["counterexample"]["cases"] is None and "counterexample_cases" not in v["numbers"]


def test_empty_lists_of_the_strip_say_so_in_words():
    e = build_verdict(report())["not_proven"]["empty"]
    assert e == {
        "boundary_notes": "The report lists no boundary notes.",
        "domains_not_tested": "The report marks no input range as not tested.",
        "rules_not_seen": "The report lists no rule condition as unseen on either side.",
        "not_converted": "The report lists no cell as not converted.",
    }


def test_a_list_with_entries_has_no_none_sentence():
    d = report(boundary_notes=["a note"], not_converted=[{"cell": "C4", "reason": "x"}])
    e = build_verdict(d)["not_proven"]["empty"]
    assert "boundary_notes" not in e and "not_converted" not in e
    assert "domains_not_tested" in e and "rules_not_seen" in e


# -- Skeptic review corrections (readable-proof task 14) ---------------------------------------

@pytest.mark.parametrize("missing", ["absent", None, {}, 0, False])
def test_only_an_empty_list_means_no_mismatches(missing):
    d = report()
    if missing == "absent":
        del d["mismatches"]
    else:
        d["mismatches"] = missing
    v = build_verdict(d)
    assert v["headline"] == "Passed" and v["claims_agreement"] is False and v["state"] == "unsupported"
    assert build_verdict({**d, "passed": False})["headline"] == "Not passed"


@pytest.mark.parametrize("cls", [["x"], {"a": 1}, None, 3])
def test_a_class_that_cannot_be_hashed_or_is_not_text_never_raises(cls):
    v = build_verdict(report(passed=False, mismatches=[bug(**{"class": cls})]))
    assert isinstance(v["headline"], str)


def test_reproduce_mode_is_only_faithful_or_intended():
    for mode, shown in (("faithful", "faithful"), ("intended", "intended"), ("auto", "not checked"), ("", "not checked")):
        assert f"--mode {shown} " in build_verdict(report(mode=mode))["reproduce"]["command"]


def test_glossary_does_not_state_an_outcome_for_faithful():
    text = {g["term"]: g["text"] for g in build_verdict(report())["glossary"]}
    assert "Aims to reproduce" in text["Faithful"] and "passes only when no difference is found" in text["Faithful"]
    assert "planted bug" in text["Mutant"]
