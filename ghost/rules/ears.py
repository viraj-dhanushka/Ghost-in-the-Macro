"""EARS rule generator (Requirements 3.1-3.7).

``generate_rules`` is a pure function of its input: the same workbook yields
identical rule text and ``rule_id`` values. Formulas that cannot be parsed are
skipped here (the converter lists them as "not converted").
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from ghost.converter import ast as A
from ghost.converter.parser import FormulaSyntaxError, parse_formula
from ghost.models import (
    Cell,
    CellRef,
    CellRoleName,
    Condition,
    Location,
    Rule,
    Threshold,
    Workbook,
)
from ghost.converter.names import resolved_name_cells, substitute_names
from ghost.rules.ids import rule_id

__all__ = ["generate_rules"]

_ADDR_RE = re.compile(r"^([A-Z]+)(\d+)$")

_CMP_WORDS = {
    "=": "equals",
    "<>": "does not equal",
    "<": "is less than",
    "<=": "is at most",
    ">": "is greater than",
    ">=": "is at least",
}
_ARITH_WORDS = {"+": "plus", "-": "minus", "*": "times", "/": "divided by", "^": "to the power of"}
_LOOKUP = {"INDEX", "MATCH", "CHOOSE"}
_ROUND_FUNCS = {"ROUND", "ROUNDUP", "ROUNDDOWN"}


def _split(ref: CellRef) -> tuple[str, str]:
    sheet, _, addr = ref.rpartition("!")
    return sheet, addr


def _shift(ref: CellRef, d_col: int, d_row: int) -> CellRef | None:
    from openpyxl.utils import column_index_from_string, get_column_letter

    sheet, addr = _split(ref)
    m = _ADDR_RE.match(addr)
    if not m:
        return None
    col = column_index_from_string(m.group(1)) + d_col
    row = int(m.group(2)) + d_row
    if col < 1 or row < 1:
        return None
    return f"{sheet}!{get_column_letter(col)}{row}"


class _Namer:
    """Resolves cell references to labels, falling back to the cell reference."""

    def __init__(self, wb: Workbook, home_sheet: str, multi_sheet: bool):
        self.wb = wb
        self.home = home_sheet
        self.multi = multi_sheet
        self.names = resolved_name_cells(wb)

    def _text_of(self, ref: CellRef | None) -> str | None:
        if ref is None:
            return None
        cell = self.wb.cells.get(ref)
        if cell is None or cell.formula is not None:
            return None
        if isinstance(cell.value, str) and cell.value.strip():
            return cell.value.strip()
        return None

    def label(self, ref: CellRef) -> str | None:
        if ref in self.names:
            return self.names[ref]  # a defined name is the author's own label
        cell: Cell | None = self.wb.cells.get(ref)
        if cell is not None and cell.label and cell.label.strip():
            return cell.label.strip()
        # Nearest left text cell, then nearest above.
        return self._text_of(_shift(ref, -1, 0)) or self._text_of(_shift(ref, 0, -1))

    def display_addr(self, ref: CellRef) -> str:
        sheet, addr = _split(ref)
        return addr if (sheet == self.home and not self.multi) else ref

    def name(self, ref: CellRef) -> str:
        label = self.label(ref)
        shown = self.display_addr(ref)
        return f"{label} [{shown}]" if label else shown


def _qualify(node: A.CellRef, home: str) -> CellRef:
    return f"{node.sheet or home}!{node.address}"


class _Renderer:
    def __init__(self, namer: _Namer, home: str):
        self.namer = namer
        self.home = home
        self.cells: list[CellRef] = []
        self.conditions: list[str] = []  # condition texts in encounter order
        self.condition_cells: list[CellRef | None] = []
        self.rounds: list[str] = []
        self.lookups: list[str] = []

    def _note_cell(self, ref: CellRef) -> None:
        if ref not in self.cells:
            self.cells.append(ref)

    def r(self, node: A.Node) -> str:
        if isinstance(node, A.Number):
            return format(node.value, "f") if node.value == node.value.to_integral() else str(node.value)
        if isinstance(node, A.String):
            return f'"{node.value}"'
        if isinstance(node, A.Boolean):
            return "TRUE" if node.value else "FALSE"
        if isinstance(node, A.ErrorLiteral):
            return node.code
        if isinstance(node, A.MissingArg):
            return "nothing"
        if isinstance(node, A.CellRef):
            ref = _qualify(node, self.home)
            self._note_cell(ref)
            return self.namer.name(ref)
        if isinstance(node, A.RangeRef):
            s, e = _qualify(node.start, self.home), _qualify(node.end, self.home)
            self._note_cell(s)
            self._note_cell(e)
            named = self.namer.names.get(f"{s}:{_split(e)[1]}")
            if named:
                return f"range {named} [{self.namer.display_addr(s)}:{_split(e)[1]}]"
            return f"range {self.namer.display_addr(s)}:{_split(e)[1]}"
        if isinstance(node, A.NameRef):
            return node.name
        if isinstance(node, A.UnaryOp):
            inner = self.r(node.operand)
            return f"negative {inner}" if node.op == "-" else inner
        if isinstance(node, A.Percent):
            return f"{self.r(node.operand)} percent"
        if isinstance(node, A.BinaryOp):
            left, right = self.r(node.left), self.r(node.right)
            if node.op in _CMP_WORDS:
                return f"{left} {_CMP_WORDS[node.op]} {right}"
            if node.op == "&":
                return f"{left} joined with {right}"
            return f"({left} {_ARITH_WORDS[node.op]} {right})"
        if isinstance(node, A.FuncCall):
            return self.call(node)
        raise TypeError(f"unknown node {node!r}")  # pragma: no cover

    def call(self, node: A.FuncCall) -> str:
        name, args = node.name, node.args
        if name == "IF" and len(args) >= 2:
            cond = self.r(args[0])
            self._add_condition(cond, args[0])
            then = self.r(args[1])
            other = self.r(args[2]) if len(args) > 2 else "FALSE"
            return f"(if {cond} then {then}, otherwise {other})"
        if name in _ROUND_FUNCS and len(args) == 2:
            value = self.r(args[0])
            digits = self.r(args[1])
            n = digits
            if isinstance(args[1], A.Number):
                n = str(int(args[1].value)) if args[1].value == args[1].value.to_integral() else digits
            how = {
                "ROUND": "half away from zero",
                "ROUNDUP": "away from zero",
                "ROUNDDOWN": "toward zero",
            }[name]
            self.rounds.append(f"rounded to {n} decimals ({how})")
            return f"{value} rounded to {n} decimals ({how})"
        if name in _LOOKUP:
            self.lookups.append(name)
            inner = ", ".join(self.r(a) for a in args)
            return f"the result of looking up {name}({inner})"
        inner = ", ".join(self.r(a) for a in args)
        return f"{name}({inner})"

    def _add_condition(self, text: str, node: A.Node) -> None:
        self.conditions.append(text)
        first = next((n for n in A.walk(node) if isinstance(n, A.CellRef)), None)
        self.condition_cells.append(_qualify(first, self.home) if first else None)


def _top_if(tree: A.Node) -> A.FuncCall | None:
    return tree if isinstance(tree, A.FuncCall) and tree.name == "IF" and len(tree.args) >= 2 else None


def _sentence(namer: _Namer, ref: CellRef, tree: A.Node, rend: _Renderer) -> str:
    target = namer.name(ref)
    top = _top_if(tree)
    if top is not None:
        cond = rend.r(top.args[0])
        rend._add_condition(cond, top.args[0])
        then = rend.r(top.args[1])
        other = rend.r(top.args[2]) if len(top.args) > 2 else "FALSE"
        return (
            f"WHEN {cond} THE SYSTEM SHALL set {target} to {then}. "
            f"OTHERWISE THE SYSTEM SHALL set {target} to {other}."
        )
    expr = rend.r(tree)
    if rend.lookups:
        return f"WHEN {target} is requested THE SYSTEM SHALL look up its value as {expr}."
    if rend.rounds and isinstance(tree, A.FuncCall) and tree.name in _ROUND_FUNCS:
        return f"WHEN {target} is calculated THE SYSTEM SHALL set {target} to {expr}."
    return f"WHEN {target} is calculated THE SYSTEM SHALL set {target} to {expr}."


def _sort_key(ref: CellRef) -> tuple[str, int, int]:
    from openpyxl.utils import column_index_from_string

    sheet, addr = _split(ref)
    m = _ADDR_RE.match(addr)
    if not m:
        return (sheet, 0, 0)
    return (sheet, int(m.group(2)), column_index_from_string(m.group(1)))


def generate_rules(
    workbook: Workbook,
    roles: Mapping[CellRef, CellRoleName] | None = None,
    thresholds: list[Threshold] | None = None,
) -> list[Rule]:
    """Return one EARS Rule per formula cell, in sheet/row/column order."""
    roles = roles or {}
    thresholds = thresholds or []
    multi = len(workbook.sheets) > 1
    vba_by_cell: dict[CellRef, list[Location]] = {}
    for t in thresholds:
        if t.source.module is not None:
            vba_by_cell.setdefault(t.cell, []).append(t.source)

    rules: list[Rule] = []
    for ref in sorted(workbook.cells, key=_sort_key):
        cell = workbook.cells[ref]
        if cell.formula is None:
            continue
        try:
            tree = substitute_names(parse_formula(cell.formula), workbook)
        except FormulaSyntaxError:
            continue
        home = _split(ref)[0]
        namer = _Namer(workbook, home, multi)
        rend = _Renderer(namer, home)
        text = _sentence(namer, ref, tree, rend)
        rid = rule_id(ref, cell.formula)
        macro_lines: list[Location] = []
        for src in rend.cells:
            for loc in vba_by_cell.get(src, []):
                if loc not in macro_lines:
                    macro_lines.append(loc)
        rules.append(
            Rule(
                rule_id=rid,
                text=text,
                cells=[ref, *[c for c in rend.cells if c != ref]],
                macro_lines=macro_lines,
                conditions=[
                    Condition(condition_id=f"{rid}-C{i}", text=t, cell=c)
                    for i, (t, c) in enumerate(zip(rend.conditions, rend.condition_cells), 1)
                ],
            )
        )
    return rules
