# L-03 measurements: `INDEX` with a 0 row or column

Task 3.5 of this spec, Coroner role. Measured 2026-11-24. Every value below was produced by running the probe, nothing is inferred.

- **Probe:** `tests/index_zero_probe.py`. It builds one workbook with openpyxl, reads every probe cell from the Referee (`RefereeClient.read`, which recalculates first), and runs Ghost's generated code (`generate_mapping` with every probe cell as OUTPUT, `emit_module`, `load_compute`) on the same workbook. It prints JSON.
- **Referee, local:** LibreOffice 26.8.3.1 (development Mac). `PYTHONPATH=. .venv/bin/python tests/index_zero_probe.py`. Raw output: `measurements-l03/referee-26.8.3.1-local.json`.
- **Referee, live image:** LibreOffice 7.4.7.2 in `ghost-local:l03`, built from the working tree with `docker build --platform linux/amd64 -t ghost-local:l03 .` and run with `docker run --rm --platform linux/amd64 -v "$PWD/tests/index_zero_probe.py:/probe/index_zero_probe.py:ro" ghost-local:l03 /opt/venv/bin/python /probe/index_zero_probe.py`. Raw output: `measurements-l03/referee-7.4.7.2-docker.json`. Not pushed, not deployed.
- **Ghost:** the unfixed code (R-08 rule in `_index`, `ghost/converter/emit_python.py:197-226`). Ghost's result was identical in both runs.
- **Pinned by:** `tests/test_index_zero_measurement.py` (Referee result for all 69 cases on major versions 7 and 26; Ghost agreement for the 36 cases it already gets right).
- **Excel:** not checked. There is no Excel in the development environment. Excel 365 spills a whole row or column instead of intersecting; that is documented Excel behaviour, not measured here.

## Result

The two LibreOffice versions gave identical results for all 69 cases. Ghost disagrees with the Referee on 33 of them (marked **WRONG**).

## Layout

Sheet `Calc` unless stated. Single column `M5:M7` = 7, 8, 9. Single row `E20:G20` = 21, 22, 23. Grid `Q5:R7` with column Q = 31, 32, 33 and column R = 41, 42, 43. Single cell `T5` = 55. `Z1` = 0. Sheet `Data`: `M5:M7` = 107, 108, 109 and `E20:G20` = 121, 122, 123. All ranges are absolute. A formula placed inside the range it reads would be a circular reference, so "inside" placements share only the row (or only the column) with the range.

## Measurement table

### Single column `M5:M7` (rows 5 to 7), row 0

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| col_r0_above_far | Calc!B3 | `=INDEX($M$5:$M$7,0)` | row 3, above | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0_above_adj | Calc!B4 | `=INDEX($M$5:$M$7,0)` | row 4, just above | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0_top_edge | Calc!B5 | `=INDEX($M$5:$M$7,0)` | row 5 = top edge | 7 | 7 | #VALUE! | **WRONG** |
| col_r0_inside | Calc!B6 | `=INDEX($M$5:$M$7,0)` | row 6, middle | 8 | 8 | #VALUE! | **WRONG** |
| col_r0_bottom_edge | Calc!B7 | `=INDEX($M$5:$M$7,0)` | row 7 = bottom edge | 9 | 9 | #VALUE! | **WRONG** |
| col_r0_below_adj | Calc!B8 | `=INDEX($M$5:$M$7,0)` | row 8, just below | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0_below_far | Calc!B12 | `=INDEX($M$5:$M$7,0)` | row 12, below | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0_inside_right | Calc!X6 | `=INDEX($M$5:$M$7,0)` | row 6, column X right of the range | 8 | 8 | #VALUE! | **WRONG** |
| col_r0c1_inside | Calc!C6 | `=INDEX($M$5:$M$7,0,1)` | row 6 | 8 | 8 | #VALUE! | **WRONG** |
| col_r0c1_outside | Calc!C9 | `=INDEX($M$5:$M$7,0,1)` | row 9 | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0c0_inside | Calc!D6 | `=INDEX($M$5:$M$7,0,0)` | row 6 | 8 | 8 | #VALUE! | **WRONG** |
| col_r0c0_outside | Calc!D9 | `=INDEX($M$5:$M$7,0,0)` | row 9 | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r2c0_outside | Calc!H9 | `=INDEX($M$5:$M$7,2,0)` | row 9 (column 0 on width 1) | 8 | 8 | 8 | ok |
| col_rZ_inside | Calc!I6 | `=INDEX($M$5:$M$7,$Z$1)` | row 6, index 0 from a cell | 8 | 8 | #VALUE! | **WRONG** |
| col_rZ_outside | Calc!I9 | `=INDEX($M$5:$M$7,$Z$1)` | row 9, index 0 from a cell | #VALUE! | #VALUE! | #VALUE! | ok |
| col_r0_plus0_inside | Calc!J6 | `=INDEX($M$5:$M$7,0)+0` | row 6, in arithmetic | 8 | 8 | #VALUE! | **WRONG** |
| col_r0_plus0_outside | Calc!J9 | `=INDEX($M$5:$M$7,0)+0` | row 9, in arithmetic | #VALUE! | #VALUE! | #VALUE! | ok |

### Single row `E20:G20` (columns E to G), column 0

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| row_c0_left_far | Calc!C30 | `=INDEX($E$20:$G$20,0)` | column C, left | #VALUE! | #VALUE! | #VALUE! | ok |
| row_c0_left_adj | Calc!D30 | `=INDEX($E$20:$G$20,0)` | column D, just left | #VALUE! | #VALUE! | #VALUE! | ok |
| row_c0_left_edge | Calc!E30 | `=INDEX($E$20:$G$20,0)` | column E = left edge | 21 | 21 | #VALUE! | **WRONG** |
| row_c0_inside | Calc!F30 | `=INDEX($E$20:$G$20,0)` | column F, middle | 22 | 22 | #VALUE! | **WRONG** |
| row_c0_right_edge | Calc!G30 | `=INDEX($E$20:$G$20,0)` | column G = right edge | 23 | 23 | #VALUE! | **WRONG** |
| row_c0_right_adj | Calc!H30 | `=INDEX($E$20:$G$20,0)` | column H, just right | #VALUE! | #VALUE! | #VALUE! | ok |
| row_c0_right_far | Calc!K30 | `=INDEX($E$20:$G$20,0)` | column K, right | #VALUE! | #VALUE! | #VALUE! | ok |
| row_c0_inside_above | Calc!F15 | `=INDEX($E$20:$G$20,0)` | column F, row 15 above the range | 22 | 22 | #VALUE! | **WRONG** |
| row_r1c0_inside | Calc!F31 | `=INDEX($E$20:$G$20,1,0)` | column F | 22 | 22 | #VALUE! | **WRONG** |
| row_r1c0_outside | Calc!C31 | `=INDEX($E$20:$G$20,1,0)` | column C | #VALUE! | #VALUE! | #VALUE! | ok |
| row_r0c0_inside | Calc!F32 | `=INDEX($E$20:$G$20,0,0)` | column F | 22 | 22 | #VALUE! | **WRONG** |
| row_r0c0_outside | Calc!C32 | `=INDEX($E$20:$G$20,0,0)` | column C | #VALUE! | #VALUE! | #VALUE! | ok |
| row_r0c2_outside | Calc!C33 | `=INDEX($E$20:$G$20,0,2)` | column C (row 0 on height 1) | 22 | 22 | 22 | ok |

### Grid `Q5:R7` (rows 5 to 7, columns Q to R)

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| grid_r0c2_above | Calc!N4 | `=INDEX($Q$5:$R$7,0,2)` | row 4, above | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0c2_top_edge | Calc!N5 | `=INDEX($Q$5:$R$7,0,2)` | row 5 = top edge | 41 | 41 | #VALUE! | **WRONG** |
| grid_r0c2_inside | Calc!N6 | `=INDEX($Q$5:$R$7,0,2)` | row 6, middle | 42 | 42 | #VALUE! | **WRONG** |
| grid_r0c2_bottom_edge | Calc!N7 | `=INDEX($Q$5:$R$7,0,2)` | row 7 = bottom edge | 43 | 43 | #VALUE! | **WRONG** |
| grid_r0c2_below | Calc!N8 | `=INDEX($Q$5:$R$7,0,2)` | row 8, below | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0c1_inside | Calc!O6 | `=INDEX($Q$5:$R$7,0,1)` | row 6 | 32 | 32 | #VALUE! | **WRONG** |
| grid_r0c1_outside | Calc!O9 | `=INDEX($Q$5:$R$7,0,1)` | row 9 | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r2c0_left_adj | Calc!P30 | `=INDEX($Q$5:$R$7,2,0)` | column P, just left | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r2c0_left_edge | Calc!Q30 | `=INDEX($Q$5:$R$7,2,0)` | column Q = left edge | 32 | 32 | #VALUE! | **WRONG** |
| grid_r2c0_right_edge | Calc!R30 | `=INDEX($Q$5:$R$7,2,0)` | column R = right edge | 42 | 42 | #VALUE! | **WRONG** |
| grid_r2c0_right_adj | Calc!S30 | `=INDEX($Q$5:$R$7,2,0)` | column S, just right | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0c0_row_inside | Calc!U6 | `=INDEX($Q$5:$R$7,0,0)` | row 6 inside, column U outside | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0c0_col_inside | Calc!Q31 | `=INDEX($Q$5:$R$7,0,0)` | column Q inside, row 31 outside | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0c0_neither | Calc!U31 | `=INDEX($Q$5:$R$7,0,0)` | row and column outside | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0_row_inside | Calc!U7 | `=INDEX($Q$5:$R$7,0)` | one argument, row 7 inside | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0_col_inside | Calc!Q32 | `=INDEX($Q$5:$R$7,0)` | one argument, column Q inside | #VALUE! | #VALUE! | #VALUE! | ok |
| grid_r0_neither | Calc!U32 | `=INDEX($Q$5:$R$7,0)` | one argument, outside | #VALUE! | #VALUE! | #VALUE! | ok |

### Range on another sheet

The formula cell's own row (or column) number is compared with the other sheet's range coordinates.

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| xsheet_col_r0_inside | Calc!Y6 | `=INDEX(Data!$M$5:$M$7,0)` | Calc row 6, Data rows 5-7 | 108 | 108 | #VALUE! | **WRONG** |
| xsheet_col_r0_outside | Calc!Y9 | `=INDEX(Data!$M$5:$M$7,0)` | Calc row 9 | #VALUE! | #VALUE! | #VALUE! | ok |
| xsheet_row_c0_inside | Calc!F35 | `=INDEX(Data!$E$20:$G$20,0)` | Calc column F, Data columns E-G | 122 | 122 | #VALUE! | **WRONG** |
| xsheet_row_c0_outside | Calc!C35 | `=INDEX(Data!$E$20:$G$20,0)` | Calc column C | #VALUE! | #VALUE! | #VALUE! | ok |
| xsheet_back_inside | Data!B6 | `=INDEX(Calc!$M$5:$M$7,0)` | Data row 6, Calc rows 5-7 | 8 | 8 | #VALUE! | **WRONG** |
| xsheet_back_outside | Data!B9 | `=INDEX(Calc!$M$5:$M$7,0)` | Data row 9 | #VALUE! | #VALUE! | #VALUE! | ok |

### Single cell `T5` (R-30)

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| cell_rng_r0_same_row | Calc!AA5 | `=INDEX($T$5:$T$5,0)` | row 5 | 55 | 55 | 55 | ok |
| cell_rng_r0_other_row | Calc!AA9 | `=INDEX($T$5:$T$5,0)` | row 9 | 55 | 55 | 55 | ok |
| cell_ref_r0_same_row | Calc!AB5 | `=INDEX($T$5,0)` | row 5 | 55 | 55 | 55 | ok |
| cell_ref_r0_other_row | Calc!AB9 | `=INDEX($T$5,0)` | row 9 | 55 | 55 | 55 | ok |
| cell_rng_r0c0_same_row | Calc!AC5 | `=INDEX($T$5:$T$5,0,0)` | row 5 | 55 | 55 | 55 | ok |
| cell_rng_r0c0_other_row | Calc!AC9 | `=INDEX($T$5:$T$5,0,0)` | row 9 | 55 | 55 | 55 | ok |

### Inside `SUM` and `AVERAGE` (array context)

| Case | Formula cell | Formula | Placement | LO 26.8.3.1 | LO 7.4.7.2 | Ghost (unfixed) | |
|---|---|---|---|---|---|---|---|
| col_r0_sum_inside | Calc!K6 | `=SUM(INDEX($M$5:$M$7,0))` | row 6 inside | 24 | 24 | #VALUE! | **WRONG** |
| col_r0_sum_outside | Calc!K9 | `=SUM(INDEX($M$5:$M$7,0))` | row 9 outside | 24 | 24 | #VALUE! | **WRONG** |
| col_r0_avg_inside | Calc!L6 | `=AVERAGE(INDEX($M$5:$M$7,0))` | row 6 inside | 8 | 8 | #VALUE! | **WRONG** |
| col_r0_avg_outside | Calc!L9 | `=AVERAGE(INDEX($M$5:$M$7,0))` | row 9 outside | 8 | 8 | #VALUE! | **WRONG** |
| row_c0_sum_inside | Calc!F34 | `=SUM(INDEX($E$20:$G$20,0))` | column F inside | 66 | 66 | #VALUE! | **WRONG** |
| row_c0_sum_outside | Calc!C34 | `=SUM(INDEX($E$20:$G$20,0))` | column C outside | 66 | 66 | #VALUE! | **WRONG** |
| grid_r0c2_sum_inside | Calc!V6 | `=SUM(INDEX($Q$5:$R$7,0,2))` | row 6 inside | 126 | 126 | #VALUE! | **WRONG** |
| grid_r0c2_sum_outside | Calc!V9 | `=SUM(INDEX($Q$5:$R$7,0,2))` | row 9 outside | 126 | 126 | #VALUE! | **WRONG** |
| grid_r2c0_sum_outside | Calc!S33 | `=SUM(INDEX($Q$5:$R$7,2,0))` | column S outside | 74 | 74 | #VALUE! | **WRONG** |
| grid_r0c0_sum | Calc!W6 | `=SUM(INDEX($Q$5:$R$7,0,0))` | row 6 | 222 | 222 | #VALUE! | **WRONG** |

## Rules read from the table

These describe what the Referee did on the cases above. They are not claims about cases that were not measured.

1. **Single column, row 0** (with the column omitted, 1 or 0): the element on the formula cell's row when that row lies in the range's rows, edges included. Otherwise `#VALUE!`. The formula cell's column does not matter (`X6` gives 8).
2. **Single row, column 0** (with the row omitted, 1 or 0): the element in the formula cell's column when that column lies in the range's columns, edges included. Otherwise `#VALUE!`. The formula cell's row does not matter (`F15`, above the range, gives 22).
3. **Grid, one index 0 and the other non-zero:** the non-zero index picks one column (or row) of the grid, then rule 1 (or 2) applies to it. `INDEX(Q5:R7,0,2)` on rows 5, 6, 7 gives 41, 42, 43; `INDEX(Q5:R7,2,0)` in columns Q and R gives 32 and 42.
4. **Grid, both indexes 0, or a single index 0:** `#VALUE!` in every placement measured (row inside, column inside, neither). A placement inside both the rows and the columns would be inside the range (a circular reference) and was not measured.
5. **A 0 on a dimension of length 1** selects that row or column wherever the formula is (`INDEX(M5:M7,2,0)` gives 8 from row 9; `INDEX(E20:G20,0,2)` gives 22 from column C). Ghost already does this.
6. **Single cell (R-30):** its value, wherever the formula is. Ghost already does this.
7. **Another sheet:** rules 1 and 2 compare the formula cell's row or column number with the range's coordinates on the other sheet, in both directions (`Calc!Y6` reads `Data!M6`; `Data!B6` reads `Calc!M6`).
8. **A computed 0** (`$Z$1` holding 0) behaves like a literal 0. **Arithmetic** (`+0`) on the result behaves like the bare `INDEX`.
9. **Inside `SUM` and `AVERAGE`:** no intersection. The aggregate runs over the whole selected row, column or grid, wherever the formula is (`SUM` of the column 24 from rows 6 and 9; `AVERAGE` 8 from row 9, where no intersection exists, so 8 is the mean and not the element). Ghost gives `#VALUE!` for all ten.

## Where Ghost is wrong (33 cases)

- 23 single-value cases inside the row or column span: rules 1, 2, 3 and 7, including the edges, the computed 0 and the `+0` case. Ghost returns `#VALUE!` because `_index` has no range origin and no formula position.
- 10 aggregate cases (rule 9). Ghost's `INDEX` returns one value, so `SUM(INDEX(...,0))` cannot see the whole row or column.

Ghost agrees on the other 36: every placement outside the span, rule 4 (grid with both or a single 0), rules 5 and 6.

## Notes for tasks 3.6 to 3.8

- Property 4 in `design.md` covers rules 1, 2 and 6. Rules 3, 7, 8 and 9 were found by this measurement and are not in Property 4 or in the L-03 disjunct of `isBugCondition` (which names single-column and single-row ranges only). The fix needs them, or the cells they apply to must be "not converted" with cell and reason.
- Rule 9 needs `INDEX` to return a range inside an aggregate, or the formula to be "not converted". The choice is for task 3.7 or the owner.
- The "Number-to-text (R-08)" bullet in `.kiro/steering/excel-semantics.md` that says `INDEX(range,0)` "on a multi-cell range gives `#VALUE!` in a single-cell formula" is contradicted by rules 1 to 3 and 9. Task 3.8 replaces it.

## Not checked

- Excel (desktop, web or 365). Excel 365 spills instead of intersecting; Excel's result was not checked for any case.
- A formula inside both the rows and the columns of a grid (circular reference).
- Whole-column or whole-row references (`M:M`, `20:20`), ranges given by defined names, `INDEX` with an area number, and `INDEX` with 0 inside other functions (`IF`, `ROUND`, `MIN`, `MAX`, `MATCH`).
- A computed 0 inside an aggregate.
- Array-entered (CSE) formulas. openpyxl wrote every probe formula as a normal formula.
