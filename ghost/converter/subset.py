"""P0 subset check and "not converted" listing (Requirement 7.7).

This module is the single source of truth for the supported function set.
Constructs outside the subset are listed with cell and reason; no code is
emitted for them and every cell that depends on them is flagged.
"""
from __future__ import annotations

from dataclasses import dataclass

from ghost.converter.ast import (
    Ast,
    BinaryOp,
    ErrorLiteral,
    FuncCall,
    NameRef,
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
