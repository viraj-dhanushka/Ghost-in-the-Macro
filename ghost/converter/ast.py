"""AST node types for the P0 Excel formula grammar.

Nodes are frozen dataclasses so they are hashable, comparable and safe to
share. Numeric literals keep their source text as ``Decimal`` (never float).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator, Union


@dataclass(frozen=True)
class Number:
    value: Decimal


@dataclass(frozen=True)
class String:
    value: str


@dataclass(frozen=True)
class Boolean:
    value: bool


@dataclass(frozen=True)
class ErrorLiteral:
    """An Excel error literal such as ``#N/A`` or ``#DIV/0!``."""

    code: str


@dataclass(frozen=True)
class MissingArg:
    """An omitted function argument, as in ``IF(A1,,B1)``."""


@dataclass(frozen=True)
class CellRef:
    col: str  # upper-case letters, e.g. "AB"
    row: int
    sheet: str | None = None
    abs_col: bool = False
    abs_row: bool = False

    @property
    def address(self) -> str:
        return f"{self.col}{self.row}"


@dataclass(frozen=True)
class RangeRef:
    start: CellRef
    end: CellRef

    @property
    def sheet(self) -> str | None:
        return self.start.sheet


@dataclass(frozen=True)
class NameRef:
    name: str


@dataclass(frozen=True)
class UnaryOp:
    op: str  # "-" or "+"
    operand: "Node"


@dataclass(frozen=True)
class Percent:
    operand: "Node"


@dataclass(frozen=True)
class BinaryOp:
    op: str  # + - * / ^ & = <> < <= > >=
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class FuncCall:
    name: str  # upper-case
    args: tuple["Node", ...]


Node = Union[
    Number,
    String,
    Boolean,
    ErrorLiteral,
    MissingArg,
    CellRef,
    RangeRef,
    NameRef,
    UnaryOp,
    Percent,
    BinaryOp,
    FuncCall,
]

# The tree type returned by ``parse_formula``.
Ast = Node


def children(node: Node) -> tuple[Node, ...]:
    if isinstance(node, (UnaryOp, Percent)):
        return (node.operand,)
    if isinstance(node, BinaryOp):
        return (node.left, node.right)
    if isinstance(node, FuncCall):
        return node.args
    return ()


def walk(node: Node) -> Iterator[Node]:
    """Yield ``node`` and all descendants, pre-order, left to right."""
    yield node
    for child in children(node):
        yield from walk(child)
