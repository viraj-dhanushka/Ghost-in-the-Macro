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

    Marks the first comparison token equal to ``op`` that sits next to ``constant``; failing that,
    the token equal to ``op`` only when it is the only one in the formula; otherwise nothing is
    marked (with two such comparisons and none next to the constant, a guess could point at the
    wrong one). The leading "=" of the formula is not a comparison.
    """
    start = 1 if formula.startswith("=") else 0
    hits = [m for m in _TOKEN.finditer(formula, start) if m.group() == op]
    chosen = next((m for m in hits if _next_to_constant(formula, m, constant)), hits[0] if len(hits) == 1 else None)
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


MAX_VBA_LINES_PER_MODULE = 400
MAX_VBA_LINES_TOTAL = 2000
MAX_VBA_CHARS_PER_MODULE = 60000
MAX_VBA_CHARS_TOTAL = 200000
MAX_VBA_MODULES = 50


def _whole_lines_within(lines: list[str], budget: int) -> list[str]:
    """The leading lines whose text, joined by newlines, fits in ``budget`` characters."""
    kept: list[str] = []
    used = 0
    for line in lines:
        add = len(line) + (1 if kept else 0)
        if used + add > budget:
            break
        kept.append(line)
        used += add
    return kept


def vba_blocks(modules: list[dict]) -> list[dict]:
    """The VBA modules as the VBA_Panel shows them: name, recorded line count, the text to show and a note.

    Limits: 400 lines and 60000 characters per module, 2000 lines and 200000 characters in all, and 50 modules
    (``vba_notice`` counts the rest). A cut is made at a whole line, and the note says how many lines are
    actually shown; a module that gets nothing is still listed with the reason. The source is returned as it
    is: the template escapes it.
    """
    remaining_lines, remaining_chars = MAX_VBA_LINES_TOTAL, MAX_VBA_CHARS_TOTAL
    out = []
    for m in modules[:MAX_VBA_MODULES]:
        source = m.get("source") or ""
        lines = source.split("\n") if source else []
        total = len(lines)
        text, note, used_lines = "", None, 0
        if total == 0:
            note = "The module is empty."
        elif remaining_lines <= 0:
            note = (f"Not shown: the display limit of {MAX_VBA_LINES_TOTAL} lines was reached. "
                    f"The module has {total} lines.")
        elif remaining_chars <= 0:
            note = (f"Not shown: the display limit of {MAX_VBA_CHARS_TOTAL} characters was reached. "
                    f"The module has {total} lines.")
        else:
            take = min(MAX_VBA_LINES_PER_MODULE, remaining_lines, total)
            shown = lines[:take]
            budget = min(MAX_VBA_CHARS_PER_MODULE, remaining_chars)
            text = "\n".join(shown)
            if len(text) > budget:
                kept = _whole_lines_within(shown, budget)
                if kept:
                    shown, text = kept, "\n".join(kept)
                    note = f"Showing the first {len(shown)} of {total} lines, cut at {budget} characters."
                elif budget < MAX_VBA_CHARS_PER_MODULE:  # only a fragment of the total budget is left
                    shown, text = [], ""
                    note = (f"Not shown: the display limit of {MAX_VBA_CHARS_TOTAL} characters was reached. "
                            f"The module has {total} lines.")
                else:  # a single line longer than the per-module limit
                    shown, text = [lines[0][:budget]], lines[0][:budget]
                    note = f"Showing part of line 1 (its first {budget} characters) of {total} lines."
            elif take < total:
                note = f"Showing the first {take} of {total} lines."
            used_lines = len(shown)
        out.append({"name": str(m.get("name", "")), "line_count": m.get("line_count", total),
                    "text": text, "note": note})
        remaining_lines -= used_lines
        remaining_chars -= len(text)
    return out


def vba_notice(modules: list[dict]) -> str | None:
    """A notice for the modules that are not listed at all (more than 50)."""
    extra = len(modules) - MAX_VBA_MODULES
    if extra <= 0:
        return None
    return f"{extra} more {'module' if extra == 1 else 'modules'} not shown."


def route_view(route) -> dict:
    """The router's answer for the Route_Panel: name, reasons and the suggested command (or None)."""
    vba_note = None
    if route.route == "Ghost converts" and route.metrics.vba_line_count > 0:
        vba_note = ("Ghost converts the formulas it supports. It does not translate the VBA: a cell that calls a VBA function "
                    "is listed above as not converted.")
    return {"route": route.route, "reasons": list(route.reasons), "command": route.atx_command,
            "vba_note": vba_note}
