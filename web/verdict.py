"""Verdict_Module: the Verdict_Card's content, built from a parsed Proof_Report and nothing else.

Pure: standard library only, no file, network or process I/O, no clock, no random source, no
import of the Referee, the verifier or the web framework. Nothing is added to the report and the
argument is never modified. A field that is missing or has the wrong type reads "not checked"
and never raises. See .kiro/specs/readable-proof/design.md.
"""
from __future__ import annotations

import json
import re
from typing import Any

NOT_CHECKED = "not checked"
NO_REASON = "no reason recorded"
EXPLAINED = "expected by decision"
CLASSES = ("translation bug", "original workbook inconsistency", EXPLAINED)
CAPTION = "Run from the migration folder; add --mutation-cases to repeat the planted-bug check."
STOP_NOTE = "The run stops at the first unexplained difference, so later cases were not tried."

_PLAIN = {
    "translation bug": "the new code differs from the workbook, and no Finding or Decision accounts for it",
    "original workbook inconsistency":
        "the new code differs from the workbook where the workbook's own formulas disagree",
    EXPLAINED: EXPLAINED,
}
_GLOSSARY = [
    ("Referee", "The original workbook, recalculated by headless LibreOffice. Its results are what "
                "the new code is compared with."),
    ("Mutant", "A deliberately broken copy of the new code (a planted bug). A mutant is killed when the "
               "comparison finds the difference it causes; a survivor is one the comparison did not catch."),
    ("Faithful", "Aims to reproduce the workbook exactly, quirks included. A Faithful run passes only "
                 "when no difference is found."),
    ("Intended", "Applies the recorded Decisions. A difference that a Decision expects is listed "
                 "as expected by decision and does not fail the run."),
]
_MISSING = object()


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _count(x: Any) -> bool:
    return _is_int(x) and x >= 0


def _show(v: Any) -> str:
    """A recorded value as text: strings as they are, everything else as compact JSON (6.0 stays 6.0)."""
    if isinstance(v, str):
        return v
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False, default=str)


def _item(label: str, v: Any) -> dict:
    ok = _count(v)
    return {"label": label, "value": v if ok else None, "text": str(v) if ok else NOT_CHECKED}


def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower() or "other"


def _mismatches(d: dict) -> list[dict] | None:
    """The mismatch objects ([] only for an empty list), or None when the list is missing or cannot be
    counted. A report without a countable list never claims that there is no difference."""
    raw = d.get("mismatches")
    if isinstance(raw, list) and all(isinstance(m, dict) for m in raw):
        return raw
    return None


def _headline(d: dict) -> tuple[str, str, bool]:
    """(text, state, claims_agreement). The one place the sentence is decided (Requirement 2)."""
    passed = d.get("passed")
    if not isinstance(passed, bool):
        return "Verdict not available", "unavailable", False
    ms = _mismatches(d)
    if ms is None:  # a list the sentence cannot count is never read as "no mismatches"
        return ("Passed", "unsupported", False) if passed else ("Not passed", "not_passed", False)
    n = d.get("cases_tested")
    where = f" on {n} cases" if _is_int(n) and n > 0 else "; number of cases: not checked"
    explained = [m for m in ms if m.get("class") == EXPLAINED]
    unexplained = len(ms) - len(explained)
    if passed:
        if not ms:
            return f"Passed: no difference found{where}", "agreement", True
        if unexplained or d.get("mode") != "intended":
            return "Passed", "unsupported", False
        ids = sorted({str(m["decision_id"]) for m in explained if m.get("decision_id")})
        tail = f"{len(explained)} expected by decision" + (f" {', '.join(ids)}" if ids else "")
        return f"Passed: no unexplained difference found{where}; {tail}", "explained", False
    text = f"Not passed: {unexplained} difference(s) found" if unexplained else "Not passed"
    return text, "not_passed", False


def verdict_text(d: dict) -> str:
    """The label ("Passed" / "Not passed") plus one sentence built only from the proof report.
    N is ``cases_tested``; K and the Decision ids come from ``mismatches``. A report that
    contradicts itself gets the bare label, never a claim the report does not support; a report
    with no ``passed`` field reads "Verdict not available"."""
    return _headline(d)[0]


def _tiles(d: dict, ms: list[dict] | None, numbers: dict) -> dict:
    def put(name: str, v: Any) -> None:
        if _count(v):
            numbers[name] = v

    inputs = {
        "generated": _item("Generated", d.get("cases_generated")),
        "targeted": _item("Targeted", d.get("cases_targeted")),
        "distinct": _item("Distinct", d.get("distinct_cases")),
    }
    for key, name in (("cases_generated", "generated"), ("cases_targeted", "targeted"),
                      ("distinct_cases", "distinct")):
        put(key, inputs[name]["value"])

    if ms is None:
        disagreements = {"total": _item("Disagreements", None), "by_class": []}
    else:
        order = list(CLASSES) + [c for c in dict.fromkeys(m["class"] for m in ms if isinstance(m.get("class"), str))
                                 if c not in CLASSES]
        by_class = []
        for c in order:
            n = sum(1 for m in ms if m.get("class") == c)
            by_class.append({"class": c, "count": _item(c, n)})
            numbers[f"mismatches_{_slug(c)}"] = n
        numbers["mismatches"] = len(ms)
        disagreements = {"total": _item("Disagreements", len(ms)), "by_class": by_class}

    mut = d.get("mutation")
    mut = mut if isinstance(mut, dict) else {}
    killed, total = mut.get("killed"), mut.get("total")
    survivors = []
    if isinstance(mut.get("mutants"), list):
        for m in mut["mutants"]:
            if isinstance(m, dict) and m.get("killed") is not True:
                reason = m.get("survivor_reason")
                survivors.append({
                    "mutant_id": str(m["mutant_id"]) if m.get("mutant_id") is not None else "no id recorded",
                    "reason": reason if isinstance(reason, str) and reason.strip() else NO_REASON,
                })
    if _count(killed) and _count(total):
        text = f"{killed} of {total}"
        bar = {"killed": killed, "total": total} if total > 0 else None
        numbers["killed"], numbers["total"], numbers["survivors"] = killed, total, len(survivors)
    else:
        text, bar = NOT_CHECKED, None
    explanation = mut.get("survivor_explanation")
    planted = {"text": text, "bar": bar, "survivors": survivors,
               "explanation": explanation if isinstance(explanation, str) and explanation else None}
    return {"inputs": inputs, "disagreements": disagreements, "planted_bugs": planted}


def _counterexample(ms: list[dict] | None, d: dict) -> dict | None:
    if not ms:
        return None
    m = next((x for x in ms if x.get("minimal") is True), ms[0])
    raw_in = m.get("inputs")
    inputs = [{"name": str(k), "value": _show(v)} for k, v in raw_in.items()] if isinstance(raw_in, dict) else []
    exp = m.get("expected") if isinstance(m.get("expected"), dict) else {}
    act = m.get("actual") if isinstance(m.get("actual"), dict) else {}
    out = m.get("output")
    if isinstance(out, str) and out in exp and out in act:
        says, got = [{"key": None, "value": _show(exp[out])}], [{"key": None, "value": _show(act[out])}]
    else:
        keys = list(exp) + [k for k in act if k not in exp]
        diff = [k for k in keys if exp.get(k, _MISSING) != act.get(k, _MISSING)]
        says = [{"key": str(k), "value": _show(exp[k])} for k in diff if k in exp]
        got = [{"key": str(k), "value": _show(act[k])} for k in diff if k in act]
    cls = m.get("class") if isinstance(m.get("class"), str) else NOT_CHECKED
    fid = m.get("finding_id") if isinstance(m.get("finding_id"), str) and m.get("finding_id") else None
    did = m.get("decision_id") if isinstance(m.get("decision_id"), str) and m.get("decision_id") else None
    plain = _PLAIN.get(cls)
    if cls == "original workbook inconsistency" and fid:
        plain = f"{plain} (Finding {fid})"
    output = out if isinstance(out, str) and out else (
        m["cell"] if isinstance(m.get("cell"), str) and m["cell"] else NOT_CHECKED)
    cases = m["cases"] if _is_int(m.get("cases")) and m["cases"] > 1 else None
    cases_line = None
    if cases is not None:
        simplest = "; the simplest is shown" if m.get("minimal") is True else ""
        distinct = d.get("distinct_cases")
        cases_line = (f"{cases} of the {distinct} distinct cases differ in this way{simplest}."
                      if _count(distinct) else f"{cases} cases differ in this way{simplest}.")
    return {"title": "Expected difference" if cls == EXPLAINED else "Counterexample",
            "inputs": inputs, "output": output, "workbook_says": says, "new_code_says": got,
            "class": cls, "plain": plain, "decision_id": did, "finding_id": fid,
            "cases": cases, "cases_line": cases_line}


def _not_proven(d: dict, numbers: dict) -> dict:
    notes = d.get("boundary_notes")
    notes = [x for x in notes if isinstance(x, str)] if isinstance(notes, list) else []
    domains = d.get("tested_domains")
    not_tested = [str(r.get("input", NOT_CHECKED)) for r in domains
                  if isinstance(r, dict) and r.get("not_tested") is True] if isinstance(domains, list) else []
    cov = d.get("rule_coverage")
    rules = []
    for r in cov if isinstance(cov, list) else []:
        if not isinstance(r, dict):
            continue
        no_true, no_false = r.get("seen_true") is False, r.get("seen_false") is False
        if no_true or no_false:
            rules.append({"rule_id": str(r.get("rule_id", NOT_CHECKED)),
                          "condition_id": str(r.get("condition_id", NOT_CHECKED)),
                          "side": "true and false" if no_true and no_false else ("true" if no_true else "false")})
    san = d.get("sanity")
    status = san.get("status") if isinstance(san, dict) else None
    if status == "not cross-checked against Excel":
        excel = "Not cross-checked against Excel."
    elif isinstance(status, str) and status:
        excel = f"Excel cross-check: {status}."
    else:
        excel = f"Excel cross-check: {NOT_CHECKED}."
    versions = d.get("versions")
    lo = versions.get("libreoffice") if isinstance(versions, dict) else None
    if isinstance(lo, str) and lo.strip():
        lo = lo.strip()
        lo = lo[len("LibreOffice"):].strip() if lo.lower().startswith("libreoffice") else lo
        libreoffice = f"Compared with the workbook as recalculated by LibreOffice {lo}." if lo else f"LibreOffice version: {NOT_CHECKED}"
    else:
        libreoffice = f"LibreOffice version: {NOT_CHECKED}"
    nc = d.get("not_converted")
    converted = []
    for e in nc if isinstance(nc, list) else []:
        if isinstance(e, dict):
            reason = e.get("reason")
            converted.append({"cell": str(e.get("cell", NOT_CHECKED)),
                              "reason": reason if isinstance(reason, str) and reason.strip() else NO_REASON})
    empty = {}
    for key, items, sentence in (
            ("boundary_notes", notes, "The report lists no boundary notes."),
            ("domains_not_tested", not_tested, "The report marks no input range as not tested."),
            ("rules_not_seen", rules, "The report lists no rule condition as unseen on either side."),
            ("not_converted", converted, "The report lists no cell as not converted.")):
        if not items:
            empty[key] = sentence
    numbers["boundary_notes"], numbers["domains_not_tested"] = len(notes), len(not_tested)
    numbers["not_converted"] = len(converted)
    return {"boundary_notes": notes, "domains_not_tested": not_tested, "rules_not_seen": rules,
            "excel": excel, "libreoffice": libreoffice, "not_converted": converted, "empty": empty}


def build_verdict(report: dict) -> dict:
    """Everything the Verdict_Card shows, from the parsed Proof_Report and nothing else."""
    d = report if isinstance(report, dict) else {}
    headline, state, claims = _headline(d)
    ms = _mismatches(d)
    numbers: dict[str, int] = {}
    n = d.get("cases_tested")
    if _is_int(n) and n > 0:
        numbers["cases_tested"] = n
    if ms is not None:
        explained = sum(1 for m in ms if m.get("class") == EXPLAINED)
        numbers["expected_by_decision"], numbers["differences"] = explained, len(ms) - explained
    tiles = _tiles(d, ms, numbers)
    tiles["inputs"]["note"] = STOP_NOTE if state == "not_passed" else None
    counterexample = _counterexample(ms, d)
    if counterexample and counterexample["cases"] is not None:
        numbers["counterexample_cases"] = counterexample["cases"]
    mode, seed = d.get("mode"), d.get("seed")
    command = ("python -m ghost.cli verify <migration-dir> "
               f"--mode {mode if mode in ('faithful', 'intended') else NOT_CHECKED} "
               f"--seed {seed if _is_int(seed) else NOT_CHECKED}")
    return {
        "headline": headline,
        "claims_agreement": claims,
        "state": state,
        "tiles": tiles,
        "counterexample": counterexample,
        "not_proven": _not_proven(d, numbers),
        "reproduce": {"command": command, "caption": CAPTION},
        "glossary": [{"term": t, "text": s} for t, s in _GLOSSARY],
        "numbers": numbers,
    }
