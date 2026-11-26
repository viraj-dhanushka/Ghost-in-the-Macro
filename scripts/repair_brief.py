"""Repair brief: the smallest evidence of what is wrong with a hand-written logic.py (Trial by Workbook).

Reads a migration folder's existing `proof-report.json` (and `rules.md`, `source.yaml` and the workbook for the
rule text and the source formula) and writes `repair-brief.json`. It changes no engine code and holds no value
that the report does not hold, apart from the rule text and the source formula. Ghost adds no path.

Usage: scripts/ghost-py scripts/repair_brief.py <migration-dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ghost.repair_brief import EXPLAINED, NOT_AVAILABLE, build_brief, parse_rules, pick as _pick  # noqa: E402,F401

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
