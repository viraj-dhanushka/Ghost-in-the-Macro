# Kiro prompt: fix the live-test findings L-02 to L-08

Paste everything below the line into Kiro with this repository open, or tell Kiro: "Follow docs/KIRO_FIX_PROMPT_LIVE_2026-11-24.md".

---

## Task: fix findings L-02 to L-08 from the live test of 24 November

Ghost in the Macro is deployed (image pushed 18:08 IST, task definition revision 4). A live test against it found four wrong results and three polish issues. Every wrong result that could be checked locally also fails locally, so these are code bugs, not deployment problems.

Fix them in this repository. Don't deploy: the owner redeploys and re-runs the live test afterwards.

### Read first
- `docs/LIVE_TEST_REPORT_2026-11-24.md`, the evidence for each finding, with job ids and quoted output.
- `.kiro/steering/ghost-guardrails.md` (hard rules), `.kiro/steering/excel-semantics.md` and `.kiro/steering/tech.md`.
- `README.md`, sections "What the proof report shows" and "Limits and known differences".

### Ground rules
1. **Test first.** For each finding, write a test that fails on the current code, then fix the code until it passes. Put the workbooks the tests need in the tests themselves (openpyxl, written to `tmp_path`), not in `/tmp`. Never weaken or delete an existing test.
2. **Keep the demo storyline exact.** After every finding, `scripts/demo.sh <temp dir>` must still give:
   - discount: Faithful pass;
   - haunted: F-001 raised; Faithful pass with 0 mismatches;
   - haunted with D-001: Intended pass, with exactly one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0).
   - The haunted and discount mutation scores must not go down (currently 33/35 and 31/33).
3. **Keep the suite green.** The baseline is `415 passed, 2 skipped`. Run the full suite at the end of each phase and record the counts.
4. **Guardrails win.** No invented values. A check that didn't run says "not checked". Unsupported constructs are "not converted" with cell and reason. Don't raise the mutation score by dropping or hiding mutants.
5. **Don't push, don't deploy, don't run AWS commands.** Leave changes uncommitted unless I ask.
6. **Log your work:**
   - Add a "Live-test resolution" table at the end of `docs/LIVE_TEST_REPORT_2026-11-24.md` with these columns: finding, status (fixed, deferred or not reproduced), what changed, and the test that proves it.
   - Add the session to `docs/KIRO_USAGE.md`: which spec, hooks and agents you used.

### Kiro setup
- Create a Bugfix spec named `live-fixes-2026-11-24`, with one requirement per finding. Use EARS wording and the "done when" criteria below.
- Run Analyze Requirements on it before you write tasks.
- Use the Skeptic agent to review each proof-strength fix (L-04), and the Coroner agent for the semantics fixes (L-02, L-03, L-05).

---

### Phase 1: wrong results

#### L-02: the report crashes on Excel error values
- **Symptom:** a job fails with `TypeError: Object of type ExcelError is not JSON serializable`. No report is written, and the panel says "Verification found mismatches." even when the baseline passed.
- **When it happens:** an `ExcelError` from `ghost/runtime/excel.py` reaches a mismatch (expected or actual values) or a mutant's counterexample.
- **Repro:** sheet `Calc`:
  - `A1` "Amount", `B1` = 4, `B2` = `=B1*2`;
  - `M1:M3` = 7, 8, 9;
  - `B4` = `=INDEX(M1:M1,0)`.
  - Verify with input `Calc!B1` and output `Calc!B4`. A mutant gives `#REF!` and the report write fails.
- **Cause:** `ghost/report/model.py:144-148`. `report_to_json` dumps data that can hold `ExcelError` objects.
- **Fix:**
  - In `report_to_dict`, serialise every Excel error as its text, for example `"#VALUE!"`. That covers mismatch inputs and expected/actual values, mutant counterexamples, boundary cases, and anything else that holds engine values.
  - Make the HTML report show them the same way.
  - Make sure the schema allows a string there.
  - Also check the MCP tools and the CLI, which use the same report path.
  - Separately, when a job fails for a reason other than mismatches, the panel must not say "Verification found mismatches." Say "The report could not be written" with the exception type, and keep any server path out of the message.
- **Done when:**
  - The repro gives a downloadable report: Faithful pass for B4, mutation score shown.
  - A workbook whose mismatch holds an Excel error also gives a report that lists the mismatch with `"#VALUE!"` text.
  - Tests cover `report_to_json` with `ExcelError` values in a mismatch and in a mutant counterexample, plus one web job.

#### L-03: `INDEX(range,0)` ignores implicit intersection
- **Symptom:** `=INDEX(M1:M3,0)` placed in `B3` (row 3, inside the rows of `M1:M3`) gives 9 in the Referee (LibreOffice 26.8.3 locally; also 7.4.7.2 live) but `#VALUE!` in Ghost.
- **Cause:** the R-08 change in `_index` (`ghost/converter/emit_python.py`) returns `#VALUE!` for row or column 0 regardless of where the formula is.
- **Fix:** apply implicit intersection the way the Referee does.
  - For a single-column range with row 0, return the element on the formula cell's row if that row is inside the range. Otherwise return `#VALUE!`.
  - For a single-row range with column 0, do the same by column.
  - Keep R-30, where a single-cell range returns its value.
  - Measure each case against the Referee, don't assume. Multi-row and multi-column ranges, cells on another sheet, and other cases you find all need a measurement.
  - Note in `excel-semantics.md` that Excel 365 spills instead, and that Excel's result was not checked.
- **Done when:**
  - Golden tests cover:
    - the formula on a row inside the range: value;
    - the formula on a row outside the range: `#VALUE!`;
    - a single-row range by column;
    - a single-cell range (R-30).
  - Each case agrees with the Referee.
  - The L-02 repro, extended with `B3` = `=INDEX(M1:M3,0)` as an output, passes Faithful.

#### L-04: tier rule on a calculated cell isn't proved at the boundary (R-04 not met)
- **Repro:** sheet `Calc`:
  - `A2` "Quantity", `B2` = 3;
  - `A3` "Price", `B3` = 25.5;
  - `A4` "Total", `B4` = `=B2*B3`;
  - `A5` "Tier", `B5` = `=IF(B4>=500,"Gold","Standard")`.
  - Use the default boxes: inputs B2, B3, output B5.
- **Symptom:**
  - The boundaries are only brackets: price 166.666/166.667 and quantity 19/20. There's no exact hit at 500.
  - The `>=`→`>` mutant (`flip_comparison` on B5) survives, with "no difference found on 62 distinct cases".
- **Cause:**
  - `ghost/verifier/flip.py:324-372` varies one input at a time from the sample values. With quantity 3, no 3-decimal price gives exactly 500. With price 25.5, no whole quantity does.
  - `flip.py:370` never records an exact hit for integer inputs (`exact = None if integer`).
- **Fix:**
  - When a condition flips on one input, retry the search with the other numeric inputs set to small values (for example 1, 2, 4, 5, 10, within their domains), so an exact equality can be reached (1 × 500).
  - Record an exact hit for integer inputs when `above` or `below` makes the comparison an equality. Use the trace hook to check that the two sides are equal; don't infer it.
  - Send the exact-hit cases to both the verifier and the mutation check.
  - Keep the evaluation budget bounded, and report in `boundary_notes` when it was cut short.
- **Done when:**
  - On the repro, the boundaries list B5's condition with an exact hit where Total = 500.
  - The `flip_comparison` mutant on B5 is killed.
  - The existing tier test in `tests/test_review_proof_strength.py` still passes.
  - The haunted demo invariants still hold. If haunted gains targeted cases, update the expected counts in the docs from real output.

#### L-05: a not-converted output is pre-checked, then fails as a "translation bug"
- **Repro:** sheet `Calc`:
  - `A2` "Quantity", `B2` = 30;
  - `D1` "Bulk level", `E1` = 50;
  - workbook names `Bulk` = `Calc!$E$1` and `Dyn` = `OFFSET(Calc!$E$1,0,0)`;
  - `C2` = `=Bulk*2`, `C3` = `=IF(B2>=Bulk,"bulk","small")`, `C4` = `=Dyn*2`.
- **Symptom:**
  - The autopsy correctly lists C4 as "not converted" (dynamic name).
  - C4 is still pre-checked as an output, so verification fails on the first case: "translation bug", actual `None`, and mutation "not checked".
- **Fix:**
  - The autopsy must neither pre-check nor offer a not-converted cell as an output. Also check `web/flow.py` (`_describe`) and the defaults in the CLI and MCP.
  - If a user or MCP caller selects one anyway, reject it with a 422 that names the cell and the reason, or leave it out of the comparison and list it as "not converted" in the report. Don't call it a translation bug.
  - Apply the same rule to volatile cells ("not verifiable as-is").
- **Done when:**
  - The repro's default boxes are B2 (and E1 if the heuristics keep it) → C2 and C3.
  - Verify passes Faithful and the report lists C4 as not converted.
  - Choosing C4 explicitly gives the documented behaviour, covered by a test.

### Phase 2: polish

#### L-06: boundary table layout
- **Where:** `ghost/report/html.py:191-201`.
- **Problems:**
  - Flip rows put "condition flip: 49 (one side), 50 (other side)" under "Owner of threshold", leaving "Change-point bracket" empty.
  - Threshold rows show raw `[{"first_changed": 50, "last_unchanged": 49}]`.
  - The `B9` flip row shows the change point (51) as its Threshold.
- **Fix:**
  - Put brackets in the bracket column as readable text, for example "49 → 50".
  - Show the real threshold constant, or "calculated" when there is none.
  - Fill "Exact hits" from L-04.
- **Done when:** a test renders a report with both kinds of boundary row and checks each column's text. The haunted report shows quantity 50 as an exact hit.

#### L-07: two different tested domains in one report
- **Problem:**
  - Survivor reasons say `min -1`, while the "Tested domains" table says min 0.
  - For scenarios, the survivor reasons say `gross_income … max 60000` against `max 10000` in the table.
- **Cause:** `ghost/verifier/coverage.py:86` always adds 0 and -1 and uses the sample value as a base. The mutation check runs those cases (`ghost/mutation/run.py:211`), even outside an input's declared minimum.
- **Fix:**
  - Clamp targeted values to each `IOSpec` min and max. Negative cases may stay only where negatives are allowed.
  - Make the survivor domain and the "Tested domains" table describe the same set of cases. Alternatively, label them clearly, for example "verification cases" and "mutation cases".
- **Done when:** for haunted, discount and scenarios, no survivor reason mentions a value outside the domain shown in the report, and a test checks this.

#### L-08: the scenarios sample shows 55 of 132 mutants killed
- **Situation:**
  - Most survivors change the rate, deduction or fee of a scenario that never becomes the cheapest on the tested inputs, so `MAX` and `INDEX`/`MATCH` hide the change.
  - `cases_targeted` is 0, because there's no `IF` to flip.
  - The wording is honest, but judges may read 42% as weak proof.
- **Fix:** first try to aim cases properly.
  - For outputs chosen by `MAX`, `MIN` or `MATCH`, search for inputs that change which row wins. For example, vary `gross_income`, `dependants` and `other_deductions` across their domains and keep the cases where the selected scenario changes.
  - Feed those to the verifier and the mutation check.
  - Report the real resulting score, whatever it is.
  - If some survivors still can't change any output, explain that in the report's mutation section in one plain sentence, for example: "These constants belong to rows that never become the best result on the tested inputs, so changing them doesn't change any output."
  - Don't remove mutants and don't change the score formula.
- **Done when:** the scenarios score improves, with cases that change the winning scenario, or the report explains the remaining survivors. A test covers whichever you did, and `docs/KIRO_USAGE.md` records the before and after scores.

---

### Final checks (report the real output of each)
1. Full suite: counts, with 0 failed.
2. `scripts/demo.sh <temp dir>`: the storyline in ground rule 2, and the mutation scores.
3. The five repro workbooks (L-02 to L-05, plus a scenarios sample run) through the web app with FastAPI `TestClient`, using the default boxes. Give each one's result, case counts, mutation score and boundaries.
4. A local Docker run of the image (LibreOffice 7.4.7.2) for the haunted flow and the L-02 to L-05 repros. Say "not checked" if Docker isn't available.
5. Update the README's "Limits and known differences" for L-03 (implicit intersection; Excel 365 spills) and L-05 (not-converted outputs aren't offered).
6. A short summary in chat:
   - what changed per finding;
   - anything deferred, with the reason;
   - a reminder for me to redeploy with `scripts/deploy_ecs_express.sh` and re-run the live test.
