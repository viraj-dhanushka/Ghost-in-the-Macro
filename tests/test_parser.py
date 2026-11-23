from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from ghost.converter.ast import (
    BinaryOp, Boolean, CellRef, FuncCall, MissingArg, NameRef, Number, Percent,
    RangeRef, String, UnaryOp, walk,
)
from ghost.converter.parser import FormulaSyntaxError, parse_formula


def test_precedence_and_associativity():
    ast = parse_formula("=1+2*3")
    assert ast == BinaryOp("+", Number(Decimal("1")), BinaryOp("*", Number(Decimal("2")), Number(Decimal("3"))))
    ast = parse_formula("=8-3-2")
    assert ast.left == BinaryOp("-", Number(Decimal("8")), Number(Decimal("3")))
    ast = parse_formula("=2^3^2")  # Excel is left-associative
    assert ast.left == BinaryOp("^", Number(Decimal("2")), Number(Decimal("3")))


def test_unary_minus_binds_tighter_than_power():
    ast = parse_formula("=-2^2")
    assert ast == BinaryOp("^", UnaryOp("-", Number(Decimal("2"))), Number(Decimal("2")))


def test_percent_comparison_concat():
    assert parse_formula("=B1*20%") == BinaryOp("*", CellRef("B", 1), Percent(Number(Decimal("20"))))
    ast = parse_formula('="a"&B1=C1')
    assert ast.op == "=" and ast.left.op == "&"
    assert parse_formula("=A1<>B1").op == "<>"
    assert parse_formula("=A1>=1").op == ">="


def test_literals_decimal_text():
    assert parse_formula("=0.1").value == Decimal("0.1")
    assert parse_formula("=.5").value == Decimal("0.5")
    assert parse_formula('="a""b"') == String('a"b')
    assert parse_formula("=TRUE") == Boolean(True)


def test_references():
    assert parse_formula("=$B$2") == CellRef("B", 2, None, True, True)
    assert parse_formula("=Inputs!B2") == CellRef("B", 2, "Inputs")
    assert parse_formula("='My Sheet'!B2:C4") == RangeRef(CellRef("B", 2, "My Sheet"), CellRef("C", 4, "My Sheet"))
    assert parse_formula("=SUM(A1:A3)").args[0] == RangeRef(CellRef("A", 1), CellRef("A", 3))
    assert parse_formula("=TaxRate*2").left == NameRef("TaxRate")


def test_functions():
    ast = parse_formula("=if(A1>=50,ROUND(A1*0.1,2),0)")
    assert isinstance(ast, FuncCall) and ast.name == "IF" and len(ast.args) == 3
    assert parse_formula("=IF(A1,,2)").args[1] == MissingArg()
    assert parse_formula("=LOG10(A1)").name == "LOG10"
    assert parse_formula("=NOW()").args == ()


@pytest.mark.parametrize("bad", ["", "=", "=1+", "=(1", "=1 2", '="x', "=A1:", "=#FOO", "=1;2", "=Sheet1!"])
def test_syntax_errors(bad):
    with pytest.raises(FormulaSyntaxError):
        parse_formula(bad)


@settings(max_examples=100, derandomize=True)
@given(st.lists(st.integers(1, 99), min_size=1, max_size=8), st.lists(st.sampled_from("+-*/&"), min_size=7, max_size=7))
def test_chain_parses_all_operands(nums, ops):
    text = "=" + str(nums[0]) + "".join(o + str(v) for o, v in zip(ops, nums[1:]))
    ast = parse_formula(text)
    assert [n.value for n in walk(ast) if isinstance(n, Number)] == [Decimal(v) for v in nums]
