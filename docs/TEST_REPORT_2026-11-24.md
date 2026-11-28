# Ghost in the Macro: test report, 24 November 2026

## Environment

- Repository at commit `8a3cca8`. The suite was **159 passed** before this review and is **192 passed, 19 xfailed** after it, because of the 52 tests added here.
- Local Referee: LibreOffice 26.8.3.1 on macOS 27.2, Python 3.13.2 venv.
- Live site: `https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws`, which reports `LibreOffice 7.4.7.2 40(Build:2)` and Python 3.11.2.
- Live load stayed modest: one request at a time, at most three verification jobs alive at once, and no load test.

## Summary

| ID | Severity | Area | Finding |
|---|---|---|---|
| R-05 | **Blocker for the demo** | Web, samples | "Scenario model" sample **fails verification on the live site** with the default inputs |
| R-19 | **Blocker for submission** | Docs | `README.md` contains only the live URL; there are no setup or run instructions |
| R-01 | Wrong result | Verifier, Intended mode **Hardened after the Skeptic review:** a Decision explains a case only if the candidate's hook for the patched cell is present and equals the transpiled Intended module's value (which differs from Faithful), and the candidate's outputs equal the Intended module's; a missing or renamed hook, or an unconvertible workbook, explains nothing. A module without `trace` gets the message "module has no trace hook, so Decisions cannot explain mismatches"| With D-001 recorded, an unrelated VAT bug **passes** ("expected by decision") after 1 case, `tests/test_review_classification_soundness.py` (variants C, D, E, no-trace, unit) |
| R-03 | Wrong result | Mapping, verifier | Decimal-validated distance is typed integer; a truncate-to-whole-km bug **passes** 300 cases |
| R-04 | Wrong result | Verifier | Thresholds on calculated cells are never probed; a Gold `>` vs `>=` bug **passes** 300 cases |
| R-06 | Wrong result | Mutation check | 2 of the 4 "equivalent on tested domain" survivors differ at ordinary distances (10.3 km, 10.01 km) |
| R-02 | Wrong result | Classification **Hardened:** also requires that the transpiled Faithful module itself disagrees with the Referee on the case; a code bug the transpiler does not share (variant H) is "translation bug"| A translation bug in Faithful mode is labelled "original workbook inconsistency", `tests/test_review_classification_soundness.py::test_variant_h_faithful_code_bug_is_not_blamed_on_the_workbook` |
| R-07 | Wrong result | Transpiler | Comparisons after division differ from Excel and LibreOffice (`=1/3*3=1` gives FALSE) |
| R-09 | Wrong result | Autopsy | False Finding for complementary conditions (`>=50` in one cell, `<50` in another) |
| R-10 | Wrong result | Autopsy | Missed thresholds (`A2*A3>=500`, `50%`); an input's current value is recorded as a threshold |
| R-11 | Wrong result | Autopsy | A real input used by two unstyled formulas is classified PARAMETER and never varied |
| R-14 | Wrong result | Decisions, MCP | A second Decision for the same Finding is accepted and then breaks every verification |
| R-27 | Wrong result | Converter | Named ranges are "not converted" (Requirement 7.4 says supported) |
| R-29 | Wrong result | Kiro hooks | All four hooks call system `python3`, which lacks Ghost's dependencies here; the golden-tests hook selects 0 tests |
| R-17 | Security (availability) | Ingestion, web | A legal 2.3 MB workbook took 30 s and 1.16 GB to analyse locally; the live task has 2 GB |
| R-18 | Security (availability, privacy) | Job runner | No per-session job cap; finished jobs and their artifacts stay in memory after the session ends |
| R-13 | Security (low) | Ingestion | VBA is invisible when an `.xlsm` is renamed `.xlsx`; the upload summary always says `has_vba: false` |
| R-12 | Polish | Autopsy | `Calculator!E5` is proposed and pre-checked as an input (known issue; confirmed) |
| R-15 | Polish (may block the Power install) | Kiro Power | `plugin.json` lacks the required `$schema`; `toolPrefix` is undocumented; launches `python` |
| R-16 | Polish | Routing | The `atx` dry run uses `-x` without the required `-t` |
| R-20 | Polish (requirements gap) | Tests | No golden semantics tests, no Excel-saved fixtures, no fuzzing, end-to-end or performance tests |
| R-21 | Polish | Report | "Exact hits" column shows change points; the Faithful report can't be downloaded when Intended also ran; server paths appear in job events |
| R-28 | Polish | Report Distinct keys normalise numbers (`Decimal('1.0')`, `Decimal('1.00')`, `1` are one case) in the verifier and the mutation check| "300 cases tested" includes repeats: 176 distinct inputs, `tests/test_case_key.py` |
| R-22 | Polish | Web text | "Unanswered findings ... are reported as mismatches" is not true in Faithful mode |
| R-23 | Polish | Accessibility | Dark-theme control borders are 2.51:1 (WCAG 1.4.11 needs 3:1); the toggle label changes with its state |
| R-24 | Polish (Referee fidelity) | Referee | Seven LibreOffice vs Excel divergences found; the live and local LibreOffice versions differ |
| R-08 | Polish | Transpiler | `INDEX(r,0)` gives `#REF!` (should be `#VALUE!`); `1E+20&""` formatting differs from Excel |
| R-25 | Polish | Transpiler | `ROUND` on values with more than 15 significant digits differs from LibreOffice |
| R-26 | Polish | Mapping | Text outputs ("Gold", scenario names) are typed `decimal` in `mapping.yaml` |

The IDs match the `reason=` text of the xfail tests where a test exists.

---

## Blockers

### R-05: "Scenario model" sample fails verification with the default inputs (live)

- **Severity:** blocker for the demo. A judge who clicks the third sample button and then **Run verification** gets FAIL.
- **Area:** web flow, autopsy roles, empty-string semantics.
- **Steps (live):** open the site → click "Scenario model (generated)" → click "3. Run verification" without changing any checkbox. Done with a cookie jar: `POST /sample/scenarios`, `GET /autopsy`, then `POST /verify` with every pre-checked box.
- **Steps (local):**
  ```bash
  .venv/bin/python samples/make_scenarios.py /tmp/s.xlsx
  .venv/bin/python -m ghost.cli rules /tmp/s.xlsx --migration /tmp/s
  .venv/bin/python -m ghost.cli convert /tmp/s.xlsx --migration /tmp/s
  .venv/bin/python -m ghost.cli verify /tmp/s
  ```
  Or: `pytest tests/test_review_proof_strength.py::test_scenarios_sample_passes_with_default_inputs`.
- **Expected:** a bundled sample passes Faithful verification.
- **Actual (live):**
  - The autopsy pre-checks **53 inputs**: every scenario name `Model!A6:A15` and every rate in the table, as well as `B2` and `B3`.
  - The job ended `failed`, "Verification found mismatches.", after `cases_tested: 1`.
  - The mismatch: `best_scenario` (`Model!B19`), class `translation bug`, expected `0.0`, actual `''`. All 53 inputs were 0 or empty.
- **Likely cause:**
  1. `ghost/autopsy/classify.py:97-104` classifies the table's constants and text labels as INPUT.
  2. The verifier generates `""` for text inputs (`ghost/verifier/strategies.py`, `st.text(max_size=12)`). The Referee writes it with `setString("")`, which leaves an empty cell, so `INDEX` returns 0.
  3. The generated `_inp` (`ghost/converter/emit_python.py:66-71`) keeps `''` as a string, so `_index` returns `''`.
  4. The project's own sample test, `tests/test_product_samples.py:47-51`, overrides the heuristic ("only highlighted input cells are real inputs"), so the suite never tests what the web app actually does. With only `Model!B2,Model!B3` as inputs, the sample passes 300 cases.
- **Suggested fix:** pre-check only highlighted or validated inputs, as the product test assumes, or treat table blocks and text referenced by `INDEX` as PARAMETER. Also make `_inp("")` return `None` (an empty cell) or stop generating empty strings.

### R-19: README has no instructions

- **Severity:** blocker for submission. Kiroween requires a repository with "instructions required for the project to be functional".
- **Steps:** `cat README.md`.
- **Expected:** Requirement 21.7: setup (LibreOffice, venv), running locally, Docker, using the Power in Kiro, creating Excel-saved fixtures with Excel for the web, safety, and a note about the feasibility spike.
- **Actual:** the file contains only "Ghost-in-the-Macro", the live demo URL and "The hosted copy will be taken down after judging." Tasks 19.1 to 19.3 are unchecked.
- **Suggested fix:** write the README (task 19.1) and finish `docs/KIRO_USAGE.md` (task 19.2) before submitting.

---

## Wrong results

### R-01: Intended mode excuses unrelated bugs

- **Area:** `ghost/verifier/classify.py`, `ghost/verifier/run.py`. This is also the path the Kiro Power uses through `verify_implementation`.
- **Steps:** `pytest tests/test_review_proof_strength.py::test_intended_mode_does_not_excuse_unrelated_bug`. Or by hand:
  1. Copy the demo's `haunted` migration.
  2. Write a hand-made `logic.py` that implements D-001 (`>=` on B9) but also has `'Calculator!E7': Decimal('0.21')` (VAT 21%).
  3. Run `ghost verify <dir> --mode intended`.
- **Expected:** FAIL. The VAT change is not explained by D-001.
- **Actual:**
  ```
  [intended] PASS: 1 cases, 1 mismatch(es), seed 20261204
      total (Calculator!B11): referee=6.0 actual=Decimal('6.05')  inputs: delivery_distance_km=0, quantity=0, unit_price=0
      class: expected by decision  F-001 D-001
  ```
  Exit code 0. The counterexample is quantity **0**, where D-001 cannot apply.
- **Likely cause:**
  - `classify.py:62-79` marks any mismatch "expected by decision" when the output cell's precedents include a cell listed in the Finding. In the haunted sample everything flows into `B11`, so every mismatch qualifies.
  - `run.py:156-160` stops at the first mismatch, so the run never looks further. The genuine haunted run also stops early: "PASS: 33 cases" locally, 75 cases live.
- **Suggested fix:**
  - Count a mismatch as expected only when the Decision explains it: the patched comparison evaluates differently on that case, and the unpatched (Faithful) code matches the Referee on that case.
  - Keep generating after expected mismatches, up to the full case budget.

### R-02: Translation bug labelled "original workbook inconsistency"

- **Steps:** same VAT-21% bug in a Faithful `logic.py` (`ghost verify --mode faithful`), or `pytest tests/test_review_proof_strength.py::test_faithful_translation_bug_is_labelled_translation_bug`.
- **Expected:** class `translation bug`.
- **Actual:** `[faithful] FAIL: 1 cases ... class: original workbook inconsistency  F-001`. The verdict is right, but the report blames the spreadsheet for a code bug.
- **Likely cause:** the same reachability test, `classify.py:62-66` and `:83-87`.
- **Suggested fix:** use "original workbook inconsistency" only when the case falls where the Finding's operators disagree, for example `B2 = 50`.

### R-03: Decimal inputs typed integer; fractional values never tested

- **Steps:**
  - `pytest tests/test_review_autopsy_and_packaging.py::test_decimal_validation_wins_over_whole_number_sample`
  - `pytest tests/test_review_proof_strength.py::test_truncated_distance_is_caught`
- **Expected:** `Calculator!B4` has data validation `decimal`, so `mapping.yaml` types it `decimal`, and a module that truncates distance to whole kilometres fails.
- **Actual:**
  - `mapping.yaml` says `delivery_distance_km: {cell: Calculator!B4, type: integer}`.
  - All 300 generated distances were Python `int` (`distance value types: Counter({'int': 300})`).
  - The truncating module gives `[faithful] PASS: 300 cases, 0 mismatch(es)`.
- **Likely cause:** `ghost/converter/mapping.py:60-69` checks `isinstance(value, int)` before the validation, and validation can only ever upgrade to integer. `ghost/verifier/strategies.py:infer_spec` honours validation, but the verifier uses the mapping's type.
- **Suggested fix:** check validation first (`decimal` validation means decimal) or reuse `infer_spec`. Consider defaulting numeric inputs to decimal unless the validation is `whole`.

### R-04: Thresholds on calculated cells are not probed (Requirement 8.4)

- **Steps:**
  1. Add `B12 = IF(B11>=500,"Gold","Standard")` to sample (a).
  2. Convert with outputs `B11,B12,B13`.
  3. Run `ghost mutate`, then verify a hand-made module that uses `>` for Gold.
  Or: `pytest tests/test_review_proof_strength.py::test_gold_threshold_on_calculated_cell_is_caught`.
- **Expected:** the `>` module fails, as Requirement 8.4 and the prototype finding require.
- **Actual:**
  - The autopsy finds `Calculator!B11 >= 500 at Calculator!B12`, but the boundaries list only `B7` and `B9`.
  - The `>` module gives `[faithful] PASS: 300 cases, 0 mismatch(es)`.
  - `ghost mutate` reports `38/48 killed`, with six survivors on B12 and B13 (flip `>=`, 500±1), all labelled `equivalent on tested domain`.
  - At 1 × 411.67 and 0 km the Referee gives `{'Calculator!B11': 500.0, 'Calculator!B12': 'Gold'}`, while mutant `M-63aaf853` (flip) gives `tier: 'Standard'`.
- **Likely cause:** `ghost/cli.py:385-397` (`_probe_boundaries`) skips any threshold whose cell is not an input (`if name is None ...: continue`), and nothing feeds calculated-cell targets into verification.
- **Suggested fix:**
  - Binary-search each numeric input for values where the calculated cell meets the threshold, as the prototype did.
  - Add those cases to `extra_cases` for both verification and the mutation check.
  - Until then, label such survivors "threshold on a calculated cell was not probed".

### R-06: Mutation survivors labelled "equivalent" are not all equivalent

These are the four survivors on the live haunted and discount runs (`29/33` and `27/31` live, `31/35` with inputs B2 to B4). I checked each by hand against the Referee (`tests/test_review_proof_strength.py::test_decimal_distance_mutants_are_not_equivalent` covers two of them):

| Mutant | Change | Input where it differs | Referee total | Mutant total |
|---|---|---|---|---|
| M-723b26a3 | B9 `ROUND(…, 2)` → `ROUND(…, 1)` | 1 × 1.00, **10.3 km** | 7.34 | 7.32 |
| M-8430e6bf | B9 `ROUND(…, 2)` → `ROUND(…, 3)` | 1 × 1.00, **10.01 km** | 7.2 | 7.204 |
| M-3cbed5dc | B9 half-up → half-even | 1 × 1.00, 10.0125 km | 7.21 | 7.20 |
| M-687cf270 | B10 half-up → half-even | 1 × **0.125**, 0 km | 6.155 | 6.145 |

- The first two are killed by ordinary one- and two-decimal distances. They survive only because of R-03.
- The last two need four-decimal distances or three-decimal prices. That is a narrow domain, but "equivalent" overstates it.
- **Suggested fix:** fix R-03, then reword the reason to name the domain actually tested, for example "same result for whole-km distances and 2-dp prices".

### R-07: Comparisons after division differ from Excel and LibreOffice

- **Steps:** `pytest tests/test_review_semantics.py -k "division"`.
- **Expected and actual:**

  | Formula | Excel | LibreOffice | Ghost |
  |---|---|---|---|
  | `=IF(10/3*3>=10,"ok","low")` | "ok" | `'ok'` | `'low'` |
  | `=1/3*3=1` | TRUE | `1.0` | `False` |
  | `=IF(7/3*3<>7,1,0)` | 0 | `0.0` | `Decimal('1')` |

- **Likely cause:** `ghost/runtime/excel.py:235-243` divides at 60-digit precision, and `xl_ge`/`xl_eq` (`:403-433`) then compare exactly. Excel and LibreOffice compare doubles, with roughly 15-digit tolerance.
- **Suggested fix:** round both sides of a comparison to 15 significant digits, as Excel does, before comparing.

### R-09: False Finding for complementary conditions

- **Steps:** a sheet with `B1 = IF(A1>=50,1,0)` and `B2 = IF(A1<50,2,3)`. Run `ghost autopsy`, or `pytest tests/test_review_autopsy_and_packaging.py::test_complementary_operators_are_not_a_finding`.
- **Expected:** no Finding. Both formulas put 50 on the same side.
- **Actual:** `F-001 operator conflict on P!A1 vs 50: P!B1 uses '>=' P!B2 uses '<'`. The user is asked to make a decision about a non-issue.
- **Likely cause:** `ghost/autopsy/findings.py:28` flags any group with two or more different operators.
- **Suggested fix:** flag a pair only when it disagrees about the boundary value (`>=` with `>`, `<=` with `<`, `>=` with `<=`, `>` with `<`). Complementary pairs such as `>=`/`<` or `>`/`<=` are fine.

### R-10: Threshold extraction misses some thresholds and invents others

- **Steps:** the probe workbook described in `tests/test_review_autopsy_and_packaging.py`, or `ghost autopsy` on it.
- **Actual:**
  - `A2*A3>=500`, `A8>=50%` and `A7>=Bulk` (a named range) produce no threshold.
  - `B9 = IF(A9>=E9,1,0)`, with A9 = 90 an input and E9 = `=40+10`, produces `P!E9 <= 90`: the input's current value is treated as a fixed threshold.
- **Likely cause:** `ghost/autopsy/thresholds.py:45-61`. `operand()` resolves *any* constant cell, inputs included, and only bare cell references or numeric literals count as sides of a comparison.
- **Suggested fix:**
  - Resolve constants only from PARAMETER (non-input) cells.
  - Record comparisons on expressions as calculated-cell thresholds (see R-04).
  - Treat `50%` as 0.5.

### R-11: A real input shared by two formulas is classified PARAMETER

- **Steps:** `A1 = 10`, `B1 = IF(A1>=50,1,0)`, `B2 = A1*2`, no fill or label. Or `pytest ...::test_input_shared_by_two_formulas_is_an_input`.
- **Expected:** INPUT.
- **Actual:** PARAMETER, so the verifier never varies the main input. In the probe workbook, `P!A1` is missing from the 10 proposed inputs.
- **Likely cause:** `ghost/autopsy/classify.py:99`, `shared_fixed = len(users) >= 2 and score == 1`.
- **Suggested fix:** don't demote a cell that thresholds are compared against. Prefer INPUT and let the user untick it.

### R-14: A second Decision for the same Finding breaks verification

- **Steps:**
  1. Over MCP, call `record_decision` on the haunted migration, which already holds D-001, with the same Finding and patch. It returns D-002.
  2. Call `generate_proof_report` or `mutation_check`.

  Or: `pytest tests/test_review_autopsy_and_packaging.py::test_second_decision_for_same_finding_is_rejected`.
- **Expected:** the second Decision is rejected, as the web app does ("already has a Decision").
- **Actual:** `{"decision": {"decision_id": "D-002", "finding_id": "F-001", ...}}`. After that, both tools fail with `Decision patch cannot be applied: D-002: patch matched no comparison in Calculator!B9`, reported against argument `migration_dir`.
- **Likely cause:** `ghost/decisions/store.py:154` (`record`) checks neither for duplicates nor whether the patch applies. Only `web/flow.py` checks for an existing Decision.
- **Suggested fix:** reject duplicate `finding_id`s in `record`, and validate the patch against the workbook when it is recorded.

### R-27: Named ranges are not converted (known gap, confirmed)

- **Steps:** a workbook defining `Bulk` as `S!$E$2`, with the formula `=Bulk*2`.
- **Actual:**
  - Ghost: `NOT CONVERTED: named reference Bulk is not supported`. Dependent outputs are omitted.
  - The Referee computes `100.0`.
  - The threshold `A7>=Bulk` is also lost (R-10).
- **Why it matters:** Requirement 7.4 says named ranges are supported, and named inputs and rates are common in finance workbooks. Today those workbooks are only partly converted. The demo samples don't use names, so the demo itself is unaffected.
- **Suggested fix:** resolve workbook-scoped defined names that point at a cell or range.

### R-29: Kiro hooks can't run as written (found while preparing the fix prompt)

- **Area:** `.kiro/hooks/*.json`. Hooks are a Kiro feature the judges score.
- **Steps:**
  - Read each hook's `action.command`.
  - Run `python3 -c "import openpyxl"`.
  - Run `.venv/bin/python -m pytest -q -m golden`.
- **Expected:** each hook runs Ghost and reports a real result.
- **Actual:**
  - All four hooks call the system `python3` (for example `python3 -m ghost.cli verify ...` and `python3 -m pytest tests -m golden -q`). On this Mac that gives `ModuleNotFoundError: No module named 'openpyxl'`.
  - The golden-tests hook would select nothing even with the right interpreter: `211 deselected`. No test carries the `golden` marker (see R-20), so the hook can never fail.
- **Not checked:** whether Kiro activates the project venv before running a hook.
- **Suggested fix:**
  - Call `.venv/bin/python`, or a small wrapper that finds the venv.
  - Mark the golden semantics tests with `@pytest.mark.golden` once they exist.
  - Trigger each hook in Kiro and record the result in `docs/KIRO_USAGE.md`.

---

## Security

### R-17: Large but legal workbooks can exhaust memory

- **Steps (local only, deliberately not sent to the live site):**
  1. Use openpyxl write-only mode to build a workbook with 50,000 rows × 20 numbers and one `SUM`.
  2. Run `.venv/bin/python -c "from ghost.cli import _analyse; _analyse('cells_1m.xlsx')"` under `/usr/bin/time -l`.
- **Actual:**
  - The file is 2,335,546 bytes (36,611,998 uncompressed), within the 5 MB, 200 MB and 20,000-formula limits.
  - Analysis took **30.4 s**, with a maximum resident set of **1,162,637,312 bytes**.
- **Why it matters:**
  - The live task has 1 vCPU and 2 GB, and keeps sessions in memory.
  - `web/app.py:229` loads the upload inside the web process, and every `GET /autopsy` loads and analyses the workbook again (`web/flow.py:_describe`).
  - A file near 5 MB, or two such uploads at once, would plausibly exhaust memory and restart the only task, wiping every session.
  - The 60 s deadline (`ghost/ingest/limits.py`) is only checked between parsing steps.
- **Suggested fix:**
  - Cap the cell count by streaming the sheet XML (or openpyxl `read_only`) before the full load, for example at 200,000 cells.
  - Parse in a subprocess with a memory limit.
  - Cache the analysis per session rather than redoing it on every view.

### R-18: No per-session job cap; job data kept after the session ends

- **Steps (live, kept small):** one session submitted three verify jobs in a row. Output: `[('running', None), ('running', None), ('queued', 1)]`, and the panel showed "Queued. Position 1."
- **Code evidence:**
  - `web/jobs.py:141` adds every job to `self._jobs`, and nothing ever removes it.
  - `forget_session` (`:168`) only kills running or queued jobs.
  - Each job keeps its `artifacts` (reports and modules) as bytes in memory.
- **Why it matters:**
  - One visitor can queue unlimited jobs and block judges, given `GHOST_MAX_JOBS=2` and a 300 s timeout per job.
  - Memory grows without limit.
  - The privacy note says data "is deleted when the session ends", but report contents stay in process memory until restart. They can't be reached once the cookie is gone.
- **Suggested fix:** cap jobs per session (for example one running and one queued), and drop a session's jobs and artifacts in `forget_session` and the sweeper.

### R-13: VBA detection depends on the file extension

- **Steps:**
  - Upload the test bench's `order_calculator_vba.xlsm` renamed to `.xlsx`, both locally and live.
  - `pytest tests/test_review_autopsy_and_packaging.py -k vba`; this skips if the test bench file is absent.
- **Actual:**
  - Live autopsy of the renamed file shows `VBA lines: 0 in 0 module(s)`, against `28 in 1` for the real `.xlsm`. Routing would therefore say "Ghost converts" without seeing any VBA.
  - The upload response says `"has_vba": false` for the real `.xlsm` too.
  - Macros were not run in either case, and the VBA function cell is listed as `not converted`.
- **Likely cause:**
  - `ghost/cli.py:107` extracts VBA only when the suffix is `.xlsm`.
  - `web/app.py:76` reads `wb.vba_modules` from `ghost.ingest.load_workbook`, which never fills it.
- **Suggested fix:** detect VBA by content (`xl/vbaProject.bin` in the zip) whatever the extension, and fill `has_vba` from that.

---

## Polish

### R-12: `Calculator!E5` proposed as an input (known issue, confirmed)

- `ghost autopsy` on samples (a) and (b) lists `inputs (4): Calculator!B2, Calculator!B3, Calculator!B4, Calculator!E5`.
- The live UI pre-checks E5, so the generated module's API includes `free_delivery_within_km`.
- The CLI demo hides this by hard-coding the inputs (`ghost/cli.py:678`, `demo_inputs = "Calculator!B2,Calculator!B3,Calculator!B4"`).
- The label "Free delivery within (km)" matches no word in `_RATE_WORDS` (`ghost/autopsy/classify.py`).
- **Fix:** extend the parameter heuristics (labels such as "within", "free" or "allowance"; constants next to other parameters), or leave non-highlighted cells unchecked. Test: `...::test_free_delivery_distance_is_a_parameter`.

### R-15: The Kiro Power may not install or start as packaged

- Kiro's Power docs (kiro.dev/docs/powers/create) list `$schema` (`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) as a **required** `plugin.json` field, and `plugin/plugin.json` doesn't have it.
- `toolPrefix` in `plugin/mcp.json` is not a documented field. The documented fields are `command`, `args`, `env`, `disabled`, `autoApprove`, `disabledTools`, `url` and `headers`. Kiro already namespaces Power server names ("supabase-local becomes power-supabase-supabase-local"), so Requirement 12.10 is met by Kiro, not by `toolPrefix`. `tests/test_plugin_package.py` asserts `toolPrefix`, which locks in an undocumented field.
- `"command": "python"` won't start on a stock Mac; `command -v python` returned "not found" here. It also needs Ghost's dependencies installed and the repository root on the import path.
- **Not checked:** an actual install in Kiro.
- **Fix:** add `$schema`; remove `toolPrefix` or confirm Kiro supports it; launch with `uvx` or a pinned `python3` entry point; test an install from the GitHub URL. Test: `...::test_plugin_manifest_has_schema`.

### R-16: `atx` dry-run command (known gap, checked against the official reference)

- Ghost prints `atx custom def exec -n excel-vba-to-python -p samples -c 'python -m pytest' -x`.
- The AWS Transform Kiro power's `steering/workload-custom-cli-reference.md` confirms `-n`, `-p`, `-c` and `-x` (`--non-interactive`). It also says `-t` (`--trust-all-tools`) is "required with `-x`", and Ghost's command omits it.
- `excel-vba-to-python` is presented as if it exists, but it must first be created (`atx custom def list`).
- AWS's VBA example uses `python3 -m py_compile **/*.py` as the build command, not `pytest`.
- **Fix:** add `-t`, say the transformation definition must exist, and drop the word "exact". Test: `...::test_atx_dry_run_includes_trust_all_tools_with_non_interactive`.

### R-20: Requirements for tests not met

| Requirement | Status |
|---|---|
| Golden semantics tests (15.12, 20.4) | Missing: no test uses `samples/make_traps.py` |
| Excel-saved fixture test that skips with a message (20.2, 20.3) | Missing: there is no `tests/fixtures/` |
| Formula fuzzing (20.6) | Missing |
| CLI end-to-end (20.8) | Missing |
| 500-case performance test (20.9) | Missing |

The matching tasks (3.5, 6.8 to 6.10, 9.3, 9.4) are optional and unchecked, so nothing claims they're done, but the requirements say SHALL. `tests/test_review_semantics.py` (31 passing cases) partly covers the golden rows.

### R-21: Report details

- The HTML "Exact hits" column (`ghost/report/html.py:167-169`) shows change-point pairs such as `[{"first_changed": 50, "last_unchanged": 49}]`. No exact-hit search runs.
- Requirement 10.3's "inputs tested" is only a count.
- When Intended mode runs, only the Intended report reaches the web downloads (`ghost/cli.py:559`), so the 300-case Faithful report can't be downloaded.
- Job events, shown in the panel and through `/jobs/{id}`, include absolute server paths such as `/tmp/ghost-sessions-<random>/<session-id>/run-1/logic_intended.py`.

### R-28: The case count includes repeats

- `verify` on samples (a) and (b) reports `cases_tested=300`, but only **176** input combinations are distinct. The first two cases are both `(0, 0, 0)`.
- The report says "Cases tested 300".
- **Fix:** report distinct inputs, or both numbers.

### R-22: Misleading UI text

- `web/templates/_autopsy.html:66` says "They are reported as mismatches, not silently resolved."
- In Faithful mode an unanswered Finding produces no mismatch: the haunted sample passes 300 cases.
- **Fix:** say "Unanswered findings keep the original behaviour and are listed in the report."

### R-23: Accessibility

- At 360 px the page and autopsy have no horizontal overflow (`scrollWidth 360`), in both themes.
- Tab order is logical, and every focused control shows `outline: solid 3px rgb(255, 210, 94)`.
- All text pairs pass AA in both themes. For example, dark text/bg is 15.54:1 and light link/bg is 7.59:1.
- **Fail:** dark-theme `--border: #5b4f73` (`web/static/style.css:5`) is **2.51:1** against the background and 2.31:1 against the surface. Text inputs and the theme toggle rely on that border, and WCAG 1.4.11 needs 3:1. `#7a6d94` gives 3.96:1 and 3.65:1.
- The toggle (`web/static/theme.js:11`) changes its label ("Dark mode" or "Light mode") as well as `aria-pressed`. In dark mode a screen reader hears "Dark mode, toggle button, not pressed".
- **Fix:** keep the label constant ("Light mode") with `aria-pressed`, or drop `aria-pressed` and use "Switch to light mode".
- **Not checked:** a real screen reader, or Playwright.

### R-24: Where the Referee (LibreOffice) differs from Excel

In each of these, Ghost matches Excel but the Referee does not. A workbook relying on any of them would show false "translation bug" mismatches.

| Formula | Excel | LibreOffice 26.8 | Ghost |
|---|---|---|---|
| `=0^0` | `#NUM!` | 1.0 | `#NUM!` |
| `=(-8)^(1/3)` | `#NUM!` | -2.0 | `#NUM!` |
| `=MATCH("2",{1;2;3},0)` | `#N/A` | 2.0 | `#N/A` |
| `=MATCH(TRUE,{1;2;3},0)` | `#N/A` | 1.0 | `#N/A` |
| `=TRUE>1` | TRUE | FALSE | TRUE |
| `=SUM("5",1)` | 6 | `#VALUE!` | 6 |
| `=TRUE&""` | "TRUE" | "1" | "TRUE" |

The live Referee is **7.4.7.2** and local development uses **26.8.3**, so results may differ between them.

**Fix:** list the divergences in the steering table, add Referee fidelity tests for them, and consider installing a newer LibreOffice in the image.

### R-08: Smaller transpiler differences

- `=INDEX(M1:M3,0)`: LibreOffice gives `#VALUE!` and Ghost `#REF!` (`ghost/converter/emit_python.py:208-209`). Test: `test_review_semantics.py::test_transpiler_bug[index_row_zero]`.
- Number-to-text for very large and small numbers:

  | Formula | Excel | LibreOffice | Ghost |
  |---|---|---|---|
  | `=1E+20&""` | "1E+20" | "1E+020" | "100000000000000000000" |
  | `=1E-20&""` | "1E-20" | "1E-020" | "0.00000000000000000001" |

  Ordinary joins match Excel, for example `ROUND(1234.5,-2)&" units"` gives "1200 units".

### R-25: `ROUND` with more than 15 significant digits

- `=ROUND(123456789012345.67,1)`: LibreOffice gives `123456789012345.7`, Ghost gives `123456789012346.0`. Ghost normalises to 15 significant digits before rounding.
- The same thing affects cents on amounts of 1e13 or more.
- Excel's result was **not checked** (no Excel available). Rare for small-business workbooks.

### R-26: Output types

- Text outputs are typed `decimal` in `mapping.yaml` (`tier`, `best_scenario`), because `ghost/converter/mapping.py:111` falls back to decimal when no Excel-saved value exists.
- Comparison is unaffected, but the contract file is misleading.

---

## Known gaps: verdicts

| Gap | Verdict |
|---|---|
| Named ranges not converted | Confirmed (R-27). It matters for real finance workbooks, not for the demo. |
| `atx` flags written from memory | `-n`, `-p`, `-c` and `-x` are correct; `-t` is missing (R-16). |
| Whether Kiro honours `toolPrefix` | Undocumented in Kiro's MCP config docs, and Kiro namespaces Power servers itself (R-15). Not checked in Kiro. |
| `mcp` unpinned, code assumes 2.x | `mcp` 2.3.0 is the latest release and imports `mcp.server.mcpserver`, so a fresh install works today. An environment with `mcp` 1.x would fail at import. Pin `mcp>=2.3,<3`. Low risk. |

## What worked

- **Test suite:** 159 passed before the review; the CLI demo (`scripts/demo.sh`) produces both migrations and all three reports in about 8 s.
- **Live haunted storyline:** F-001 shown; D-001 recorded; Intended mode PASS with one mismatch (`expected by decision`, F-001, D-001, minimal inputs `quantity: 50`, Referee 6.0 against 0) in 9.9 s. `report.json`, `report.html`, `module.py` and `module.zip` all download, with `Content-Disposition: attachment`.
- **Live discount sample:** Faithful PASS, 300 cases, mutation `27/31`.
- **Reports:** the three live reports (haunted, discount, scenarios) validate against `proof-report-1.json` (jsonschema Draft 2020-12). Local reports were not schema-checked separately. Unrun checks are labelled honestly: sanity `not cross-checked against Excel`, and mutation `not checked` when the baseline fails.
- **Seed reproducibility:** the same seed gives an identical 300-case sequence, and a different seed gives a different one.
- **Rules:** identical `rules.md`, `traceability.yaml` and `findings.yaml` across two runs on regenerated workbooks; every traced cell exists; `rule_id` follows `ghost/rules/ids.py`.
- **Catching real bugs:** wrong rounding on the discount (half-even) caught at 455 × 0.03; an off-by-one in the scenario lookup caught on the first case (`referee='Flat 20' actual='Flat 25 + deduction'`).
- **Transpiler vs Referee:** 31 of 34 edge cases in `tests/test_review_semantics.py` agree, including:
  - every Excel semantics table row that's in scope;
  - `ROUND` with negative digits;
  - `MOD` with decimals and divide-by-zero;
  - text vs numbers;
  - empty cells in `SUM` and `AVERAGE`;
  - `IFERROR`;
  - `MATCH`/`INDEX` misses;
  - `CHOOSE` out of range;
  - quoted sheet names;
  - `%` and `%%`;
  - `^` precedence (`-2^2 = 4`, `2^3^2 = 64`);
  - number-to-text for ordinary values.
- **Upload safety (local and live):**

  | Upload | Response |
  |---|---|
  | `.csv`, renamed `.txt` | 422 "Unsupported file type. Accepted formats: .xlsx and .xlsm." |
  | 6 MB file | 413 "File is larger than the 5 MB limit." |
  | Zip bomb (300 MB part) | 422 "Workbook expands to too much data; rejected." |
  | Billion laughs | 422 `EntitiesForbidden(name='lol' ...)` |
  | XXE on `/etc/passwd` | 422 `EntitiesForbidden(name='xxe', system_id='file:///etc/passwd' ...)` |
  | 20,001 formulas | 422 "Workbook has more than 20,000 formulas; the limit is 20,000." |

- **Escaping:** a sheet named `<img src=x>` and labels or results containing `<script>` are escaped in the autopsy, job panel and report. The inline report sends `Content-Security-Policy: sandbox; default-src 'none'; style-src 'unsafe-inline'`.
- **Sessions:** a second cookie jar gets 404 on `/jobs/{id}`, `/run/{id}/panel`, `report.json`, `report.html`, `module.py` and `module.zip`. Garbage, forged-MAC, sid-only and empty cookies get 404 and a fresh session cookie. Live cookies are `HttpOnly; Path=/; SameSite=lax; Secure`.
- **Bad requests:** bogus refs in `/verify` (`Nope!Z9`, `Calc!B1:B3`, a formula cell as input, no outputs) give 422 with a clear message, never 500. Bad decisions (offered-option mismatch, unknown finding, missing author or reason) give 422.
- **Queue:** `GHOST_MAX_JOBS=2` runs two jobs and queues the third with position 1, then drains. `/healthz` reported `{"status":"ok","referee":{"available":true}}`.
- **MCP server:** all 13 tools are listed over stdio.
  - Eleven succeeded with valid arguments.
  - `generate_proof_report` and `mutation_check` were only called after the duplicate Decision in R-14, where they returned structured errors. Their CLI equivalents (`ghost verify`, `ghost mutate`) work.
  - Argument errors come back structured and name the argument, for example `required argument 'workbook' is missing`, `unknown argument 'bogus'`, `invalid argument 'cases': Input should be greater than or equal to 1`. A broken module gives `module cannot be loaded: SyntaxError ...`.
  - One small gap: an unsupported input value (`{"Calculator!B2": {"x": 1}}`) comes back as `referee_error` without naming the argument (Requirement 12.11).
  - `extract_vba` left the file unchanged (same SHA-256 and mtime).
- **Layout and theme:** 360 px works in dark and light themes, and the toggle works.

## What I could not test

- **Real Excel:** there's no Excel here and no Excel-saved fixtures, so the Sanity Check against Excel values was not run. Expected Excel results in R-07, R-08 and R-24 are documented Excel behaviour, not measured.
- **Installing the Power in Kiro:** not checked (no Kiro in this environment).
- **AWS read-only checks (`describe`, logs):** not checked. The `aws-mcp` connector failed to connect, and I did not run the AWS CLI.
- **Job timeout on the live site:** not checked; it would need a five-minute job. It is unit-tested (`tests/test_web_jobs.py::test_timeout_kills_job`), but the 300 s value is hard-coded and not configurable.
- **R-17 on the live site:** not attempted, because it would probably restart the only task.
- **Health check under load:** not measured. The container `HEALTHCHECK` runs every 30 s, and `/healthz` starts a LibreOffice at most once a minute.
- **Screen reader and Playwright:** not checked.
- **VBA conversion and TypeScript export (P2):** not implemented, so not tested.

## Tests added (uncommitted)

| File | Passing | Expected to fail (`xfail(strict=True)`) |
|---|---|---|
| `tests/test_review_proof_strength.py` | 2 evidence tests (an order totals 500.00 and is Gold; the decimal-distance mutants differ) | R-01, R-02, R-03, R-04, R-05 |
| `tests/test_review_semantics.py` | 31 edge-case regression tests | R-07 (two cases), R-08 |
| `tests/test_review_autopsy_and_packaging.py` | none | R-09, R-10 (two), R-11, R-12, R-03, R-13 (two), R-14, R-15, R-16 |

- **Totals:** 33 passing and 19 expected failures. The full suite is now `192 passed, 19 xfailed`.
- Each xfail turns into a failure once its bug is fixed (strict mode), so remove the marker when that happens.
- (Historical, at review time) The two R-13 tests used the feasibility test bench macro sample and were skipped in CI. They now use the generated sample (see Resolution).

## Resolution

Status is fixed, deferred or pending. Phase 1 checkpoint: full suite `207 passed, 17 xfailed`; `tests/test_web_samples.py` and `tests/test_web_flow.py` `8 passed`.

Phase 2 checkpoint (task 4.12): full suite `250 passed, 12 xfailed`; `tests/test_web_samples.py`, `tests/test_web_flow.py` and `tests/unit/test_mcp_verify_intended.py` `11 passed`. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 generated + 6 targeted, 195 distinct, 0 mismatches); haunted raises F-001; haunted Faithful PASS (300 generated + 9 targeted, 198 distinct, 0 mismatches); haunted Intended with D-001 PASS with 1 expected difference (F-001, D-001) at quantity=50, minimal. All five demo `proof-report.json` files validate against `proof-report-1.json`. Skeptic reproductions: R-01 variants C, D, E and R-02 variant H now fail as translation bugs; the flip-probing cap, narrow-window and equality cases are found or reported in `boundary_notes`. The remaining 12 xfail are R-07 (2), R-08, R-09, R-10 (2), R-11, R-13 (2), R-14, R-15, R-16.

Phase 3 checkpoint (task 5.10): full suite `273 passed, 5 xfailed` (the 5 xfails are R-07 twice, R-08, R-15, R-16, all in later phases); `tests/test_web_samples.py` and `tests/test_web_flow.py` `8 passed`. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 generated + 6 targeted, 195 distinct); haunted raises F-001 (`>=` at B7 against `>` at B9), Faithful PASS (300 generated + 9 targeted, 198 distinct, 0 mismatches), Intended with D-001 PASS (300 generated + 9 targeted, 198 distinct, 1 expected difference explaining 26 distinct cases, minimal example quantity=50). All 5 demo proof-report.json files validate against `proof-report-1.json`. No `xfail` remains for R-09, R-10, R-11, R-13, R-14 (or R-26).

Phase 4 checkpoint (task 6.7): full suite `301 passed, 5 xfailed` (the 5 xfails are R-07 twice, R-08, R-15, R-16, all in later phases); the 7 web test files (`test_web_analysis_cache`, `test_web_app`, `test_web_flow`, `test_web_jobs`, `test_web_no_server_paths`, `test_web_samples`, `test_web_session_end_jobs`) `42 passed`. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 generated + 6 targeted, 195 distinct); haunted raises F-001; haunted Faithful PASS (300 generated + 9 targeted, 198 distinct, 0 mismatches); haunted Intended with D-001 PASS (300 generated + 9 targeted, 198 distinct, 1 expected difference F-001/D-001 explaining 26 distinct cases, minimal example quantity=50). All 3 demo `proof-report.json` files validate against `proof-report-1.json`. Docker (`docker build --platform linux/amd64 -t ghost-local:cp4 .`, run with `GHOST_SESSION_SECRET=test`, port 18083, then stopped and removed), haunted flow with curl and a cookie jar: `/healthz` 200 with `referee.available` true; `POST /sample/haunted` 200; `GET /autopsy` 200 with F-001, pre-checked inputs `Calculator!B2`, `B3`, `B4` and output `Calculator!B11`; `POST /decision` (`set|Calculator!B9|>|>=`) 200, D-001; `POST /verify` 200; a second `POST /verify` while the first ran returned 429 with the busy message; `/jobs/{id}` reached `done`, `passed` true, 64 events with no absolute path; `report.json` (served at `/run/{id}/report.json`) has mode intended, passed true, 300 generated + 9 targeted, 198 distinct, one expected difference (D-001) at quantity=50, mutation 33/35 killed, no `/Users` or `/tmp` strings. Checked rows R-17, R-18, R-21 (paths) and MCP error naming against code, tests and these runs; the R-18 row was malformed (extra columns) and is now one row.

Phase 5 checkpoint (task 7.7): full suite run twice, both `350 passed, 2 xfailed` (186 s and 189 s; the 2 xfails are R-15 and R-16, Phase 6); no failure in `tests/test_web_jobs.py::test_job_completes_collects_artifacts_and_cleans_up` in either run, so the earlier one-off failure did not reproduce and is not diagnosed. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 generated + 6 targeted, 195 distinct, 0 mismatches); haunted raises F-001 (`>=` at B7 against `>` at B9); haunted Faithful PASS (300 generated + 9 targeted, 198 distinct); haunted Intended with D-001 PASS (1 expected difference F-001/D-001, minimal example quantity=50, explains 26 distinct cases). All 5 demo `proof-report.json` files validate against `proof-report-1.json`. Vendored runtime: `excel.py` in the freshly converted `discount` and `haunted` folders is byte-identical to `ghost/runtime/excel.py`; the web `module.zip` (haunted, Intended with D-001) contains `logic.py`, `excel.py`, `mapping.yaml`, `rules.md`, its `excel.py` is byte-identical, and `import mig.logic` as a package in a clean folder with `env -i` and no `ghost` on `sys.path` runs `compute` and leaves `ghost` out of `sys.modules`. A bare `import logic` from inside the folder fails (relative import, then fallback to `ghost`); that import style is unchanged by Phase 5. Docker: image rebuilt (`ghost-local:p5`, LibreOffice 7.4.7.2); `tests/test_referee_libreoffice_differences.py` (R-24 pins) mounted read-only and run with the image's Python: `7 passed`. 1x1 `INDEX(...,0)` (left at `#REF!` by task 7.3): new finding R-30 below. Rows R-07, R-08, R-24, R-25, R-27 checked against code, tests and these runs.

Phase 6 checkpoint (task 8.6): full suite `380 passed` in 199 s (0 failed, 0 xfailed, 0 skipped), first clean run after the five parallel edits. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 generated + 6 targeted, 195 distinct, 0 mismatches); haunted raises F-001, Faithful PASS (300 + 9 targeted, 198 distinct, 0 mismatches), D-001 recorded, Intended PASS with 1 mismatch classed "expected by decision" at quantity=50 (referee 6.0, actual 0). All 5 demo proof-report.json files validate against `proof-report-1.json`. `uvx --from . ghost-mcp` from a temp dir answers `initialize` and `tools/list` (13 tools). Docker image built locally; haunted flow by curl: `/healthz` 200 (Referee available), sample 200, autopsy page contains "Unanswered findings keep the original behaviour and are listed in the report.", decision D-001 200, verify 200, second verify 429, job done, `report.html` contains "Change-point bracket" and "Tested domains", `report.html?mode=faithful` 200 and `report.json?mode=faithful` 200; container and image removed. `plugin/plugin.json` validates against the saved schema; the removal of `skills`/`mcpServers` is an open owner check (KIRO_USAGE install checklist step 5). `tests/test_review_semantics.py` still contains a conditional `xfail` marker for cases not listed in `FIXED`; all current cases are in `FIXED`, so none is applied.

Phase 7 checkpoint (task 9.8): full suite run once on the combined code: `415 passed, 2 skipped` in 214 s (0 failed, 0 xfailed). The 2 skips are `tests/test_excel_saved_fixtures.py` (empty `tests/fixtures/excel-saved/`, no real Excel-saved file yet). `-m golden`: `26 passed, 391 deselected`. `-m "not slow"`: 416 of 417 collected (1 slow test deselected); `-m slow`: 1 passed in 5 s. `scripts/demo.sh` into a temp folder, exit 0: discount Faithful PASS (300 generated + 6 targeted, 195 distinct, 0 mismatches); haunted raises F-001 (`>=` at B7 against `>` at B9); haunted Faithful PASS (300 + 9 targeted, 198 distinct, 0 mismatches); D-001 recorded; haunted Intended PASS with 1 mismatch classed "expected by decision" (F-001/D-001) at quantity=50 (referee 6.0, actual 0), explaining 26 distinct cases. All 5 demo `proof-report.json` files validate against `proof-report-1.json`. No `xfail` marker is applied in `tests/test_review_*.py` (the conditional one in `test_review_semantics.py` applies to no current case). `git status` shows no `demo-out/`, `.kiro/specs/_hooktest` or graveyard test files; `graveyard/` holds only `.gitkeep`.

| Finding | Status | Reason | Test |
|---|---|---|---|
| R-01 | fixed (CLI, web and MCP) | Intended mismatch is "expected by decision" only when the transpiled Faithful module matches the Referee, the module differs from Faithful, and the Decision's patched comparison (trace hook) differs; otherwise "translation bug". Expected mismatches no longer stop the run; one shrunk example per Decision with an optional `cases` count. Skeptic follow-up (variants C, D, E): a missing or renamed trace hook explains nothing, and the candidate's outputs must equal the Intended module's, so a VAT bug plus D-001 fails as a translation bug. Haunted Intended: 300 generated cases, 1 expected difference at quantity=50 (the number of cases it explains is engine output in the report) | `tests/test_review_proof_strength.py::test_intended_mode_does_not_excuse_unrelated_bug`, `tests/test_review_classification_soundness.py`, `tests/unit/test_mcp_verify_intended.py`, `tests/test_property_intended_classification.py::test_property_3_intended_classification_soundness`, `tests/test_verifier_classify.py::test_explaining_decision_needs_all_three_conditions` |
| R-02 | fixed | Faithful mismatch is "original workbook inconsistency" only when the comparisons at the Finding's locations evaluate to different truth values on that case (trace hook); otherwise "translation bug". Skeptic follow-up (variant H): in Faithful mode the trace given to the classifier is empty unless the transpiled Faithful module itself disagrees with the Referee on that case, so a code bug the transpiler does not share is a "translation bug" | `tests/test_review_proof_strength.py::test_faithful_translation_bug_is_labelled_translation_bug`, `tests/test_verifier_classify.py::test_faithful_inconsistency_needs_disagreeing_comparisons` |
| R-03 | fixed | One shared function, `ghost/converter/typeinfer.py:infer_input_type`, used by `mapping._type_of` and `strategies.infer_spec`: data validation decides first (`decimal` -> decimal, `whole` -> integer), then the sample value (int -> integer, float -> decimal, str -> string, bool -> boolean). A whole-valued float with no validation is decimal: Excel-saved whole numbers read as `int`, so a float marks a deliberate decimal and the wider type catches truncation bugs; samples (a) and (b) hold `int` values and stay as before. Discount `delivery_distance_km` is now `decimal`; Faithful passes 300 cases | `tests/test_review_proof_strength.py::test_truncated_distance_is_caught`, `tests/test_review_autopsy_and_packaging.py::test_decimal_validation_wins_over_whole_number_sample`, `tests/test_property_type_inference.py::test_property_5_type_inference` |
| R-04 | fixed | Condition-flip probing (`ghost/verifier/flip.py`) on the transpiled Faithful module; the cases on both sides of each flip, plus exact hits, go to the verifier's `extra_cases` and the mutation check's targeted cases (CLI, web jobs through the CLI, and MCP `verify_implementation`, which also returns `boundary_notes`), are checked against the Referee and listed as boundaries (optional report fields only). Reported haunted case count is now 309 (300 generated + 9 targeted). Added time: under 0.01 s probing, no measurable change in CLI verify with mutation (3.6 to 4.3 s). Skeptic follow-up: what probing does not check is reported (optional `boundary_notes` in the report, CLI output): evaluation cap reached, per-search and case-limit truncation, pairs with no flip found, text inputs not probed, and the whole probe when the workbook cannot be converted. The grid is also seeded with numeric formula literals and their +-1 and +-tolerance, which catches `AND(B1>10,B1<20)` and `B3=777` | `tests/test_review_proof_strength.py::test_gold_threshold_on_calculated_cell_is_caught`, `::test_tier_flip_cases_kill_threshold_mutants_and_boundaries_list_b12`, `tests/test_flip_reporting.py`, `tests/unit/test_mcp_verify_intended.py::test_response_carries_the_same_boundary_notes_as_the_cli` |
| R-05 | fixed | Table blocks and INDEX/MATCH text are PARAMETER; `_inp("")` means an empty cell; demo defaults aligned with autopsy defaults | `tests/test_review_proof_strength.py::test_scenarios_sample_passes_with_default_inputs`, `tests/test_web_samples.py::test_bundled_sample_passes_faithful_with_default_inputs` |
| R-06 | fixed | `ghost/mutation/run.py` no longer says "equivalent on tested domain". A survivor reads "no difference found on N distinct cases; tested domain: <input>: <type>, min, max, decimal places; ...", derived from the cases actually run (`tested_domains`, `no_difference_reason`). Skeptic follow-up: the router text no longer says Ghost "proves" the result. After R-03 and R-04 the ROUND-digit constant +-1 mutants on `Calculator!B9` are killed in a real run. Remaining survivors on discount and haunted (31/33 and 33/35) are the two half-even rounding mutants, which need 4-dp distances or 3-dp prices | `tests/test_mutation_wording.py` (5 tests, incl. `test_haunted_round_digit_mutants_are_killed`); `tests/test_review_proof_strength.py::test_decimal_distance_mutants_are_not_equivalent` unchanged; `ghost/router/explain.py` no longer says Ghost "proves" the result: it "checks the result against the original workbook" (no other "prove" claims in README, web, plugin or report HTML) |
| R-07 | fixed | `xl_compare` in `ghost/runtime/excel.py` normalises both numeric sides to 15 significant digits (half away from zero) before comparing | `tests/test_review_semantics.py::test_transpiler_bug[compare_after_division]`, `[equality_after_division]`, `tests/test_property_comparison_normalisation.py` (3 tests) |
| R-08 | fixed | `_index` returns `#VALUE!` for row or column 0 on a multi-cell range. `_decimal_text` writes scientific notation (`1E+20`, `1E-20`, `1.23456789012346E+17`) for magnitudes >= 1E16 or < 1E-14, the switch points measured on the Referee (not verified in Excel). `values_equal` treats two strings as equal when both are scientific notation (`-?d(.d+)?E[+-]dd{1,2}`) of the same value, so "1E+20" equals the Referee's "1E+020"; any other string pair stays exact. INDEX with 0 on a single-cell range: see R-30 (fixed) | `tests/test_review_semantics.py::test_transpiler_bug[index_row_zero]` (xfail removed), `::test_transpiler_matches_referee[text_*]` (7 Referee cases), `tests/test_number_to_text.py` |
| R-09 | fixed | `ghost/autopsy/findings.py` compares truth sets over {below, at, above}; a Finding needs two operators whose sets are neither equal nor complementary | `tests/test_review_autopsy_and_packaging.py::test_complementary_operators_are_not_a_finding`, `tests/test_property_operator_consistency.py::test_property_4_operator_consistency` (both pass) |
| R-10 | fixed | `extract_thresholds(workbook, vba, roles)` resolves comparison constants only from non-INPUT cells (roles default to the autopsy classification; `_analyse`, `run_verification` and MCP `verify_implementation` pass the confirmed or mapped roles, so the web flow recomputes on every confirm). `50%` is 0.5. Expression comparisons such as `A2*A3>=500` are recorded with the rendered expression as `cell` and the formula cell as `source`. An input's current value is no longer a threshold on a formula cell. `A7>=Bulk` stays open until task 7.4 | `tests/test_review_autopsy_and_packaging.py::test_input_value_is_not_treated_as_a_threshold`, `::test_expression_and_percent_thresholds_are_recorded` (both pass) |
| R-11 | fixed | `ghost/autopsy/classify.py` no longer demotes a constant that a formula compares directly with a numeric literal (read from the formula ASTs, not from computed thresholds). Rate labels, R-12 blocks and R-05 table blocks stay PARAMETER | `tests/test_review_autopsy_and_packaging.py::test_input_shared_by_two_formulas_is_an_input` (passes) |
| R-12 | fixed | `Calculator!E5` is classified PARAMETER by the autopsy heuristics | `tests/test_review_autopsy_and_packaging.py::test_free_delivery_distance_is_a_parameter` |
| R-13 | fixed | `ghost.ingest.load_workbook` detects `xl/vbaProject.bin` in the zip whatever the extension and extracts it statically with olevba (`ghost/ingest/vba.py`); the web summary, autopsy metrics, CLI and MCP share it. The two tests now use the generated `macro_samples` fixture (test-bench path removed). Guardrail (task 5.10): when `xl/vbaProject.bin` exists but cannot be read, `Workbook.vba_present` is True and `vba_error` carries the reason; the upload summary (`has_vba` true, `vba_error`), autopsy page and CLI show "VBA present but could not be read: <reason>" and "VBA: not checked" instead of reporting no VBA | `tests/test_review_autopsy_and_packaging.py::test_vba_found_in_renamed_macro_workbook`, `::test_upload_summary_reports_vba` (pass); `tests/test_vba_unreadable.py` (corrupt `xl/vbaProject.bin`, 2 tests) |
| R-14 | fixed | `record` rejects a second Decision for the same `finding_id` or `rule_id`, naming the existing `decision_id`; CLI `decide` and MCP `record_decision` also emit the Intended module at record time and reject a patch that cannot be applied. Web is unchanged (409 "already has a Decision"). Two fixtures in `tests/test_decisions_store.py` recorded the same finding twice to test ID assignment; they now use F-001 and F-002, with no assertion changed. | `tests/test_review_autopsy_and_packaging.py::test_second_decision_for_same_finding_is_rejected`, `tests/test_property_decision_uniqueness.py::test_property_8_decision_uniqueness`, `tests/test_decision_patch_validation.py` |
| R-15 | fixed (install from the GitHub URL not checked in Kiro) | `plugin/plugin.json` has `$schema` and validates against the fetched schema (the schema has `additionalProperties: false`, so the non-conforming `skills` and `mcpServers` keys were removed; skills are found under `skills/` and servers in `mcp.json` by convention). `plugin/mcp.json` has no `toolPrefix` and launches `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp` (new `[project.scripts] ghost-mcp = mcp_server.server:main`). Prerequisites are in the guardrails skill and README. **Test edit for the owner:** `tests/test_plugin_package.py::test_mcp_json_uses_ghost_prefix_and_real_module` was replaced by `test_mcp_json_uses_documented_fields_and_a_real_entry_point`; it no longer asserts `toolPrefix.startswith("ghost_")` and `args == ["-m", "mcp_server.server"]` (both were the bug) and now asserts no `toolPrefix`, only documented fields, command `uvx`, the `ghost-mcp` script target and the repository URL. A schema validation test was added. | `tests/test_review_autopsy_and_packaging.py::test_plugin_manifest_has_schema` (xfail removed, passes), `tests/test_plugin_package.py` |
| R-16 | fixed | `ghost/router/explain.py`: command is now `atx custom def exec -n excel-vba-to-python -p <dir> -c 'python3 -m compileall -q .' -x -t`. Reference checked online: https://docs.aws.amazon.com/transform/latest/userguide/custom-command-reference.html (lists `-x`/`--non-interactive` and `-t`/`--trust-all-tools`) and https://docs.aws.amazon.com/transform/latest/userguide/custom-workflows.html (full automation is `-x -t`). Note: the current web reference table does not itself say "required with -x"; the report's claim came from the Kiro power's CLI reference, so Ghost follows the documented `-x -t` pairing. The explanation and the route skill/steering now say the transformation definition must exist (`atx custom def list`) and no longer call the command "exact". Build command: `**/*.py` only recurses with globstar and is not expanded at all without a shell, so `python3 -m compileall -q .` is used (standard library, recursive, non-zero exit on a syntax error; syntax check only). The command is never executed. | `tests/test_review_autopsy_and_packaging.py::test_atx_dry_run_includes_trust_all_tools_with_non_interactive` (xfail removed); `tests/unit/test_router_explain.py::test_atx_command_uses_trust_flag_portable_build_and_names_prerequisite` |
| R-17 | fixed (cap + cache) | `MAX_CELLS = 200_000` in `ghost/ingest/limits.py`, counted in the defusedxml pre-scan of `xl/worksheets/*.xml` with a streaming `iterparse` that frees each `<c>`/`<row>`; over the cap raises `TooManyCells` ("Workbook has more than 200,000 cells; the limit is 200,000 cells.") before openpyxl loads anything. Web upload returns 422 with that message. A 250,000-cell write-only workbook is rejected in about 0.6 s. Documented in `.kiro/steering/tech.md` and README. Cache: `web/flow.py::_analysis` keeps one parsed analysis per session (`Session.analysis_cache`), keyed on workbook path, sha256 and confirmed inputs/outputs; cleared on new upload/sample, on session delete and sweep. Decisions are read fresh on each call, so decision state is never stale. No subprocess parsing added | `tests/test_ingest_max_cells.py` (4 tests: fast rejection with openpyxl load disabled, web upload, samples still upload and analyse); `tests/test_web_analysis_cache.py` (5 tests: 1 parse across repeated GET /autopsy, no reparse after a decision, invalidation on new sample/upload, input change recomputes, one entry dropped with session) |
| R-18 | fixed (cap; jobs and artifacts removed at session end) | Cap: at most one queued-or-running job per session. `JobRunner.submit` raises `SessionBusy`; `POST /verify` returns 429 "This session already has a verification queued or running. Wait for it to finish, then start a new run." and re-shows the active job's panel. `web/static/htmx-errors.js` lets htmx swap 409/422/429 bodies. Documented in README. Session end: `JobRunner.forget_session` removes the session's jobs from the runner, clears their artifacts and events, dequeues queued jobs and kills running process groups (a job that finishes afterwards no longer collects artifacts). `SessionStore.on_delete` hooks call it on DELETE /session, sweep and close, so `/jobs/{id}` returns 404. | `tests/test_web_jobs.py` (3 new tests, `test_concurrency_limit_and_queue_position` now uses three sessions); `tests/test_web_flow.py` (3 new tests: 429 with message and panel, new run after a finished job, swap script loaded).; `tests/test_web_session_end_jobs.py` (4 tests: DELETE /session, sweep with a short idle timeout, other sessions keep their jobs, running process killed and queue emptied) |
| R-19 | fixed | README written (URL, quick start, CLI demo, web app, Docker, Power, Excel-saved fixtures, safety, limits, test-bench note). Updated at task 9.7: Power launch via `uvx --from git+... ghost-mcp` with uv and LibreOffice prerequisites, `MAX_CELLS` and other limits, per-session 429 cap, `GHOST_MUTATION_CASES`, `tests/fixtures/excel-saved/`, `-m golden` and `-m "not slow"`, hooks via `scripts/ghost-py`, known differences (R-24 table, R-25 unverified ROUND, R-08 number-to-text, R-30 INDEX, named ranges supported and dynamic names not converted), what the proof report shows, deploy doc pointer | manual: followed command by command (task 3.6); task 9.7 checked each command: `ghost --help`, `scripts/demo.sh` into a temp folder, `pytest -m golden --collect-only -q` (26 tests), `-m "not slow" --collect-only -q`, `scripts/ghost-py` |
| R-20 | partly fixed (all five test kinds added; no real Excel-saved fixture exists yet) | Added the tests the requirements promise. Golden semantics tests from `samples/make_traps.py`, marked `golden`, checked against the Referee and the generated code (26 tests). An Excel-saved fixtures folder with a README and a test that skips with a message naming the folder while it is empty. No real Excel-saved file exists yet, so no cross-check against Excel has run (owner to create the files in Excel for the web); the report says "not cross-checked against Excel". Formula fuzzing (Property 9, Hypothesis, explicit seed, 60 examples) found no mismatches between the Referee and the transpiled code. It does not cover operator precedence or text and boolean inputs, so those are not checked. CLI end-to-end runs `scripts/demo.sh` as a subprocess into a temp folder. Performance verifies 500 cases in about 5 s including LibreOffice start-up (limit 60 s). | `tests/golden/test_semantics_golden.py` (`pytest -m golden`); `tests/test_excel_saved_fixtures.py` (2 skipped: empty folder, empty parameter set); `tests/test_property_formula_fuzzing.py` (Property 9); `tests/test_cli_end_to_end.py` (6 tests); `tests/test_performance_slow.py` (marker `slow`, registered in `pyproject.toml`) |
| R-21 | fixed | Paths part fixed (task 6.5). Rest fixed (task 8.3): the HTML boundary table has a "Change-point bracket" column (the old values) and an "Exact hits" column that shows only flip-probing exact values, else "not checked". Optional `tested_domains` in the report JSON and HTML (type, min, max, decimal places from the cases run). With both modes the Faithful report downloads at `/run/{id}/report.html?mode=faithful` and `report.json?mode=faithful`, linked in the job panel | `tests/test_report_details.py`; demo reports validate against `proof-report-1.json` |
| MCP error naming (Req. 12.11) | fixed | `evaluate_original` checks input values before starting the Referee; a dict or list returns `invalid_argument` naming `inputs.<cell>`. `boundary_cases` and `verify_implementation` already named their arguments | `tests/unit/test_mcp_server.py::test_evaluate_original_non_scalar_input_names_the_cell`, `::test_boundary_cases_and_verify_name_bad_arguments` |
| R-22 | fixed | `web/templates/_autopsy.html` now says "Unanswered findings keep the original behaviour and are listed in the report." An unanswered F-001 on haunted (no Decision) appears in `report.json` and `report.html` (Faithful, passes) | `tests/test_web_autopsy_text.py` |
| R-23 | fixed | Dark `--border` is `#7a6d94` (3.96:1 on bg, 3.65:1 on surface; light border 4.21:1 and 4.66:1). Toggle label is constant "Light mode", `aria-pressed` carries the state. Not checked: a real screen reader or browser | `tests/test_web_accessibility.py` |
| R-24 | fixed (documented and pinned; image not upgraded) | The seven divergences are in the "Where LibreOffice differs from Excel" table in `.kiro/steering/excel-semantics.md`. Measured through the Referee locally (26.8.3.1) and in image `ghost-local:cp4` (7.4.7.2): identical results for all seven, so the earlier suspicion that the two versions differ on these is not borne out. Excel results remain "not verified" (documented behaviour only) | `tests/test_referee_libreoffice_differences.py` |
| R-25 | deferred: awaiting owner's Excel check | Documented only, behaviour unchanged. `=ROUND(123456789012345.67,1)`: Referee gives `123456789012345.7` (LibreOffice 26.8.3.1 local and 7.4.7.2 in `ghost-local:cp4`, both measured 2026-11-24); Ghost's `xl_round` gives `123456789012346.0`. Excel result not verified; owner to check in Excel for the web (checklist in `docs/KIRO_USAGE.md`). Notes in `.kiro/steering/excel-semantics.md` and the README | none (document only) |
| R-26 | fixed | Output type comes from the Excel-saved value, else from the formula AST (`infer_formula_kind` in `ghost/converter/typeinfer.py`): text literals in every IF branch, `&`, text functions, INDEX into a text range give `string`. Undecided cases (mixed branches, unknown functions) keep the `decimal` default, noted in `mapping.py` | `tests/unit/test_mapping_text_outputs.py` |
| R-27 | fixed | Workbook-scoped names that are one cell or one rectangle resolve in subset check, emitter, thresholds, classification and rule text (name used as label). Dynamic (OFFSET/INDIRECT), sheet-scoped, multi-area, external and unknown-sheet names stay "not converted" with a reason. Measured against the Referee: `=Bulk*2` and `SUM(Prices)*B2` match, `IF(B2>=Bulk,...)` verifies Faithful | `tests/test_named_ranges.py` |
| R-28 | fixed | `cases_tested` keeps its meaning (every case checked, repeats included). New optional report fields `cases_generated`, `cases_targeted`, `distinct_cases` (schema stays `proof-report-1`, no version bump). HTML, CLI, MCP and web panel show the generated, targeted and distinct counts. Skeptic follow-up: the distinct count uses a normalised case key (`case_key`: Decimal normalised, ints and floats via `Decimal(repr(x))`), so 1, 1.0 and Decimal('1') count once. HTML, CLI, MCP and web panel show e.g. "300 generated + 9 targeted, 198 distinct". Phase 2 checkpoint demo run: 195 distinct (discount, 300 generated + 6 targeted) and 198 distinct (haunted, 300 generated + 9 targeted); the review's 176 counted generated cases only, before later fixes added targeted cases | `tests/unit/test_case_counts.py`, `tests/test_case_key.py` |
| R-29 | fixed, hook trigger in Kiro pending owner check | Hooks call the venv Python and were run by hand with real output. The owner still has to trigger each hook in Kiro (checklist in `docs/KIRO_USAGE.md`). Re-run by hand after task 9.1 (task 9.2): autopsy, report, verify and golden all exit 0; the golden hook now selects 26 tests and they pass. Kiro IDE trigger pending owner | hooks run by hand (tasks 3.7, 9.2) |

### R-30: `INDEX(...,0)` on a single-cell range (found at the Phase 5 checkpoint, fixed in the task 7.3 follow-up)

Measured through the Referee (LibreOffice 26.8.3.1 local) against the transpiled module, with `M1=7`, `M2=8`, `M3=9`:

| Formula | Referee | Ghost |
|---|---|---|
| `=INDEX(M1:M1,0)` | 7 | `#REF!` |
| `=INDEX(M1:M1,1,0)` | 7 | `#REF!` |
| `=INDEX(M1:M1,0,0)` | 7 | `#REF!` |
| `=INDEX(M1,0)` | 7 | `#REF!` |
| `=INDEX(M1:M1,1)` | 7 | 7 |
| `=INDEX(M1:M3,0)` | `#VALUE!` | `#VALUE!` |
| `=INDEX(M1:M3,0,0)` | `#VALUE!` | `#VALUE!` |
| `=INDEX(M1:O1,1,0)` | `#VALUE!` | `#VALUE!` |

Ghost differs from the Referee on the four single-cell cases with a 0 argument. The Referee returns the cell value (the whole range is one cell). Excel's result for these is not verified. Task 7.3 only covered ranges with more than one cell. Status: **fixed**. `_index` now treats a 0 on a dimension of length 1 as that single row or column, and a 0 on a longer dimension as `#VALUE!`. Further Referee probes agree with this rule: `INDEX(M1:M3,2,0)` is 8, `INDEX(M1:O1,0,2)` is 0 (empty N1), `INDEX(M1:M1,0,1)` is 7, `INDEX(M1:M3,0,1)` is `#VALUE!`, `INDEX(M1:O1,0)` is `#VALUE!`. Excel's result for the 1-length cases is not verified. Tests: 11 `index_*` Referee cases in `tests/test_review_semantics.py::test_transpiler_matches_referee`.

Follow-up: the generated `logic.py` header now tries `.excel`, then `excel` (run from the folder), then `ghost.runtime.excel`, so an unzipped `module.zip` imports without the ghost package. Tests: `tests/test_generated_module_standalone.py`.
