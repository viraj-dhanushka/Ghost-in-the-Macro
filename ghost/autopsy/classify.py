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

from ghost.converter.subset import find_not_converted
from ghost.models import Cell, CellRef, CellRoleName, Workbook

__all__ = ["cell_label", "classify", "input_score"]

# A label containing one of these words marks the constant as a rate/fixed value.
_RATE_WORDS = re.compile(
    r"\b(rate|vat|tax|gst|percent|percentage|pct|fee|rebate|margin|markup|"
    r"threshold|limit|factor|multiplier|constant|allowance|within|free)\b|%",
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


def cell_label(wb: Workbook, ref: CellRef) -> str | None:
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


def _left_label(wb: Workbook, ref: CellRef) -> str | None:
    """Kept for the callers in this module; delegates to the public ``cell_label``."""
    return cell_label(wb, ref)


def _above_below_ref(ref: CellRef, step: int) -> CellRef | None:
    sheet, _, addr = ref.rpartition("!")
    m = _ADDR_RE.match(addr)
    if not m:
        return None
    row = int(m.group(2)) + step
    if row < 1:
        return None
    return f"{sheet}!{m.group(1)}{row}"


def _in_parameter_block(workbook: Workbook, ref: CellRef) -> bool:
    """True when an unmarked, labelled constant is sandwiched between two
    constants whose own labels name a rate or fixed value (a block of parameters).

    Cells with a fill or validation are never pulled into a block: the author
    marked them as inputs.
    """
    cell = workbook.cells[ref]
    if cell.fill or cell.validation or not _left_label(workbook, ref):
        return False
    for step in (-1, 1):
        nb = _above_below_ref(ref, step)
        other = workbook.cells.get(nb) if nb else None
        if other is None or other.formula is not None or other.fill or other.validation:
            return False
        label = _left_label(workbook, nb)
        if not (label and _RATE_WORDS.search(label)):
            return False
    return True


_LOOKUP_RE = re.compile(r"\b(INDEX|MATCH|VLOOKUP|HLOOKUP|LOOKUP|XLOOKUP)\s*\(", re.IGNORECASE)
_SPLIT_RE = re.compile(r"^(.*)!([A-Z]+)(\d+)$")

# A table block spans at least this many columns and rows of unmarked constants.
# Two columns is a label/value list, which is not a table.
_TABLE_MIN_COLS = 3
_TABLE_MIN_ROWS = 3


def _table_block_cells(workbook: Workbook) -> set[CellRef]:
    """Cells that belong to a table block of constants (R-05).

    A table block is a 4-connected group of constant cells (numbers or text)
    with no fill and no validation, at least 3 columns by 3 rows in extent.
    Filled or validated cells are marked as inputs by the author and never join.
    """
    from openpyxl.utils import column_index_from_string

    pos: dict[tuple[str, int, int], CellRef] = {}
    for ref, cell in workbook.cells.items():
        if cell.formula is not None or cell.fill or cell.validation:
            continue
        if cell.value is None or isinstance(cell.value, bool):
            continue
        m = _SPLIT_RE.match(ref)
        if m:
            pos[(m.group(1), column_index_from_string(m.group(2)), int(m.group(3)))] = ref

    block: set[CellRef] = set()
    seen: set[tuple[str, int, int]] = set()
    for start in sorted(pos):
        if start in seen:
            continue
        group = []
        stack = [start]
        seen.add(start)
        while stack:
            key = stack.pop()
            group.append(key)
            sheet, col, row = key
            for nb in ((sheet, col - 1, row), (sheet, col + 1, row), (sheet, col, row - 1), (sheet, col, row + 1)):
                if nb in pos and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        cols = {k[1] for k in group}
        rows = {k[2] for k in group}
        if (max(cols) - min(cols) + 1 >= _TABLE_MIN_COLS and max(rows) - min(rows) + 1 >= _TABLE_MIN_ROWS):
            block.update(pos[k] for k in group)
    return block


def _is_lookup_text(workbook: Workbook, cell: Cell, users: set[CellRef]) -> bool:
    """Text constant read by a formula that uses INDEX/MATCH/LOOKUP (R-05)."""
    if not isinstance(cell.value, str) or cell.fill or cell.validation:
        return False
    return any(
        (f := workbook.cells.get(u)) is not None and f.formula and _LOOKUP_RE.search(f.formula)
        for u in users
    )


def _compared_with_literal(workbook: Workbook) -> set[CellRef]:
    """Cells that some formula compares directly with a numeric literal (R-11).

    Read from the formula ASTs, not from computed thresholds, so classification
    does not depend on thresholds that are themselves computed from the roles.
    ``A1>=50`` and ``50<A1`` both count A1. A comparison between two cells
    (``B2>=E2``) does not.
    """
    from ghost.autopsy.thresholds import _literal, _qualify
    from ghost.converter import ast as A
    from ghost.converter.names import substitute_names
    from ghost.converter.parser import FormulaSyntaxError, parse_formula

    found: set[CellRef] = set()
    for ref in sorted(workbook.cells):
        formula = workbook.cells[ref].formula
        if not formula:
            continue
        try:
            tree = substitute_names(parse_formula(formula), workbook)
        except FormulaSyntaxError:
            continue
        for node in A.walk(tree):
            if not isinstance(node, A.BinaryOp) or node.op not in ("=", "<>", "<", "<=", ">", ">="):
                continue
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if isinstance(side, A.CellRef) and _literal(other) is not None:
                    found.add(_qualify(side, ref))
    return found


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


def not_offerable_outputs(workbook: Workbook) -> set[CellRef]:
    """Cells that must never be offered or pre-checked as outputs (L-05).

    Not-converted cells (with their dependents, as ``find_not_converted`` lists
    them) and not-verifiable cells (volatile or external constructs) plus
    everything that depends on them. One shared rule for the mapping defaults,
    the web autopsy, the CLI and MCP.
    """
    bad: set[CellRef] = {e.cell for e in find_not_converted(workbook) if e.cell}
    bad |= {f.cell for f in workbook.features if f.not_verifiable and f.cell}
    dependents: dict[CellRef, set[CellRef]] = {}
    for formula_ref, reads in workbook.deps.items():
        for src in reads:
            dependents.setdefault(src, set()).add(formula_ref)
    todo = list(bad)
    while todo:
        for d in dependents.get(todo.pop(), ()):
            if d not in bad:
                bad.add(d)
                todo.append(d)
    return bad


def unverifiable_output_reasons(
    workbook: Workbook, cells: Iterable[CellRef]
) -> dict[CellRef, str]:
    """For each requested output that cannot be verified, say why (L-05).

    The reason is the engine's own: the ``find_not_converted`` text, or the
    not-verifiable feature (volatile or external construct). A dependant of
    such a cell names the cell it reads. Cells that are fine, or not in the
    workbook, are absent from the result.
    """
    wanted = [c for c in dict.fromkeys(cells)]
    bad = not_offerable_outputs(workbook)
    if not any(c in bad for c in wanted):
        return {}
    not_converted: dict[CellRef, list[str]] = {}
    for e in find_not_converted(workbook):
        if e.cell:
            not_converted.setdefault(e.cell, []).append(e.reason)
    volatile = {
        f.cell: f"not verifiable as-is: {f.kind} {f.detail}".rstrip()
        for f in workbook.features
        if f.not_verifiable and f.cell
    }
    out: dict[CellRef, str] = {}
    for cell in wanted:
        if cell not in bad:
            continue
        if cell in not_converted:
            out[cell] = "not converted: " + "; ".join(not_converted[cell])
        elif cell in volatile:
            out[cell] = volatile[cell]
        else:
            src = sorted(p for p in workbook.deps.get(cell, ()) if p in bad)
            out[cell] = "not verifiable as-is: depends on " + ", ".join(src)
    return out


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

    table_cells = _table_block_cells(workbook)
    compared = _compared_with_literal(workbook)

    not_offered = not_offerable_outputs(workbook)

    roles: dict[CellRef, CellRoleName] = {}
    for ref in sorted(workbook.cells):
        cell = workbook.cells[ref]
        users = dependents.get(ref, set()) - {ref}
        if cell.formula is not None:
            if ref in selected:
                roles[ref] = "OUTPUT"  # explicit choice; rejected elsewhere (task 3.15)
            elif ref in not_offered:
                roles[ref] = "INTERMEDIATE"  # never a default output (L-05)
            elif not users:
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
        in_block = _in_parameter_block(workbook, ref)
        # Fixed value shared by several formulas with no input-style signal.
        # A constant compared with a threshold is an input (R-11).
        shared_fixed = len(users) >= 2 and score == 1 and ref not in compared
        in_table = ref in table_cells or _is_lookup_text(workbook, cell, users)
        if rate_labelled or in_block or in_table or shared_fixed:
            roles[ref] = "PARAMETER"
        else:
            roles[ref] = "INPUT"
    return roles
