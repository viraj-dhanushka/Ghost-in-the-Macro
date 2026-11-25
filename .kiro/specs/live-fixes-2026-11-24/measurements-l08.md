# L-08 baseline measurements (task 5.6)

Measurement only. No engine code changed. Run on 25 Nov 2026, LibreOffice 26.8.3 (`GHOST_SOFFICE=~/Applications/LibreOffice.app/Contents/MacOS/soffice`), seed 20261204 (default).

Reproduce (repo root):

```
.venv/bin/python samples/make_scenarios.py /tmp/l08/scenarios.xlsx
.venv/bin/python -m ghost.cli convert /tmp/l08/scenarios.xlsx --migration /tmp/l08/mig \
    --inputs Model!B2,Model!B3,Model!E2 --outputs Model!B19,Model!B20
.venv/bin/python -m ghost.cli mutate /tmp/l08/mig --mode faithful          # ~13 s
.venv/bin/python .kiro/specs/live-fixes-2026-11-24/measure_l08_sweep.py /tmp/l08/mig /tmp/l08/scenarios.xlsx --referee
.venv/bin/python .kiro/specs/live-fixes-2026-11-24/measure_l08_survivors.py /tmp/l08/mig/proof-report.json
```

Raw outputs: `measurements-l08-sweep.json`, `measurements-l08-survivors.json`.

## 1. Real run against the Referee

| Item | Value |
|---|---|
| Verification (Faithful) | passed, 0 mismatches |
| Mutation score | **54 / 132 killed** (78 survivors). Live was 55/132; the one difference is L-07 dropping the -1 cases |
| cases_generated | 300 |
| cases_targeted | **0** (as expected, no IF to flip) |
| distinct cases (verification) | 152 |
| distinct cases (per mutant, from survivor reasons) | 58 |
| Tested domains (report) | dependants 0..10000, gross_income 0..60000, other_deductions 0..10000, all integers |
| Wall time | about 13 s locally |

Survivors by operator: constant_plus_one 37, constant_minus_one 31, rounding_mode 10 (total 78).
Killed: constant_minus_one 30, constant_plus_one 24 (total 54). Every rounding_mode mutant survived.

## 2. Which rows ever win?

Sheet: scenario rows are Model rows 6..15 (row n is scenario n-5). B19 = `INDEX(A6:A15, MATCH(B18, H6:H15, 0))` with B18 = `MAX(-cost)`, so the lowest net cost wins and a tie goes to the first row.

Method (`measure_l08_sweep.py`): exact Decimal replica of `F{r}`. First checked against the transpiled `logic.py` on 3000 cases: **0 mismatches**. Then two sweeps:

- Default boxes (allowance E3 fixed at 800, as in the real run): 3,025 grid cases (gross 0..60000 step 2500, dependants {0,1,2,3,5,10,20,50,100,1000,10000}, other_deductions 0..10000 step 1000) plus 300,000 seeded random cases (50% uniform, 40% log-uniform, 10% edge values).
- Allowance also varied 0..10000 as if E3 were a fourth box: 18,150 grid plus 600,000 random cases.

| Row | Scenario | Can win? (default boxes) | Wins in 300k random + grid | Sample input where it wins (gross, dependants, other_deductions) | Referee B19 / B20 at that input |
|---|---|---|---|---|---|
| 6 | Flat 20 | yes (only at cost 0, by tie-break) | 98,654 | (0, 0, 0) | Flat 20 / 0 |
| 7 | Flat 25 + deduction | yes | 1,242 | (2500, 0, 1000) | Flat 25 + deduction / 0 |
| 8 | Low rate, high fee | **never** | 0 | none | n/a |
| 9 | Credit A | yes | 16,714 | (2500, 0, 2000) | Credit A / -25 |
| 10 | Credit B | yes | 172,701 | (7500, 0, 7000) | Credit B / -350 |
| 11 | Deduction heavy | yes (rare) | 216 | (5000, 0, 0) | Deduction heavy / 300 |
| 12 | Hybrid | **never** | 0 | none | n/a |
| 13 | Premium | **never** | 0 | none | n/a |
| 14 | Family | yes | 13,498 | (2500, 0, 0) | Family / 100 |
| 15 | Minimal | **never** | 0 | none | n/a |

The Referee agreed with the replica on all six first-win inputs (B19 name and B20 value). The second sweep (allowance varied) gives the same winning set {6, 7, 9, 10, 11, 14} and the same never-winning set {8, 12, 13, 15}; its sample inputs and counts are in `measurements-l08-sweep.json`.

"Never" is a sampling result (about 300k to 600k cases plus the grid), not a proof. For rows 8, 12, 13, 15 it is also plausible by inspection: each has a fixed fee of 1500 or more or a rate and fee that Credit B / Flat 20 undercut at every income.

Row 6 wins only where its cost is exactly 0 (taxable income 0), so its rate never affects a winning output.

## 3. Survivor table (operator, cell, row)

All 78 survivors, grouped. Row = cell row (scenario row). "Win" = the row can win somewhere (section 2).

| Cell | Survivors (operator ×count) | Row can win? |
|---|---|---|
| B6 | plus_one | win |
| B7, B9, B11 | plus_one each | win |
| B8, B12, B13, B15 | plus_one each | never |
| C6 | plus_one | win |
| C7, C9, C11 | plus_one, minus_one each | win |
| C8, C12, C13, C15 | plus_one, minus_one each | never |
| D11 | minus_one | win |
| D8, D12, D13, D15 | minus_one each | never |
| E11 | plus_one, minus_one | win |
| E8, E12, E13, E15 | plus_one, minus_one each | never |
| F6 | rounding_mode, plus_one, minus_one | win |
| F7 | rounding_mode, plus_one, minus_one | win |
| F9 | rounding_mode, plus_one, minus_one | win |
| F10 | rounding_mode, plus_one | win |
| F11 | rounding_mode, plus_one ×2, minus_one ×2 | win |
| F14 | rounding_mode, plus_one ×2, minus_one | win |
| F8, F12, F13, F15 | rounding_mode, plus_one ×2, minus_one ×2 | never |

Each F cell holds two constants (the `MAX` floor 0 and the `ROUND` digits 2), so two plus_one or two minus_one survivors on one F cell are the two constants.

Not survivors (all killed): the cells of row 10 (B, C, D, E), D6, D7, D9, D14, E3, E6, E7, E9, E14 and others where the changed value always moves the winner.

## 4. Groups

### (a) vs (b), by "row can win" (what the task asked)

| Group | Count |
|---|---|
| (a) constants on rows that can win somewhere in the domain (6, 7, 9, 10, 11, 14) | **34** |
| (b) constants on rows that never win (8, 12, 13, 15) | **44** |
| Total | 78 |

### Refinement: can any input in the domain separate the mutant from the original?

(a) is not all killable. The survivor script rebuilds each mutant on an exact integer replica and searches the same sweep (grid plus 200,000 random cases) for any input where B19 or B20 changes.

| Subgroup | Count |
|---|---|
| (b) never-win rows, no input changes any output | 44 (0 killable) |
| (a) win rows, a separating input exists (**a targeted search could kill**) | **19** |
| (a) win rows, no input changes any output | 15 |
| Total | 78 |

The 15 in (a) with no separating input are:
- 6 `rounding_mode` mutants on F6, F7, F9, F10, F11, F14. Every cost is exact to the cent (integer income times a rate with 2 decimals), so rounding mode can't change a value. Equivalent mutants.
- 5 ROUND digits 2→3 mutants on F7, F9, F10, F11, F14. Same reason.
- 1 ROUND digits 2→1 mutant on F11 (inferred from counts, see caveats).
- 2 F6 survivors (plus_one, minus_one) and B6 plus_one: row 6 only wins at cost 0, so its floor, digits and rate never change an output.
- (6 + 5 + 1 + 3 = 15.)

Killable-by-search examples (gross, dependants, other_deductions), first found:

| Mutant | Input that separates it |
|---|---|
| B7 +1 (rate) | (3087, 1, 21) |
| B9 +1 | (5000, 1, 3000) |
| B11 +1, C11 +1 | (7500, 3, 0) |
| C6 +1 | (6, 0, 5) |
| C7 -1 | (5000, 0, 3000) |
| C9 -1 | (5000, 0, 4000) |
| C11 -1, D11 -1, E11 ±1 | (5000, 0, 0) |
| F11 floor -1 | (6289, 2, 2) |
| F14 digits -1 | (35526, 1, 1118) |
| F7 digits -1 | (2244, 0, 1) |
| F9 digits -1 | (3839, 6146, 2) |

(These separate on the replica. They were not each replayed on the Referee.)

## 5. What this means for 5.7

- Best case for a targeted search: kill all 19 → **73 / 132 (55%)**. The other 59 survivors (44 on never-winning rows, 15 equivalent) can't be killed by any input in the domain, so 5.7 alone can't get the score much above half.
- The 44 on rows 8, 12, 13, 15 are exactly the case task 5.8's sentence describes. The 15 equivalent mutants on winning rows (rounding mode, ROUND digits +1, row 6) are a different reason: the changed constant can't alter any value. A report sentence limited to "rows that never become the best result" would cover 44 of the 59, not all.
- The 19 killable ones need inputs near specific winner switches (e.g. income 5000 with no deductions, 3087/1/21). The default 300 random cases plus 58 distinct mutation cases don't reach them. A search that varies gross_income, dependants and other_deductions and keeps cases where the winning row changes, aimed at each row's win region, should find them.
- Winner distribution is skewed: row 10 wins about 58% of random cases, rows 6, 9, 14 most of the rest, rows 7 and 11 under 1% each. Rows 7 and 11 are the hardest to hit randomly.
- Also true with allowance E3 varied: same winning rows. E3 isn't a default box, so the killable count above is for the default boxes only.

## 6. Caveats

- "No input" means none found in the grid plus 200k random cases (survivor script) or 300k to 600k (sweep script). It is exact for the 44 never-win rows by the sweep, and exact for the equivalent rounding mutants by arithmetic. It is a search result for B6 and the row-6 constants.
- For F cells the report doesn't say which constant a mutant changed. The killable count for F cells is the number of separable variants minus the variants already killed, so it is exact in total but not attributed to a specific mutant id.
- Mutation operators were modelled as constant ±1 (rate stored in percent, so a rate +1 is 100 points). That matches which cells were killed in the real run (e.g. D+1 kills everywhere), but the script doesn't read the engine's operator code.
- Not done by this task: recording the "before" score in `docs/KIRO_USAGE.md` (the task text lists it, but this request was measurement only). Nothing committed, no AWS.
