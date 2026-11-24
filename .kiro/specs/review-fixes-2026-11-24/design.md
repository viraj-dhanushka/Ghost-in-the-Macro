# Review Fixes 2026-11-24 Bugfix Design

## Overview

The 24 November review found 29 defects (R-01 to R-29). They fall into five groups: demo and submission blockers (R-05, R-12, R-19, R-29), weak proof (R-01 to R-04, R-06, R-28), autopsy, decision and ingestion errors (R-09 to R-11, R-13, R-14, R-26), robustness (R-17, R-18, R-21 paths, MCP error naming), and transpiler, Referee, packaging and test-coverage gaps (R-07, R-08, R-15, R-16, R-20 to R-25, R-27).

The fix approach is test first and phased, in the order of `docs/KIRO_FIX_PROMPT_2026-11-24.md`. Nineteen strict-xfail tests already encode the correct behaviour. Each fix makes its test pass and then removes the `xfail` marker. Findings without a test get one first. The haunted demo (F-001, Faithful 300 cases, Intended with D-001 and quantity = 50) must hold after every task.

Dependencies between fixes that the task order respects:
- R-03 and R-04 must land before R-06 can claim the ROUND-digit mutants are killed.
- R-05 (PARAMETER heuristics) and R-11 (INPUT for compared constants) pull in opposite directions; R-11 must keep the R-05 tests green.
- R-10 (constants only from non-INPUT cells) feeds R-04 (condition-flip probing) and R-27 (named thresholds).
- R-04's exact hits feed the report column in R-21 (rest).
- R-20 golden tests feed the R-29 hook.

## Glossary

- **Bug_Condition (C)**: For each finding, the input or workbook feature that triggers the defect (see Bug Details).
- **Property (P)**: The behaviour required for inputs where C holds (the "Done when" text, clauses 2.1 to 2.31).
- **Preservation**: The demo storyline, the green suite, the guardrails and the process rules (clauses 3.1 to 3.12).
- **Finding / Decision**: Ghost terms. A Finding (F-001) is a contradiction in a workbook. A Decision (D-001) is the human answer recorded in `decisions.yaml`.
- **Faithful / Intended mode**: Faithful reproduces the workbook exactly. Intended applies Decisions.
- **Referee**: Headless LibreOffice used as the oracle.
- **Trace hook**: The comparison-tracing hook in `ghost/converter/emit_python.py`, used by the verifier and the mutation check.
- **Condition-flip probing**: New in R-04. Binary search over numeric inputs for the point where an IF condition changes truth value.
- **Strict xfail**: `@pytest.mark.xfail(strict=True)`. An unexpected pass fails the suite, which forces removal of the marker.
- **Baseline**: `192 passed, 19 xfailed` before any fix.

## Bug Details

### Bug Condition

The defects are independent, so the bug condition is a disjunction over the findings. Each disjunct is a concrete input class.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type GhostScenario  // workbook, inputs, mode, decisions, request or repository state
  OUTPUT: boolean

  RETURN (X.sample = "scenarios" AND X.useAutopsyDefaults)                           // R-05
      OR (X.autopsyRole("Calculator!E5") = INPUT)                                     // R-12
      OR X.repoState.readmeLacksSetup                                                 // R-19
      OR (X.hook IN hooks AND X.hook.interpreter = "python3")                         // R-29
      OR (X.mode = "intended" AND X.mismatchIsUnrelatedToDecision)                    // R-01
      OR (X.mode = "faithful" AND X.mismatchIsTranslationBug AND X.outputDependsOnFinding) // R-02
      OR (X.input.validation = "decimal" AND X.input.sample IS whole)                 // R-03
      OR X.threshold.onCalculatedCellOrExpression                                     // R-04, R-10
      OR X.mutantSurvivedWithEquivalentLabel                                          // R-06
      OR X.report.casesTested > X.report.distinctInputs                               // R-28
      OR X.findingOperators ARE complementary                                         // R-09
      OR X.constantComparedIsInputCell OR X.thresholdSideIsPercentOrNamed             // R-10
      OR X.inputSharedByTwoFormulasWithThreshold                                      // R-11
      OR X.decisionRecordedTwiceForFinding                                            // R-14
      OR X.workbookHasVbaProject AND NOT X.suffixIs(".xlsm")                          // R-13
      OR X.outputIsTextAndTypedDecimal                                                // R-26
      OR X.workbook.cellCount > MAX_CELLS                                             // R-17
      OR X.session.activeJobs >= 1 OR X.session.deleted                               // R-18
      OR X.jobEventContainsAbsolutePath                                               // R-21
      OR X.mcpEvaluateOriginalInput IS NOT scalar                                     // MCP naming
      OR X.formulaComparesDivisionResult                                              // R-07
      OR X.formula IN {INDEX(r,0), number-to-text of 1E+20 or 1E-20}                  // R-08
      OR X.formulaUsesDefinedName                                                     // R-27
      OR X.formulaHitsLibreOfficeExcelDivergence                                      // R-24
      OR X.roundOperandExceeds15SignificantDigits                                     // R-25
      OR X.pluginManifestLacksSchema OR X.atxCommandLacksTrustFlag                    // R-15, R-16
      OR X.reportColumnMislabelledOrFaithfulReportHidden OR X.uiTextFalse             // R-21, R-22
      OR X.darkBorderContrast < 3.0 OR X.toggleLabelChangesWithState                  // R-23
      OR X.testCategoryMissing                                                        // R-20
END FUNCTION
```

### Examples

- **R-01**: haunted `logic.py` with D-001 plus VAT 21%. Expected: FAIL, class "translation bug". Actual: `PASS: 1 cases, 1 mismatch(es)` at quantity = 0.
- **R-03**: a distance module that truncates to whole km. Expected: FAIL once fractional distances are generated. Actual: PASS 300 cases, all `int`.
- **R-04**: `B12 = IF(B11>=500,"Gold","Standard")` with a `>` module. Expected: FAIL at the order that totals exactly 500.00. Actual: PASS 300 cases.
- **R-05**: sample (c) with 53 pre-checked inputs. Expected: PASS. Actual: FAIL at case 1, `best_scenario` expected `0.0`, actual `''`.
- **R-07**: `=1/3*3=1`. Expected TRUE. Actual `False`.
- **R-09**: `B1=IF(A1>=50,1,0)` and `B2=IF(A1<50,2,3)`. Expected: no Finding. Actual: F-001.
- **R-14**: a second `record_decision` for F-001. Expected: rejected naming D-001. Actual: D-002 accepted, then every verify fails.
- **Edge case (preservation)**: haunted, D-001, Intended, quantity = 50. Expected and actual: one expected difference.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The haunted sample raises F-001, passes Faithful over 300 cases, and with D-001 passes Intended with exactly one expected difference at quantity = 50.
- The discount sample passes Faithful, and all three bundled samples pass through the web flow with default inputs.
- The suite stays green. The baseline is 192 passed and 19 xfailed.
- Guardrails hold: Decimal money, Excel rounding, no macros from uploads, no invented data, no guessed constructs.
- Generated output is deterministic and reports validate against `proof-report-1.json`.
- No push, no deploy, no mutating AWS command, changes left uncommitted.

**Scope:**
Inputs that match none of the disjuncts of `isBugCondition` are unaffected. This includes whole-number inputs with `whole` validation, formulas without division-then-compare, workbooks without defined names, single-Decision flows in the web app, and reports where every generated case is distinct.

## Hypothesized Root Cause

Causes below come from the review report and are already pinned to file and line. Each task confirms its cause with the existing strict-xfail test before changing code.

| Finding | Likely cause |
|---|---|
| R-05 | `autopsy/classify.py:97-104` classifies table constants and labels as INPUT. `strategies.py` generates `""`. `_inp` (`emit_python.py:66-71`) keeps `""` a string while the Referee reads an empty cell. `tests/test_product_samples.py:47-51` overrides the defaults. |
| R-12 | `_RATE_WORDS` in `classify.py` has no word matching "Free delivery within (km)". `cli.py:678` hides the problem by hard-coding inputs. |
| R-19 | README tasks 19.1 to 19.3 of the main spec were never done. |
| R-29 | Hooks call `python3`. No test carries `@pytest.mark.golden`. |
| R-01, R-02 | `verifier/classify.py:62-87` marks any mismatch whose output has a Finding cell among its precedents. `verifier/run.py:156-160` stops at the first mismatch. |
| R-03 | `converter/mapping.py:60-69` checks `isinstance(value, int)` before validation, and validation can only upgrade to integer. `infer_spec` honours validation but the verifier uses the mapping type. |
| R-04, R-10 | `cli.py:385-397` `_probe_boundaries` skips thresholds whose cell is not an input. `thresholds.py:45-61` `operand()` resolves any constant cell and only bare references and numeric literals count as sides. |
| R-06 | `mutation/run.py:118` hard-codes the "equivalent on tested domain" reason. |
| R-28 | The case counter counts generated cases, not distinct inputs. |
| R-09 | `findings.py:28` flags any group with two or more different operators. |
| R-11 | `classify.py:99`, `shared_fixed = len(users) >= 2 and score == 1`. |
| R-14 | `decisions/store.py:154` `record` checks neither duplicates nor patch applicability. Only `web/flow.py` checks. |
| R-13 | `cli.py:107` extracts VBA only for `.xlsm`. `web/app.py:76` reads `wb.vba_modules`, which `ghost.ingest.load_workbook` never fills. |
| R-26 | `mapping.py:111` falls back to decimal when no Excel-saved value exists. |
| R-17 | `web/app.py:229` loads the upload in-process. Every `GET /autopsy` reanalyses (`web/flow.py:_describe`). The 60 s deadline is checked only between parsing steps. |
| R-18 | `web/jobs.py:141` never removes jobs. `forget_session` (`:168`) kills running jobs only. |
| R-07 | `runtime/excel.py:235-243` divides at 60 digits, and `xl_ge` and `xl_eq` (`:403-433`) compare exactly. |
| R-08 | `emit_python.py:208-209` maps INDEX 0 to `#REF!`. Number-to-text lacks Excel's scientific notation. |
| R-27 | The parser raises "named reference not supported". |
| R-15, R-16 | Missing `$schema`, undocumented `toolPrefix`, `python` launcher, `-t` omitted. |
| R-21 | `report/html.py:167-169` shows change points. `cli.py:559` returns only the Intended report. Job events carry absolute paths. |

## Correctness Properties

Property 1: Bug Condition - Each reviewed defect produces the corrected behaviour

_For any_ scenario where the bug condition holds (isBugCondition returns true) for finding R-nn, the fixed system SHALL produce the behaviour in the matching expected-behaviour clause, and the finding's exploration test (the existing strict-xfail test, or the new test added for it) SHALL pass with its `xfail` marker removed.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15, 2.16, 2.17, 2.18, 2.19, 2.20, 2.21, 2.22, 2.23, 2.24, 2.25, 2.26, 2.27, 2.28, 2.29, 2.30, 2.31**

Property 2: Preservation - Demo storyline, suite and guardrails are unchanged

_For any_ scenario where the bug condition does NOT hold, the fixed system SHALL produce the same result as before, and after every task the haunted sample SHALL raise F-001, pass Faithful over 300 cases, and pass Intended with D-001 with exactly one expected difference at quantity = 50, with the suite green and every guardrail intact.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12**

Property 3: Intended-mode classification soundness (PBT)

_For any_ module and any case where Intended mode finds a mismatch, the mismatch SHALL be classified "expected by decision" if and only if the Faithful module matches the Referee on that case, the Intended module differs from the Faithful module on that case, and the Decision's patched comparison evaluates differently in the two modules. Otherwise it SHALL be a "translation bug".

**Validates: Requirements 2.5, 2.6**

Property 4: Operator consistency (PBT)

_For any_ two comparison operators on the same cell and constant, the pair SHALL be reported as a conflict if and only if their truth sets over {below, at, above} are neither equal nor complementary.

**Validates: Requirements 2.11**

Property 5: Type inference (PBT)

_For any_ input cell with data validation and sample value, the mapping type and the verifier strategy type SHALL be equal, and `decimal` validation SHALL give a decimal type for every sample value.

**Validates: Requirements 2.7**

Property 6: Condition-flip probing finds the boundary (PBT)

_For any_ IF condition that is monotone in one numeric input, the probe SHALL return a pair of values on opposite sides of the flip that are within the search tolerance, and the extra cases SHALL include both sides and the exact hit when one exists.

**Validates: Requirements 2.8**

Property 7: Comparison normalisation (PBT)

_For any_ two decimals that differ only beyond the 15th significant digit, `xl_eq` SHALL return TRUE and `xl_ge`, `xl_le` SHALL treat them as equal. For decimals that differ within 15 digits the order SHALL be unchanged.

**Validates: Requirements 2.21**

Property 8: Decision uniqueness (PBT)

_For any_ sequence of `record` calls, at most one Decision per `finding_id` or `rule_id` SHALL be stored, and a repeat SHALL raise `InvalidDecision` naming the existing `decision_id`.

**Validates: Requirements 2.14**

Property 9: Formula fuzzing agrees with the Referee (PBT)

_For any_ formula drawn from the P0 grammar (excluding the R-24 divergences), the transpiled module SHALL equal the Referee within 1e-6 for numbers, exactly for strings, and by type for errors.

**Validates: Requirements 2.31**

## Fix Implementation

### Changes Required

Files are listed per phase. The prompt's phase order is the implementation order.

**Phase 1 (blockers)**
- `ghost/autopsy/classify.py`: table blocks and `INDEX`/`MATCH` text become PARAMETER (R-05). Extend `_RATE_WORDS` and add a block-of-parameters rule (R-12).
- `ghost/converter/emit_python.py`: `_inp("")` returns an empty-cell value (R-05).
- `ghost/cli.py:678` and `tests/test_product_samples.py`: default inputs equal the demo inputs; new web test for each bundled sample.
- `README.md`, `.kiro/hooks/*.json`, `tests/` (R-19, R-29).

**Phase 2 (proof integrity)**
- `ghost/verifier/classify.py`, `ghost/verifier/run.py`: three-condition test, keep going after expected mismatches, shrink one per Decision. MCP `verify_implementation` calls the same function (R-01, R-02).
- `ghost/converter/mapping.py`, `ghost/verifier/strategies.py`: one shared type-inference function (R-03).
- New `ghost/verifier/flip.py` (condition-flip probing), `ghost/cli.py` `_probe_boundaries`, `ghost/mutation/run.py` (R-04, R-10 expressions).
- `ghost/mutation/run.py`: new survivor wording and tested domains (R-06).
- `ghost/report/model.py`, `ghost/report/html.py`, `ghost/report/schema/proof-report-1.json`: optional `distinct_cases` field (R-28).

**Phase 3 (autopsy, decisions, VBA)**
- `ghost/autopsy/findings.py` (R-09), `ghost/autopsy/thresholds.py` and `classify.py` (R-10, R-11), `ghost/decisions/store.py` (R-14), `ghost/ingest/` and `web/app.py` and `samples/make_xlsm.py` (R-13), `ghost/converter/mapping.py` (R-26).

**Phase 4 (security)**
- `ghost/ingest/limits.py` (`MAX_CELLS`), `web/flow.py`, `web/app.py` (R-17); `web/jobs.py` (R-18); job event text (R-21 paths); `mcp_server/server.py` (error naming).

**Phase 5 (semantics)**
- `ghost/runtime/excel.py` (R-07, R-08), `ghost/converter/parser.py`, `emit_python.py`, `ghost/autopsy/thresholds.py`, `ghost/rules/` (R-27), `.kiro/steering/excel-semantics.md` and Referee tests (R-24), documentation only (R-25).

**Phase 6 (polish)**
- `plugin/plugin.json`, `plugin/mcp.json`, `tests/test_plugin_package.py` (R-15); `ghost/router/route.py` (R-16); `ghost/report/html.py`, `ghost/cli.py:559` (R-21 rest); `web/templates/_autopsy.html`, `web/static/style.css`, `web/static/theme.js` (R-22, R-23).

**Phase 7 (tests)**
- New golden, fixture, fuzz, e2e and performance tests (R-20), README update.

**Cross-cutting**
- `docs/KIRO_USAGE.md` entry per fix. Resolution table appended to `docs/TEST_REPORT_2026-11-24.md`.

**Stop and ask the owner** if any of these turns out bigger than described: R-01 (classification change touches the demo's Intended run), R-04 (condition-flip probing), R-27 (named ranges), R-17 (subprocess parsing), R-05 (if the PARAMETER heuristic changes the demo defaults), and R-28 (schema change).

**Decisions made in this design where the sources leave a choice:**
- R-18: the second `/verify` returns 429 (the other option, replacing the queued job, is rejected because it silently discards work). The message and the README document this.
- R-15: launch with `python3` unless `uvx` is available and tested; the choice is recorded in `docs/KIRO_USAGE.md`.
- R-16: use `python3 -m py_compile **/*.py` as the build command, as in AWS's VBA example.
- R-23: keep the toggle label constant ("Light mode") with `aria-pressed`.
- R-17: `MAX_CELLS = 200_000`; the 250,000-cell test file is rejected well above it.

## Testing Strategy

### Validation Approach

Two phases per finding: confirm the bug with the existing strict-xfail test (the exploration test), then fix and confirm the same test passes, with the marker removed. Findings without a test get a failing test first.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples on unfixed code. The 19 strict-xfail tests already do this and fail (xfail) today.

**Test Plan**: Run `.venv/bin/python -m pytest -q tests/test_review_*.py` and confirm `192 passed, 19 xfailed` before the first change. For findings with no existing test, write the test and watch it fail.

**Test Cases**:
1. **Proof strength**: `test_intended_mode_does_not_excuse_unrelated_bug`, `test_faithful_translation_bug_is_labelled_translation_bug`, `test_truncated_distance_is_caught`, `test_gold_threshold_on_calculated_cell_is_caught`, `test_scenarios_sample_passes_with_default_inputs` (R-01 to R-05). These need LibreOffice.
2. **Autopsy and packaging**: R-09, R-10 (two), R-11, R-12, R-03, R-13 (two), R-14, R-15, R-16 tests in `test_review_autopsy_and_packaging.py`.
3. **Semantics**: `test_transpiler_bug` cases for R-07 (two) and R-08 (`index_row_zero`).
4. **No test yet**: R-06 (the passing evidence test `test_decimal_distance_mutants_are_not_equivalent` stays as is), R-17, R-18, R-19, R-21, R-22, R-23, R-24, R-26, R-27, R-28, R-29, MCP naming, R-08 number-to-text. A new test is written first for each.

**Expected Counterexamples**:
- Mismatch at quantity = 0 reported "expected by decision" (R-01).
- Only `int` distances generated (R-03).
- `Calculator!B12` absent from boundaries (R-04).
- `''` against `0.0` at case 1 on sample (c) (R-05).

### Fix Checking

**Goal**: For every input where the bug condition holds, the fixed system gives the expected behaviour.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result := fixedSystem(X)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**Goal**: Inputs outside the bug condition behave as before.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT originalSystem(X) = fixedSystem(X)
END FOR
```

**Testing Approach**: Property-based tests where the input domain is large (Properties 3 to 9). The demo invariants are checked by `scripts/demo.sh` and by a small script of assertions on its outputs, after each phase.

**Test Plan**: Before the first fix, run `scripts/demo.sh` and the suite and record the outputs. After each phase, compare.

**Test Cases**:
1. **Demo storyline**: F-001 raised, Faithful 300 cases pass, Intended with D-001 passes with one expected difference at quantity = 50.
2. **Discount sample**: Faithful passes 300 cases; the half-even rounding mutant is still caught at 455 × 0.03.
3. **Web flow**: each bundled sample with default checkboxes passes (new test); haunted with D-001 passes Intended.
4. **Existing suite**: all 192 passing tests stay green.

### Unit Tests

- Autopsy classification, thresholds and findings (R-05, R-09 to R-12).
- Decision store (R-14), mapping and strategy inference (R-03, R-26), ingestion limits and VBA detection (R-13, R-17).
- Job runner caps and cleanup (R-18), job-event path scrubbing (R-21), MCP error naming.
- Runtime comparison and INDEX behaviour (R-07, R-08), named-range resolution (R-27).
- Plugin manifest, `atx` command text, UI text and CSS contrast (R-15, R-16, R-22, R-23).

### Property-Based Tests

- Properties 3 to 9 above, using Hypothesis with an explicit seed, each citing its property number and requirements.
- Existing property tests (tolerance symmetry, `rule_id` stability) stay unchanged.

### Integration Tests

- Web flow for each bundled sample through `POST /sample/{id}`, `GET /autopsy` and `POST /verify` (FastAPI TestClient).
- Intended-mode run on the haunted sample, including MCP `verify_implementation`.
- CLI end-to-end through `scripts/demo.sh` (R-20), and the 500-case performance test.
- Golden semantics tests against the Referee and generated code.
