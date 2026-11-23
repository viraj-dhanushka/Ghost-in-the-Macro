"""Generate Sample (e) "Traps": one block per row of the Excel_Semantics_Table.

Labelled "generated". Contains formulas only (openpyxl writes no cached values),
so the workbook is "not cross-checked against Excel". Output is deterministic.

Usage: python samples/make_traps.py [output.xlsx]

Sheet "Traps" columns: A table row, B case, C input 1, D input 2, E formula.
Rows 3, 4, 6 (VBA) and 11 (dates) of the table are P2 and listed on "About"
as not included; they cannot be expressed as worksheet formulas.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

LABEL = "generated"

# (table row, case, input1, input2, formula template using {r}); None input = empty cell
CASES: list[tuple[int, str, object, object, str]] = [
    (1, "ROUND(2.5,0) = 3", 2.5, None, "=ROUND(C{r},0)"),
    (1, "ROUND(-2.5,0) = -3", -2.5, None, "=ROUND(C{r},0)"),
    (1, "ROUND(0.125,2) = 0.13", 0.125, None, "=ROUND(C{r},2)"),
    (2, "ROUND(2.675,2) = 2.68", 2.675, None, "=ROUND(C{r},2)"),
    (5, "MOD(-7,3) = 2", -7, 3, "=MOD(C{r},D{r})"),
    (5, "MOD(7,-3) = -2", 7, -3, "=MOD(C{r},D{r})"),
    (7, "Empty cell in arithmetic: =C+1 is 1", None, None, "=C{r}+1"),
    (7, 'Empty cell in text: =C&"x" is "x"', None, None, '=C{r}&"x"'),
    (8, "TRUE+1 = 2", True, None, "=C{r}+1"),
    (8, "FALSE+1 = 1", False, None, "=C{r}+1"),
    (9, 'Case-insensitive: "Gold"="GOLD" is TRUE', "Gold", "GOLD", "=C{r}=D{r}"),
    (10, "Floating noise: 0.1+0.2 vs 0.3", 0.1, 0.2, "=C{r}+D{r}"),
]

NOT_INCLUDED = [
    (3, "VBA Round (P2)"),
    (4, "VBA Int / Fix (P2)"),
    (6, "VBA Mod (P2)"),
    (11, "Dates, 1900 leap-year quirk (P2)"),
]


def build() -> Workbook:
    wb = Workbook()
    wb.properties.creator = "ghost"
    wb.properties.created = _dt.datetime(2026, 1, 1)
    wb.properties.modified = _dt.datetime(2026, 1, 1)

    ws = wb.active
    ws.title = "Traps"
    ws["A1"] = f"Sample (e) Traps ({LABEL})"
    ws["A1"].font = Font(bold=True)
    for col, head in zip("ABCDE", ["Table row", "Case", "Input 1", "Input 2", "Result"]):
        ws[f"{col}3"] = head
        ws[f"{col}3"].font = Font(bold=True)

    for i, (row_no, case, in1, in2, formula) in enumerate(CASES):
        r = 4 + i
        ws[f"A{r}"] = row_no
        ws[f"B{r}"] = case
        if in1 is not None:
            ws[f"C{r}"] = in1
        if in2 is not None:
            ws[f"D{r}"] = in2
        ws[f"E{r}"] = formula.format(r=r)

    ws.column_dimensions["B"].width = 44

    about = wb.create_sheet("About")
    about["A1"] = f"Sample (e) Traps: {LABEL} by samples/make_traps.py. No Excel-saved values."
    about["A2"] = "One block per P0 row of the Excel_Semantics_Table (rows 1, 2, 5, 7, 8, 9, 10)."
    about["A4"] = "Not included (need VBA or date support):"
    for i, (n, name) in enumerate(NOT_INCLUDED):
        about[f"A{5 + i}"] = f"Row {n}: {name}"
    return wb


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent / "traps.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    build().save(out)
    print(f"wrote {out} ({LABEL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
