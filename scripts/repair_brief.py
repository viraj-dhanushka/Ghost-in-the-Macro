"""Repair brief: the smallest evidence of what is wrong with a hand-written logic.py (Trial by Workbook).

Reads a migration folder's existing `proof-report.json` (and `rules.md`, `source.yaml` and the workbook for the
rule text and the source formula) and writes `repair-brief.json`. It changes no engine code and holds no value
that the report does not hold, apart from the rule text and the source formula. It never holds a path.

Usage: scripts/ghost-py scripts/repair_brief.py <migration-dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable

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


def _pick(mismatches: list) -> dict | None:
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
    m = _pick(report.get("mismatches") or [])
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
            "actual": m.get("actual"),
        },
        "rule": {
            "rule_id": rule_id,
            "rule_text": rule["text"] if rule else NOT_AVAILABLE,
            "source_formula": formula or NOT_AVAILABLE,
        },
    }


def _formula_reader(migration_dir: Path) -> Callable[[str], str | None]:
    """Reads a cell's formula from the migration's workbook (read-only, macros never run); None on any problem."""
    try:
        rel = re.search(r"^workbook:\s*(.+?)\s*$", (migration_dir / "source.yaml").read_text(encoding="utf-8"), re.M)
        import openpyxl
        wb = openpyxl.load_workbook((migration_dir / rel.group(1)).resolve(), read_only=False)
    except Exception:  # noqa: BLE001 - a missing workbook just means "not available"
        return lambda cell: None

    def formula_of(cell: str) -> str | None:
        try:
            sheet, _, addr = cell.rpartition("!")
            v = wb[sheet][addr].value
        except Exception:  # noqa: BLE001
            return None
        return v if isinstance(v, str) and v.startswith("=") else None

    return formula_of


def write_brief(migration_dir: str | Path) -> dict:
    mdir = Path(migration_dir)
    report = json.loads((mdir / "proof-report.json").read_text(encoding="utf-8"))  # FileNotFoundError if absent
    rules = (mdir / "rules.md").read_text(encoding="utf-8") if (mdir / "rules.md").is_file() else ""
    brief = build_brief(report, rules, _formula_reader(mdir))
    (mdir / "repair-brief.json").write_text(json.dumps(brief, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return brief


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: repair_brief.py <migration-dir>", file=sys.stderr)
        return 2
    print(json.dumps(write_brief(args[0]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
