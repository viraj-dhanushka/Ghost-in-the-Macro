Fix every finding in the 24 November review of Ghost in the Macro, in the order given below, without breaking the demo.

## Read first

- `docs/TEST_REPORT_2026-11-24.md`: findings R-01 to R-29, each with steps to reproduce, quoted output, the likely cause (file and line) and a suggested fix.
- `tests/test_review_proof_strength.py`, `tests/test_review_semantics.py` and `tests/test_review_autopsy_and_packaging.py`. Each `xfail(strict=True)` test encodes the correct behaviour and names its finding ID in `reason=`.
- The steering files in `.kiro/steering/`. The guardrails are hard rules: never run macros from uploads, use Decimal for money, use Excel rounding, never invent data, never guess unsupported constructs.

## Ground rules

1. **Test first.** Every finding has a test, or gets one before it is fixed.
   - When a fix makes a strict-xfail test pass, remove its marker; strict mode turns an unexpected pass into a failure.
   - Never delete a test or weaken what it expects. If you think a test expects the wrong thing, stop and show me the evidence.
2. **Keep the demo working at every step.** The haunted sample must still:
   - raise F-001;
   - pass Faithful verification over 300 cases;
   - with D-001 recorded, pass Intended verification with exactly one expected difference, whose minimal counterexample is quantity = 50.

   Run `scripts/demo.sh` after each phase.
3. **Keep the suite green.** Run `.venv/bin/python -m pytest -q` after each finding. Baseline: `192 passed, 19 xfailed`.
4. **No push, no deploy.** Don't run AWS commands that change anything. Leave changes uncommitted unless I ask you to commit. I'll review the changes and deploy with `scripts/deploy_ecs_express.sh` myself.
5. **Keep a record.**
   - Log each fix in `docs/KIRO_USAGE.md`: the Kiro feature used and what changed.
   - Add a "Resolution" table to the end of `docs/TEST_REPORT_2026-11-24.md`: one row per finding, saying fixed or deferred, with the reason and the test.
6. **Time.** Submissions close Fri 4 Dec 2026, 2:00 PM PT. Finish Phase 1 before anything else. If a later fix would change the demo flow or looks much bigger than described, stop and ask me first.

## Set it up in Kiro

- Create a spec named `review-fixes-2026-11-24`, using the Bugfix spec type if Kiro offers it:
  - one requirement per finding ID, with the "Done when" text below as its acceptance criteria;
  - tasks in the phase order below, marking the property-based-test tasks.
- Run Analyze Requirements on the spec before starting.
- Use the custom agents where they fit: Skeptic for the verifier and mutation work, Coroner for the autopsy work.

---

## Phase 1: demo and submission blockers

### R-05 and R-12: default inputs, and empty strings (the scenarios sample fails on the live site)

**Problem:**
- The autopsy proposes, and the web app pre-checks, 53 inputs for sample (c), including the scenario names `Model!A6:A15` and every rate in the table. Samples (a) and (b) also pre-check `Calculator!E5` ("Free delivery within (km)").
- The verifier generates `""` for text inputs. The Referee stores that as an empty cell, so `INDEX` returns 0, while the generated `_inp` keeps `""` as a string.
- `tests/test_product_samples.py` overrides the defaults, so the suite never tested what the web app does.

**Fix:**
- Treat table blocks of constants, and text referenced through `INDEX`/`MATCH` ranges, as PARAMETER.
- Treat `E5` as a PARAMETER: improve the parameter heuristics in `ghost/autopsy/classify.py`, for example "within", "free" or "allowance" labels, or a constant sitting in a block of other parameters.
- Make `_inp("")` mean an empty cell, matching the Referee, and/or stop generating empty strings.

**Done when:**
- `test_scenarios_sample_passes_with_default_inputs` and `test_free_delivery_distance_is_a_parameter` pass.
- A new web test runs each bundled sample through the web flow (`POST /sample/{id}`, `GET /autopsy`, `POST /verify` with the pre-checked boxes) and every one passes Faithful.
- The demo's defaults equal the inputs `ghost/cli.py:678` hard-codes, and the override is either removed or justified.

### R-19: README

**Fix:** write `README.md` to cover Requirement 21.7:
- live URL;
- quick start: LibreOffice on macOS (`~/Applications` or `/Applications`) and the Debian packages `libreoffice-calc-nogui` and `libreoffice-script-provider-python`, plus the venv;
- CLI demo;
- running the web app locally;
- Docker build and run, with the environment variables;
- using the Kiro Power;
- creating Excel-saved test files with Excel for the web;
- safety: macros never run from uploads;
- limits and known differences between LibreOffice and Excel;
- an honest note that the feasibility test bench was built outside this repository before the spec and isn't included.

Confirm `.kiro/` is committed and not ignored. Update the README again at the end of Phase 7.

**Done when:** a fresh clone can follow it command by command.

### R-29: Kiro hooks can't run

**Problem:**
- All four hooks in `.kiro/hooks/` call the system `python3`, which on this Mac gives `ModuleNotFoundError: No module named 'openpyxl'`.
- The golden-tests hook runs `pytest -m golden`, which selects 0 tests (`211 deselected`).

**Fix:** call `.venv/bin/python`, or a small wrapper script that finds the venv, and give the golden hook real tests (Phase 7).

**Done when:** each hook, triggered in Kiro, runs and reports a real result, recorded in `docs/KIRO_USAGE.md`.

---

## Phase 2: integrity of the proof

### R-01: Intended mode excuses unrelated bugs

**Problem:**
- In Intended mode, `ghost/verifier/classify.py:62-79` marks any mismatch "expected by decision" when the output depends on a cell listed in the Finding.
- `ghost/verifier/run.py:156-160` stops at the first mismatch.
- So a VAT bug (21%) passes after 1 case, with quantity = 0. The Kiro Power path (`verify_implementation`) has the same problem.

**Fix:**
- A mismatch counts as "expected by decision" only when all three hold, checked with the existing trace hook:
  1. the transpiled Faithful module (no patch) matches the Referee on that case;
  2. the Intended module differs from the Faithful module on that case;
  3. the Decision's patched comparison evaluates differently in the two modules on that case.

  Anything else is a "translation bug".
- For a hand-written or AI-written module, generate the transpiled Faithful module and use it for this check. If the workbook isn't fully convertible, classify the mismatch as a translation bug.
- Don't stop on an expected mismatch. Record it and keep generating until the case budget is used up. Only an unexpected mismatch stops the run and gets shrunk. Still shrink one example per expected Decision for the report.

**Done when:**
- `test_intended_mode_does_not_excuse_unrelated_bug` passes.
- The haunted Intended run reports about 300 cases, with one expected difference whose minimal case is quantity = 50.
- MCP `verify_implementation` uses the same logic.

### R-02: Faithful mode blames the workbook for a code bug

**Fix:** use "original workbook inconsistency" only when the comparisons at the Finding's locations evaluate to different truth values on that case. Otherwise it's a "translation bug".

**Done when:** `test_faithful_translation_bug_is_labelled_translation_bug` passes.

### R-03: decimal inputs are typed integer

**Fix:** data validation decides first (`decimal` means decimal, `whole` means integer), then the sample value. Use one shared inference function for both `ghost/converter/mapping.py:60-69` and `ghost/verifier/strategies.py:infer_spec`.

**Done when:** `test_decimal_validation_wins_over_whole_number_sample` and `test_truncated_distance_is_caught` pass, and samples (a) and (b) still pass.

### R-04 and R-10 (expressions): thresholds on calculated cells and expressions

**Problem:** `_probe_boundaries` (`ghost/cli.py:385-397`) skips any threshold whose cell isn't an input. Comparisons on expressions such as `A2*A3>=500` are never recorded.

**Fix:** add condition-flip probing.
- For every IF condition in the transpiled Faithful module, binary-search each numeric input, with the other inputs at their base values plus a few random base points, for where the condition flips. Use the trace hook to detect the flip.
- Add the cases on both sides of each flip, plus exact hits where the compared value equals the threshold, to `extra_cases` for verification and for the mutation check.
- Report them as boundaries.
- Verify these cases against the Referee like any other case.
- This covers calculated cells (`B11>=500`) and expressions (`A2*A3>=500`).

**Done when:**
- `test_gold_threshold_on_calculated_cell_is_caught` passes.
- On the tier workbook (in the report and the test), the flip and ±1 mutants on `B12`/`B13` are killed.
- The boundaries list `B12`/`B13`.

### R-06: honest reasons for surviving mutants

**Fix:**
- Replace "equivalent on tested domain" (`ghost/mutation/run.py:118`) with wording like "no difference found on N distinct cases", followed by each input's tested domain (type, min, max, decimal places).
- Never claim equivalence.

**Done when:**
- After R-03 and R-04, the constant ±1 mutants on the ROUND digits of `Calculator!B9` in the haunted sample are killed. They differ from the Referee at 10.3 km and 10.01 km.
- Reports and tests use the new wording.

### R-28: case count includes repeats

**Fix:** report cases generated and distinct inputs separately. Add an optional schema field, keeping `proof-report-1.json` backward compatible or bumping the version with tests, and update the HTML.

**Done when:** a report shows, for example, "300 generated, 176 distinct".

---

## Phase 3: autopsy, decisions and VBA

### R-09: false Finding for complementary operators

**Fix:** give each operator a truth set over {below, at, above} the constant:

| Operator | True when the value is |
|---|---|
| `>=` | at, above |
| `>` | above |
| `<=` | below, at |
| `<` | below |
| `=` | at |
| `<>` | below, above |

Two comparisons are consistent when their sets are equal or complementary; otherwise they conflict.

**Done when:** `test_complementary_operators_are_not_a_finding` passes and the haunted sample still raises F-001 (`>=` against `>`).

### R-10: threshold extraction rules

**Fix:**
- Resolve comparison constants only from non-INPUT cells. Pass roles, or the confirmed inputs, into extraction, and recompute after the user confirms inputs.
- Treat `50%` as 0.5.
- Drop the invented "formula cell compared with an input's current value" thresholds. Condition-flip probing covers those cases.

**Done when:** `test_input_value_is_not_treated_as_a_threshold` and `test_expression_and_percent_thresholds_are_recorded` pass.

### R-11: a real input shared by two formulas becomes PARAMETER

**Fix:** a constant compared against a threshold is INPUT unless it's labelled as a rate. Table blocks stay PARAMETER (see R-05).

**Done when:** `test_input_shared_by_two_formulas_is_an_input` passes and the R-05 tests still pass.

### R-14: duplicate Decisions

**Fix:**
- `ghost.decisions.store.record` rejects a second Decision for the same `finding_id` or `rule_id`, raising `InvalidDecision` and naming the existing `decision_id`.
- Where the workbook is known (CLI and MCP, through `source.yaml`), validate the patch when it is recorded.

**Done when:** `test_second_decision_for_same_finding_is_rejected` passes and the web behaviour is unchanged.

### R-13: VBA detection depends on the file extension

**Fix:**
- Detect `xl/vbaProject.bin` in the zip whatever the extension, extract it statically with olevba, and set `has_vba` in the upload summary from the result.
- Add `samples/make_xlsm.py`: an `.xlsm` pair built through the Referee's `save_with_vba`, never running macros, as in Requirement 5.15.
- Point the two R-13 tests at that generated sample instead of the absolute test-bench path, so they run in CI.

**Done when:** `test_vba_found_in_renamed_macro_workbook` and `test_upload_summary_reports_vba` pass without the test-bench folder.

### R-26: text outputs typed decimal

**Fix:** formulas that produce text are typed `string` in `mapping.yaml`.

---

## Phase 4: security and robustness

### R-17: memory exhaustion from large but legal workbooks

**Fix:**
- Add `MAX_CELLS` (for example 200,000), counted during the existing defusedxml pre-scan of the sheet XML, before openpyxl loads anything. Reject with a message naming the limit.
- Cache the analysis per session and workbook so `GET /autopsy` doesn't reparse.
- Consider parsing uploads in a subprocess with a memory limit.

**Done when:**
- A workbook of about 250,000 cells, built in the test with openpyxl write-only mode, is rejected in under 5 seconds.
- Upload and autopsy for the bundled samples still work.
- The limit is documented in `.kiro/steering/tech.md` and the README.

### R-18: job cap and memory retention

**Fix:**
- Allow at most one queued-or-running job per session. A second `/verify` returns 429 with a clear message, or replaces the queued job; document which.
- Remove a session's jobs and their artifacts from memory when the session is deleted or swept (`web/jobs.py:141`, `:168`).

**Done when:** tests cover both.

### R-21 (part): server paths in job events

**Fix:** job events show names relative to the run, never absolute server paths.

### MCP error naming (Requirement 12.11)

**Fix:** `evaluate_original` with a non-scalar input value returns `invalid_argument` naming `inputs.<cell>`, not `referee_error`.

---

## Phase 5: transpiler and Referee semantics

### R-07: comparisons after division

**Fix:** in `ghost/runtime/excel.py`, compare numbers after normalising both sides to 15 significant digits, as Excel does.

**Done when:** both R-07 cases in `tests/test_review_semantics.py` pass and every other semantics test still passes.

### R-08: INDEX 0, and number-to-text

**Fix:**
- `INDEX` with row or column 0 in a single-cell formula returns `#VALUE!`.
- Convert very large and very small numbers to text the way Excel does: `1E+20&""` gives "1E+20" and `1E-20&""` gives "1E-20".
- LibreOffice writes "1E+020". Either compare scientific-notation strings with the same value as equal, or list the case as a known difference.

**Done when:** `test_transpiler_bug[index_row_zero]` passes and the new cases are tested.

### R-27: named ranges

**Fix:**
- Resolve workbook-scoped defined names that point at one cell or a rectangular range on one sheet. That means dependencies, the emitter, thresholds, and rule text, which should use the name as its label.
- Dynamic names (OFFSET or INDIRECT based) stay "not converted".

**Done when:** `=Bulk*2` matches the Referee, and `B2>=Bulk` records a threshold with the named cell's value.

### R-24: where LibreOffice differs from Excel

**Fix:**
- Add a "Where LibreOffice differs from Excel" table to `.kiro/steering/excel-semantics.md` covering `0^0`, `(-8)^(1/3)`, `MATCH("2",numbers,0)`, `MATCH(TRUE,numbers,0)`, `TRUE>1`, `SUM("5",1)` and `TRUE&""`.
- Add Referee fidelity tests that pin current LibreOffice behaviour, so an upgrade is noticed.
- Note that the live site runs 7.4.7.2 and local development runs 26.8.3.
- Upgrading LibreOffice in the image is optional, and only if the Docker build and the full suite pass.

### R-25: ROUND with more than 15 significant digits

**Fix:** don't change behaviour until I confirm Excel's result for `=ROUND(123456789012345.67,1)` in Excel for the web. Document it as unverified.

---

## Phase 6: Power, routing, report and UI polish

### R-15: Power packaging

**Fix:**
- Add `"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"` to `plugin/plugin.json`.
- Remove `toolPrefix` from `plugin/mcp.json`; Kiro namespaces Power servers itself. Update `tests/test_plugin_package.py` to match.
- Use a launch command that works on a Mac with no `python` command, for example `python3`, or a `ghost-mcp` console script run with `uvx`.
- Document the prerequisites (LibreOffice and Ghost's Python dependencies) in a setup section of the skills and in the README.
- Leave me a checklist for installing the Power from the GitHub URL after I push.

**Done when:** `test_plugin_manifest_has_schema` passes.

### R-16: atx dry-run command

**Fix:**
- Add `-t` next to `-x`; the AWS Transform CLI reference says `-t` is required with `-x`.
- Explain that the transformation definition must be created first (check with `atx custom def list`).
- Stop calling the command "exact".
- Use `python3 -m py_compile **/*.py` as the build command, or justify the current one.

**Done when:** `test_atx_dry_run_includes_trust_all_tools_with_non_interactive` passes.

### R-21 (rest): report details

**Fix:**
- Rename the "Exact hits" column, which actually shows change points, and add the real exact hits from Phase 2.
- List each input's tested domain.
- When both modes ran, make the Faithful report downloadable too, for example with `report.html?mode=faithful`.

### R-22 and R-23: UI text and accessibility

**Fix:**
- Change the text at `web/templates/_autopsy.html:66` to "Unanswered findings keep the original behaviour and are listed in the report."
- Dark theme `--border`: use a colour with at least 3:1 contrast; `#7a6d94` gives 3.96:1 on the background and 3.65:1 on the surface.
- Keep the theme toggle's label constant (for example "Light mode") and let `aria-pressed` carry the state.

---

## Phase 7: the tests the requirements promise (R-20)

- **Golden semantics tests** built from `samples/make_traps.py`, marked `@pytest.mark.golden`. Check each in-scope row of the Excel semantics table against both the Referee and the generated code. These are what the R-29 hook runs.
- **Excel-saved fixtures:** a `tests/fixtures/excel-saved/` folder with a README explaining how to make the files in Excel for the web, plus a sanity-check test that skips with a message naming the folder when it's empty. Never fake a result.
- **Formula fuzzing:** a property-based test that draws formulas from a Hypothesis grammar of the P0 subset (small depth, small values, R-24 differences excluded), compares the Referee with the transpiled code, and shrinks failures to the smallest formula.
- **CLI end-to-end:** run `scripts/demo.sh` into a temp folder and check its outputs.
- **Performance:** 500 cases in under 60 seconds, marked slow.

---

## Before you tell me you're done

1. The full suite passes, and no `xfail` marker is left in `tests/test_review_*.py`, unless that finding is marked deferred, with a reason, in the Resolution table.
2. `scripts/demo.sh`:
   - discount passes;
   - haunted raises F-001 and passes Faithful;
   - haunted with D-001 passes Intended over about 300 cases, with one expected difference whose minimal case is quantity = 50.
3. A local web check (FastAPI TestClient): each bundled sample with the default checkboxes passes, and the haunted sample with D-001 passes Intended.
4. A short summary for me:
   - what changed for each finding;
   - the tests added or updated;
   - anything deferred, and why;
   - the deploy command for me to run.
