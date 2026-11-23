"""Cell role classification (Requirement 2.1-2.6).

Roles:
- OUTPUT: formula cell with no dependents, or a user-selected cell.
- INTERMEDIATE: formula cell with dependents, not user-selected.
- INPUT / PARAMETER: constant cell referenced by at least one formula.

Constants that no formula references get no role (they are labels or notes).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ghost.models import Cell, CellRef, CellRoleName, Workbook

__all__ = ["classify", "input_score"]

# A label containing one of these words marks the constant as a rate/fixed value.
_RATE_WORDS = re.compile(
    r"\b(rate|vat|tax|gst|percent|percentage|pct|fee|rebate|margin|markup|"
    r"threshold|limit|factor|multiplier|constant)\b|%",
    re.IGNORECASE,
)

_ADDR_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _left_ref(ref: CellRef) -> CellRef | None:
    from openpyxl.utils import column_index_from_string, get_column_letter

    sheet, _, addr = ref.rpartition("!")
    m = _ADDR_RE.match(addr)
    if not m:
        return None
    col = column_index_from_string(m.group(1))
    if col <= 1:
        return None
    return f"{sheet}!{get_column_letter(col - 1)}{m.group(2)}"


def _left_label(wb: Workbook, ref: CellRef) -> str | None:
    """Text of the immediately left-adjacent constant text cell, if any."""
    left = _left_ref(ref)
    if left is None:
        return None
    cell = wb.cells.get(left)
    if cell is None or cell.formula is not None:
        return None
    if isinstance(cell.value, str) and cell.value.strip():
        return cell.value.strip()
    return None


def input_score(cell: Cell, label: str | None) -> int:
    """INPUT score: referenced constant (+1) plus fill, validation and label (+1 each)."""
    score = 1  # the caller only scores constants that a formula references
    if cell.fill:
        score += 1
    if cell.validation:
        score += 1
    if label:
        score += 1
    return score


def classify(
    workbook: Workbook, user_outputs: Iterable[CellRef] = ()
) -> dict[CellRef, CellRoleName]:
    """Assign a role to every formula cell and every referenced constant cell."""
    selected = set(user_outputs)

    # dependents[x] = formula cells that read x
    dependents: dict[CellRef, set[CellRef]] = {}
    for formula_ref, reads in workbook.deps.items():
        for src in reads:
            dependents.setdefault(src, set()).add(formula_ref)

    roles: dict[CellRef, CellRoleName] = {}
    for ref in sorted(workbook.cells):
        cell = workbook.cells[ref]
        users = dependents.get(ref, set()) - {ref}
        if cell.formula is not None:
            if ref in selected or not users:
                roles[ref] = "OUTPUT"
            else:
                roles[ref] = "INTERMEDIATE"
            continue
        if ref in selected:
            roles[ref] = "OUTPUT"
            continue
        if not users:
            continue  # unreferenced constant: label or note
        label = _left_label(workbook, ref)
        score = input_score(cell, label)
        rate_labelled = bool(label and _RATE_WORDS.search(label))
        # Fixed value shared by several formulas with no input-style signal.
        shared_fixed = len(users) >= 2 and score == 1
        if rate_labelled or shared_fixed:
            roles[ref] = "PARAMETER"
        else:
            roles[ref] = "INPUT"
    return roles
