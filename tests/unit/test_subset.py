"""Unit tests for the P0 subset check (Requirement 7.7)."""
from ghost.converter.parser import parse_formula
from ghost.converter.subset import SUPPORTED_FUNCTIONS, check_subset, find_not_converted
from ghost.ingest import features
from ghost.models import Cell, Workbook


def test_supported_formula_has_no_findings():
    assert check_subset(parse_formula("=IF(A1>=50,ROUND(A1*0.1,2),0)"), "S!B1") == []


def test_unsupported_function_listed_with_cell_and_reason():
    out = check_subset(parse_formula("=VLOOKUP(A1,B1:C3,2,FALSE)"), "S!D1")
    assert len(out) == 1
    assert out[0].cell == "S!D1" and "VLOOKUP" in out[0].reason


def test_dependents_flagged_and_features_share_function_set():
    wb = Workbook(path="x")
    wb.cells = {
        "S!A1": Cell(ref="S!A1", value=1),
        "S!B1": Cell(ref="S!B1", formula="=TEXT(A1,\"0\")"),
        "S!C1": Cell(ref="S!C1", formula="=B1+1"),
        "S!D1": Cell(ref="S!D1", formula="=A1+1"),
    }
    wb.deps = {"S!B1": {"S!A1"}, "S!C1": {"S!B1"}, "S!D1": {"S!A1"}}
    out = find_not_converted(wb)
    assert [(e.cell, e.dependent) for e in out] == [("S!B1", False), ("S!C1", True)]
    assert features.SUPPORTED_FUNCTIONS is SUPPORTED_FUNCTIONS
