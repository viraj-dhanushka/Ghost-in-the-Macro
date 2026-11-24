"""Threshold extraction (requirement 2.7).

A Threshold is a comparison of a cell with a numeric literal, found in a
formula AST or in a VBA condition. Output order is deterministic.
"""

from __future__ import annotations

import re
from decimal import Decimal

from ghost.converter import ast as A
from ghost.converter.names import substitute_names
from ghost.converter.parser import FormulaSyntaxError, parse_formula
from ghost.models import Location, Threshold, VbaModule, Workbook

_COMPARISONS = {"=", "<>", "<", "<=", ">", ">="}
# Operator to use when the literal is on the left: ``50 <= B2`` is ``B2 >= 50``.
_FLIP = {"=": "=", "<>": "<>", "<": ">", "<=": ">=", ">": "<", ">=": "<="}


def _literal(node: A.Node) -> Decimal | None:
    if isinstance(node, A.Number):
        return node.value
    if isinstance(node, A.Percent):
        inner = _literal(node.operand)
        return None if inner is None else inner / 100
    if isinstance(node, A.UnaryOp) and isinstance(node.operand, A.Number):
        return -node.operand.value if node.op == "-" else node.operand.value
    return None


def _qualify(ref: A.CellRef, formula_cell: str) -> str:
    sheet = ref.sheet or formula_cell.rsplit("!", 1)[0]
    return f"{sheet}!{ref.address}"


def _render(node: A.Node, sheet: str) -> str:
    """Deterministic text of an expression, used as the key of an expression threshold."""
    if isinstance(node, A.Number):
        return format(node.value, "f")
    if isinstance(node, A.String):
        return '"' + node.value + '"'
    if isinstance(node, A.Boolean):
        return "TRUE" if node.value else "FALSE"
    if isinstance(node, A.CellRef):
        return f"{node.sheet or sheet}!{node.address}" if node.sheet else node.address
    if isinstance(node, A.RangeRef):
        return f"{_render(node.start, sheet)}:{node.end.address}"
    if isinstance(node, A.NameRef):
        return node.name
    if isinstance(node, A.UnaryOp):
        return f"{node.op}{_render(node.operand, sheet)}"
    if isinstance(node, A.Percent):
        return f"{_render(node.operand, sheet)}%"
    if isinstance(node, A.BinaryOp):
        return f"({_render(node.left, sheet)}{node.op}{_render(node.right, sheet)})"
    if isinstance(node, A.FuncCall):
        return f"{node.name}({','.join(_render(a, sheet) for a in node.args)})"
    return "?"


def _is_expression(node: A.Node) -> bool:
    """An arithmetic or function expression that reads at least one cell."""
    if isinstance(node, A.BinaryOp):
        if node.op in _COMPARISONS or node.op == "&":
            return False
    elif not isinstance(node, (A.UnaryOp, A.Percent, A.FuncCall)):
        return False
    return any(isinstance(n, (A.CellRef, A.RangeRef)) for n in A.walk(node))


def thresholds_from_ast(
    tree: A.Node,
    formula_cell: str,
    constants: dict[str, Decimal] | None = None,
) -> list[Threshold]:
    """Thresholds in one formula's AST, in left-to-right order.

    ``constants`` maps ``Sheet!A1`` to the numeric value of a constant (non-formula)
    cell. A comparison against such a cell counts as a comparison against its
    value, so ``B2>=E2`` with ``E2 = 50`` is the threshold ``B2 >= 50``.

    A comparison of an expression with a constant (``A2*A3>=500``) is recorded
    with the rendered expression, qualified by the sheet, as its ``cell``.
    """
    consts = constants or {}

    def operand(node: A.Node) -> Decimal | None:
        lit = _literal(node)
        if lit is None and isinstance(node, A.CellRef):
            return consts.get(_qualify(node, formula_cell))
        return lit

    found: list[Threshold] = []
    for node in A.walk(tree):
        if not isinstance(node, A.BinaryOp) or node.op not in _COMPARISONS:
            continue
        if isinstance(node.left, A.CellRef) and (const := operand(node.right)) is not None:
            ref, op = node.left, node.op
        elif isinstance(node.right, A.CellRef) and (const := operand(node.left)) is not None:
            ref, op = node.right, _FLIP[node.op]
        elif _is_expression(node.left) and (const := operand(node.right)) is not None:
            ref, op = node.left, node.op
        elif _is_expression(node.right) and (const := operand(node.left)) is not None:
            ref, op = node.right, _FLIP[node.op]
        else:
            continue
        if isinstance(ref, A.CellRef):
            cell = _qualify(ref, formula_cell)
        else:
            cell = f"{formula_cell.rsplit('!', 1)[0]}!{_render(ref, formula_cell.rsplit('!', 1)[0])}"
        found.append(
            Threshold(
                cell=cell,
                operator=op,
                constant=const,
                source=Location(cell=formula_cell),
            )
        )
    return found


# --------------------------------------------------------------------------
# VBA
# --------------------------------------------------------------------------

_NUM = r"-?\d+(?:\.\d+)?"
_OPS = r"<>|<=|>=|=|<|>"
_RANGE = r"(?:\w+\.)?Range\(\s*\"([A-Za-z]+\d+)\"\s*\)(?:\.Value2?)?"
_OPERAND = rf"(?:{_RANGE}|([A-Za-z_]\w*(?:\.\w+)*))"
_LEFT_CELL = re.compile(rf"{_OPERAND}\s*({_OPS})\s*({_NUM})(?![\w.])", re.IGNORECASE)
_RIGHT_CELL = re.compile(rf"(?<![\w.\"])({_NUM})\s*({_OPS})\s*{_OPERAND}", re.IGNORECASE)
_CONDITION_LINE = re.compile(
    r"^\s*(?:If|ElseIf|While|Do\s+While|Do\s+Until|Loop\s+While|Loop\s+Until|Until|Case\s+Is)\b"
    r"|\bIIf\s*\(",
    re.IGNORECASE,
)
# String literals are blanked, except the argument of Range("B11").
_STRING = re.compile(r'(?<!Range\()"[^"\n]*"', re.IGNORECASE)


def _strip_comment(line: str) -> str:
    out, in_str = [], False
    for ch in line:
        if ch == '"':
            in_str = not in_str
        elif ch == "'" and not in_str:
            break
        out.append(ch)
    return "".join(out)


def _vba_operand(range_addr: str | None, name: str | None, sheet: str) -> str | None:
    if range_addr:
        return f"{sheet}!{range_addr.upper()}"
    if name and name.lower() not in {"if", "elseif", "while", "until", "is", "then", "and", "or", "not", "case"}:
        return name
    return None


def thresholds_from_vba(modules: list[VbaModule], default_sheet: str = "") -> list[Threshold]:
    """Thresholds in VBA conditions. Range("B11") operands become ``Sheet!B11``;
    other operands (variables, properties) are recorded by their source text."""
    found: list[Threshold] = []
    for module in modules:
        for lineno, raw in enumerate(module.source.splitlines(), start=1):
            line = _strip_comment(raw)
            if not _CONDITION_LINE.search(line):
                continue
            line = _STRING.sub('""', line)
            hits: list[tuple[int, str | None, str, str]] = []
            for m in _LEFT_CELL.finditer(line):
                hits.append((m.start(), _vba_operand(m.group(1), m.group(2), default_sheet), m.group(3), m.group(4)))
            for m in _RIGHT_CELL.finditer(line):
                hits.append((m.start(), _vba_operand(m.group(3), m.group(4), default_sheet), _FLIP[m.group(2)], m.group(1)))
            for _, cell, op, const in sorted(hits, key=lambda h: h[0]):
                if cell is None:
                    continue
                found.append(
                    Threshold(
                        cell=cell,
                        operator=op,
                        constant=Decimal(const),
                        source=Location(module=module.name, line=lineno),
                    )
                )
    return found


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def extract_thresholds(
    workbook: Workbook,
    vba: list[VbaModule] | None = None,
    roles: dict[str, str] | None = None,
) -> list[Threshold]:
    """All Thresholds from formula ASTs and VBA comparisons.

    Comparison constants are resolved only from cells whose role is not INPUT.
    ``roles`` is the confirmed role map (or any map where INPUT cells are marked);
    when omitted, the autopsy default classification is used.

    ``vba`` defaults to ``workbook.vba_modules``. Formulas outside the supported
    grammar are skipped here; they are reported as "not converted" elsewhere.
    """
    modules = workbook.vba_modules if vba is None else vba
    result: list[Threshold] = []
    constants: dict[str, Decimal] = {}
    if roles is None:
        from ghost.autopsy.classify import classify

        roles = dict(classify(workbook))
    for ref, c in workbook.cells.items():
        if (
            roles.get(ref) != "INPUT"
            and not c.formula
            and isinstance(c.value, (int, float))
            and not isinstance(c.value, bool)
        ):
            constants[ref] = Decimal(repr(c.value))
    for ref in sorted(workbook.cells):
        cell = workbook.cells[ref]
        if not cell.formula:
            continue
        try:
            tree = parse_formula(cell.formula)
        except FormulaSyntaxError:
            continue
        result.extend(thresholds_from_ast(substitute_names(tree, workbook), ref, constants))
    sheet = workbook.sheets[0] if workbook.sheets else ""
    result.extend(thresholds_from_vba(modules, sheet))
    return result
