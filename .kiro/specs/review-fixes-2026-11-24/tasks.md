# Implementation Plan

## Standing rules for every task

These come from `docs/KIRO_FIX_PROMPT_2026-11-24.md` and apply to each task below. They are stated once here to keep each task short.

- Test first. Run the finding's test before the fix and confirm it fails (xfail). After the fix, remove only the `xfail` marker. Never delete a test or weaken its expectation. If a test seems wrong, stop and show the owner the evidence.
- After each finding run `.venv/bin/python -m pytest -q`. Baseline is `192 passed, 19 xfailed`. The xfailed count falls and the passed count rises as fixes land.
- After each phase run `scripts/demo.sh` and check the demo invariants: haunted raises F-001, Faithful passes 300 cases, Intended with D-001 passes with exactly one expected difference at quantity = 50.
- No push, no deploy, no AWS command that changes anything. Leave changes uncommitted.
- Log each fix in `docs/KIRO_USAGE.md` (Kiro feature used and what changed). Add the finding's row to the Resolution table at the end of `docs/TEST_REPORT_2026-11-24.md` (fixed or deferred, reason, test).
- Tasks marked **STOP-AND-ASK** may turn out bigger than described or change the demo flow. If so, stop and ask the owner before continuing.
- Use the Skeptic agent for verifier and mutation work and the Coroner agent for autopsy work where they fit.
- Property-based-test tasks are marked **(PBT)** and use Hypothesis with an explicit seed. Each cites its property number and requirements.

## Tasks

- [x] 1. Write bug condition exploration baseline
  - **Property 1: Bug Condition** - Reviewed defects R-01 to R-29
  - **IMPORTANT**: The exploration tests already exist. Do not rewrite them.
  - **GOAL**: Confirm the starting state before any change
  - Run `.venv/bin/python -m pytest -q` and confirm `192 passed, 19 xfailed`
  - Run `.venv/bin/python -m pytest -q -rx tests/test_review_proof_strength.py tests/test_review_semantics.py tests/test_review_autopsy_and_packaging.py` and record which `reason=` IDs xfail: R-01 to R-05 (5), R-07 twice and R-08 once (3), R-09, R-10 twice, R-11, R-12, R-03, R-13 twice, R-14, R-15, R-16 (11)
  - **EXPECTED OUTCOME**: Every one of the 19 tests xfails (this confirms the bugs exist). Record the output in a scratch note, not in the repository
  - Note that the two R-13 tests skip where the external test bench folder is absent
  - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 1.8, 1.11, 1.12, 1.13, 1.14, 1.15, 1.21, 1.22, 1.26, 1.27_

- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - Demo storyline and suite stay intact
  - **IMPORTANT**: Follow observation-first methodology
  - Run `scripts/demo.sh` on the unfixed code and record: F-001 raised for haunted; haunted Faithful passes 300 cases; haunted with D-001 passes Intended with one expected difference at quantity = 50; discount passes
  - Reuse `tests/test_product_samples.py` where it already asserts these. Add `tests/test_demo_invariants.py` for any invariant not asserted yet, reading engine output only (no invented values)
  - The test must tolerate the later R-01 change, which raises the Intended case count from 33 to about 300, so it asserts "exactly one expected difference, minimal quantity = 50" and not the case count
  - Run on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms the baseline to preserve)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

- [x] 3. Phase 1: demo and submission blockers (R-05, R-12, R-19, R-29)

  - [x] 3.1 Write the web test for every bundled sample (R-05)
    - New test in `tests/test_web_flow.py` (or a new file): for each bundled sample, `POST /sample/{id}`, `GET /autopsy`, `POST /verify` with the pre-checked boxes, wait for the job, assert Faithful PASS
    - It will fail for `scenarios` before the fix; mark it `xfail(strict=True, reason="R-05 ...")` until task 3.3 lands, then remove the marker
    - _Requirements: 1.1, 2.1_

  - [x] 3.2 Fix R-12: treat `Calculator!E5` as a PARAMETER
    - Extend the parameter heuristics in `ghost/autopsy/classify.py` (labels "within", "free", "allowance"; a constant sitting in a block of other parameters)
    - Turn green: `test_free_delivery_distance_is_a_parameter` in `tests/test_review_autopsy_and_packaging.py`
    - Remove its `xfail` marker
    - _Bug_Condition: isBugCondition(X) where autopsyRole("Calculator!E5") = INPUT_
    - _Expected_Behavior: Calculator!E5 is PARAMETER on samples (a) and (b)_
    - _Preservation: B2, B3, B4 stay INPUT; F-001 unchanged_
    - _Requirements: 1.2, 2.2, 3.1_

  - [x] 3.3 Fix R-05: table blocks and INDEX/MATCH text are PARAMETER
    - **STOP-AND-ASK**: if the heuristic changes which inputs the demo or samples (a) and (b) pre-check, stop and ask
    - In `ghost/autopsy/classify.py` (`:97-104`), classify table blocks of constants and text referenced through `INDEX`/`MATCH` ranges as PARAMETER
    - Turn green: `test_scenarios_sample_passes_with_default_inputs` in `tests/test_review_proof_strength.py` (needs LibreOffice) and the task 3.1 web test
    - Remove both `xfail` markers
    - _Bug_Condition: isBugCondition(X) where X.sample = "scenarios" AND X.useAutopsyDefaults_
    - _Expected_Behavior: Faithful PASS with the pre-checked inputs_
    - _Preservation: samples (a) and (b) still pass; R-11 tests (task 5.3) must stay green later_
    - _Requirements: 1.1, 2.1, 3.6_

  - [x] 3.4 Fix R-05: `_inp("")` means an empty cell
    - In `ghost/converter/emit_python.py` (`:66-71`), make `_inp("")` return the empty-cell value that matches the Referee (`setString("")` leaves an empty cell)
    - Alternatively stop the verifier generating `""` in `ghost/verifier/strategies.py`; pick the option that keeps the semantics tests passing and record the choice in `docs/KIRO_USAGE.md`
    - Add a unit test: an `INDEX` over an empty input returns 0 in generated code and in the Referee
    - _Requirements: 1.1, 2.1, 3.7_

  - [x] 3.5 Align the demo defaults with the autopsy defaults (R-05)
    - Compare the inputs hard-coded at `ghost/cli.py:678` (`Calculator!B2,Calculator!B3,Calculator!B4`) with the autopsy's pre-checked inputs for samples (a) and (b)
    - Remove the override in `ghost/cli.py` and `tests/test_product_samples.py:47-51`, or keep it with a code comment justifying it
    - _Requirements: 2.1, 3.6_

  - [x] 3.6 Write the README (R-19)
    - Cover Requirement 21.7 as listed in clause 2.3: live URL, quick start (macOS LibreOffice paths, Debian packages, venv), CLI demo, running the web app, Docker build and run with `GHOST_SOFFICE` and `GHOST_MAX_JOBS`, using the Kiro Power, creating Excel-saved fixtures with Excel for the web, safety, limits and LibreOffice-versus-Excel differences, and the honest test-bench note
    - Confirm `.kiro/` is committed and not listed in `.gitignore`
    - Verify by following the README command by command in a scratch copy
    - _Requirements: 1.3, 2.3_

  - [x] 3.7 Fix the four hooks (R-29)
    - In `.kiro/hooks/*.json`, call `.venv/bin/python` or a small wrapper script that finds the venv
    - Run each hook's command by hand and record the real output
    - The golden hook still selects 0 tests until Phase 7 adds them; note this in `docs/KIRO_USAGE.md`
    - The owner triggers each hook inside Kiro (a sub-agent cannot); leave a checklist in `docs/KIRO_USAGE.md`
    - _Requirements: 1.4, 2.4_

  - [x] 3.8 Checkpoint: Phase 1
    - Run the full suite and `scripts/demo.sh`; check the demo invariants
    - Create the Resolution table at the end of `docs/TEST_REPORT_2026-11-24.md` with rows for R-05, R-12, R-19, R-29 (R-29 marked "fixed, hook trigger in Kiro pending owner check")
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 4. Phase 2: integrity of the proof (R-01, R-02, R-03, R-04, R-10 expressions, R-06, R-28)

  - [x] 4.1 **Property 3: Intended-mode classification soundness (PBT)** - write the test
    - Hypothesis test over generated modules (haunted base plus injected unrelated edits such as a VAT constant, plus the D-001 patch) and cases: a mismatch is "expected by decision" iff the three conditions of clause 2.5 hold
    - Needs LibreOffice. Expected to fail before task 4.2
    - _Requirements: 2.5, 2.6_

  - [x] 4.2 Fix R-01: classify Intended mismatches by the three-condition test
    - **STOP-AND-ASK**: this changes the haunted Intended run (about 33 cases now, about 300 after). If the demo invariants fail or the change is bigger than described, stop and ask
    - In `ghost/verifier/classify.py` (`:62-79`), implement the three conditions using the existing trace hook: Faithful module matches the Referee, Intended differs from Faithful, patched comparison evaluates differently in the two
    - For a hand-written or AI-written module, generate the transpiled Faithful module for the check; if the workbook is not fully convertible, classify as translation bug
    - In `ghost/verifier/run.py` (`:156-160`), keep generating after an expected mismatch; stop and shrink only on an unexpected one; shrink one example per expected Decision for the report
    - Turn green: `test_intended_mode_does_not_excuse_unrelated_bug` and the task 4.1 PBT; remove the `xfail` marker
    - Verify the haunted Intended run: about 300 cases, one expected difference, minimal case quantity = 50
    - _Bug_Condition: isBugCondition(X) where X.mode = "intended" AND X.mismatchIsUnrelatedToDecision_
    - _Expected_Behavior: expectedBehavior(result) from design, Property 3_
    - _Preservation: Faithful behaviour unchanged; demo Intended result unchanged in substance_
    - _Requirements: 1.5, 2.5, 3.3_

  - [x] 4.3 Fix R-01 on the MCP path
    - Make `verify_implementation` in `mcp_server/server.py` call the same classification and run logic as the CLI
    - Add a test that runs the VAT-21% module through `verify_implementation` and expects FAIL
    - _Requirements: 1.5, 2.5_

  - [x] 4.4 Fix R-02: label Faithful translation bugs correctly
    - In `ghost/verifier/classify.py` (`:62-66`, `:83-87`), use "original workbook inconsistency" only when the comparisons at the Finding's locations evaluate to different truth values on that case; otherwise "translation bug"
    - Turn green: `test_faithful_translation_bug_is_labelled_translation_bug`; remove the `xfail` marker
    - Keep `tests/test_verifier_classify.py` green; a genuine F-001 mismatch (for example `B2 = 50`) stays "original workbook inconsistency"
    - _Requirements: 1.6, 2.6_

  - [x] 4.5 **Property 5: Type inference (PBT)** - write the test
    - For any validation (`decimal`, `whole`, none) and sample value, mapping type equals verifier strategy type, and `decimal` validation always gives decimal
    - Expected to fail before task 4.6
    - _Requirements: 2.7_

  - [x] 4.6 Fix R-03: one shared type-inference function
    - Add one function used by `ghost/converter/mapping.py` (`:60-69`) and `ghost/verifier/strategies.py` (`infer_spec`): validation decides first, sample value second
    - Turn green: `test_decimal_validation_wins_over_whole_number_sample`, `test_truncated_distance_is_caught`, and the task 4.5 PBT; remove both `xfail` markers
    - Samples (a) and (b) must still pass Faithful (300 cases)
    - _Requirements: 1.7, 2.7, 3.2, 3.6_

  - [x] 4.7 **Property 6: Condition-flip probing finds the boundary (PBT)** - write the test
    - For monotone conditions in one numeric input (`x*k >= t`, `x > t`), the probe returns values on opposite sides within tolerance and includes the exact hit when one exists
    - Expected to fail before task 4.8
    - _Requirements: 2.8_

  - [x] 4.8 Implement condition-flip probing (R-04, R-10 expressions)
    - **STOP-AND-ASK**: this is the largest change in Phase 2. If it needs changes beyond a new module plus wiring into `_probe_boundaries`, `verify` and `mutate`, or slows `scripts/demo.sh` noticeably, stop and ask
    - New module (for example `ghost/verifier/flip.py`): for every IF condition in the transpiled Faithful module, binary-search each numeric input (other inputs at base values plus a few random base points) using the trace hook to detect the flip
    - Return both sides of each flip plus exact hits where the compared value equals the threshold
    - Pass the task 4.7 PBT
    - _Bug_Condition: isBugCondition(X) where X.threshold.onCalculatedCellOrExpression_
    - _Requirements: 1.8, 2.8_

  - [x] 4.9 Wire flip probing into verification, mutation and boundaries (R-04)
    - In `ghost/cli.py` (`:385-397`, `_probe_boundaries`), feed the flip cases into `extra_cases` for `verify` and `mutate`, report them as boundaries, and verify them against the Referee
    - Turn green: `test_gold_threshold_on_calculated_cell_is_caught`; remove the `xfail` marker
    - On the tier workbook, assert the flip and ±1 mutants on `B12`/`B13` are killed and the boundaries list `B12` and `B13`
    - Check that the haunted demo's boundaries and the Faithful 300-case result are unchanged
    - _Requirements: 1.8, 2.8, 3.2_

  - [x] 4.10 Fix R-06: honest survivor wording
    - In `ghost/mutation/run.py` (`:118`), replace "equivalent on tested domain" with "no difference found on N distinct cases" plus each input's tested domain (type, min, max, decimal places). Never claim equivalence
    - Add a test that, after tasks 4.6 and 4.9, the constant ±1 mutants on the ROUND digits of `Calculator!B9` in the haunted sample are killed
    - Update existing tests and report text that use the old wording. Keep `test_decimal_distance_mutants_are_not_equivalent` unchanged
    - _Requirements: 1.9, 2.9_

  - [x] 4.11 Fix R-28: generated versus distinct cases
    - **STOP-AND-ASK**: if the schema change cannot stay backward compatible, ask before bumping the version
    - Count distinct inputs in the verifier. Add an optional field to `ghost/report/schema/proof-report-1.json` and `ghost/report/model.py`. Update `ghost/report/html.py` to show "300 generated, 176 distinct"
    - Add tests: old reports still validate; a new report shows both numbers; sample (a) shows 176 distinct for seed 20261204 (read from engine output, not hard-coded if it differs)
    - _Requirements: 1.10, 2.10, 3.9_

  - [x] 4.12 Checkpoint: Phase 2
    - Run the full suite and `scripts/demo.sh`; check the demo invariants (haunted Intended: about 300 cases, one expected difference, quantity = 50)
    - Run the Skeptic agent on the verifier and mutation changes
    - Append Resolution rows for R-01, R-02, R-03, R-04, R-06, R-10 (expressions), R-28 to the report
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 5. Phase 3: autopsy, decisions and VBA (R-09, R-10, R-11, R-14, R-13, R-26)

  - [x] 5.1 **Property 4: Operator consistency (PBT)** - write the test
    - For any two operators from `>=`, `>`, `<=`, `<`, `=`, `<>`, a conflict is raised iff the truth sets over {below, at, above} are neither equal nor complementary
    - Expected to fail before task 5.2
    - _Requirements: 2.11_

  - [x] 5.2 Fix R-09: truth-set comparison in findings
    - In `ghost/autopsy/findings.py` (`:28`), replace "two or more different operators" with the truth-set rule
    - Turn green: `test_complementary_operators_are_not_a_finding` and the task 5.1 PBT; remove the `xfail` marker
    - The haunted sample still raises F-001 (`>=` against `>`)
    - _Requirements: 1.11, 2.11, 3.1_

  - [x] 5.3 Fix R-10: threshold extraction rules
    - In `ghost/autopsy/thresholds.py` (`:45-61`), resolve comparison constants only from non-INPUT cells (pass roles or confirmed inputs in and recompute after the user confirms inputs), treat `50%` as 0.5, drop thresholds that treat an input's current value as a fixed threshold, and record comparisons on expressions as calculated-cell thresholds (consumed by task 4.9)
    - Turn green: `test_input_value_is_not_treated_as_a_threshold` and `test_expression_and_percent_thresholds_are_recorded`; remove both `xfail` markers
    - `A7>=Bulk` (named range) stays open until task 7.3
    - _Requirements: 1.12, 2.12_

  - [x] 5.4 Fix R-11: a compared constant is an INPUT
    - In `ghost/autopsy/classify.py` (`:99`, `shared_fixed`), do not demote a cell that thresholds are compared against unless it is labelled as a rate. Table blocks stay PARAMETER
    - Turn green: `test_input_shared_by_two_formulas_is_an_input`; remove the `xfail` marker
    - The task 3.1 web test and `test_scenarios_sample_passes_with_default_inputs` must stay green
    - _Requirements: 1.13, 2.13, 3.6_

  - [x] 5.5 **Property 8: Decision uniqueness (PBT)** - write the test
    - For any sequence of `record` calls, at most one Decision per `finding_id` or `rule_id` is stored and a repeat raises `InvalidDecision` naming the existing `decision_id`
    - Expected to fail before task 5.6
    - _Requirements: 2.14_

  - [x] 5.6 Fix R-14: reject duplicate Decisions
    - In `ghost/decisions/store.py` (`:154`, `record`), reject a second Decision for the same `finding_id` or `rule_id`, raising `InvalidDecision` that names the existing `decision_id`
    - Where the workbook is known (CLI and MCP, through `source.yaml`), validate the patch when it is recorded
    - Turn green: `test_second_decision_for_same_finding_is_rejected` and the task 5.5 PBT; remove the `xfail` marker
    - Web behaviour ("already has a Decision") is unchanged; `tests/test_decisions_store.py` stays green
    - _Requirements: 1.14, 2.14, 3.3_

  - [x] 5.7 Add the generated macro sample (R-13)
    - New `samples/make_xlsm.py` building an `.xlsm` pair through the Referee's `save_with_vba`, never running macros (Requirement 5.15). Label it "generated". Do not commit a hand-edited workbook
    - Add a test that the script is deterministic enough to run in CI (skips with a message if LibreOffice is absent)
    - _Requirements: 1.15, 2.15, 3.7_

  - [x] 5.8 Fix R-13: detect VBA by content
    - Detect `xl/vbaProject.bin` in the zip whatever the extension and extract it statically with olevba (`ghost/cli.py:107`, `ghost/ingest/`). Fill `has_vba` in the upload summary (`web/app.py:76`) from the result
    - Re-point `test_vba_found_in_renamed_macro_workbook` and `test_upload_summary_reports_vba` at the generated sample and remove the test-bench path and the `skipif`; keep every assertion. Remove their `xfail` markers
    - Confirm macros are not run and the uploaded file is not modified
    - _Requirements: 1.15, 2.15, 3.5, 3.7, 3.9_

  - [x] 5.9 Fix R-26: text outputs typed `string`
    - In `ghost/converter/mapping.py` (`:111`), type formulas that produce text as `string` when no Excel-saved value exists
    - Add a test on the tier workbook and sample (c): `tier` and `best_scenario` are `string`
    - Comparison results for the bundled samples are unchanged
    - _Requirements: 1.16, 2.16_

  - [x] 5.10 Checkpoint: Phase 3
    - Run the full suite and `scripts/demo.sh`; check the demo invariants
    - Run the Coroner agent on the autopsy changes
    - Append Resolution rows for R-09, R-10, R-11, R-13, R-14, R-26
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 6. Phase 4: security and robustness (R-17, R-18, R-21 paths, MCP error naming)

  - [x] 6.1 Write the R-17 test, then add `MAX_CELLS`
    - Test: build a workbook of about 250,000 cells with openpyxl write-only mode, upload it, expect rejection in under 5 seconds with a message naming the limit
    - Add `MAX_CELLS = 200_000` to `ghost/ingest/limits.py`, counted during the existing defusedxml pre-scan before openpyxl loads anything
    - Bundled samples still upload and analyse
    - _Requirements: 1.17, 2.17_

  - [x] 6.2 Cache the analysis per session and workbook (R-17)
    - **STOP-AND-ASK**: parsing in a subprocess with a memory limit is optional in the prompt ("consider"). Do the cache only. If the cap and cache are not enough to bound memory, stop and ask before adding a subprocess
    - In `web/flow.py` (`_describe`) and `web/app.py` (`:229`), cache the analysis so `GET /autopsy` does not reparse. Invalidate when the workbook or confirmed inputs change
    - Document `MAX_CELLS` in `.kiro/steering/tech.md` and the README
    - _Requirements: 1.17, 2.17_

  - [x] 6.3 Fix R-18: per-session job cap
    - Write a test first: a second `/verify` in the same session while one is queued or running returns 429 with a clear message
    - In `web/jobs.py`, allow at most one queued-or-running job per session. The design records 429 as the choice. Document it in the README
    - _Requirements: 1.18, 2.18_

  - [x] 6.4 Fix R-18: drop jobs and artifacts at session end
    - Write a test first: after `forget_session` and after the sweeper, the session's jobs and artifact bytes are gone from `self._jobs`
    - Fix `web/jobs.py` (`:141`, `:168`) and the sweeper. Existing `tests/test_web_jobs.py` stays green
    - _Requirements: 1.18, 2.18_

  - [x] 6.5 Fix R-21 (paths): no absolute server paths in job events
    - Write a test first: no event from `/jobs/{id}` or the panel contains an absolute path or the session folder name
    - Show names relative to the run
    - _Requirements: 1.19, 2.19_

  - [x] 6.6 Fix MCP error naming (Requirement 12.11)
    - Write a test first: `evaluate_original` with `{"Calculator!B2": {"x": 1}}` returns `invalid_argument` naming `inputs.Calculator!B2`
    - Fix in `mcp_server/server.py`
    - _Requirements: 1.20, 2.20_

  - [x] 6.7 Checkpoint: Phase 4
    - Run the full suite and `scripts/demo.sh`; check the demo invariants
    - Append Resolution rows for R-17, R-18, R-21 (paths) and MCP error naming
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 7. Phase 5: transpiler and Referee semantics (R-07, R-08, R-27, R-24, R-25)

  - [x] 7.1 **Property 7: Comparison normalisation (PBT)** - write the test
    - Decimals differing only beyond the 15th significant digit compare equal; decimals differing within 15 digits keep their order
    - Expected to fail before task 7.2
    - _Requirements: 2.21_

  - [x] 7.2 Fix R-07: compare at 15 significant digits
    - In `ghost/runtime/excel.py` (`:235-243`, `:403-433`), normalise both sides to 15 significant digits before comparing in `xl_eq`, `xl_ge` and the other comparisons
    - Turn green: both R-07 cases in `test_review_semantics.py::test_transpiler_bug` and the task 7.1 PBT; remove their `xfail` entries from `BUGS`
    - Every other semantics test and the Excel semantics golden table stay green
    - _Requirements: 1.21, 2.21, 3.7_

  - [x] 7.3 Fix R-08: INDEX 0 and number-to-text
    - `INDEX` with row or column 0 in a single-cell formula returns `#VALUE!` (`ghost/converter/emit_python.py:208-209`)
    - Convert very large and very small numbers to text as Excel does (`1E+20&""` is "1E+20", `1E-20&""` is "1E-20")
    - Add tests for the number-to-text cases. LibreOffice writes "1E+020": either compare scientific-notation strings with the same value as equal, or list the case as a known difference (record which in the semantics table)
    - Turn green: `test_transpiler_bug[index_row_zero]`; remove its `xfail` entry
    - _Requirements: 1.22, 2.22_

  - [x] 7.4 Fix R-27: named ranges
    - **STOP-AND-ASK**: this touches the parser, dependencies, emitter, thresholds and rule text. If it needs more than resolving workbook-scoped names to one cell or one rectangular range, stop and ask
    - Write the tests first: `=Bulk*2` (name `Bulk` = `S!$E$2`) matches the Referee; `B2>=Bulk` records a threshold with the named cell's value; an OFFSET/INDIRECT-based name is "not converted" with cell and reason
    - Resolve names in `ghost/converter/parser.py`, `emit_python.py`, `ghost/autopsy/thresholds.py` and `ghost/rules/`; rule text uses the name as the label
    - Output stays deterministic
    - _Requirements: 1.23, 2.23, 3.7, 3.8_

  - [x] 7.5 Document R-24: where LibreOffice differs from Excel
    - Add the "Where LibreOffice differs from Excel" table to `.kiro/steering/excel-semantics.md` for `0^0`, `(-8)^(1/3)`, `MATCH("2",numbers,0)`, `MATCH(TRUE,numbers,0)`, `TRUE>1`, `SUM("5",1)`, `TRUE&""`
    - Add Referee fidelity tests pinning today's LibreOffice result for each, so an upgrade is noticed
    - Note live LibreOffice 7.4.7.2 against local 26.8.3. Upgrading the image is optional and only if the Docker build and full suite pass; do not run Docker deploy commands
    - _Requirements: 1.24, 2.24_

  - [x] 7.6 Document R-25: ROUND over 15 significant digits (document only)
    - Do not change behaviour. Add a note in `docs/TEST_REPORT_2026-11-24.md` Resolution table and README limits: "unverified; owner to check `=ROUND(123456789012345.67,1)` in Excel for the web"
    - Mark R-25 "deferred" in the Resolution table
    - _Requirements: 1.25, 2.25_

  - [x] 7.7 Checkpoint: Phase 5
    - Run the full suite and `scripts/demo.sh`; check the demo invariants
    - Append Resolution rows for R-07, R-08, R-24, R-25 (deferred), R-27
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.11_

- [x] 8. Phase 6: Power, routing, report and UI polish (R-15, R-16, R-21 rest, R-22, R-23)

  - [x] 8.1 Fix R-15: Power packaging
    - Add `"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"` to `plugin/plugin.json`
    - Remove `toolPrefix` from `plugin/mcp.json` and update `tests/test_plugin_package.py` to assert the documented fields instead; show the owner this test edit in the Resolution table because it removes an assertion
    - Use a launch command that works with no `python` on the Mac (`python3`, or a `ghost-mcp` console script run with `uvx`). Document prerequisites in the skills and README
    - Turn green: `test_plugin_manifest_has_schema`; remove the `xfail` marker
    - Add the install checklist for the owner to `docs/KIRO_USAGE.md`
    - _Requirements: 1.26, 2.26_

  - [x] 8.2 Fix R-16: `atx` dry-run command
    - In `ghost/router/route.py`, add `-t` next to `-x`; state the transformation definition must exist first (`atx custom def list`); stop calling it "exact"; use `python3 -m py_compile **/*.py` as the build command
    - Turn green: `test_atx_dry_run_includes_trust_all_tools_with_non_interactive`; remove the `xfail` marker
    - _Requirements: 1.27, 2.27_

  - [x] 8.3 Fix R-21 (rest): report column, tested domains, Faithful download
    - Rename "Exact hits" in `ghost/report/html.py` (`:167-169`) and add the real exact hits from task 4.9
    - List each input's tested domain (type, min, max, decimal places)
    - When both modes ran, make the Faithful report downloadable (for example `report.html?mode=faithful`; `ghost/cli.py:559`, `web/app.py`)
    - Add tests for each; reports still validate against `proof-report-1.json`
    - _Requirements: 1.28, 2.28, 3.9_

  - [x] 8.4 Fix R-22: autopsy page text
    - Change `web/templates/_autopsy.html:66` to "Unanswered findings keep the original behaviour and are listed in the report."
    - Add a test on the rendered page
    - _Requirements: 1.29, 2.29_

  - [x] 8.5 Fix R-23: dark border contrast and toggle label
    - Set the dark theme `--border` in `web/static/style.css:5` to a colour with at least 3:1 contrast (`#7a6d94` gives 3.96:1 and 3.65:1)
    - Keep the toggle label constant ("Light mode") in `web/static/theme.js:11` with `aria-pressed` carrying the state
    - Add a contrast-ratio test that computes the ratio from the CSS value, and a test on the toggle markup
    - _Requirements: 1.30, 2.30_

  - [x] 8.6 Checkpoint: Phase 6
    - Run the full suite and `scripts/demo.sh`; check the demo invariants
    - Append Resolution rows for R-15, R-16, R-21 (rest), R-22, R-23
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 9. Phase 7: the tests the requirements promise (R-20)

  - [x] 9.1 Golden semantics tests
    - Build from `samples/make_traps.py`, mark `@pytest.mark.golden`. Check each in-scope row of the Excel semantics table against the Referee and the generated code. Exclude the R-24 divergences
    - Confirm `pytest -m golden` selects tests and passes
    - _Requirements: 1.31, 2.31_

  - [x] 9.2 Re-check the golden hook (R-29)
    - Run the golden hook command by hand; it must now select the new tests and report a real result
    - Record the result in `docs/KIRO_USAGE.md`. The owner triggers it in Kiro
    - _Requirements: 2.4, 2.31_

  - [x] 9.3 Excel-saved fixtures folder
    - Create `tests/fixtures/excel-saved/` with a README explaining how to make the files in Excel for the web, and a sanity test that skips with a message naming the folder when it is empty
    - Never fake a result; the report says "not cross-checked against Excel" when no fixture exists
    - _Requirements: 1.31, 2.31, 3.7_

  - [x] 9.4 **Property 9: Formula fuzzing agrees with the Referee (PBT)**
    - Hypothesis grammar of the P0 subset (small depth, small values, R-24 divergences excluded); compare the Referee with the transpiled code; shrink failures to the smallest formula
    - Explicit seed. Needs LibreOffice. If it finds new transpiler bugs, record them as new findings and ask the owner before fixing
    - _Requirements: 2.31_

  - [x] 9.5 CLI end-to-end test
    - Run `scripts/demo.sh` into a temp folder and check its outputs against the demo invariants
    - _Requirements: 1.31, 2.31, 3.6_

  - [x] 9.6 Performance test
    - 500 cases verified in under 60 seconds, marked slow (register the marker in `pyproject.toml` or `pytest.ini`)
    - _Requirements: 1.31, 2.31_

  - [x] 9.7 Update the README
    - Add the Phase 7 test commands, the `MAX_CELLS` limit, the job cap and the Power checklist if not yet present
    - _Requirements: 2.3_

  - [x] 9.8 Checkpoint: Phase 7
    - Run the full suite (including slow and golden) and `scripts/demo.sh`; check the demo invariants
    - Append Resolution rows for R-20 and R-29
    - Ensure all tests pass, ask the user if questions arise
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.11_

- [x] 10. Final checkpoint: before telling the owner it is done
  - Run `.venv/bin/python -m pytest -q`. The full suite passes and no `xfail` marker remains in `tests/test_review_*.py`, unless that finding is marked deferred with a reason in the Resolution table
  - Run `scripts/demo.sh`: discount passes; haunted raises F-001 and passes Faithful; haunted with D-001 passes Intended over about 300 cases with one expected difference whose minimal case is quantity = 50
  - Run a local web check with FastAPI TestClient: each bundled sample with the default checkboxes passes Faithful, and haunted with D-001 passes Intended
  - Confirm the Resolution table has one row per finding R-01 to R-29, each fixed or deferred with a reason and a test, and `docs/KIRO_USAGE.md` has an entry per fix
  - Confirm `git status` shows only uncommitted changes, with no push, deploy or mutating AWS command run
  - Write the summary for the owner: what changed for each finding, tests added or updated, anything deferred and why (R-25 for sure), the owner's manual checks (hooks in Kiro, Power install from GitHub, Excel result for R-25), and the deploy command `scripts/deploy_ecs_express.sh`
  - Ensure all tests pass, ask the user if questions arise
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.10, 3.11_
