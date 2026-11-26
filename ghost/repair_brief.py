"""Repair brief: the smallest evidence of what is wrong with a candidate (Trial by Workbook, large-workbook-lane).
Built only from a proof report, plus the rule text (from rules.md) and the source formula. Ghost adds no path. A value
that came from the candidate's own result ("<compute raised ...>") is cut to 200 characters, because it is text the
candidate wrote and an agent will read it.
Used by `ghost challenge` (written to --out) and by scripts/repair_brief.py (Feature 5's hook step).
"""
from __future__ import annotations
import re
from typing import Callable
__all__ = ["EXPLAINED", "NOT_AVAILABLE", "build_brief", "parse_rules", "pick"]
NOT_AVAILABLE = "not available"
EXPLAINED = "expected by decision"


def parse_rules(text: str) -> dict[str, dict]:
    """rules.md -> {rule_id: {"text": EARS text, "cell": first source cell}}. Only what the file says."""
    rules: dict[str, dict] = {}
    current = None
    body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"##\s+(R-[0-9A-Za-z]+)\s*$", line)
        if m:
            current, body = m.group(1), []
            rules[current] = {"text": NOT_AVAILABLE, "cell": None}
        elif current and line.startswith("Source:"):
            cells = [c.strip() for c in line[len("Source:"):].split(",") if c.strip()]
            rules[current]["cell"] = cells[0] if cells else None
            if body:
                rules[current]["text"] = " ".join(body)
            current = None
        elif current and line.strip():
            body.append(line.strip())
    return rules


def _cut(actual):
    if not isinstance(actual, dict):
        return actual
    return {k: (v[:200] + "...") if isinstance(v, str) and v.startswith("<compute raised") and len(v) > 200 else v
            for k, v in actual.items()}
def pick(mismatches: list) -> dict | None:
    ms = [m for m in mismatches if isinstance(m, dict)]
    unexplained = [m for m in ms if m.get("class") != EXPLAINED] or ms
    if not unexplained:
        return None
    return next((m for m in unexplained if m.get("minimal") is True), unexplained[0])


def build_brief(report: dict, rules_text: str, formula_of: Callable[[str], str | None]) -> dict:
    """The brief for one proof report. ``formula_of(cell)`` gives a cell's formula text or None."""
    passed = report.get("passed")
    if passed is True:
        return {"status": "passed"}
    if not isinstance(passed, bool):
        return {"status": NOT_AVAILABLE}
    m = pick(report.get("mismatches") or [])
    head = {"status": "failed", "mode": report.get("mode"), "seed": report.get("seed")}
    if m is None:
        return {**head, "counterexample": None, "note": "the report lists no mismatch"}
    rule_id = m.get("rule_id") or NOT_AVAILABLE
    rule = parse_rules(rules_text).get(rule_id)
    cell = rule["cell"] if rule else None
    formula = formula_of(cell) if cell else None
    extra = {}
    ids = [d.get("decision_id") for d in (report.get("decisions") or []) if isinstance(d, dict) and d.get("decision_id")]
    if ids and report.get("mode") == "faithful":
        extra = {
            "decision_ids": ids,
            "warning": ("This migration has recorded Decisions (" + ", ".join(ids) + "). The difference may be "
                        "intended behaviour, not a bug in logic.py. Ask the user before changing the code."),
        }
    return {
        **head,
        **extra,
        "found_by": (NOT_AVAILABLE if not isinstance(report.get("cases_generated"), int) else
                     "targeted boundary case" if report["cases_generated"] == 0 else "search (shrunk)"),
        "counterexample": {
            "inputs": m.get("inputs"),
            "output": m.get("output") or NOT_AVAILABLE,
            "cell": m.get("cell") or NOT_AVAILABLE,
            "referee": m.get("expected"),
            "actual": _cut(m.get("actual")),
        },
        "rule": {
            "rule_id": rule_id,
            "rule_text": rule["text"] if rule else NOT_AVAILABLE,
            "source_formula": formula or NOT_AVAILABLE,
        },
    }
