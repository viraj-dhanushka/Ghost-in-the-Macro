# Implementation Plan

## Overview

Fixes for live-test findings L-02 to L-08, from `bugfix.md` and `design.md` in this folder. Order: exploration tests (task 1), preservation tests (task 2), Phase 1 wrong results L-02, L-03, L-04, L-05 (task 3), checkpoint (task 4), Phase 2 polish L-06, L-07, L-08 (task 5), checkpoint (task 6), final checks (task 7). Every fix task is required.

## Standing rules for every task

These come from `docs/KIRO_FIX_PROMPT_LIVE_2026-11-24.md` and apply to each task below.

- Test first. Each finding has a test that fails on the current code before its fix. Repro workbooks are built inside the tests with openpyxl into `tmp_path`, never in `/tmp`. Failing tests are marked `@pytest.mark.xfail(strict=True, reason="L-0n ...")`. A fix removes only the marker. Never weaken or delete a test. If a test seems to expect the wrong thing, stop and show the owner the evidence.
- Baseline: `.venv/bin/python -m pytest -q` gives `415 passed, 2 skipped` (417 collected). After task 1 the strict-xfail tests add to the xfailed count. The count falls as fixes land.
- After each finding, and at each checkpoint, run `scripts/demo.sh <temp dir>` and check: discount Faithful pass; haunted F-001 and Faithful 0 mismatches; haunted with D-001 Intended pass with exactly one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0); haunted mutation ≥ 33/35 and discount ≥ 31/33.
- Guardrails win: no invented values, "not checked" for checks that did not run, "not converted" with cell and reason, no dropped or hidden mutants, no change to the score formula.
- No push, no deploy, no AWS command. Leave changes uncommitted.
- Log each finding in the "Live-test resolution" table at the end of `docs/LIVE_TEST_REPORT_2026-11-24.md` (finding, status: fixed, deferred or not reproduced, what changed, test that proves it) and in the session entry in `docs/KIRO_USAGE.md` (spec, hooks, agents).
- **STOP-AND-ASK** marks tasks that could alter the demo flow or the haunted case counts, or grow large. If that happens, stop and ask the owner before continuing.
- **Skeptic** and **Coroner** mark tasks whose result is reviewed by that agent (`.kiro/agents/skeptic.json`, `.kiro/agents/coroner.json`). Record the agent's verdict in `docs/KIRO_USAGE.md`.
- **(PBT)** marks property-based tests. They use Hypothesis with an explicit seed and cite their property number and requirements.
- Dependencies: L-02 (task 3.1 to 3.4) comes before the web checks of L-03 (3.8) and L-05 (3.15). L-06's exact-hit column (5.2) depends on L-04 (3.10 to 3.12). L-08 (5.6 to 5.8) runs after L-07 (5.3 to 5.5) because both use the effective domains.

## Tasks

- [x] 1. Write bug condition exploration tests (L-02 to L-05)
  - **Property 1: Bug Condition** - Live findings L-02 to L-05 give wrong results
  - **CRITICAL**: These tests MUST FAIL on unfixed code. Failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: The tests encode the expected behaviour and will validate the fixes when they pass
  - **GOAL**: Surface counterexamples for each wrong result
  - **Scoped PBT Approach**: The bugs are deterministic, so scope each property to the concrete repro workbooks
  - New file `tests/test_live_findings.py` with openpyxl builders writing into `tmp_path`:
    - `sem_index`: sheet `Calc`, `A1` "Amount", `B1` = 4, `B2` = `=B1*2`, `M1:M3` = 7, 8, 9, `B4` = `=INDEX(M1:M1,0)`; a variant adds `B3` = `=INDEX(M1:M3,0)`
    - `tier`: `A2` "Quantity", `B2` = 3, `A3` "Price", `B3` = 25.5, `A4` "Total", `B4` = `=B2*B3`, `A5` "Tier", `B5` = `=IF(B4>=500,"Gold","Standard")`
    - `sem_names`: `A2` "Quantity", `B2` = 30, `D1` "Bulk level", `E1` = 50, names `Bulk` = `Calc!$E$1` and `Dyn` = `OFFSET(Calc!$E$1,0,0)`, `C2` = `=Bulk*2`, `C3` = `=IF(B2>=Bulk,"bulk","small")`, `C4` = `=Dyn*2`
  - Tests, each strict xfail naming its finding (isBugCondition disjuncts from design):
    - L-02: `report_to_json` on a report with `ExcelError("#VALUE!")` in a mismatch's actual value and `ExcelError("#REF!")` in a mutant counterexample succeeds and shows the text
    - L-02: `sem_index` through FastAPI `TestClient`, input `Calc!B1`, output `Calc!B4`: job done, Faithful pass, `report.json` and `report.html` 200, mutation score present
    - L-02: a job that fails writing the report shows "The report could not be written" with the exception type, and not "Verification found mismatches."
    - L-03: `B3` = `=INDEX(M1:M3,0)` gives the Referee's value (9) in the generated code
    - L-04: `tier` with default boxes B2, B3 → B5: a B5 boundary has an exact hit where Total = 500, and the `flip_comparison` mutant on B5 is killed
    - L-05: `sem_names` autopsy neither offers nor pre-checks `Calc!C4`; `POST /verify` with C4 returns 422 naming `Calc!C4` and the reason
  - Tests needing LibreOffice skip with a message when the Referee is unavailable
  - Run on UNFIXED code
  - **EXPECTED OUTCOME**: Every test xfails (this proves the bugs exist)
  - Document the counterexamples in `docs/KIRO_USAGE.md` (expected: `TypeError: Object of type ExcelError is not JSON serializable`; Ghost `#VALUE!` against Referee 9; exact `None` and surviving `M-…` `flip_comparison` on B5; `translation bug` with actual `None` for `calc_c4`). If one does not fail, record it as "not reproduced" and ask the owner
  - Run the full suite and record the counts (`415 passed, 2 skipped, N xfailed`)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - Demo storyline, mutation scores and pinned behaviour stay intact
  - **IMPORTANT**: Follow observation-first methodology
  - Run `scripts/demo.sh <temp dir>` on UNFIXED code and record the real output: discount Faithful pass; haunted F-001; haunted Faithful 0 mismatches and its case counts (live: 300 generated + 9 targeted, 198 distinct); haunted with D-001 Intended with one "expected by decision" mismatch at quantity = 50, Referee 6.0, new code 0; mutation 33/35 (haunted) and 31/33 (discount)
  - Reuse `tests/test_demo_invariants.py` and `tests/test_mutation_samples.py`. Add only the invariants not yet asserted: Referee 6.0 and new code 0 on the expected mismatch; killed ≥ 33 with total ≥ 35 (haunted) and killed ≥ 31 with total ≥ 33 (discount). Assert floors, not exact case counts, so L-04 and L-07 can change counts without breaking the test
  - Add a test that an output that is an Excel error on both sides (`=10/B1` at B1 = 0) passes
  - Confirm the INDEX cases in `tests/test_review_semantics.py` (R-30 single cell, row 0 outside the range's rows) and the default boxes in `tests/test_web_samples.py` are asserted; add any that are missing
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms the baseline to preserve)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9, 3.10, 3.11_

- [x] 3. Phase 1: wrong results (L-02, L-03, L-04, L-05)

  - [x] 3.1 **Property 3: Excel errors serialise as their text (PBT)** - write the test
    - Hypothesis test: reports whose mismatch values, mutant counterexamples and boundary cases hold `ExcelError` values of every code, mixed with Decimals, strings, booleans and `None`
    - Assert `report_to_json` succeeds, validates against `proof-report-1.json`, shows each error as its code text, the HTML shows the same text, and two calls give identical bytes
    - Expected to fail before task 3.2; mark strict xfail `L-02`
    - _Requirements: 2.1, 3.12_

  - [x] 3.2 Fix L-02: serialise Excel errors in reports
    - Add an `ExcelError` branch to `_jsonable` in `ghost/report/model.py` (`:58-72`) returning `value.code`; route mutant `killed_by` and boundary cases through it
    - Render the same text in `ghost/report/html.py`
    - Check every engine-value field in `ghost/report/schema/proof-report-1.json` accepts a string; widen only where needed, keeping old reports valid
    - Turn green: task 3.1 PBT and the task 1 `report_to_json` test; remove their markers
    - **Coroner**: review the change
    - _Bug_Condition: isBugCondition(X) where an ExcelError is in X.reportEngineValues_
    - _Expected_Behavior: expectedBehavior from design, Property 3_
    - _Preservation: reports without errors are byte-identical; schema backward compatible_
    - _Requirements: 1.1, 2.1, 3.9, 3.12_

  - [x] 3.3 Fix L-02: report a write failure as a write failure
    - In `ghost/cli.py`, wrap report writing so a failure prints `ghost: error: The report could not be written (<ExceptionType>)` and returns a new exit code (for example `EXIT_REPORT_NOT_WRITTEN = 4`). Keep exit 1 for mismatches
    - In `web/jobs.py` (`:278-283`), say "Verification found mismatches." only for exit 1 with a collected report. Otherwise say "The report could not be written (<ExceptionType>)", passed through `scrub_paths`, falling back to the exit code
    - Make the MCP report tools in `mcp_server/server.py` use the same serialiser and return a structured error naming the exception type, never a server path
    - Unit tests: panel text for exit 0, 1 with report, 1 without report, 4, other codes; no server path
    - Turn green: the task 1 panel-text test; remove its marker
    - _Requirements: 1.1, 2.1, 3.12_

  - [x] 3.4 Verify L-02 end to end
    - Turn green: the task 1 `sem_index` B4 web test (Faithful pass, report downloadable, mutation score shown); remove its marker
    - Add a test: a workbook with `=SUM("5",1)` (Referee `#VALUE!`, Ghost 6; see `.kiro/steering/excel-semantics.md`) gives a report listing the mismatch with `"#VALUE!"` text
    - Run the CLI and the MCP `generate_proof_report` path on `sem_index` and confirm a report is written
    - Add the L-02 row to the Live-test resolution table
    - _Requirements: 2.1, 3.14_

  - [x] 3.5 Measure `INDEX(range,0)` on the Referee (L-03)
    - _Depends on: 3.4 (reports must be writable for the web check later)_
    - Build a measurement workbook in a test (openpyxl into `tmp_path`) and read each case from the Referee: single column with row 0 from a formula row inside and outside the range; single row with column 0 from a column inside and outside; single cell (R-30); multi-row and multi-column ranges with row 0, column 0 and both 0, inside and outside; the formula on another sheet from the range; any other case found
    - Record the measured table (LibreOffice 26.8.3 locally; 7.4.7.2 in task 7.4 or "not checked") in `docs/KIRO_USAGE.md`. Do not assume any result
    - **Coroner**: review the measurement table
    - _Requirements: 2.2_

  - [x] 3.6 **Property 4: INDEX with 0 follows implicit intersection (PBT)** - write the test
    - Hypothesis test on the runtime `_index` with range origin and formula position: single-column ranges with row 0, single-row ranges with column 0, single cells, with the rules measured in task 3.5
    - Expected to fail before task 3.7; mark strict xfail `L-03`
    - _Requirements: 2.2, 3.10_

  - [x] 3.7 Fix L-03: implicit intersection in `INDEX`
    - In `ghost/converter/emit_python.py`, emit the range origin in `_Rng` for `INDEX` arguments (`range_arg`, `:414-421`) and pass the formula cell's sheet, row and column at the call site (`:487`)
    - Change `_index` (`:197-226`) to apply the measured rules; keep R-30. Any measured case Ghost cannot reproduce is "not converted" with cell and reason
    - Emitted code stays deterministic
    - Turn green: task 3.6 PBT and the task 1 L-03 test; remove their markers. `tests/test_review_semantics.py` stays green
    - _Bug_Condition: isBugCondition(X) where INDEX(rng,0) sits inside rng's rows or columns_
    - _Expected_Behavior: expectedBehavior from design, Property 4_
    - _Preservation: clause 3.10 cases unchanged_
    - _Requirements: 1.2, 2.2, 3.10, 3.12_

  - [x] 3.8 Golden tests, docs and web check for L-03
    - _Depends on: 3.4, 3.7_
    - Add golden tests (`@pytest.mark.golden`) against the Referee and the generated code: formula on a row inside the range (value); on a row outside (`#VALUE!`); single-row range by column; single-cell range (R-30)
    - Run the `sem_index` variant with outputs `Calc!B3` and `Calc!B4` through `TestClient`: Faithful pass
    - Update `.kiro/steering/excel-semantics.md`: replace the INDEX 0 line with the measured rule table, and note that Excel 365 spills instead and Excel's result was not checked
    - **Coroner**: review the golden results and the semantics note
    - Add the L-03 row to the Live-test resolution table
    - _Requirements: 2.2, 3.14_

  - [x] 3.9 **Property 5: Exact hits are found and confirmed for product and integer thresholds (PBT)** - write the test
    - Hypothesis test on `find_flips` over `a * b op t` (op in `>=`, `>`, `<=`, `<`), a integer, b integer or decimal, domains containing 1, t whole and reachable
    - Assert an exact hit exists, the trace hook confirms the two sides are equal, no unconfirmed exact hit is reported, and a cut-short budget adds a `boundary_notes` entry
    - Keep the existing Property 6 test in `tests/test_property_condition_flip.py` unchanged
    - Expected to fail before task 3.11; mark strict xfail `L-04`
    - _Requirements: 2.3_

  - [x] 3.10 Fix L-04: record integer exact hits
    - In `ghost/verifier/flip.py` (`:370`), replace `exact = None if integer` with a trace-hook check of `below` and `above`; record the value where the two compared sides are equal
    - If the trace hook reports only truth values, extend it to report the compared values; keep generated code deterministic
    - Unit tests: haunted quantity 50 is an exact hit for `B7`'s `>=50` and for `B9`'s `>50`
    - _Requirements: 1.3, 2.3_

  - [x] 3.11 Fix L-04: retry the flip search with small values for the other inputs
    - **STOP-AND-ASK**: if the retry needs more than changes in `flip.py` plus wiring, or slows `scripts/demo.sh` noticeably, stop and ask
    - In `_search` / `find_flips`, when a condition flips on one input, rerun with each other numeric input set to small values from {1, 2, 4, 5, 10} inside its domain; keep cases with a trace-hook-confirmed exact hit
    - Cap extra evaluations per condition and in total with module constants; add a `boundary_notes` entry when a cap is reached
    - Turn green: task 3.9 PBT; remove its marker
    - _Bug_Condition: isBugCondition(X) where X has a calculated-cell condition with no exact hit reachable from sample values_
    - _Expected_Behavior: expectedBehavior from design, Property 5_
    - _Requirements: 1.3, 2.3_

  - [x] 3.12 Wire L-04 exact hits into verification and mutation, then verify
    - **STOP-AND-ASK**: if the haunted case counts or mutation scores change, or the expected-by-decision mismatch changes, stop and show the owner the real output before continuing
    - In `ghost/cli.py` (`_probe_boundaries`, `flip_extra`), add exact-hit cases to `flip_extra` so they reach the verifier (`extra_cases`) and the mutation check (`targeted`); fill each boundary's `exact` field
    - Turn green: the task 1 L-04 test (exact hit at Total = 500, `flip_comparison` on B5 killed); remove its marker
    - Confirm `tests/test_review_proof_strength.py` tier tests and `tests/test_mutation_samples.py` still pass, and the haunted demo invariants hold. If haunted gains targeted cases, update the expected counts in `README.md` and the docs from real output
    - **Skeptic**: review the proof-strength change (exact hits, killed mutant, haunted invariants)
    - Add the L-04 row to the Live-test resolution table
    - _Preservation: clauses 3.1 to 3.5_
    - _Requirements: 1.3, 2.3, 3.4, 3.5, 3.14, 3.15_

  - [x] 3.13 **Property 6: Not-converted and not-verifiable cells are never offered as outputs (PBT)** - write the test
    - Hypothesis test over generated workbooks mixing convertible formulas, OFFSET- or INDIRECT-based names, unsupported functions and volatile functions (NOW, TODAY, RAND, RANDBETWEEN), with dependants
    - Assert the default outputs from `web/flow.py` `_describe`, the CLI and MCP contain none of them, and an explicit request is rejected naming the cell and reason
    - Expected to fail before tasks 3.14 and 3.15; mark strict xfail `L-05`
    - _Requirements: 2.4, 3.11_

  - [x] 3.14 Fix L-05: do not offer not-converted or not-verifiable outputs
    - In `web/flow.py` `_describe` (`:116-153`), remove `find_not_converted` cells and not-verifiable cells (and their dependants) from offered outputs; they stay in the "not converted" and "not verifiable" lists
    - Apply the same rule to the CLI default outputs (`ghost/cli.py`) and the MCP defaults (`mcp_server/server.py`)
    - Turn green: the task 1 L-05 defaults test; the `sem_names` defaults are B2 (and E1 if the heuristics keep it) → C2, C3
    - Confirm the three bundled samples keep their default boxes
    - _Bug_Condition: isBugCondition(X) where a not-converted or not-verifiable cell is offered as an output_
    - _Expected_Behavior: expectedBehavior from design, Property 6_
    - _Preservation: clause 3.11_
    - _Requirements: 1.4, 2.4, 3.11_

  - [x] 3.15 Fix L-05: reject explicit selection and list not-converted cells in the report
    - _Depends on: 3.4_
    - Reject a not-converted or not-verifiable output with 422 in `POST /verify`, `invalid_argument` in MCP, and a `CliError` in the CLI, each naming the cell and the reason. Never classify it as a translation bug
    - Add an optional `not_converted` array (`{cell, reason}`) to the report model, HTML and schema, filled from `find_not_converted`
    - Turn green: task 3.13 PBT and the task 1 explicit-selection test; remove their markers
    - Run `sem_names` with the default boxes through `TestClient`: Faithful pass, report lists `Calc!C4` as not converted
    - **Coroner**: review the autopsy defaults and the not-converted listing
    - Add the L-05 row to the Live-test resolution table
    - _Requirements: 1.4, 2.4, 3.7, 3.12, 3.14_

  - [x] 3.16 Verify the bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Live findings L-02 to L-05 give correct results
    - **IMPORTANT**: Re-run the SAME tests from task 1. Do NOT write new tests
    - Run `.venv/bin/python -m pytest -q tests/test_live_findings.py` and confirm no `xfail` marker remains for L-02 to L-05
    - **EXPECTED OUTCOME**: Tests PASS (confirms the bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.17 Verify preservation tests still pass
    - **Property 2: Preservation** - Demo storyline, mutation scores and pinned behaviour stay intact
    - **IMPORTANT**: Re-run the SAME tests from task 2. Do NOT write new tests
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.9, 3.10, 3.11_

- [x] 4. Checkpoint: Phase 1
  - Run the full suite and record the counts (0 failed)
  - Run `scripts/demo.sh <temp dir>`; check the storyline and record the mutation scores
  - Confirm the Live-test resolution table has rows for L-02 to L-05 and `docs/KIRO_USAGE.md` has the Phase 1 entries, including the Skeptic and Coroner verdicts
  - Ensure all tests pass, ask the user if questions arise
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.14_

- [x] 5. Phase 2: polish (L-06, L-07, L-08)

  - [x] 5.1 Write the L-06 test first
    - _Depends on: 3.10, 3.12 (exact hits exist)_
    - Test that renders a report with a threshold boundary row and a condition-flip row and checks each column's text: Threshold shows the constant or "calculated"; "Change-point bracket" shows "49 → 50" style text; "Owner of threshold" shows only operator ownership; "Exact hits" shows the exact value; no raw JSON anywhere in the table
    - Test that the haunted report shows quantity 50 as an exact hit
    - Mark strict xfail `L-06`; run and confirm it fails
    - _Requirements: 1.5, 2.5_

  - [x] 5.2 Fix L-06: boundary table layout
    - In `ghost/report/html.py` (`:191-201`), move the flip text into the bracket column as "below → above", render threshold-row brackets from `last_unchanged` and `first_changed`, show the real threshold or "calculated", keep only `operator_includes` in "Owner of threshold", and fill "Exact hits" from the `exact` field
    - Turn green: task 5.1 tests; remove the markers. Reports still validate against the schema
    - Add the L-06 row to the Live-test resolution table
    - _Bug_Condition: isBugCondition(X) where X.report.boundaries is not empty_
    - _Requirements: 1.5, 2.5, 3.12, 3.14_

  - [x] 5.3 **Property 7: Targeted values stay inside the effective domain (PBT)** - write the test
    - Hypothesis test over integer and decimal inputs with effective domains (min possibly negative; max absent so `default_max` applies), base values and threshold constants
    - Assert every value from `candidate_inputs` and every flip, exact-hit and selection-change case lies inside the effective domain
    - Add a test over haunted, discount and scenarios: no survivor reason mentions a value outside the domain shown in the report's "Tested domains" table
    - Expected to fail before tasks 5.4 and 5.5; mark strict xfail `L-07`
    - _Requirements: 1.6, 2.6_

  - [x] 5.4 Fix L-07: clamp targeted values to the effective domain
    - **STOP-AND-ASK**: clamping drops the scenarios sample value 60,000 (outside `default_max` 10,000, `ghost/verifier/run.py:53`) and the -1 cases for inputs with min 0. If the haunted or discount mutation score falls, the haunted case counts change, or scenarios loses its sample value, stop and show the owner the real output with the options: clamp as written, widen the effective domain to include the workbook's own sample value, or the labelling alternative
    - Pass each input's effective domain into `candidate_inputs` (`ghost/verifier/coverage.py:77-96`) and the flip search; drop values outside it; keep negatives only where allowed
    - _Requirements: 1.6, 2.6, 3.5, 3.15_

  - [x] 5.5 Fix L-07: one case set for survivor reasons and "Tested domains"
    - Compute the "Tested domains" table (`ghost/report/domains.py`, `ghost/cli.py:646`) and survivor reasons (`ghost/mutation/run.py:145-169`) over the same case set, or label them "verification cases" and "mutation cases"
    - Turn green: task 5.3 tests; remove the markers
    - Confirm the demo invariants and mutation floors; update counts in docs from real output if they changed
    - Add the L-07 row to the Live-test resolution table
    - _Requirements: 1.6, 2.6, 3.5, 3.8, 3.14_

  - [x] 5.6 Measure the L-08 baseline
    - _Depends on: 5.5_
    - Run the scenarios sample with the default boxes (`Model!B2`, `B3`, `E2` → `Model!B19`, `B20`) and record the real mutation score (live: 55/132), the survivor breakdown by operator and cell, and `cases_targeted`
    - Record the "before" score in `docs/KIRO_USAGE.md`
    - _Requirements: 1.7, 2.7_

  - [x] 5.7 Fix L-08: aim cases at changing the winning row
    - **STOP-AND-ASK**: if the targeted search needs more than a new module (for example `ghost/verifier/selection.py`) plus wiring in `ghost/cli.py`, or slows the scenarios job noticeably (live: 30.5 s), stop and ask. Task 5.8 alone then meets the "Done when"
    - Write the test first: on a small two-row `MIN` table built in `tmp_path`, the search finds cases where the selected row changes, and those cases reach the verifier and the mutation check
    - Find outputs chosen by `MAX`, `MIN`, `MATCH` or `INDEX`/`MATCH`; vary numeric inputs (`gross_income`, `dependants`, `other_deductions` for scenarios) across their effective domains with a bounded budget; keep cases where the selected position changes; add them to `extra_cases` and the mutation check's targeted cases
    - Report the real resulting score. Do not remove mutants or change the score formula
    - _Requirements: 1.7, 2.7, 3.8_

  - [x] 5.8 Fix L-08: explain remaining survivors in the report
    - Write the test first: a report with survivors on rows that never win shows the one-sentence explanation in the mutation section (HTML and JSON), and a report without such survivors does not
    - Add the sentence, for example "These constants belong to rows that never become the best result on the tested inputs, so changing them doesn't change any output." Use engine output to decide when it applies; never invent it
    - Record the "after" score in `docs/KIRO_USAGE.md` next to the "before" score
    - Add the L-08 row to the Live-test resolution table
    - _Requirements: 1.7, 2.7, 3.7, 3.8, 3.14_

  - [x] 5.9 Verify preservation tests still pass after Phase 2
    - **Property 2: Preservation** - Demo storyline, mutation scores and pinned behaviour stay intact
    - **IMPORTANT**: Re-run the SAME tests from task 2. Do NOT write new tests
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.9, 3.10, 3.11_

- [x] 6. Checkpoint: Phase 2
  - Run the full suite and record the counts (0 failed)
  - Run `scripts/demo.sh <temp dir>`; check the storyline and record the mutation scores
  - Confirm the Live-test resolution table has rows for L-06 to L-08
  - Ensure all tests pass, ask the user if questions arise
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.14_

- [x] 7. Final checks (report the real output of each)

  - [x] 7.1 Full suite
    - Run `.venv/bin/python -m pytest -q`; record the counts with 0 failed, and confirm no `xfail` marker remains in `tests/test_live_findings.py` except for findings marked deferred in the Live-test resolution table
    - _Requirements: 3.6_

  - [x] 7.2 Demo storyline
    - Run `scripts/demo.sh <temp dir>`; report discount Faithful pass, haunted F-001 and Faithful 0 mismatches, haunted with D-001 Intended pass with one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0), and the mutation scores (at least 33/35 and 31/33)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 7.3 Repro workbooks and scenarios through the web app
    - With FastAPI `TestClient` and the default boxes, run: `sem_index` (L-02, output B4), `sem_index` with B3 (L-03), `tier` (L-04), `sem_names` (L-05), and the scenarios sample
    - Report each one's result, case counts (generated, targeted, distinct), mutation score and boundaries
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_

  - [x] 7.4 Local Docker run
    - Build and run the image locally (LibreOffice 7.4.7.2); do not push or deploy it
    - Run the haunted flow and the L-02 to L-05 repros against the container; also record the 7.4.7.2 column of the L-03 measurement table
    - Write "not checked" for anything that could not run, including the whole task if Docker is not available
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.13_

  - [x] 7.5 Update the README
    - In "Limits and known differences", add L-03 (implicit intersection for `INDEX(range,0)`; Excel 365 spills; Excel's result not checked) and L-05 (not-converted and not-verifiable outputs are not offered and are rejected if requested)
    - Update any case counts that changed, from real output
    - _Requirements: 2.2, 2.4_

  - [x] 7.6 Complete the logs
    - Confirm the Live-test resolution table at the end of `docs/LIVE_TEST_REPORT_2026-11-24.md` has one row per finding L-02 to L-08 (finding, status, what changed, test)
    - Confirm the `docs/KIRO_USAGE.md` session entry names this spec, the hooks that ran, the Skeptic and Coroner reviews, and the L-08 before and after scores
    - Confirm `git status` shows only uncommitted changes, with no push, deploy or AWS command run
    - _Requirements: 3.13, 3.14_

  - [x] 7.7 Summary for the owner
    - In chat: what changed per finding; anything deferred, with the reason; and a reminder to redeploy with `scripts/deploy_ecs_express.sh` and re-run the live test
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.13, 3.14_

## Notes

- The fix prompt asks for Analyze Requirements before tasks. It was not run while writing this spec; run it on `bugfix.md` before starting task 1, and update the spec from its answers.
- Choices made in `design.md` where the prompt allows options: L-05 explicit selection is rejected (422, `invalid_argument`, `CliError`), not silently left out; L-02 uses a new CLI exit code for "report not written" and keeps exit 1 for mismatches; L-02's "mismatch holds an Excel error" test uses `=SUM("5",1)` (Referee `#VALUE!`, Ghost 6), because the natural repro (B3) stops mismatching once L-03 is fixed.
- Open owner questions, raised at the STOP-AND-ASK points: L-07 clamping against the mutation-score floors and the scenarios sample value 60,000 above `default_max` 10,000 (task 5.4); haunted case-count changes from L-04 (task 3.12); L-08 search size (task 5.7).
- The report schema has no `not_converted` field today. Task 3.15 adds it as optional so old reports stay valid.
