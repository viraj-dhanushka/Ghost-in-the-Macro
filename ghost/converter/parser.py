"""Tokenizer and precedence-climbing parser for the P0 Excel formula grammar.

Precedence, lowest to highest: comparison, ``&``, ``+ -``, ``* /``, ``^``,
postfix ``%``, unary ``- +``. As in Excel, unary minus binds tighter than
``^`` (``-2^2`` is 4) and binary operators are left-associative.

Anything outside the grammar raises ``FormulaSyntaxError``; the parser never
guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .ast import (
    Ast,
    BinaryOp,
    Boolean,
    CellRef,
    ErrorLiteral,
    FuncCall,
    MissingArg,
    NameRef,
    Node,
    Number,
    Percent,
    RangeRef,
    String,
    UnaryOp,
)


class FormulaSyntaxError(ValueError):
    """Raised when a formula is not in the supported grammar."""

    def __init__(self, message: str, pos: int = -1):
        super().__init__(message if pos < 0 else f"{message} (at position {pos})")
        self.pos = pos


@dataclass(frozen=True)
class Token:
    kind: str  # NUMBER STRING BOOL ERROR SHEET CELL FUNC NAME OP LPAREN RPAREN COMMA COLON PERCENT EOF
    text: str
    pos: int


_ERRORS = ("#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!")

_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_QUOTED_SHEET = re.compile(r"'((?:[^']|'')+)'!")
_PLAIN_SHEET = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)!")
_CELL = re.compile(r"(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_.(])")
_IDENT = re.compile(r"[A-Za-z_\\][A-Za-z0-9_.\\]*")
_OPS = ("<>", "<=", ">=", "+", "-", "*", "/", "^", "&", "=", "<", ">")


def tokenize(text: str) -> list[Token]:
    """Split a formula (without the leading ``=``) into tokens."""
    tokens: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            j, buf = i + 1, []
            while True:
                if j >= n:
                    raise FormulaSyntaxError("unterminated string literal", i)
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            tokens.append(Token("STRING", "".join(buf), i))
            i = j + 1
            continue
        if ch == "#":
            upper = text[i:].upper()
            for err in _ERRORS:
                if upper.startswith(err):
                    tokens.append(Token("ERROR", err, i))
                    i += len(err)
                    break
            else:
                raise FormulaSyntaxError("unknown error literal", i)
            continue
        if ch == "'":
            m = _QUOTED_SHEET.match(text, i)
            if not m:
                raise FormulaSyntaxError("malformed quoted sheet name", i)
            tokens.append(Token("SHEET", m.group(1).replace("''", "'"), i))
            i = m.end()
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            m = _NUMBER.match(text, i)
            assert m
            tokens.append(Token("NUMBER", m.group(0), i))
            i = m.end()
            continue
        if ch.isalpha() or ch in "_$\\":
            m = _PLAIN_SHEET.match(text, i)
            if m:
                tokens.append(Token("SHEET", m.group(1), i))
                i = m.end()
                continue
            m = _CELL.match(text, i)
            if m:
                tokens.append(Token("CELL", m.group(0), i))
                i = m.end()
                continue
            m = _IDENT.match(text, i)
            if not m:
                raise FormulaSyntaxError(f"unexpected character {ch!r}", i)
            word = m.group(0)
            j = m.end()
            if j < n and text[j] == "(":
                kind = "FUNC"
            elif word.upper() in ("TRUE", "FALSE"):
                kind = "BOOL"
            else:
                kind = "NAME"
            tokens.append(Token(kind, word, i))
            i = j
            continue
        if ch == "(":
            tokens.append(Token("LPAREN", ch, i))
        elif ch == ")":
            tokens.append(Token("RPAREN", ch, i))
        elif ch == ",":
            tokens.append(Token("COMMA", ch, i))
        elif ch == ":":
            tokens.append(Token("COLON", ch, i))
        elif ch == "%":
            tokens.append(Token("PERCENT", ch, i))
        else:
            for op in _OPS:
                if text.startswith(op, i):
                    tokens.append(Token("OP", op, i))
                    i += len(op)
                    break
            else:
                raise FormulaSyntaxError(f"unexpected character {ch!r}", i)
            continue
        i += 1
    tokens.append(Token("EOF", "", n))
    return tokens


_COMPARISONS = ("=", "<>", "<", "<=", ">", ">=")


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.i = 0

    @property
    def cur(self) -> Token:
        return self.toks[self.i]

    def advance(self) -> Token:
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def at_op(self, *ops: str) -> bool:
        return self.cur.kind == "OP" and self.cur.text in ops

    def expect(self, kind: str) -> Token:
        if self.cur.kind != kind:
            raise FormulaSyntaxError(
                f"expected {kind} but found {self.cur.kind} {self.cur.text!r}", self.cur.pos
            )
        return self.advance()

    def parse(self) -> Node:
        node = self.comparison()
        if self.cur.kind != "EOF":
            raise FormulaSyntaxError(f"unexpected token {self.cur.text!r}", self.cur.pos)
        return node

    def _binary(self, operand, ops: tuple[str, ...]) -> Node:
        left = operand()
        while self.at_op(*ops):
            op = self.advance().text
            left = BinaryOp(op, left, operand())
        return left

    def comparison(self) -> Node:
        return self._binary(self.concat, _COMPARISONS)

    def concat(self) -> Node:
        return self._binary(self.additive, ("&",))

    def additive(self) -> Node:
        return self._binary(self.multiplicative, ("+", "-"))

    def multiplicative(self) -> Node:
        return self._binary(self.power, ("*", "/"))

    def power(self) -> Node:
        return self._binary(self.percent, ("^",))

    def percent(self) -> Node:
        node = self.unary()
        while self.cur.kind == "PERCENT":
            self.advance()
            node = Percent(node)
        return node

    def unary(self) -> Node:
        if self.at_op("-", "+"):
            op = self.advance().text
            return UnaryOp(op, self.unary())
        return self.primary()

    def primary(self) -> Node:
        tok = self.cur
        if tok.kind == "NUMBER":
            self.advance()
            return Number(Decimal(tok.text))
        if tok.kind == "STRING":
            self.advance()
            return String(tok.text)
        if tok.kind == "BOOL":
            self.advance()
            return Boolean(tok.text.upper() == "TRUE")
        if tok.kind == "ERROR":
            self.advance()
            return ErrorLiteral(tok.text)
        if tok.kind == "LPAREN":
            self.advance()
            node = self.comparison()
            self.expect("RPAREN")
            return node
        if tok.kind == "FUNC":
            return self.func_call()
        if tok.kind in ("SHEET", "CELL"):
            return self.reference()
        if tok.kind == "NAME":
            self.advance()
            return NameRef(tok.text)
        raise FormulaSyntaxError(f"unexpected token {tok.text!r}", tok.pos)

    def func_call(self) -> Node:
        name = self.advance().text.upper()
        if name.startswith("_XLFN."):
            name = name[6:]
        self.expect("LPAREN")
        args: list[Node] = []
        if self.cur.kind == "RPAREN":
            self.advance()
            return FuncCall(name, ())
        while True:
            if self.cur.kind in ("COMMA", "RPAREN"):
                args.append(MissingArg())
            else:
                args.append(self.comparison())
            if self.cur.kind == "COMMA":
                self.advance()
                continue
            self.expect("RPAREN")
            break
        return FuncCall(name, tuple(args))

    def cell(self, sheet: str | None) -> CellRef:
        tok = self.expect("CELL")
        m = _CELL.fullmatch(tok.text)
        assert m
        row = int(m.group(4))
        if row < 1:
            raise FormulaSyntaxError(f"invalid cell reference {tok.text!r}", tok.pos)
        return CellRef(m.group(2).upper(), row, sheet, bool(m.group(1)), bool(m.group(3)))

    def reference(self) -> Node:
        sheet: str | None = None
        if self.cur.kind == "SHEET":
            sheet = self.advance().text
            if self.cur.kind == "NAME":
                # Sheet-qualified defined name, e.g. Sheet1!Rate.
                return NameRef(f"{sheet}!{self.advance().text}")
        start = self.cell(sheet)
        if self.cur.kind == "COLON":
            self.advance()
            end_sheet = sheet
            if self.cur.kind == "SHEET":
                end_sheet = self.advance().text
                if end_sheet != sheet:
                    raise FormulaSyntaxError("3-D references are not supported", self.cur.pos)
            end = self.cell(end_sheet)
            return RangeRef(start, end)
        return start


def parse_formula(text: str) -> Ast:
    """Parse a formula string (with or without the leading ``=``) into an AST."""
    body = text.strip()
    if body.startswith("="):
        body = body[1:]
    if not body.strip():
        raise FormulaSyntaxError("empty formula")
    return _Parser(tokenize(body)).parse()
