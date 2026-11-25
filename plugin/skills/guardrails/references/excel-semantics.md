---
inclusion: fileMatch
fileMatchPattern: "{ghost/converter/**,ghost/runtime/**,samples/make_traps.py,tests/**/*semantics*,.kiro/specs/**/logic.py}"
---

# Excel_Semantics_Table

Golden table of Excel and VBA behaviours. Golden tests check every row against both the Referee (LibreOffice) and the generated Python code. Sample (e) "Traps" has one row per entry.

| # | Area | Behaviour | Examples | Req |
|---|---|---|---|---|
| 1 | Worksheet ROUND | Half away from zero | `ROUND(2.5,0)=3`, `ROUND(-2.5,0)=-3`, `ROUND(0.125,2)=0.13` | 15.1 |
| 2 | Worksheet ROUND precision | Evaluated on 15 significant digits | `ROUND(2.675,2)=2.68` | 15.2 |
| 3 | VBA Round (P2) | Half-even (banker's) | `Round(2.5)=2`, `Round(3.5)=4`, `Round(0.125,2)=0.12` | 15.3 |
| 4 | VBA Int / Fix (P2) | Int is floor, Fix is truncation | `Int(-2.5)=-3`, `Fix(-2.5)=-2` | 15.4 |
| 5 | Worksheet MOD | Result has the sign of the divisor | `MOD(-7,3)=2` | 15.5 |
| 6 | VBA Mod (P2) | Result has the sign of the dividend | `-7 Mod 3 = -1` | 15.6 |
| 7 | Empty cell | 0 in arithmetic, "" in text operations | `=A1+1` with A1 empty is 1; `=A1&"x"` is "x" | 15.7 |
| 8 | Booleans | TRUE is 1 and FALSE is 0 in arithmetic | `=TRUE+1` is 2 | 15.8 |
| 9 | Text comparison | Case-insensitive | `="Gold"="GOLD"` is TRUE | 15.9 |
| 10 | Floating noise | Differences within 1e-6 are equal for verification | `0.1+0.2` vs `0.3` | 15.10 |
| 11 | Dates (P2) | 1900 leap-year quirk: serial 60 is 29 Feb 1900 | serial 60 | 15.11 |

## Implementation notes

- Convert floats with `Decimal(repr(x))`. For ROUND, first normalise to 15 significant digits, then quantize with `ROUND_HALF_UP` (which is half away from zero for Decimal).
- Worksheet MOD(a, b) = `a - b * floor(a / b)`. Python `%` on ints matches; `Decimal.__mod__` does not (it takes the dividend's sign), so do not use it directly.
- Worksheet INT is floor. ROUNDUP and ROUNDDOWN round away from zero and toward zero respectively.
- Excel errors (`#DIV/0!`, `#VALUE!`, `#N/A`, ...) propagate through formulas and are compared by error type, never coerced to numbers.
- LibreOffice worksheet ROUND matches Excel; LibreOffice VBA Round follows half-even, so rows 3 and 6 must use a VBA-compatible code path, never the worksheet one.
- Rows 3, 4, 6 and 11 are excluded from golden tests until VBA and date support exist.

## Where LibreOffice differs from Excel

In these seven cases Ghost's generated code follows Excel and the Referee (LibreOffice) does not. A workbook that relies on one of them shows a false "translation bug" mismatch. They are excluded from golden tests and from formula fuzzing. `tests/test_referee_libreoffice_differences.py` pins the LibreOffice results so an upgrade is noticed.

| Expression | Excel | LibreOffice 7.4.7.2 (live image) | LibreOffice 26.8.3.1 (local) | Ghost generated code |
|---|---|---|---|---|
| `0^0` | `#NUM!` | 1 | 1 | `#NUM!` |
| `(-8)^(1/3)` | `#NUM!` | -2 | -2 | `#NUM!` |
| `MATCH("2",numbers,0)` | `#N/A` | 2 | 2 | `#N/A` |
| `MATCH(TRUE,numbers,0)` | `#N/A` | 1 | 1 | `#N/A` |
| `TRUE>1` | TRUE | FALSE | FALSE | TRUE |
| `SUM("5",1)` | 6 | `#VALUE!` | `#VALUE!` | 6 |
| `TRUE&""` | "TRUE" | "1" | "1" | "TRUE" |

- **Excel column:** not verified by measurement. There is no Excel in the development environment. The values are the documented Excel behaviour as recorded in `docs/TEST_REPORT_2026-11-24.md` (R-24). Treat them as "Excel: not verified" until checked in Excel for the web.
- **LibreOffice columns:** measured through the Referee on 2026-11-24. The live column ran in the Docker image `ghost-local:cp4` (Debian bookworm, `soffice --version` 7.4.7.2); the local column ran on the development install (26.8.3.1). `numbers` was cells holding 1, 2, 3. The two versions gave identical results for all seven.
- **Ghost column:** measured by running the transpiler output on the same formulas.
- **Versions:** the live site runs LibreOffice 7.4.7.2. Local development runs the local version (26.8.3.1). Verification results on the two can differ for constructs not listed here, so check the Referee version in any proof report. The image has not been upgraded.

## Number-to-text (R-08)

Ghost writes numbers as text (`&""`) with 15 significant digits. Magnitudes of 1E16 and above, or below 1E-14, use scientific notation with a sign and at least two exponent digits: `1E+20&""` is "1E+20", `1E-20&""` is "1E-20", `123456789012345678&""` is "1.23456789012346E+17". Other numbers stay plain: `(0.1+0.2)&""` is "0.3", `1/3&""` is "0.333333333333333".

- The Referee (LibreOffice) writes three exponent digits ("1E+020"). The verifier treats two strings as equal when both are scientific notation of the same value. All other strings compare exactly, so "100" and "1E+02" differ.
- The switch points (above 1E15 and below 1E-14) were measured on LibreOffice 26.8.3.1. Excel's exact switch points are not verified; only the 1E+20 and 1E-20 cases are documented Excel behaviour.
- `INDEX` with a 0 row or column: see "INDEX with a 0 row or column (L-03)" below. A 0 on a longer dimension does not always give `#VALUE!`; the Referee applies implicit intersection.

## INDEX with a 0 row or column (L-03)

Measured through the Referee on 2026-11-24 on LibreOffice 26.8.3.1 (local) and 7.4.7.2 (image `ghost-local:l03`). Both versions gave identical results on every case below. The full measurement (69 cases) is in `.kiro/specs/live-fixes-2026-11-24/measurements-l03.md`; more contexts are pinned in `tests/test_index_zero_contexts.py`. Ghost's generated code follows these rules (`_index`, `_index_area` in `ghost/converter/emit_python.py`).

| Range and indexes | Formula cell's row or column inside the range's span | Outside the span | Inside `SUM`, `AVERAGE`, `MIN`, `MAX`, `AND`, `OR` |
|---|---|---|---|
| Single column, row 0 (column omitted, 1 or 0): `INDEX($M$5:$M$7,0)` | element on the formula's row, edges included (row 6 gives 8) | `#VALUE!` | whole column (`SUM` gives 24) |
| Single row, column 0 (row omitted, 1 or 0): `INDEX($E$20:$G$20,0)` | element in the formula's column (column F gives 22) | `#VALUE!` | whole row (66) |
| Grid, one index 0 and the other non-zero: `INDEX($Q$5:$R$7,0,2)` | the selected column (or row), then intersect (row 6 gives 42) | `#VALUE!` | whole selected column or row (126) |
| Grid, both indexes 0 | `#VALUE!` (a cell inside both spans would be circular, not measured) | `#VALUE!` | whole grid (222) |
| Grid, one index given (`INDEX($Q$5:$R$7,2)`): the omitted column is 0 | element in the formula's column (column Q gives 32) | `#VALUE!` | whole row (74) |
| A 0 on a dimension of length 1 (`INDEX(M1:M3,2,0)`, `INDEX(M1:O1,0,2)`) | the cell, wherever the formula is | the cell | not measured |
| Single cell (R-30): `INDEX(T5:T5,0)`, `INDEX(T5,0)`, `INDEX(T5:T5,0,0)` | its value | its value | not measured |

- **Span:** only the row number (single column) or the column number (single row) is compared. The formula's other coordinate does not matter (`X6` and `F15` intersect). A range on another sheet is compared by the formula cell's own row or column number, in both directions.
- **Indexes:** a computed 0 (a cell holding 0) behaves like a literal 0. Fractions truncate. `"0"`, FALSE and an empty cell are 0; TRUE is 1. A negative index is `#VALUE!`.
- **Context:** arithmetic on the result (`INDEX(...)+0`) and `IF`, `ROUND`, `IFERROR`, `CHOOSE` at the top level intersect like a bare `INDEX`. A direct `INDEX` argument of `SUM`, `AVERAGE`, `MIN`, `MAX`, `AND` or `OR` is a reference and does not intersect.
- **Not converted:** an `INDEX` that can select a whole row or column and is passed through `IF`, `IFERROR` or `CHOOSE` inside an aggregate (`SUM(IFERROR(INDEX(M5:M7,0),0))`) is listed as "not converted" with reason `INDEX_PASSED_THROUGH` (`ghost/converter/subset.py`). The Referee keeps it as a reference, and `IFERROR` gives 24 on row 6 but 0 on row 9. Ghost does not reproduce this.
- **Excel:** not checked. There is no Excel in the development environment. Excel 365 spills a whole row or column (a dynamic array) instead of intersecting, so a workbook saved by Excel 365 can hold a spilled result where the Referee intersects. Legacy Excel's implicit intersection is documented behaviour, not measured here.
- **Golden tests:** `tests/golden/test_index_zero_golden.py` checks the single column inside and outside, the single row by column and the single cell (R-30) against the Referee and the generated code.

### Found, not fixed

- **Index past the end differs by LibreOffice version.** `INDEX(M1:M3,5)`, `INDEX(M5:M7,0,2)`, `INDEX(Q5:R7,4,0)` and similar give `#REF!` on 26.8.3.1 and `#VALUE!` on 7.4.7.2 (the live image). Ghost gives `#REF!`, so on the live site a workbook whose `INDEX` goes past the end shows a mismatch. Excel: not checked. `tests/test_review_semantics.py` (`index_out_of_range`) and `tests/test_index_zero_contexts.py` (`PAST_END`) pin the Referee result per major version and Ghost's `#REF!` on both.
- **`IF` passing a reference into `SUM`.** `SUM(IF(TRUE,N5))` and `SUM(IF(TRUE,INDEX(N5:N7,1)))` with text in N5 give 0 on the Referee and `#VALUE!` in Ghost. The Referee passes the `IF` result to `SUM` as a reference, so `SUM` skips the text; Ghost passes the value. Found in task 3.7; re-measured in task 3.8 with the same result on LibreOffice 26.8.3.1 and 7.4.7.2. Ghost behaved this way before L-03 too. Excel: not checked.

## ROUND with more than 15 significant digits (unverified)

`=ROUND(123456789012345.67,1)` has 17 significant digits. Ghost and the Referee disagree on it, and Excel's result has not been checked. Behaviour is unchanged until the owner confirms Excel's result in Excel for the web.

| Engine | Result (measured 2026-11-24) |
|---|---|
| Referee, LibreOffice 26.8.3.1 (local) | `123456789012345.7` |
| Referee, LibreOffice 7.4.7.2 (image `ghost-local:cp4`) | `123456789012345.7` |
| Ghost runtime `xl_round(Decimal("123456789012345.67"), 1)` | `123456789012346.0` |
| Excel | not verified |

- Ghost normalises the operand to 15 significant digits first (`123456789012346`) and then rounds, so the digit after the decimal point is lost. LibreOffice rounds the value as stored.
- A workbook that rounds values with more than 15 significant digits can show a mismatch against the Referee that is not a translation bug. Do not treat a pass or a fail on such a cell as evidence about Excel.
- Status: deferred, awaiting the owner's Excel check (R-25). After the owner records Excel's result, decide whether Ghost's rule stays, changes, or the case joins the table above.
