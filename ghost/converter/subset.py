"""P0 subset check and "not converted" listing (Requirement 7.7).

This module is the single source of truth for the supported function set.
Constructs outside the subset are listed with cell and reason; no code is
emitted for them and every cell that depends on them is flagged.
"""
from __future__ import annotations

from dataclasses import dataclass

from openpyxl.utils import column_index_from_string

from ghost.converter.ast import (
    Ast,
    BinaryOp,
    ErrorLiteral,
    FuncCall,
    NameRef,
    Number,
    RangeRef,
    walk,
)
from ghost.converter.names import name_reason, substitute_names
from ghost.converter.parser import FormulaSyntaxError, parse_formula
from ghost.models import Workbook

__all__ = [
    "SUPPORTED_FUNCTIONS",
    "NotConverted",
    "check_subset",
    "find_not_converted",
]

# P0 function subset (Requirement 7.3).
SUPPORTED_FUNCTIONS = frozenset(
    {
        "IF", "AND", "OR", "NOT", "IFERROR", "ROUND", "ROUNDUP", "ROUNDDOWN",
        "INT", "MOD", "ABS", "MIN", "MAX", "SUM", "AVERAGE", "CHOOSE", "INDEX",
        "MATCH",
    }
)

_OPERATORS = frozenset({"+", "-", "*", "/", "^", "&", "=", "<>", "<", "<=", ">", ">="})

# L-03: functions whose direct INDEX arguments are references (whole selection),
# and functions that pass a reference through from these argument positions.
_AGGREGATE_FUNCS = frozenset({"SUM", "AVERAGE", "MIN", "MAX", "AND", "OR"})
_PASS_THROUGH = {"IF": slice(1, None), "IFERROR": slice(0, None), "CHOOSE": slice(1, None)}
INDEX_PASSED_THROUGH = (
    "INDEX that can select a whole row or column (an index of 0, or one computed at run "
    "time), passed through IF, IFERROR or CHOOSE inside SUM, AVERAGE, MIN, MAX, AND or OR "
    "(reference context), is not converted"
)


def _may_select_whole(index: FuncCall) -> bool:
    """True when this INDEX can select a whole row or column of a multi-cell range."""
    if not index.args or not isinstance(index.args[0], RangeRef):
        return False  # a single cell, or not a range (the emitter rejects it)
    rng = index.args[0]
    rows = abs(rng.end.row - rng.start.row) + 1
    cols = abs(column_index_from_string(rng.end.col) - column_index_from_string(rng.start.col)) + 1
    if rows == 1 and cols == 1:
        return False
    if len(index.args) == 2 and rows > 1 and cols > 1:
        return True  # an omitted column on a grid is 0
    return any(not (isinstance(a, Number) and a.value >= 1) for a in index.args[1:])


def _passed_through_index(node: Ast) -> bool:
    """An INDEX that may select a whole row or column reaches ``node``'s value
    through IF, IFERROR or CHOOSE."""
    if not isinstance(node, FuncCall):
        return False
    if node.name == "INDEX":
        return _may_select_whole(node)
    if node.name in _PASS_THROUGH:
        return any(_passed_through_index(a) for a in node.args[_PASS_THROUGH[node.name]])
    return False


@dataclass(frozen=True)
class NotConverted:
    """A formula (or dependent cell) that is not converted, with the reason."""

    cell: str | None
    reason: str
    # True when the cell itself is fine but depends on a not-converted cell.
    dependent: bool = False


def check_subset(
    ast: Ast, cell: str | None = None, workbook: Workbook | None = None
) -> list[NotConverted]:
    """Return one entry per distinct out-of-subset construct in ``ast``.

    With ``workbook``, resolvable defined names are substituted first (R-27) and
    only the unresolvable ones are listed, each with its reason."""
    if workbook is not None:
        ast = substitute_names(ast, workbook)
    out: list[NotConverted] = []
    seen: set[str] = set()

    def add(reason: str) -> None:
        if reason not in seen:
            seen.add(reason)
            out.append(NotConverted(cell=cell, reason=reason))

    for node in walk(ast):
        if isinstance(node, FuncCall) and node.name not in SUPPORTED_FUNCTIONS:
            add(f"function {node.name} is outside the P0 subset")
        elif isinstance(node, NameRef):
            why = f": {name_reason(workbook, node.name)}" if workbook is not None else ""
            add(f"named reference {node.name} is not supported{why}")
        elif isinstance(node, BinaryOp) and node.op not in _OPERATORS:
            add(f"operator {node.op} is outside the P0 subset")
        elif isinstance(node, ErrorLiteral):
            continue
        elif isinstance(node, RangeRef) and node.start.sheet != node.end.sheet:
            add("3-D reference is not supported")
        if (
            isinstance(node, FuncCall)
            and node.name in _AGGREGATE_FUNCS
            and any(
                isinstance(a, FuncCall) and a.name in _PASS_THROUGH and _passed_through_index(a)
                for a in node.args
            )
        ):
            add(INDEX_PASSED_THROUGH)
    return out


def find_not_converted(workbook: Workbook) -> list[NotConverted]:
    """List every formula cell that cannot be converted, plus its dependents.

    Direct entries come first (sorted by cell), then dependents (sorted by
    cell). Output is deterministic. Nothing is guessed: an unparseable
    formula is listed with its syntax error.
    """
    direct: dict[str, list[NotConverted]] = {}
    for ref in sorted(workbook.cells):
        formula = workbook.cells[ref].formula
        if not formula:
            continue
        try:
            ast = parse_formula(formula)
        except FormulaSyntaxError as exc:
            direct[ref] = [NotConverted(cell=ref, reason=f"formula not parsed: {exc}")]
            continue
        found = check_subset(ast, ref, workbook)
        if found:
            direct[ref] = found

    entries = [e for ref in sorted(direct) for e in direct[ref]]

    # Transitive dependents: a cell is flagged if any precedent is flagged.
    flagged = set(direct)
    changed = True
    while changed:
        changed = False
        for ref, precedents in workbook.deps.items():
            if ref not in flagged and any(p in flagged for p in precedents):
                flagged.add(ref)
                changed = True
    for ref in sorted(flagged - set(direct)):
        bad = sorted(p for p in workbook.deps.get(ref, ()) if p in flagged)
        entries.append(
            NotConverted(
                cell=ref,
                reason="depends on not-converted cell " + ", ".join(bad),
                dependent=True,
            )
        )
    return entries
