# Bugfix Requirements Document

## Introduction

The live test of 24 November 2026 (`docs/LIVE_TEST_REPORT_2026-11-24.md`) ran against the deployed build (image pushed 18:08 IST, task definition revision 4, LibreOffice 7.4.7.2). It found four wrong results (L-02 to L-05) and three polish issues (L-06 to L-08). Every wrong result that could be checked locally (L-02, L-03, L-04) also fails locally on LibreOffice 26.8.3, so these are code bugs, not deployment problems. L-05 was not checked locally.

The wrong results hurt the proof Ghost exists to give. A job crashes and loses its report when an Excel error value reaches a mismatch or a mutant's counterexample (L-02). `INDEX(range,0)` disagrees with the Referee when the formula sits inside the range's rows (L-03). A tier rule on a calculated cell is never tested at its exact boundary, so a `>=`→`>` mutant survives (L-04). A not-converted output is pre-checked and then reported as a "translation bug" (L-05). The polish issues make the report harder to read: the boundary table puts values in the wrong columns (L-06), survivor reasons and the "Tested domains" table describe different case sets (L-07), and the scenarios sample shows 55 of 132 mutants killed with no explanation (L-08).

`docs/KIRO_FIX_PROMPT_LIVE_2026-11-24.md` is the authoritative source. Each requirement below matches one finding. The defect clause (1.x) and the expected-behaviour clause (2.x) share a number, and each 2.x clause carries the prompt's "Done when" text as its acceptance criteria. Clauses 3.x hold the demo storyline, mutation scores, suite baseline, guardrails and process rules that must not change. Phase 1 is L-02 to L-05, in that order, because the web checks for L-03 and L-05 need reports that can be written (L-02). Phase 2 is L-06 to L-08.

## Bug Analysis

### Current Behavior (Defect)

1.1 (L-02) WHEN an `ExcelError` value from `ghost/runtime/excel.py` reaches a mismatch's inputs, expected or actual values, a mutant's counterexample, or any other report field that holds engine values (for example, sheet `Calc` with `B1` = 4, `M1:M3` = 7, 8, 9, `B4` = `=INDEX(M1:M1,0)`, input `Calc!B1`, output `Calc!B4`, where a mutant such as `INDEX(M1:M1,1+1)` gives `#REF!`) THEN the system raises `TypeError: Object of type ExcelError is not JSON serializable` in `report_to_json`, writes no report (`report.json` and `report.html` return 404), and the web panel says "Verification found mismatches." even when the baseline passed.

1.2 (L-03) WHEN `=INDEX(M1:M3,0)` is placed in a cell whose row lies inside the rows of `M1:M3` (for example `B3`, row 3) THEN the system returns `#VALUE!` while the Referee returns 9 (LibreOffice 26.8.3 locally and 7.4.7.2 live), because Ghost ignores implicit intersection.

1.3 (L-04) WHEN a tier rule compares a calculated cell with a threshold (sheet `Calc`: `B2` Quantity = 3, `B3` Price = 25.5, `B4` = `=B2*B3`, `B5` = `=IF(B4>=500,"Gold","Standard")`, default boxes B2, B3 → B5) THEN the system reports only brackets (price 166.666/166.667, quantity 19/20) with no exact hit at Total = 500, never records an exact hit for integer inputs, and the `flip_comparison` mutant on B5 (`>=`→`>`) survives with "no difference found on 62 distinct cases".

1.4 (L-05) WHEN the autopsy lists a cell as "not converted" (sheet `Calc`: `B2` Quantity = 30, `E1` Bulk level = 50, names `Bulk` = `Calc!$E$1` and `Dyn` = `OFFSET(Calc!$E$1,0,0)`, `C2` = `=Bulk*2`, `C3` = `=IF(B2>=Bulk,"bulk","small")`, `C4` = `=Dyn*2`) THEN the system still offers and pre-checks C4 as an output, and verification fails on the first case as a "translation bug" with actual `None` and mutation "not checked".

1.5 (L-06) WHEN the HTML report renders the boundary table (`ghost/report/html.py:191-201`) THEN the system puts the flip text "condition flip: 49 (one side), 50 (other side)" under "Owner of threshold" and leaves "Change-point bracket" empty on flip rows, shows raw JSON such as `[{"first_changed": 50, "last_unchanged": 49}]` on threshold rows, shows the change point (51) as the Threshold of the `B9` flip row, and shows "not checked" for exact hits that exist (quantity 50 for `B7`'s `>=50` in the haunted report).

1.6 (L-07) WHEN a report shows both survivor reasons and the "Tested domains" table THEN the system describes two different case sets: survivor reasons say `quantity: integer, min -1` while the table says min 0 (haunted), and survivor reasons say `gross_income … max 60000` while the table says max 10000 (scenarios), because the mutation check runs targeted values 0 and -1 and the sample value as a base even outside an input's declared minimum and maximum.

1.7 (L-08) WHEN the scenarios sample is verified with the default boxes THEN the system reports mutation "55 of 132 killed" with `cases_targeted` 0, because most survivors change the rate, deduction or fee of a scenario that never wins on the tested inputs (so `MAX`, `MIN` and `INDEX`/`MATCH` hide the change), no case is aimed at changing the winning row, and the report does not explain why these survivors exist.

### Expected Behavior (Correct)

2.1 (L-02) WHEN an `ExcelError` value reaches any report field that holds engine values (mismatch inputs, expected and actual values, mutant counterexamples, boundary cases, or any other) THEN the system SHALL serialise it in `report_to_dict` as its error text (for example `"#VALUE!"`), SHALL show the same text in the HTML report, SHALL accept a string in every such place in `proof-report-1.json`, and SHALL use the same path for the MCP tools and the CLI. WHEN a job fails for a reason other than mismatches THEN the panel SHALL say "The report could not be written" with the exception type and SHALL NOT say "Verification found mismatches." or show any server path. Acceptance criteria:
- The L-02 repro (input `Calc!B1`, output `Calc!B4`) gives a downloadable report with Faithful pass for B4 and the mutation score shown.
- A workbook whose mismatch holds an Excel error gives a report that lists the mismatch with `"#VALUE!"` text.
- Tests cover `report_to_json` with `ExcelError` values in a mismatch and in a mutant counterexample, plus one web job.

2.2 (L-03) WHEN `INDEX` gets row 0 on a single-column range, or column 0 on a single-row range, THEN the system SHALL apply implicit intersection the way the Referee does: return the element on the formula cell's row (or column) when that row (or column) lies inside the range, and `#VALUE!` otherwise. The system SHALL keep R-30 (a single-cell range returns its value). Every case (including multi-row and multi-column ranges, a formula on another sheet from the range, and any other case found) SHALL be measured against the Referee, not assumed, and any case Ghost cannot match SHALL be "not converted" with cell and reason. `.kiro/steering/excel-semantics.md` SHALL note that Excel 365 spills instead and that Excel's result was not checked. Acceptance criteria:
- Golden tests cover: the formula on a row inside the range (value); the formula on a row outside the range (`#VALUE!`); a single-row range by column; a single-cell range (R-30).
- Each golden case agrees with the Referee.
- The L-02 repro extended with `B3` = `=INDEX(M1:M3,0)` as an output passes Faithful.

2.3 (L-04) WHEN a condition flips on one numeric input THEN the system SHALL retry the search with the other numeric inputs set to small values within their domains (for example 1, 2, 4, 5, 10) so that an exact equality can be reached (1 × 500), SHALL record an exact hit for integer inputs when the `above` or `below` value makes the comparison an equality as confirmed by the trace hook (never inferred), SHALL send the exact-hit cases to both the verifier and the mutation check, SHALL keep the evaluation budget bounded, and SHALL say in `boundary_notes` when the search was cut short. Acceptance criteria:
- On the L-04 repro, the boundaries list B5's condition with an exact hit where Total = 500.
- The `flip_comparison` mutant on B5 is killed.
- The existing tier tests in `tests/test_review_proof_strength.py` still pass.
- The haunted demo invariants (clauses 3.1 to 3.5) still hold. If haunted gains targeted cases, the expected counts in the docs are updated from real output.

2.4 (L-05) WHEN the autopsy lists a cell as "not converted", or as "not verifiable as-is" (volatile or external constructs), THEN the system SHALL neither offer nor pre-check it as an output in the web autopsy (`web/flow.py` `_describe`), the CLI defaults or the MCP defaults. WHEN a user or MCP caller selects such a cell anyway THEN the system SHALL reject the request with a 422 (web), an `invalid_argument` error (MCP) or a CLI error, each naming the cell and the reason, and SHALL NOT call it a translation bug. The proof report SHALL list the workbook's not-converted cells with cell and reason. Acceptance criteria:
- The L-05 repro's default boxes are B2 (and E1 if the heuristics keep it) → C2 and C3.
- Verify with the default boxes passes Faithful, and the report lists C4 as not converted.
- Choosing C4 explicitly gives the documented behaviour, covered by a test.

2.5 (L-06) WHEN the HTML report renders the boundary table THEN the system SHALL put brackets in the "Change-point bracket" column as readable text (for example "49 → 50") for both flip rows and threshold rows, SHALL show the real threshold constant in the Threshold column or "calculated" when there is none, SHALL never show raw JSON, and SHALL fill "Exact hits" from clause 2.3. Acceptance criteria:
- A test renders a report with both kinds of boundary row (threshold and condition flip) and checks each column's text.
- The haunted report shows quantity 50 as an exact hit.

2.6 (L-07) WHEN targeted values are generated for verification or the mutation check THEN the system SHALL clamp them to each `IOSpec` minimum and maximum, keeping negative cases only where the domain allows negatives, and SHALL make survivor reasons and the "Tested domains" table describe the same set of cases (or label them clearly, for example "verification cases" and "mutation cases"). Acceptance criteria:
- For haunted, discount and scenarios, no survivor reason mentions a value outside the domain shown in the report.
- A test checks this.

2.7 (L-08) WHEN an output is chosen by `MAX`, `MIN` or `MATCH` THEN the system SHALL search for inputs that change which row wins (for example by varying `gross_income`, `dependants` and `other_deductions` across their domains and keeping cases where the selected scenario changes), SHALL feed those cases to the verifier and the mutation check, and SHALL report the real resulting score. WHEN survivors still cannot change any output THEN the report's mutation section SHALL explain this in one plain sentence (for example "These constants belong to rows that never become the best result on the tested inputs, so changing them doesn't change any output."). The system SHALL NOT remove mutants or change the score formula. Acceptance criteria:
- The scenarios score improves with cases that change the winning scenario, or the report explains the remaining survivors.
- A test covers whichever was done.
- `docs/KIRO_USAGE.md` records the before and after scores.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the discount sample runs through `scripts/demo.sh <temp dir>` THEN the system SHALL CONTINUE TO pass Faithful.

3.2 WHEN the haunted sample is analysed THEN the system SHALL CONTINUE TO raise F-001 (operator conflict on `Calculator!B2` against 50: `Calculator!B7` uses `>=`, `Calculator!B9` uses `>`).

3.3 WHEN the haunted sample is verified in Faithful mode THEN the system SHALL CONTINUE TO pass with 0 mismatches.

3.4 WHEN D-001 ("bulk means 50 or more") is recorded and the haunted sample is verified in Intended mode THEN the system SHALL CONTINUE TO pass with exactly one mismatch, classified "expected by decision" (F-001, D-001), whose minimal counterexample is quantity = 50 with Referee 6.0 and new code 0.

3.5 WHEN the mutation check runs on the haunted and discount samples THEN the system SHALL CONTINUE TO kill at least 33 of 35 (haunted) and 31 of 33 (discount) mutants. A score may rise. It SHALL NOT fall, and the mutant totals SHALL NOT drop because mutants were removed or hidden.

3.6 WHEN the full suite runs (`.venv/bin/python -m pytest -q`) at the end of each phase THEN the system SHALL CONTINUE TO have 0 failed tests, starting from the baseline `415 passed, 2 skipped`. The counts SHALL be recorded at each checkpoint, and no existing test SHALL be weakened or deleted.

3.7 WHEN any fix touches values, reports, unsupported constructs or volatile constructs THEN the system SHALL CONTINUE TO obey the Ghost guardrails: no invented values, "not checked" for a check that did not run, "not converted" with cell and reason for unsupported constructs, "not verifiable as-is" for volatile and external constructs, Decimal for money with floats converted by `Decimal(repr(x))`, Excel rounding, and no macros from uploads.

3.8 WHEN the mutation check reports a score THEN the system SHALL CONTINUE TO use the current score formula (killed over generated) with every generated mutant counted, and survivor reasons SHALL CONTINUE TO say "no difference found on N distinct cases" and never claim equivalence.

3.9 WHEN an output is an Excel error on both sides (for example `=10/B1` at B1 = 0) THEN the system SHALL CONTINUE TO pass that case.

3.10 WHEN `INDEX` is evaluated with a non-zero row and column, on a single-cell range (R-30: `INDEX(M1:M1,0)`, `INDEX(M1,0)`, `INDEX(M1:M1,0,0)`), or with row 0 on a multi-row range from a formula cell outside the range's rows THEN the system SHALL CONTINUE TO return the current results (the element, the cell's value, and `#VALUE!` respectively).

3.11 WHEN a bundled sample is opened with no not-converted or not-verifiable outputs THEN the system SHALL CONTINUE TO pre-check the same default boxes: discount and haunted `Calculator!B2`, `B3`, `B4` → `Calculator!B11`; scenarios `Model!B2`, `B3`, `E2` → `Model!B19`, `B20`.

3.12 WHEN a report is produced THEN the system SHALL CONTINUE TO validate against `proof-report-1.json` (new fields optional, old reports still valid), produce identical output for identical input, keep server paths out of events, panels and reports, and copy the uploaded workbook without modifying it.

3.13 WHEN work on this spec runs THEN the team SHALL CONTINUE TO make no push, no deploy and no AWS command, and SHALL leave changes uncommitted unless the owner asks. The owner redeploys with `scripts/deploy_ecs_express.sh` and re-runs the live test.

3.14 WHEN a finding is fixed, deferred or not reproduced THEN the team SHALL CONTINUE TO log it: a "Live-test resolution" table at the end of `docs/LIVE_TEST_REPORT_2026-11-24.md` (columns: finding, status as fixed, deferred or not reproduced, what changed, and the test that proves it), and a session entry in `docs/KIRO_USAGE.md` naming the spec, hooks and agents used.

3.15 WHEN a change could alter the demo flow or the haunted case counts, or turns out much larger than described THEN the team SHALL CONTINUE TO stop and ask the owner before continuing.
