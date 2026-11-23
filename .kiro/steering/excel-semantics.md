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
