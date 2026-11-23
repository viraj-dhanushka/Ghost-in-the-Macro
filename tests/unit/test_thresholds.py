from decimal import Decimal

from ghost.autopsy.thresholds import extract_thresholds
from ghost.models import Cell, VbaModule, Workbook


def test_formula_and_vba_thresholds():
    wb = Workbook(path="x", sheets=["S"])
    wb.cells["S!C1"] = Cell(ref="S!C1", formula='=IF(B2>=50,0.1,0)+IF(50<B2,1,0)')
    wb.cells["S!C2"] = Cell(ref="S!C2", formula="=IF(S!B2>-5,1,0)")
    src = 'If Range("B11").Value >= 500 Then\n  x = 5\nElseIf 10 > n Then\n'
    wb.vba_modules = [VbaModule(name="M", source=src, line_count=3)]
    got = [(t.cell, t.operator, t.constant, t.source.cell or (t.source.module, t.source.line))
           for t in extract_thresholds(wb)]
    assert got == [
        ("S!B2", ">=", Decimal("50"), "S!C1"),
        ("S!B2", ">", Decimal("50"), "S!C1"),
        ("S!B2", ">", Decimal("-5"), "S!C2"),
        ("S!B11", ">=", Decimal("500"), ("M", 1)),
        ("n", "<", Decimal("10"), ("M", 3)),
    ]
