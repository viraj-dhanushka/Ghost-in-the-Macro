"""Autopsy presentation helpers (readable-proof, Requirements 8 and 9).

Pure: standard library only. They turn the Finding's own fields and a cell's label, value or
formula into the short texts and marked-up pieces the autopsy template prints. Nothing here
evaluates a formula or states an outcome.
"""
from __future__ import annotations

import re
from typing import Any

# Comparison tokens, longest first so that ">=" and "<>" are not read as ">" or "<".
_TOKEN = re.compile(r"<>|<=|>=|=|<|>")


def finding_title(kind: str) -> str:
    """"operator_conflict" -> "Operator conflict"; the title comes from the Finding's kind."""
    return str(kind).replace("_", " ").strip().capitalize()


def short_ref(ref: str, same_sheet_as: str) -> str:
    """"Calculator!B7" -> "B7" when it is on the same sheet as ``same_sheet_as``."""
    sheet, _, addr = ref.rpartition("!")
    return addr if sheet == same_sheet_as.rpartition("!")[0] else ref


def _name(loc: dict, finding_cell: str) -> str:
    if loc.get("cell"):
        return short_ref(loc["cell"], finding_cell)
    if loc.get("module") or loc.get("line"):
        return f"{loc.get('module') or 'macro'}:{loc.get('line') or '?'}"
    return "an unnamed macro line"


def consequence(constant: str, finding_cell: str, locations: list[dict]) -> str:
    """"at exactly 50, B7 uses >= and B9 uses >": built only from the Finding's own fields."""
    parts = [f"{_name(loc, finding_cell)} uses {loc.get('op', '')}" for loc in locations]
    if len(parts) > 1:
        body = ", ".join(parts[:-1]) + " and " + parts[-1]
    else:
        body = "".join(parts)
    return f"at exactly {constant}, {body}"


def _next_to_constant(formula: str, m: re.Match, constant: str) -> bool:
    after, before = formula[m.end():].lstrip(), formula[:m.start()].rstrip()
    if after.startswith(constant) and not after[len(constant):len(constant) + 1].replace(".", "0").isalnum():
        return True
    if before.endswith(constant):
        prev = before[:-len(constant)][-1:]
        return not prev.replace(".", "0").isalnum()
    return False


def formula_segments(formula: str, op: str, constant: str) -> list[tuple[str, bool]]:
    """Split ``formula`` into (text, is_marked_operator) pieces that join back to the formula.

    Marks the first comparison token equal to ``op`` that sits next to ``constant``, else the first
    token equal to ``op``, else nothing. The leading "=" of the formula is not a comparison.
    """
    start = 1 if formula.startswith("=") else 0
    hits = [m for m in _TOKEN.finditer(formula, start) if m.group() == op]
    chosen = next((m for m in hits if _next_to_constant(formula, m, constant)), hits[0] if hits else None)
    if chosen is None:
        return [(formula, False)]
    pieces = [(formula[:chosen.start()], False), (chosen.group(), True), (formula[chosen.end():], False)]
    return [p for p in pieces if p[0]]


def checkbox_text(cell: str, label: str | None, value: Any = None, formula: str | None = None) -> str:
    """"label (address), value in the workbook: V" / "label (address), formula: F" / the address alone."""
    text = f"{label} ({cell})" if label else cell
    if formula is not None:
        return f"{text}, formula: {formula}"
    if value is not None:
        return f"{text}, value in the workbook: {value}"
    return text
