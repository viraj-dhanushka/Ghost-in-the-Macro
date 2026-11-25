# Live Fixes 2026-11-24 Bugfix Design

## Overview

The live test of 24 November found seven defects, L-02 to L-08 (`docs/LIVE_TEST_REPORT_2026-11-24.md`). Four give wrong results: the report writer crashes on Excel error values (L-02), `INDEX(range,0)` ignores implicit intersection (L-03), a tier rule on a calculated cell is never hit exactly at its threshold (L-04), and a not-converted output is pre-checked and then called a translation bug (L-05). Three are polish: the boundary table layout (L-06), two different tested domains in one report (L-07), and an unexplained low mutation score on the scenarios sample (L-08).

The approach is test first and phased, following `docs/KIRO_FIX_PROMPT_LIVE_2026-11-24.md`. Every repro workbook is built inside the test with openpyxl into `tmp_path`. Each finding gets a strict-xfail test that fails on the current code, and the fix removes only the marker. The demo storyline, the haunted and discount mutation scores and the suite baseline (`415 passed, 2 skipped`) are checked at each phase checkpoint.

Order and dependencies:
- L-02 comes first. L-03 and L-05 are verified through web jobs, and a web job cannot show a report until L-02 is fixed (the L-03 repro's mutants also produce `#REF!`).
- L-06's "Exact hits" column depends on L-04's integer exact hits.
- L-07 changes which targeted values exist, so it lands before L-08, whose search runs over the same domains.
- L-04 and L-07 both change the targeted case set for haunted. Either can change the haunted counts ("300 generated + 9 targeted, 198 distinct") and the mutation scores, so both stop and ask the owner if that happens.

## Glossary

- **Bug_Condition (C)**: For each finding, the workbook, request or report state that triggers the defect. The overall condition is the disjunction in Bug Details.
- **Property (P)**: The behaviour required where C holds: the "Done when" text in clauses 2.1 to 2.7.
- **Preservation**: Clauses 3.1 to 3.15: demo storyline, mutation scores, suite baseline, guardrails and process rules.
- **F / F'**: Ghost before and after the fix.
- **Referee**: Headless LibreOffice running the original workbook as the oracle. Live runs 7.4.7.2; local development runs 26.8.3.
- **`ExcelError`**: The error value class in `ghost/runtime/excel.py:72`. Its `code` attribute holds the text, for example `"#VALUE!"`.
- **Implicit intersection**: When a single-cell formula receives a whole row or column, the Referee picks the element on the formula cell's own row (or column) if it lies inside the range.
- **Condition flip / exact hit**: From `ghost/verifier/flip.py`. A flip is a pair of input values (`below`, `above`) on opposite sides of an IF condition. An exact hit is an input value at which the compared sides are equal.
- **Trace hook**: The comparison-tracing hook in the generated module. It reports each condition's truth value and, after this fix, the two compared values.
- **Targeted cases**: Cases added on top of the 300 generated ones: flip cases (`flip_extra`) and `candidate_inputs` (`ghost/verifier/coverage.py:77`).
- **Effective domain**: An input's `IOSpec` min and max, with `VerifyConfig.default_max` (10,000, `ghost/verifier/run.py:53`) filled in where the `IOSpec` has no max. This is the domain the "Tested domains" table reflects.
- **Not converted / not verifiable as-is**: Cells listed by `find_not_converted` (`ghost/converter/subset.py:85`), and features with `not_verifiable` set (volatile and external constructs).
- **Repro workbooks**: `sem_index` (L-02, L-03), `tier` (L-04), `sem_names` (L-05), as specified in the prompt.

## Bug Details

### Bug Condition

The seven defects are independent, so the bug condition is a disjunction. Each disjunct is a concrete input class.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type GhostRun  // workbook, chosen inputs and outputs, mode, decisions, rendered report
  OUTPUT: boolean

  RETURN (EXISTS v IN X.reportEngineValues : v IS ExcelError)                          // L-02
      OR (X.jobFailedForReasonOtherThanMismatches)                                     // L-02 panel text
      OR (EXISTS cell IN X.outputs :
            cell.formula CONTAINS INDEX(rng, 0 [, ...])
            AND (rng.cols = 1 AND rng.rows > 1 AND cell.row IN rng.rowSpan
                 OR rng.rows = 1 AND rng.cols > 1 AND cell.col IN rng.colSpan))       // L-03
      OR (EXISTS cond IN X.ifConditions :
            cond.side IS calculated from >= 2 numeric inputs
            AND NOT exactHitReachableFromSampleValues(cond)
            OR cond.flipsOnIntegerInput)                                              // L-04
      OR (EXISTS cell IN X.offeredOrSelectedOutputs :
            cell IN notConverted(X.workbook) OR cell IN notVerifiable(X.workbook))   // L-05
      OR (X.report.boundaries IS NOT EMPTY)                                           // L-06
      OR (EXISTS v IN X.targetedValues : v OUTSIDE effectiveDomain(v.input))          // L-07
      OR (EXISTS out IN X.outputs : out IS selected by MAX, MIN or MATCH
            AND X.casesChangingWinner = 0)                                            // L-08
END FUNCTION
```

### Expected Behavior Specification

```
FUNCTION expectedBehavior(X, result)
  INPUT: X of type GhostRun, result of type JobResult
  OUTPUT: boolean

  RETURN result.reportWritten
         AND (FOR ALL v IS ExcelError IN engineValues(X) : reportText(v) = v.code)    // L-02
         AND (result.failedForOtherReason IMPLIES
              result.panel STARTS WITH "The report could not be written"
              AND result.panel NAMES exceptionType AND NOT containsServerPath(result.panel))
         AND (FOR ALL INDEX(rng,0) cells : ghost(cell) = referee(cell))                // L-03
         AND (FOR ALL flip conditions with a reachable equality :
              result.boundaries HAS exact hit confirmed by the trace hook
              AND exact-hit case IN verifierCases AND IN mutationCases)               // L-04
         AND (defaults(X) ∩ (notConverted ∪ notVerifiable) = ∅
              AND explicitSelection(notConverted ∪ notVerifiable) IS rejected naming cell and reason
              AND result.report.not_converted LISTS every not-converted cell)        // L-05
         AND boundaryColumnsReadable(result.html)                                      // L-06
         AND survivorDomains(result) ⊆ testedDomainsTable(result)                      // L-07
         AND (result.scenariosScore > 55/132 WITH winner-changing cases
              OR result.report.mutation EXPLAINS remaining survivors)                 // L-08
END FUNCTION
```

### Examples

- **L-02**: `sem_index`, input `Calc!B1`, output `Calc!B4` (`=INDEX(M1:M1,0)`). Expected: job done, Faithful pass (7 on both sides), report downloadable, mutation score shown. Actual: job `failed`, "Verification found mismatches.", `report.json` 404, `TypeError: Object of type ExcelError is not JSON serializable` (live job `Q9AJ-lpaRwgwaabm`).
- **L-03**: `sem_index`, output `Calc!B3` (`=INDEX(M1:M3,0)` on row 3). Expected: 9, as the Referee. Actual: `#VALUE!` (local; the live job `_wl241QgcLA4-GAU` failed on L-02 first).
- **L-04**: `tier`, inputs B2 = 3 and B3 = 25.5, output B5. Expected: a boundary with an exact hit where Total = 500 (for example quantity 1, price 500), and the `flip_comparison` mutant on B5 killed. Actual: brackets 166.666/166.667 and 19/20, exact `None`, mutation 4 of 5, survivor `M-e39c9b66` (live job `rWR5ZAGFf_qnh3q5`).
- **L-05**: `sem_names`, default boxes B2, E1 → C2, C3, C4. Expected: defaults → C2, C3; C4 listed as not converted. Actual: C4 pre-checked; first case fails as "translation bug" with actual `None` (live job `Pl8wPBBeITA8UvIV`).
- **L-06**: haunted report, job `zBkkB8Vok9fwCW0q`. Flip text sits under "Owner of threshold", threshold rows show `[{"first_changed": 50, "last_unchanged": 49}]`, "Exact hits" says "not checked" for quantity 50.
- **L-07**: haunted survivors say `quantity: integer, min -1`; the table says min 0. Scenarios survivors say `gross_income … max 60000`; the table says max 10000.
- **L-08**: scenarios, job `PTGz_4QP4TtdgXDU`: mutation 55/132, `cases_targeted` 0, 77 survivors (`constant_plus_one` 36, `constant_minus_one` 31, `rounding_mode` 10), mostly on rows F6 to F15 and B6 to E15.
- **Edge case (preservation, L-02)**: `=10/B1` at B1 = 0 is `#DIV/0!` on both sides. Expected and actual: pass (live job `I_gq7peCOkZqvyMk`).
- **Edge case (preservation, L-03)**: `=INDEX(M1:M3,0)` on a row outside 1 to 3 stays `#VALUE!` on both sides. The existing cases in `tests/test_review_semantics.py` place formulas in column B on rows after the M range, so they pin this case.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `scripts/demo.sh <temp dir>`: discount passes Faithful. Haunted raises F-001 and passes Faithful with 0 mismatches. Haunted with D-001 passes Intended with exactly one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0).
- Mutation scores: haunted at least 33/35 and discount at least 31/33. No mutant is dropped or hidden and the score formula is unchanged.
- Suite: 0 failed, from the baseline `415 passed, 2 skipped` (417 collected). Strict-xfail tests added by task 1 count as xfailed until their fix lands.
- Default boxes of the three bundled samples (clause 3.11).
- An Excel error on both sides of an output still passes (clause 3.9).
- `INDEX` cases pinned today (R-30 single-cell, non-zero indexes, row 0 outside the range's rows) keep their results (clause 3.10).
- Reports validate against `proof-report-1.json` with new fields optional. Output is deterministic. No server paths. The uploaded workbook is copied and never modified.
- Guardrails: no invented values, "not checked", "not converted" with cell and reason, "not verifiable as-is", Decimal money, Excel rounding, no macros from uploads.
- Process: no push, deploy or AWS command; changes left uncommitted; logging in the live test report and `docs/KIRO_USAGE.md`.

**Scope:**
All inputs that match no disjunct of `isBugCondition` are unaffected. This includes:
- Reports whose engine values hold no `ExcelError`, and jobs that end with real mismatches (the panel still says "Verification found mismatches.").
- `INDEX` with non-zero arguments, on a single cell, or from a formula cell outside the range.
- IF conditions on a single input whose exact hit is already reachable (decimal inputs today).
- Workbooks with no not-converted or not-verifiable cells.
- Targeted values already inside the effective domain.

## Hypothesized Root Cause

Each cause below was checked against the code at the cited lines while writing this design. The exploration tests in task 1 confirm or refute each one before any fix.

1. **L-02, serialisation**: `_jsonable` (`ghost/report/model.py:58-72`) converts `Decimal`, `date`, `Enum`, containers and NaN, but has no branch for `ExcelError`. `report_to_json` (`:144-148`) then calls `json.dumps` on the result and raises `TypeError`. The HTML report is rendered from the same dict, so it fails the same way.

2. **L-02, panel text**: `web/jobs.py:278-281` maps any subprocess exit code 1 to "Verification found mismatches.". The CLI returns `EXIT_FAIL = 1` (`ghost/cli.py:94`) both for mismatches and for every caught error in `main` (`:922-943`), and an uncaught exception such as this `TypeError` makes Python exit with 1 as well. Exit code 1 therefore cannot tell mismatches from crashes.

3. **L-03**: `_index` (`ghost/converter/emit_python.py:197-226`) returns `VALUE` when row 0 meets `rng.rows != 1` (or column 0 meets `rng.cols != 1`). It cannot do anything else: `range_arg` (`:414-421`) emits `_Rng(rows, cols, [values])` with no origin, and the call site (`:487`) does not pass the formula cell's position.

4. **L-04, single-input search**: `_search` (`ghost/verifier/flip.py:324-372`) varies one input at a time from the base inputs, so on `tier` the other input stays at its sample value (3 or 25.5) and no grid point gives Total = 500 exactly.

5. **L-04, integer exact hits**: `flip.py:370` sets `exact = None if integer`, so an integer flip (haunted quantity 49/50 on `>=50`) never records the exact hit, even when `above` or `below` makes the comparison an equality.

6. **L-05**: `_describe` (`web/flow.py:116-153`) builds `out_cells` from roles OUTPUT and INTERMEDIATE and pre-checks every OUTPUT, without removing `find_not_converted` cells or not-verifiable features, though it computes both lists for the page. The emitter leaves such outputs out of the result (`emit_python.py:8-11`), so `actual` is `None`, and the verifier's classifier calls that a translation bug. The CLI and MCP defaults (`mcp_server/server.py:263`) have the same gap.

7. **L-06**: `html.py:191-201` puts the flip text in the "Owner of threshold" cell, writes `b["exact_hits"]` (a list of change-point dicts) straight into "Change-point bracket", and shows `b["threshold"]`, which for flip rows holds the change point.

8. **L-07**: `candidate_inputs` (`ghost/verifier/coverage.py:77-96`) adds 0 and -1 to every numeric input and keeps the sample as base, with no domain check. The mutation check passes them as targeted cases (`ghost/cli.py:613`; `ghost/mutation/run.py:211`, `tested = baseline.cases + extra`), and the survivor reason is computed over that set (`mutation/run.py:145-169`). The "Tested domains" table is computed over the verification cases only (`ghost/cli.py:646`, `tested_domain_rows(mapping, res.cases)`), which come from strategies bounded by the effective domain. The scenarios max of 10,000 comes from `VerifyConfig.default_max` (`ghost/verifier/run.py:53`), not from the `IOSpec`, and the sample value 60,000 lies outside it.

9. **L-08**: Targeted cases come only from IF conditions (flip probing) and threshold constants. `MAX`, `MIN` and `MATCH` selections have no condition to flip, so `cases_targeted` is 0 and nothing aims at changing the winning row.

## Correctness Properties

Property 1: Bug Condition - Each live finding produces the corrected behaviour

_For any_ run where the bug condition holds (isBugCondition returns true) for finding L-0n, the fixed system SHALL produce the behaviour in the matching expected-behaviour clause, and that finding's exploration test from task 1 (or the test-first test written in its Phase 2 task) SHALL pass with its `xfail` marker removed.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

Property 2: Preservation - Demo storyline, mutation scores, suite and guardrails are unchanged

_For any_ run where the bug condition does NOT hold, the fixed system SHALL produce the same result as the original. After every phase, `scripts/demo.sh` SHALL give discount Faithful pass, haunted F-001 and Faithful 0 mismatches, and haunted with D-001 Intended pass with exactly one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0). The haunted and discount mutation scores SHALL be at least 33/35 and 31/33, and the suite SHALL have 0 failed.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15**

Property 3: Excel errors serialise as their text (PBT)

_For any_ proof report whose mismatch inputs, expected and actual values, mutant counterexamples or boundary cases contain `ExcelError` values of any code (`#DIV/0!`, `#VALUE!`, `#REF!`, `#N/A`, `#NUM!`, `#NAME?`, `#NULL!`), mixed with Decimals, strings, booleans and `None`, `report_to_json` SHALL succeed, the result SHALL validate against `proof-report-1.json`, each `ExcelError` SHALL appear as its `code` text, the HTML report SHALL show the same text, and two calls on the same report SHALL give identical bytes.

**Validates: Requirements 2.1, 3.12**

Property 4: INDEX with 0 follows implicit intersection (PBT)

_For any_ single-column range of n ≥ 2 rows starting at row t and any formula cell row r, the runtime `_index(rng, 0)` SHALL return the element at position r − t + 1 when t ≤ r ≤ t + n − 1 and `#VALUE!` otherwise. The same SHALL hold by column for a single-row range with column 0, and a single-cell range SHALL return its value for any formula position (R-30). Each rule SHALL first be measured on the Referee (task 3.5).

**Validates: Requirements 2.2, 3.10**

Property 5: Exact hits are found and confirmed for product and integer thresholds (PBT)

_For any_ condition `a * b op t` (op in `>=`, `>`, `<=`, `<`) with a an integer input, b an integer or decimal input, both domains containing 1, and t a whole number inside the reachable range, `find_flips` SHALL return a flip for the condition with an exact hit at which the trace hook reports the two compared values as equal, SHALL never report an exact hit the trace hook does not confirm, and SHALL stay within its evaluation budget, adding a `boundary_notes` entry when the budget cut the search short.

**Validates: Requirements 2.3**

Property 6: Not-converted and not-verifiable cells are never offered as outputs (PBT)

_For any_ generated workbook mixing convertible formulas with not-converted formulas (OFFSET- or INDIRECT-based names, unsupported functions) and volatile formulas (NOW, TODAY, RAND, RANDBETWEEN), including formulas that depend on them, the default outputs from the web autopsy, the CLI and MCP SHALL contain no cell listed by `find_not_converted` or flagged not verifiable, and an explicit request for one SHALL be rejected naming the cell and the reason.

**Validates: Requirements 2.4, 3.11**

Property 7: Targeted values stay inside the effective domain (PBT)

_For any_ input with integer or decimal type and any effective domain [min, max] (min possibly negative, max possibly absent so `default_max` applies), any base value and any threshold constants, every value produced by `candidate_inputs` and every flip, exact-hit or selection-change case SHALL lie inside the effective domain, and the survivor domain text SHALL be computed over the same case set as the "Tested domains" table (or carry a distinct label).

**Validates: Requirements 2.6**

## Fix Implementation

### Changes Required

Assuming the root cause analysis is confirmed by task 1:

**L-02: Excel errors in reports**

**File**: `ghost/report/model.py`
**Function**: `_jsonable`, `report_to_dict`, `report_to_json`
1. **Serialise errors**: add a branch for `ghost.runtime.excel.ExcelError` returning `value.code`, before the container branches. Route every engine-value field through `_jsonable`, including mutant `killed_by` cases and boundary cases.
2. **Schema check**: confirm every place in `ghost/report/schema/proof-report-1.json` that holds engine values accepts a string (mismatch `inputs`, `expected`, `actual` are untyped objects today; check the mutant counterexample and boundary fields). Widen only where needed, keeping old reports valid.

**File**: `ghost/report/html.py`
3. **HTML text**: render `ExcelError` text the same way, escaped like any other value.

**Files**: `ghost/cli.py`, `web/jobs.py`, `mcp_server/server.py`
4. **Distinct failure path**: in the CLI, wrap report writing so that an exception becomes one line, `ghost: error: The report could not be written (TypeError)`, and a new exit code (for example `EXIT_REPORT_NOT_WRITTEN = 4`). In `web/jobs.py:278-283`, say "Verification found mismatches." only for exit 1 with a collected report. For exit 4, or exit 1 without a report, say "The report could not be written (<exception type>)", taking the type from the CLI line and passing the text through `scrub_paths`. Fall back to the exit code when no type is known.
5. **MCP**: make the report-producing tools use the same `report_to_dict`, and return a structured error naming the exception type (never a server path) if writing fails.

**L-03: INDEX implicit intersection**

**File**: `ghost/converter/emit_python.py`
**Functions**: `range_arg`, the `INDEX` call site (`:487`), `_index`
1. **Measure first**: task 3.5 measures every case on the Referee before code changes. The rule set implemented is the measured one.
2. **Origin and position**: emit range origin (sheet, top row, left column) in `_Rng` for `INDEX` arguments, and pass the formula cell's sheet, row and column as constants (for example `_index(rng, r, c, at=("Calc", 3, 2))`). Keep the emitted text deterministic.
3. **Rule**: single column with row 0 and rows > 1: element on the formula row if inside, else `#VALUE!`. Single row with column 0 and columns > 1: the same by column. Single cell: its value (R-30, unchanged). Multi-row and multi-column ranges, and a formula on another sheet from the range: as measured.
4. **Not converted**: any measured case Ghost cannot reproduce is marked "not converted" with cell and reason when the 0 is a literal. A computed index that reaches such a case at run time returns the measured Referee result if known, otherwise the cell is not converted.

**File**: `.kiro/steering/excel-semantics.md`
5. **Documentation**: replace the "`INDEX(range,0)` … gives `#VALUE!`" line with the measured rule table, both LibreOffice versions where measured, and the note that Excel 365 spills instead and Excel's result was not checked.

**L-04: exact hits on calculated cells**

**File**: `ghost/verifier/flip.py`
**Functions**: `_search`, `_exact_hit`, `find_flips`
1. **Integer exact hits**: replace `exact = None if integer` (`:370`) with a check of `below` and `above`: evaluate each with the trace hook and record the one where the two compared values are equal. Never infer equality from the operator.
2. **Trace hook values**: if the hook reports only truth values today, extend it to report the two compared values for a condition id. The emitter change keeps generated code deterministic.
3. **Small-values retry**: when a condition flips on input x, rerun the search on x with each other numeric input set in turn to small values from {1, 2, 4, 5, 10} that lie inside its effective domain. Keep cases where the trace hook confirms an exact hit.
4. **Budget**: cap the extra evaluations per condition and in total with module constants, and add a `boundary_notes` entry naming the condition when the cap is reached.

**File**: `ghost/cli.py` (`_probe_boundaries`, `flip_extra`) and `ghost/mutation/run.py`
5. **Wiring**: add exact-hit cases to `flip_extra`, which already reaches both the verifier (`extra_cases`) and the mutation check (`targeted`). Report each exact hit in the boundary's `exact` field.

**L-05: not-converted outputs**

**Files**: `web/flow.py` (`_describe`), `ghost/cli.py` (default outputs), `mcp_server/server.py` (defaults)
1. **Defaults**: remove from offered outputs every cell in `find_not_converted` and every cell with a not-verifiable feature, plus their dependants as `find_not_converted` already lists them. Show them in the existing "not converted" and "not verifiable" lists instead.
2. **Explicit selection**: reject with HTTP 422 in `POST /verify`, `invalid_argument` in MCP, and a `CliError` in the CLI, each naming the cell and the reason. This design picks rejection over "leave out and list" because a report then never shows a pass for a set of outputs that silently lost one.

**Files**: `ghost/report/model.py`, `ghost/report/html.py`, schema
3. **Report**: add an optional `not_converted` array (`{cell, reason}`) to the report and the HTML, filled from `find_not_converted`, so the default-box report lists C4.

**L-06: boundary table**

**File**: `ghost/report/html.py:191-201`
1. **Bracket column**: flip rows show "49 → 50" from `below` and `above`; threshold rows show "49 → 50" from `last_unchanged` and `first_changed`. No raw JSON.
2. **Threshold column**: the real threshold constant, or "calculated" when the condition has none (flip rows on calculated cells).
3. **Owner column**: the operator ownership text only (`operator_includes`), or the not-checked text.
4. **Exact hits**: the `exact` field from L-04, or "not checked" only when no exact hit was searched for.

**L-07: one tested domain**

**Files**: `ghost/verifier/coverage.py` (`candidate_inputs`), `ghost/verifier/flip.py`, `ghost/cli.py`, `ghost/mutation/run.py`, `ghost/report/domains.py`
1. **Clamp**: pass each input's effective domain into `candidate_inputs` and the flip search, and drop values outside it. 0 and -1 stay only where the domain allows them.
2. **One case set**: compute the "Tested domains" table and survivor reasons over the same set (verification cases plus targeted cases), or keep two sets and label them "verification cases" and "mutation cases".
3. **Owner decision (STOP-AND-ASK)**: clamping drops the scenarios sample value 60,000 (outside `default_max` 10,000) from the mutation cases, and dropping -1 could lower the haunted or discount score. If either happens, stop and ask. Options: clamp as written; widen the effective domain to include the workbook's own sample value; or use the labelling alternative.

**L-08: aim at the winning row**

**File**: new `ghost/verifier/selection.py` (or an extension of `flip.py`), wired in `ghost/cli.py`
1. **Find selectors**: in the transpiled Faithful module, find outputs whose value comes from `MAX`, `MIN`, `MATCH` or `INDEX`/`MATCH` over a computed range.
2. **Search**: vary each numeric input across its effective domain (grid plus bisection, bounded budget, as in `flip.py`) and keep cases where the selected position changes.
3. **Feed**: add those cases to `extra_cases` and to the mutation check's targeted cases. Report the real score.
4. **Explain**: in the report's mutation section, when survivors remain on constants whose rows never win on the tested inputs, add one plain sentence saying so. Do not remove mutants or change the score formula.
5. **STOP-AND-ASK**: if the search needs more than a new module and wiring, or slows the scenarios job noticeably (live today: 30.5 s), stop and ask; the explanation sentence alone then meets the "Done when".

**Cross-cutting**
- `docs/LIVE_TEST_REPORT_2026-11-24.md`: "Live-test resolution" table at the end.
- `docs/KIRO_USAGE.md`: session entry (spec, hooks, agents), L-08 before and after scores.
- `README.md` "Limits and known differences": L-03 (implicit intersection; Excel 365 spills) and L-05 (not-converted outputs are not offered).

**Choices made in this design where the sources leave a choice:**
- L-02's "mismatch holds an Excel error" check uses a stable LibreOffice divergence from `.kiro/steering/excel-semantics.md`: `=SUM("5",1)` gives `#VALUE!` in the Referee and 6 in Ghost. The natural repro (B3 before L-03) stops mismatching once L-03 is fixed.
- L-05 explicit selection is rejected (422, `invalid_argument`, `CliError`), not silently left out.
- L-02 uses a new CLI exit code for "report not written" and keeps exit 1 for mismatches, so `scripts/demo.sh` and existing tests see no change.

## Testing Strategy

### Validation Approach

Two phases per finding. First, a test built on the repro workbook fails on the unfixed code (strict xfail with `reason="L-0n ..."`), confirming the root cause. Then the fix makes it pass, and only the marker is removed. Preservation tests observe the unfixed behaviour first and must pass before and after every fix.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate L-02 to L-05 before any fix, and confirm or refute the root causes above.

**Test Plan**: New file `tests/test_live_findings.py` with builders for `sem_index`, `tier` and `sem_names` (openpyxl into `tmp_path`, names created with `openpyxl.workbook.defined_name.DefinedName`). Run on the unfixed code and record the failures. Tests that need LibreOffice skip with a message when the Referee is unavailable.

**Test Cases**:
1. **L-02 report write**: `report_to_json` on a report with an `ExcelError("#VALUE!")` in a mismatch's actual value and an `ExcelError("#REF!")` in a mutant's counterexample (will fail: `TypeError`).
2. **L-02 web job**: `sem_index` through `TestClient` with input `Calc!B1`, output `Calc!B4`; expect status done, Faithful pass, `report.json` 200, mutation score present (will fail: job failed, 404).
3. **L-02 panel text**: a job whose subprocess fails writing the report; expect "The report could not be written (TypeError)" (will fail: "Verification found mismatches.").
4. **L-03 inside the range**: `=INDEX(M1:M3,0)` in `B3`; expect Ghost equals the Referee (9) (will fail: `#VALUE!`).
5. **L-04 exact hit**: `tier` with default boxes; expect a B5 boundary with an exact hit where Total = 500 and the `flip_comparison` mutant on B5 killed (will fail: exact `None`, mutant survives).
6. **L-05 defaults**: `sem_names` autopsy; expect C4 neither offered nor pre-checked (will fail: pre-checked).
7. **L-05 explicit selection**: `POST /verify` with C4; expect 422 naming `Calc!C4` and the reason (will fail: job runs, "translation bug").

**Expected Counterexamples**:
- `TypeError: Object of type ExcelError is not JSON serializable` from `report_to_json`.
- Ghost `#VALUE!` against Referee 9 for B3.
- Boundaries `('Calc!B5', 'price', 166.666, 166.667, None)` and `('Calc!B5', 'quantity', 19, 20, None)`, survivor `flip_comparison` on B5.
- `{'class': 'translation bug', 'output': 'calc_c4', 'actual': {... 'calc_c4': None}}`.

### Fix Checking

**Goal**: For every input where the bug condition holds, the fixed system gives the expected behaviour.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result := ghost_fixed(X)
  ASSERT expectedBehavior(X, result)
END FOR
```

### Preservation Checking

**Goal**: For every input where the bug condition does not hold, the fixed system gives the same result as the original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT ghost_original(X) = ghost_fixed(X)
END FOR
```

**Testing Approach**: Property-based testing is used where the input domain is large (Properties 3 to 7): report contents, range shapes and formula positions, threshold products, workbook mixes and domains. The demo storyline and mutation scores are checked by running `scripts/demo.sh` and reading its reports.

**Test Plan**: Before the first fix, run `scripts/demo.sh <temp dir>` and the full suite on the unfixed code and record the real output: case counts, the one expected mismatch, mutation scores, default boxes of the three samples. Write preservation tests from those observations.

**Test Cases**:
1. **Demo storyline**: reuse `tests/test_demo_invariants.py`; add assertions for Referee 6.0 and new code 0 on the expected mismatch if missing.
2. **Mutation floors**: haunted killed ≥ 33 of 35 and discount killed ≥ 31 of 33, with totals not lower than 35 and 33 (extend `tests/test_mutation_samples.py` or add to the demo invariants).
3. **Error on both sides**: `=10/B1` at 0 passes.
4. **INDEX pinned cases**: the existing `tests/test_review_semantics.py` INDEX cases stay green.
5. **Default boxes**: the three samples keep their default boxes (`tests/test_web_samples.py`).

### Unit Tests

- `_jsonable` and `report_to_json` with each Excel error code; HTML text for errors (L-02).
- `web/jobs.py` status text for exit 0, 1 with report, 1 without report, 4, and other codes; no server path (L-02).
- `_index` with origin and position for each measured case; emitted code deterministic (L-03).
- Integer exact hit at haunted quantity 50 for `>=50` and at 50 for `>50` (L-04).
- `_describe`, CLI and MCP defaults on `sem_names`; 422, `invalid_argument` and `CliError` text (L-05).
- Boundary table rendering with a threshold row and a flip row, column by column (L-06).
- `candidate_inputs` with min 0, a negative min, and `default_max` (L-07).
- Selection-change search on a two-row `MIN` table (L-08).

### Property-Based Tests

- Properties 3 to 7, with Hypothesis and an explicit seed, each citing its property number and requirements in the docstring.
- Existing property tests (condition flip Property 6 of the earlier spec, formula fuzzing, type inference) stay unchanged and green.

### Integration Tests

- Web flow through FastAPI `TestClient` with the default boxes for each repro (L-02 B4, L-03 B3 and B4, L-04 `tier`, L-05 `sem_names`) and the scenarios sample: result, case counts, mutation score, boundaries.
- `scripts/demo.sh <temp dir>` after each phase.
- Golden semantics tests for `INDEX` placements against the Referee (marked `@pytest.mark.golden`).
- A local Docker run of the image (LibreOffice 7.4.7.2) for the haunted flow and the repros, or "not checked" if Docker is unavailable.

## L-03 Measurements (task 3.5)

Measured 2026-11-24 with `tests/index_zero_probe.py` on the Referee: LibreOffice 26.8.3.1 (local) and 7.4.7.2 (Docker image `ghost-local:l03`, built from the working tree, not pushed). The full 69-case table, with both versions and Ghost's current result for each, is in `measurements-l03.md` in this folder; the raw probe output is in `measurements-l03/`. `tests/test_index_zero_measurement.py` pins it. The two versions agree on every case. Excel was not checked.

| Rule | Case (formula position) | Referee (both versions) | Ghost (unfixed) |
|---|---|---|---|
| 1 | Single column, row 0 (column omitted, 1 or 0); formula row inside the range rows, edges included; any column | element on the formula row | `#VALUE!` (**wrong**) |
| 1 | Same, formula row above or below | `#VALUE!` | `#VALUE!` |
| 2 | Single row, column 0 (row omitted, 1 or 0); formula column inside, edges included; any row | element in the formula column | `#VALUE!` (**wrong**) |
| 2 | Same, formula column left or right | `#VALUE!` | `#VALUE!` |
| 3 | Grid, row 0 with column k (or row k with column 0); formula row (column) inside | element of column k (row k) on the formula row (column) | `#VALUE!` (**wrong**) |
| 3 | Same, outside | `#VALUE!` | `#VALUE!` |
| 4 | Grid, both 0 or one argument 0; row inside, column inside, or neither | `#VALUE!` | `#VALUE!` |
| 5 | 0 on a dimension of length 1 (`INDEX(M5:M7,2,0)`, `INDEX(E20:G20,0,2)`), any position | the element | the element |
| 6 | Single cell (R-30), any position | the cell value | the cell value |
| 7 | Range on another sheet: formula's own row/column number compared with the other sheet's range | as rules 1 and 2 | `#VALUE!` when inside (**wrong**) |
| 8 | Computed 0 (`$Z$1` = 0), or `INDEX(...)+0` | as the literal 0 | `#VALUE!` when inside (**wrong**) |
| 9 | Inside `SUM` or `AVERAGE`, any position | aggregate over the whole selected row, column or grid | `#VALUE!` (**wrong**) |

Ghost is wrong on 33 of 69 cases: 23 under rules 1, 2, 3, 7 and 8, and 10 under rule 9. Rules 3, 7, 8 and 9 go beyond Property 4 and the L-03 disjunct of `isBugCondition`, which name only single-column and single-row ranges. Task 3.7 must cover them or mark the affected cells "not converted" with cell and reason. Not checked: Excel, a formula inside both the rows and columns of a grid (circular), whole-column references, defined-name ranges, `INDEX` with an area number, `INDEX` with 0 inside other functions, a computed 0 inside an aggregate, array-entered formulas.
