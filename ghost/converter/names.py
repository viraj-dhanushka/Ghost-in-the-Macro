"""Defined-name resolution (R-27).

Workbook-scoped names that point at one cell or one rectangle on one sheet are
replaced by the cell or range they name. Every other name is left as a
``NameRef`` and listed as "not converted" with a reason. Nothing is guessed.
"""
from __future__ import annotations

import dataclasses
import re

from ghost.converter.ast import Ast, CellRef, NameRef, Node, RangeRef, children
from ghost.models import Workbook

__all__ = ["name_target", "name_reason", "resolved_name_cells", "substitute_names"]

_ADDR = re.compile(r"^([A-Z]+)(\d+)$")


def _lookup(table: dict[str, str], name: str) -> str | None:
    if name in table:
        return table[name]
    up = name.upper()
    hits = sorted(k for k in table if k.upper() == up)
    return table[hits[0]] if hits else None


def _cell(sheet: str, addr: str) -> CellRef:
    m = _ADDR.match(addr)
    assert m
    return CellRef(m.group(1), int(m.group(2)), sheet)


def name_target(workbook: Workbook, name: str) -> Node | None:
    """CellRef or RangeRef that ``name`` stands for, or None when it is not resolvable."""
    if _lookup(workbook.name_issues, name) is not None:
        return None
    target = _lookup(workbook.name_targets, name)
    if target is None:
        return None
    sheet, _, rest = target.rpartition("!")
    first, _, last = rest.partition(":")
    if not last:
        return _cell(sheet, first)
    return RangeRef(_cell(sheet, first), _cell(sheet, last))


def name_reason(workbook: Workbook, name: str) -> str:
    """Why ``name`` is not resolved."""
    if "!" in name:
        return "sheet-scoped name is not resolved"
    return _lookup(workbook.name_issues, name) or "name is not defined in this workbook"


def substitute_names(tree: Ast, workbook: Workbook) -> Ast:
    """Replace every resolvable NameRef; unresolvable ones stay for the caller to list."""
    if not workbook.name_targets:
        return tree

    def go(node: Node) -> Node:
        if isinstance(node, NameRef):
            return name_target(workbook, node.name) or node
        if not children(node):
            return node
        if hasattr(node, "operand"):
            return dataclasses.replace(node, operand=go(node.operand))
        if hasattr(node, "left"):
            return dataclasses.replace(node, left=go(node.left), right=go(node.right))
        return dataclasses.replace(node, args=tuple(go(a) for a in node.args))

    return go(tree)


def resolved_name_cells(workbook: Workbook) -> dict[str, str]:
    """``Sheet!A1`` or ``Sheet!A1:B3`` -> name, for rule-text labels."""
    out: dict[str, str] = {}
    for name in sorted(workbook.name_targets, key=lambda n: (n.upper(), n)):
        target = workbook.name_targets[name]
        if name_target(workbook, name) is not None:
            out.setdefault(target, name)
    return out
