# Bugfix Requirements Document

## Introduction

The 24 November 2026 review (`docs/TEST_REPORT_2026-11-24.md`) found 29 issues, R-01 to R-29, in Ghost in the Macro. Several of them weaken the proof Ghost exists to give: Intended mode excuses unrelated bugs (R-01), decimal inputs are tested as integers (R-03), and thresholds on calculated cells are never probed (R-04). Others break the demo and the submission: the "Scenario model" sample fails on the live site (R-05), the README has no instructions (R-19), and the Kiro hooks cannot run (R-29).

`docs/KIRO_FIX_PROMPT_2026-11-24.md` is the authoritative source for the fixes. Each defect clause below carries its finding ID. The matching expected-behaviour clause has the same number and holds the "Done when" text of the fix prompt. R-01 and R-05/R-12 are the highest priority. R-25 is document-only until the owner checks Excel.

Nineteen strict-xfail tests in `tests/test_review_proof_strength.py`, `tests/test_review_semantics.py` and `tests/test_review_autopsy_and_packaging.py` name their finding in `reason=`. They are the bug-condition exploration tests and already exist. Findings without such a test get one before the fix. Process rules (test first, never weaken a test, run `scripts/demo.sh` after each phase, no push or deploy, leave changes uncommitted, log in `docs/KIRO_USAGE.md`, add a Resolution table) are in clauses 3.4 to 3.11 and in the design.

Clause numbers follow the fix prompt's phase order. Where a finding spans two phases (R-21) or two aspects (R-10), it has one clause per part so each part can be traced to a task.

## Bug Analysis

### Current Behavior (Defect)

1.1 (R-05) WHEN a user opens the "Scenario model" sample and runs verification with the autopsy's pre-checked inputs THEN the system pre-checks 53 inputs (scenario names and rates), generates `""` for text inputs, and fails Faithful verification on case 1 because the Referee reads `""` as an empty cell (`INDEX` returns 0) while the generated `_inp` keeps `""` as a string.

1.2 (R-12) WHEN the autopsy runs on samples (a) and (b) THEN the system proposes and pre-checks `Calculator!E5` ("Free delivery within (km)") as an input, so the generated API exposes `free_delivery_within_km`.

1.3 (R-19) WHEN a visitor opens `README.md` THEN the system shows only the project name, the live URL and a take-down note, with no setup, run, Docker, Power or safety instructions (Requirement 21.7).

1.4 (R-29) WHEN any of the four hooks in `.kiro/hooks/` runs THEN the system calls the system `python3`, which fails with `ModuleNotFoundError: No module named 'openpyxl'`, and the golden-tests hook selects 0 tests (`-m golden` deselects all 211).

1.5 (R-01) WHEN Intended mode runs with D-001 recorded and the module has an unrelated bug (VAT 21%) THEN the system classifies the mismatch "expected by decision" because the output depends on a Finding's cell, stops at the first mismatch (quantity = 0, where D-001 cannot apply), and reports PASS after 1 case. MCP `verify_implementation` behaves the same way.

1.6 (R-02) WHEN Faithful mode finds a mismatch caused by a translation bug on an output that depends on a Finding's cells THEN the system labels it "original workbook inconsistency" instead of "translation bug".

1.7 (R-03) WHEN an input has `decimal` data validation but a whole-number sample value (`Calculator!B4`, value 12) THEN the system types it `integer` in `mapping.yaml`, generates only whole values, and a module that truncates the distance passes 300 cases.

1.8 (R-04, R-10 expressions) WHEN a threshold applies to a calculated cell (`B11>=500`) or to an expression (`A2*A3>=500`) THEN the system never probes it (`_probe_boundaries` skips non-input cells), a `>` instead of `>=` for Gold passes 300 cases, and the mutation check leaves six B12/B13 survivors labelled "equivalent on tested domain".

1.9 (R-06) WHEN a mutant survives the mutation check THEN the system labels it "equivalent on tested domain", although the ROUND-digit mutants on `Calculator!B9` differ from the Referee at 10.3 km and 10.01 km.

1.10 (R-28) WHEN a verification report states "Cases tested 300" THEN the system counts repeated inputs, so only 176 of the 300 inputs are distinct.

1.11 (R-09) WHEN one cell is compared with the same constant using complementary operators (`>=50` in one formula, `<50` in another) THEN the system raises a false "operator conflict" Finding.

1.12 (R-10) WHEN thresholds are extracted THEN the system resolves constants from INPUT cells (inventing `P!E9 <= 90` from `A9>=E9` with A9 = 90), and ignores `A2*A3>=500`, `A8>=50%` and `A7>=Bulk`.

1.13 (R-11) WHEN a real input with no fill, validation or label is used by two formulas and compared with a threshold THEN the system classifies it PARAMETER (`shared_fixed`), so the verifier never varies it.

1.14 (R-14) WHEN a second Decision is recorded for a Finding that already has one (through the MCP server or CLI) THEN the system accepts it as D-002, and every later `generate_proof_report` and `mutation_check` fails with "patch matched no comparison".

1.15 (R-13) WHEN a macro workbook is renamed `.xlsx`, or a real `.xlsm` is uploaded THEN the system reports 0 VBA lines and `has_vba: false`, because VBA is read only when the suffix is `.xlsm` and `wb.vba_modules` is never filled. Routing never sees the VBA.

1.16 (R-26) WHEN a formula produces text (`tier`, `best_scenario`) and the workbook has no Excel-saved value THEN the system types the output `decimal` in `mapping.yaml`.

1.17 (R-17) WHEN a legal workbook of about 1.7 million cells (2.3 MB, under every current limit) is uploaded THEN the system takes 30 s and 1.16 GB to analyse it, and every `GET /autopsy` reloads and re-analyses the workbook, which can exhaust the 2 GB task and wipe all sessions.

1.18 (R-18) WHEN one session starts several verification jobs, or ends THEN the system lets it queue unlimited jobs, and keeps finished jobs and their report and module bytes in memory after the session is deleted.

1.19 (R-21, paths) WHEN job events are shown in the panel or through `/jobs/{id}` THEN the system includes absolute server paths such as `/tmp/ghost-sessions-<random>/<session-id>/run-1/logic_intended.py`.

1.20 (MCP error naming, Requirement 12.11) WHEN `evaluate_original` receives a non-scalar input value (`{"Calculator!B2": {"x": 1}}`) THEN the system returns `referee_error` without naming the argument.

1.21 (R-07) WHEN a formula compares a value that came out of a division (`=1/3*3=1`, `=IF(10/3*3>=10,...)`) THEN the system compares 60-digit Decimals exactly and returns `False` or `'low'` where Excel and LibreOffice return TRUE or `'ok'`.

1.22 (R-08) WHEN `INDEX(r,0)` is evaluated, or a very large or small number is joined to text (`1E+20&""`, `1E-20&""`) THEN the system returns `#REF!` and the full decimal expansion, where Excel returns `#VALUE!`, `"1E+20"` and `"1E-20"`.

1.23 (R-27) WHEN a formula uses a workbook-scoped defined name (`=Bulk*2`, `B2>=Bulk`) THEN the system reports "named reference Bulk is not supported", omits the dependent outputs and loses the threshold.

1.24 (R-24) WHEN a workbook relies on a case where LibreOffice differs from Excel (`0^0`, `(-8)^(1/3)`, `MATCH("2",numbers,0)`, `MATCH(TRUE,numbers,0)`, `TRUE>1`, `SUM("5",1)`, `TRUE&""`) THEN the system gives a false "translation bug" mismatch, and the semantics table and tests do not list the seven divergences or the 7.4.7.2 (live) against 26.8.3 (local) version gap.

1.25 (R-25) WHEN `=ROUND(123456789012345.67,1)` is evaluated THEN Ghost gives `123456789012346.0` and LibreOffice gives `123456789012345.7`; Excel's result is unverified.

1.26 (R-15) WHEN the Power is installed from `plugin/` THEN `plugin.json` lacks the required `$schema`, `mcp.json` has the undocumented `toolPrefix`, and the launch command `python` does not exist on a stock Mac.

1.27 (R-16) WHEN the routing dry run prints the `atx` command THEN the command has `-x` without the required `-t`, presents `excel-vba-to-python` as if it already exists, calls the command "exact", and uses `python -m pytest` as the build command.

1.28 (R-21, rest) WHEN the HTML report is generated and downloaded THEN the "Exact hits" column shows change points, "inputs tested" is only a count, and the Faithful report cannot be downloaded when Intended mode also ran.

1.29 (R-22) WHEN the autopsy page explains unanswered Findings (`web/templates/_autopsy.html:66`) THEN the text says they "are reported as mismatches", which is false in Faithful mode.

1.30 (R-23) WHEN the dark theme is shown THEN `--border` (`#5b4f73`) has 2.51:1 contrast against the background (WCAG 1.4.11 needs 3:1), and the theme toggle changes its label as well as `aria-pressed`, so a screen reader hears "Dark mode, toggle button, not pressed".

1.31 (R-20) WHEN the repository's tests are inspected THEN the system has no golden semantics tests (`@pytest.mark.golden`), no `tests/fixtures/excel-saved/` folder with a skip test, no formula fuzzing, no CLI end-to-end test and no 500-case performance test (Requirements 15.12, 20.2 to 20.4, 20.6, 20.8, 20.9).

### Expected Behavior (Correct)

2.1 (R-05) WHEN the "Scenario model" sample runs through the web flow with the pre-checked inputs THEN the system SHALL treat table blocks of constants, and text referenced through `INDEX`/`MATCH` ranges, as PARAMETER, SHALL make `_inp("")` mean an empty cell as the Referee does, and SHALL pass Faithful verification. `test_scenarios_sample_passes_with_default_inputs` SHALL pass, a new web test SHALL run every bundled sample through `POST /sample/{id}`, `GET /autopsy` and `POST /verify` with the pre-checked boxes and each SHALL pass Faithful, and the demo's defaults SHALL equal the inputs hard-coded at `ghost/cli.py:678` (the override removed or justified).

2.2 (R-12) WHEN the autopsy runs on samples (a) and (b) THEN the system SHALL classify `Calculator!E5` as PARAMETER through improved heuristics in `ghost/autopsy/classify.py` (labels such as "within", "free" or "allowance", or a constant in a block of other parameters), and `test_free_delivery_distance_is_a_parameter` SHALL pass.

2.3 (R-19) WHEN a visitor opens `README.md` THEN the system SHALL give, command by command: the live URL; quick start (LibreOffice on macOS, the Debian packages `libreoffice-calc-nogui` and `libreoffice-script-provider-python`, and the venv); the CLI demo; running the web app locally; Docker build and run with the environment variables; using the Kiro Power; creating Excel-saved test files with Excel for the web; safety (macros never run from uploads); limits and known LibreOffice-versus-Excel differences; and an honest note that the feasibility test bench was built outside the repository and is not included. `.kiro/` SHALL be committed and not ignored. A fresh clone SHALL be able to follow the README. The README SHALL be updated again at the end of Phase 7.

2.4 (R-29) WHEN a hook in `.kiro/hooks/` runs THEN the system SHALL call `.venv/bin/python` (or a wrapper script that finds the venv), the golden hook SHALL select real tests once Phase 7 adds them, and each hook, triggered in Kiro, SHALL run and report a real result recorded in `docs/KIRO_USAGE.md`.

2.5 (R-01) WHEN Intended mode finds a mismatch THEN the system SHALL count it "expected by decision" only when (a) the transpiled Faithful module without the patch matches the Referee on that case, (b) the Intended module differs from the Faithful module on that case, and (c) the Decision's patched comparison evaluates differently in the two modules on that case, checked with the existing trace hook. Any other mismatch SHALL be a "translation bug". For a hand-written or AI-written module the system SHALL generate the transpiled Faithful module for this check, and SHALL classify the mismatch as a translation bug if the workbook is not fully convertible. The run SHALL keep generating after an expected mismatch until the case budget is used, SHALL stop and shrink only on an unexpected mismatch, and SHALL still shrink one example per expected Decision for the report. `test_intended_mode_does_not_excuse_unrelated_bug` SHALL pass, the haunted Intended run SHALL report about 300 cases with one expected difference whose minimal case is quantity = 50, and MCP `verify_implementation` SHALL use the same logic.

2.6 (R-02) WHEN Faithful mode finds a mismatch THEN the system SHALL label it "original workbook inconsistency" only when the comparisons at the Finding's locations evaluate to different truth values on that case, and otherwise "translation bug". `test_faithful_translation_bug_is_labelled_translation_bug` SHALL pass.

2.7 (R-03) WHEN an input type is inferred THEN the system SHALL let data validation decide first (`decimal` is decimal, `whole` is integer) and the sample value second, using one shared inference function for `ghost/converter/mapping.py:60-69` and `ghost/verifier/strategies.py:infer_spec`. `test_decimal_validation_wins_over_whole_number_sample` and `test_truncated_distance_is_caught` SHALL pass, and samples (a) and (b) SHALL still pass.

2.8 (R-04, R-10 expressions) WHEN verification or the mutation check runs THEN the system SHALL add condition-flip probing: for every IF condition in the transpiled Faithful module, binary-search each numeric input (other inputs at base values plus a few random base points) for where the condition flips, detected with the trace hook; add the cases on both sides of each flip, plus exact hits where the compared value equals the threshold, to `extra_cases` for verification and the mutation check; report them as boundaries; and verify them against the Referee. This SHALL cover calculated cells (`B11>=500`) and expressions (`A2*A3>=500`). `test_gold_threshold_on_calculated_cell_is_caught` SHALL pass, the flip and ±1 mutants on `B12`/`B13` of the tier workbook SHALL be killed, and the boundaries SHALL list `B12` and `B13`.

2.9 (R-06) WHEN a mutant survives THEN the system SHALL report "no difference found on N distinct cases" followed by each input's tested domain (type, min, max, decimal places), and SHALL never claim equivalence. After R-03 and R-04, the constant ±1 mutants on the ROUND digits of `Calculator!B9` in the haunted sample SHALL be killed, and reports and tests SHALL use the new wording.

2.10 (R-28) WHEN a report states the number of cases THEN the system SHALL report cases generated and distinct inputs separately (for example "300 generated, 176 distinct"), through an optional schema field that keeps `proof-report-1.json` backward compatible (or a version bump with tests), and the HTML SHALL show both.

2.11 (R-09) WHEN two comparisons of the same cell with the same constant are checked THEN the system SHALL use truth sets over {below, at, above}: `>=` is {at, above}, `>` is {above}, `<=` is {below, at}, `<` is {below}, `=` is {at}, `<>` is {below, above}. Two comparisons SHALL be consistent when their sets are equal or complementary, and conflict otherwise. `test_complementary_operators_are_not_a_finding` SHALL pass and the haunted sample SHALL still raise F-001 (`>=` against `>`).

2.12 (R-10) WHEN thresholds are extracted THEN the system SHALL resolve comparison constants only from non-INPUT cells (roles or confirmed inputs passed into extraction and recomputed after the user confirms inputs), SHALL treat `50%` as 0.5, and SHALL drop the invented "formula cell compared with an input's current value" thresholds. `test_input_value_is_not_treated_as_a_threshold` and `test_expression_and_percent_thresholds_are_recorded` SHALL pass.

2.13 (R-11) WHEN a constant is compared against a threshold THEN the system SHALL classify it INPUT unless it is labelled as a rate, and table blocks SHALL stay PARAMETER. `test_input_shared_by_two_formulas_is_an_input` SHALL pass and the R-05 tests SHALL still pass.

2.14 (R-14) WHEN a second Decision is recorded for the same `finding_id` or `rule_id` THEN `ghost.decisions.store.record` SHALL reject it with `InvalidDecision` naming the existing `decision_id`, and where the workbook is known (CLI and MCP, through `source.yaml`) SHALL validate the patch when it is recorded. `test_second_decision_for_same_finding_is_rejected` SHALL pass and the web behaviour SHALL be unchanged.

2.15 (R-13) WHEN a workbook is ingested THEN the system SHALL detect `xl/vbaProject.bin` in the zip whatever the extension, extract it statically with olevba, and set `has_vba` in the upload summary from the result. `samples/make_xlsm.py` SHALL build an `.xlsm` through the Referee's `save_with_vba` without running macros (Requirement 5.15). `test_vba_found_in_renamed_macro_workbook` and `test_upload_summary_reports_vba` SHALL use that generated sample and pass without the test-bench folder.

2.16 (R-26) WHEN a formula produces text THEN the system SHALL type the output `string` in `mapping.yaml`.

2.17 (R-17) WHEN a workbook is uploaded THEN the system SHALL count cells in the existing defusedxml pre-scan against `MAX_CELLS` (for example 200,000) before openpyxl loads anything and reject with a message naming the limit, SHALL cache the analysis per session and workbook so `GET /autopsy` does not reparse, and MAY parse in a subprocess with a memory limit. A workbook of about 250,000 cells built in the test with openpyxl write-only mode SHALL be rejected in under 5 seconds, upload and autopsy of the bundled samples SHALL still work, and the limit SHALL be documented in `.kiro/steering/tech.md` and the README.

2.18 (R-18) WHEN a session starts a verification job THEN the system SHALL allow at most one queued-or-running job per session (a second `/verify` returns 429 with a clear message, or replaces the queued job; the choice is documented), and SHALL remove a session's jobs and artifacts from memory when the session is deleted or swept (`web/jobs.py:141`, `:168`). Tests SHALL cover both.

2.19 (R-21, paths) WHEN job events are shown THEN the system SHALL show names relative to the run and never absolute server paths.

2.20 (MCP error naming) WHEN `evaluate_original` receives a non-scalar input value THEN the system SHALL return `invalid_argument` naming `inputs.<cell>`, not `referee_error`.

2.21 (R-07) WHEN two numbers are compared THEN `ghost/runtime/excel.py` SHALL normalise both sides to 15 significant digits first, as Excel does. Both R-07 cases in `tests/test_review_semantics.py` SHALL pass and every other semantics test SHALL still pass.

2.22 (R-08) WHEN `INDEX` gets row or column 0 in a single-cell formula THEN the system SHALL return `#VALUE!`, and SHALL convert very large and very small numbers to text as Excel does (`1E+20&""` is "1E+20", `1E-20&""` is "1E-20"). The LibreOffice form "1E+020" SHALL be treated either as equal to the same scientific-notation value in comparison or as a listed known difference. `test_transpiler_bug[index_row_zero]` SHALL pass and the number-to-text cases SHALL be tested.

2.23 (R-27) WHEN a formula uses a workbook-scoped defined name that points at one cell or a rectangular range on one sheet THEN the system SHALL resolve it in dependencies, the emitter, thresholds and rule text (the name is the label); dynamic names (OFFSET or INDIRECT based) SHALL stay "not converted". `=Bulk*2` SHALL match the Referee, and `B2>=Bulk` SHALL record a threshold with the named cell's value.

2.24 (R-24) WHEN the semantics are documented THEN `.kiro/steering/excel-semantics.md` SHALL have a "Where LibreOffice differs from Excel" table for the seven divergences, Referee fidelity tests SHALL pin current LibreOffice behaviour so an upgrade is noticed, and the note SHALL state that the live site runs 7.4.7.2 and local development runs 26.8.3. Upgrading LibreOffice in the image is optional and only if the Docker build and the full suite pass.

2.25 (R-25) WHEN `ROUND` receives more than 15 significant digits THEN the system SHALL keep its current behaviour until the owner confirms Excel's result for `=ROUND(123456789012345.67,1)` in Excel for the web, and the report SHALL document it as unverified.

2.26 (R-15) WHEN the Power is packaged THEN `plugin/plugin.json` SHALL contain `"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"`, `toolPrefix` SHALL be removed from `plugin/mcp.json` with `tests/test_plugin_package.py` updated to match, the launch command SHALL work on a Mac with no `python` command (for example `python3`, or a `ghost-mcp` console script run with `uvx`), the prerequisites (LibreOffice and Ghost's Python dependencies) SHALL be documented in the skills and README, and a checklist for installing the Power from the GitHub URL SHALL be left for the owner. `test_plugin_manifest_has_schema` SHALL pass.

2.27 (R-16) WHEN the routing dry run prints the `atx` command THEN it SHALL include `-t` next to `-x`, SHALL say the transformation definition must be created first (check with `atx custom def list`), SHALL not call the command "exact", and SHALL use `python3 -m py_compile **/*.py` as the build command or justify the current one. `test_atx_dry_run_includes_trust_all_tools_with_non_interactive` SHALL pass.

2.28 (R-21, rest) WHEN the report is generated THEN the system SHALL rename the "Exact hits" column (it shows change points) and add the real exact hits from clause 2.8, SHALL list each input's tested domain, and when both modes ran SHALL make the Faithful report downloadable too (for example `report.html?mode=faithful`).

2.29 (R-22) WHEN the autopsy page explains unanswered Findings THEN the text SHALL read "Unanswered findings keep the original behaviour and are listed in the report."

2.30 (R-23) WHEN the dark theme is shown THEN `--border` SHALL have at least 3:1 contrast (`#7a6d94` gives 3.96:1 on the background and 3.65:1 on the surface), and the theme toggle's label SHALL stay constant (for example "Light mode") while `aria-pressed` carries the state.

2.31 (R-20) WHEN the test suite runs THEN it SHALL include: golden semantics tests built from `samples/make_traps.py`, marked `@pytest.mark.golden`, checking each in-scope row of the Excel semantics table against the Referee and generated code; a `tests/fixtures/excel-saved/` folder with a README explaining how to make files in Excel for the web, and a sanity test that skips with a message naming the folder when it is empty and never fakes a result; a Hypothesis formula-fuzzing test over the P0 subset (small depth, small values, R-24 differences excluded) that shrinks failures to the smallest formula; a CLI end-to-end test that runs `scripts/demo.sh` into a temp folder and checks its outputs; and a 500-case performance test under 60 seconds, marked slow.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the haunted sample (b) is analysed THEN the system SHALL CONTINUE TO raise Finding F-001 (`>=` against `>` on the bulk threshold).

3.2 WHEN the haunted sample is verified in Faithful mode THEN the system SHALL CONTINUE TO pass 300 cases with zero mismatches.

3.3 WHEN D-001 ("bulk means 50 or more") is recorded and the haunted sample is verified in Intended mode THEN the system SHALL CONTINUE TO pass with exactly one expected difference (reported once, classified "expected by decision F-001 D-001") whose minimal counterexample is quantity = 50.

3.4 WHEN the full suite runs after any finding is fixed THEN the system SHALL CONTINUE TO be green (`.venv/bin/python -m pytest -q`). The baseline is 192 passed and 19 xfailed. Each fix moves its tests from xfailed to passed and adds new passing tests, and the final state has no `xfail` marker in `tests/test_review_*.py` except for findings marked deferred with a reason in the Resolution table.

3.5 WHEN a fix makes a strict-xfail test pass THEN the team SHALL CONTINUE TO keep that test and remove only its `xfail` marker. No test is deleted and no expectation is weakened; if a test seems to expect the wrong thing, work stops and the evidence is shown to the owner.

3.6 WHEN a bundled sample (discount, haunted, scenarios) runs through the CLI or web flow with default inputs THEN the system SHALL CONTINUE TO pass Faithful verification, and `scripts/demo.sh` SHALL CONTINUE TO pass after each phase (discount passes; haunted raises F-001 and passes Faithful; haunted with D-001 passes Intended).

3.7 WHEN any fix touches money, rounding, macros, unsupported constructs or reports THEN the system SHALL CONTINUE TO obey the Ghost guardrails: no behaviour change without a recorded Decision, Decimal for money (floats converted with `Decimal(repr(x))`), Excel rounding, no macros from uploads, no invented data ("not checked" for checks that did not run), unsupported constructs listed as "not converted", and no secrets in the repository.

3.8 WHEN a migration is generated twice from identical input THEN the system SHALL CONTINUE TO produce identical code, rule text, `rule_id` values and reports (no timestamps or random values in generated artifacts).

3.9 WHEN a report is produced THEN the system SHALL CONTINUE TO validate against `proof-report-1.json`, and the uploaded workbook SHALL CONTINUE TO be copied and never modified.

3.10 WHEN work on this spec runs THEN the team SHALL CONTINUE TO make no push and no deploy, run no AWS command that changes anything, and leave changes uncommitted unless the owner asks; the owner deploys with `scripts/deploy_ecs_express.sh`.

3.11 WHEN a finding is fixed or deferred THEN the team SHALL CONTINUE TO log the Kiro feature used and what changed in `docs/KIRO_USAGE.md`, and SHALL add a "Resolution" table (one row per finding: fixed or deferred, reason, test) at the end of `docs/TEST_REPORT_2026-11-24.md`.

3.12 WHEN a later fix would change the demo flow or looks much bigger than described THEN the team SHALL CONTINUE TO stop and ask the owner first.
