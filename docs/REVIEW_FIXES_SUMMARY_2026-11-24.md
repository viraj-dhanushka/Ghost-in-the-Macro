# Review fixes summary, 2026-11-24

All changes are uncommitted. Nothing was pushed, deployed or run against AWS.

## Final checks

1. **Full suite:** `415 passed, 2 skipped, 0 xfailed` (209 s). No `xfail(strict=True)` marker is left in `tests/test_review_*.py`. The only `xfail` code is the conditional in `test_review_semantics.py::test_transpiler_bug`, and every case there is in `FIXED`. The 2 skips are `tests/test_excel_saved_fixtures.py`, because `tests/fixtures/excel-saved/` holds no real Excel-saved file yet.
2. **`scripts/demo.sh /tmp/demo-final`** (exit 0):
   - discount: Faithful PASS (300 generated + 6 targeted, 195 distinct).
   - haunted: F-001 raised (`>=` at B7, `>` at B9). Faithful PASS (300 + 9 targeted, 198 distinct, 0 mismatches).
   - haunted with D-001: Intended PASS, 300 generated cases, one mismatch classed "expected by decision" (F-001 / D-001), minimal case quantity=50 (referee 6.0, actual 0), explaining 26 distinct cases.
   - The three `proof-report.json` files report `passed: true`.
3. **Web check (FastAPI TestClient).** I did not write a throwaway script, because existing tests cover it and they passed in the full run:
   - `tests/test_web_samples.py::test_bundled_sample_passes_faithful_with_default_inputs` is parametrised over every bundled sample. It posts `/sample/{id}`, reads the boxes the autopsy page pre-checks, posts `/verify` with exactly those boxes, then asserts `mode == "faithful"` and `passed is True`.
   - `tests/test_web_flow.py::test_haunted_end_to_end_through_web` records D-001 and verifies with B2, B3, B4 → B11. It asserts `passed is True`, `mode == "intended"` and mutation kills > 0. Those inputs equal the autopsy defaults, which `tests/test_product_samples.py::test_autopsy_defaults_equal_demo_inputs_and_outputs` asserts.
   - That flow test asserts a pass but not the number of expected differences. The one-difference-at-quantity=50 check is in the CLI run above and in `tests/test_demo_invariants.py`.

## Per finding

| ID | What changed |
|---|---|
| R-01 | Intended mismatch is "expected by decision" only if the transpiled Faithful module matches the Referee, the module differs from Faithful, and the Decision's patched comparison differs (trace hook). Otherwise it is a translation bug. The run continues past expected mismatches (CLI, web, MCP). |
| R-02 | Faithful "original workbook inconsistency" label only when comparisons at the Finding's locations disagree on that case. Otherwise translation bug. |
| R-03 | One shared type inference (`ghost/converter/typeinfer.py`): data validation first, then sample value. Used by mapping and verifier. |
| R-04 | Condition-flip probing (`ghost/verifier/flip.py`) on calculated cells and expressions. Cases go to verification and mutation, and are reported as boundaries. |
| R-05 | Table blocks and INDEX/MATCH text are PARAMETER. `_inp("")` means an empty cell. Demo defaults equal autopsy defaults. |
| R-06 | Survivors read "no difference found on N distinct cases" with tested domains. The ROUND-digit ±1 mutants on haunted `B9` are now killed. |
| R-07 | Comparisons normalise both sides to 15 significant digits. |
| R-08 | INDEX row/column 0 on a multi-cell range gives `#VALUE!`. Large and small numbers become scientific-notation text. `1E+20` equals the Referee's `1E+020`. |
| R-09 | Findings use truth sets over {below, at, above}. Complementary operators are no longer a Finding. |
| R-10 | Thresholds resolve constants only from non-INPUT cells. `50%` is 0.5. Expression thresholds are recorded. Input current values are no longer thresholds. |
| R-11 | A constant compared with a numeric literal stays an INPUT unless labelled as a rate. |
| R-12 | `Calculator!E5` is a PARAMETER. |
| R-13 | VBA is detected from `xl/vbaProject.bin` whatever the extension, statically via olevba. A new generated `samples/make_xlsm.py` replaces the test-bench path. Unreadable VBA shows "not checked". |
| R-14 | `record` rejects a second Decision for the same finding or rule, naming the existing ID. CLI and MCP also validate the patch at record time. |
| R-15 | `plugin.json` has `$schema` and validates against it. `toolPrefix` is removed. Launch is `uvx --from git+... ghost-mcp` (new console script). Prerequisites are documented. |
| R-16 | atx dry-run adds `-t` next to `-x`, says the transformation definition must exist (`atx custom def list`), is no longer called "exact", and uses a `compileall` build command. |
| R-17 | `MAX_CELLS = 200_000` is counted in the defusedxml pre-scan. A 250,000-cell workbook is rejected in about 0.6 s. Analysis is cached per session. Subprocess parsing was not added. |
| R-18 | One queued-or-running job per session (429 with message). Jobs and artifacts are removed at session delete and sweep. |
| R-19 | README written and updated at the end of Phase 7. |
| R-20 | Added golden semantics tests (26, `-m golden`), the Excel-saved fixtures folder with README and skip test, formula fuzzing (Property 9, no mismatches found), CLI end-to-end test, and a slow performance test (500 cases in 3.7 s). |
| R-21 | No absolute server paths in job events. Boundary table split into "Change-point bracket" and real "Exact hits". Tested domains are in the report. `report.html?mode=faithful` is downloadable. |
| R-22 | Autopsy text now says "Unanswered findings keep the original behaviour and are listed in the report." |
| R-23 | Dark `--border` is `#7a6d94` (3.96:1 and 3.65:1). The toggle label is constant "Light mode" with `aria-pressed`. |
| R-24 | "Where LibreOffice differs from Excel" table added, with Referee fidelity tests. Local 26.8.3.1 and image 7.4.7.2 gave identical results. Image not upgraded. |
| R-25 | Deferred. Behaviour unchanged and documented. Referee gives `123456789012345.7`; Ghost's `xl_round` gives `123456789012346.0`. |
| R-26 | Text-producing formulas are typed `string` in `mapping.yaml`. |
| R-27 | Workbook-scoped names for one cell or one rectangle resolve everywhere, and rule text uses the name. Dynamic, sheet-scoped, multi-area and external names stay "not converted". |
| R-28 | Optional report fields `cases_generated`, `cases_targeted`, `distinct_cases`. The schema stays `proof-report-1`. HTML, CLI, MCP and web show e.g. "300 generated + 9 targeted, 198 distinct". |
| R-29 | The four hooks call the venv Python through `scripts/ghost-py` and `scripts/ghost_hook.py`. They were run by hand with real output. The golden hook now selects 26 tests. |
| R-30 | Found during the work: `INDEX(...,0)` on a single-cell range returned `#REF!` where the Referee gives the cell value. Fixed. |
| MCP 12.11 | `evaluate_original` with a non-scalar input returns `invalid_argument` naming `inputs.<cell>`. |

## Tests added or updated

New files (all under `tests/` unless noted):
- Proof strength and classification: `test_review_proof_strength.py`, `test_review_classification_soundness.py`, `test_property_intended_classification.py`, `unit/test_mcp_verify_intended.py`, `test_case_key.py`, `unit/test_case_counts.py`.
- Autopsy and decisions: `test_review_autopsy_and_packaging.py`, `test_property_operator_consistency.py`, `test_property_type_inference.py`, `test_property_decision_uniqueness.py`, `test_decision_patch_validation.py`, `unit/test_mapping_text_outputs.py`.
- Samples and VBA: `test_sample_xlsm.py`, `test_vba_unreadable.py`, `test_empty_text_input.py`, `test_demo_invariants.py`, `test_cli_end_to_end.py`.
- Semantics: `test_review_semantics.py`, `test_property_comparison_normalisation.py`, `test_referee_libreoffice_differences.py`, `test_named_ranges.py`, `test_property_formula_fuzzing.py`, `tests/golden/`, `test_generated_module_standalone.py`.
- Flip probing and reports: `test_flip_reporting.py`, `test_report_details.py`, `test_mutation_wording.py`.
- Web: `test_web_samples.py`, `test_web_analysis_cache.py`, `test_web_session_end_jobs.py`, `test_web_no_server_paths.py`, `test_web_autopsy_text.py`, `test_web_accessibility.py`.
- Fixtures: `test_excel_saved_fixtures.py` plus `tests/fixtures/excel-saved/README.md`.

Existing files with added tests: `test_verifier_classify.py`, `test_web_flow.py`, `test_web_jobs.py`, `unit/test_mcp_server.py`, `unit/test_router_explain.py`, `test_product_samples.py`.

## Test edits that removed or changed assertions

`git diff tests/` shows these removed lines. All other changed test files only add lines.
- **`tests/test_plugin_package.py`:** `test_mcp_json_uses_ghost_prefix_and_real_module` asserted `toolPrefix` starts with `ghost_` and `args == ["-m", "mcp_server.server"]`. Both are gone. The replacement test asserts documented fields only, no `toolPrefix`, `command == "uvx"`, last arg `ghost-mcp`, and that `pyproject.toml` defines `ghost-mcp = mcp_server.server:main`.
- **`tests/test_decisions_store.py`:** two fixtures recorded the same finding twice to test ID assignment. They now use F-001 and F-002. No assertion changed.
- **`tests/test_web_jobs.py::test_concurrency_limit_and_queue_position`:** the three submits used one session. They now use sessions `s1`, `s2`, `s3`, because one session may hold only one active job (R-18). Assertions are unchanged.
- **`tests/test_product_samples.py`:** the role override (scenario-table inputs demoted to PARAMETER by fill colour) is removed. The test now uses the autopsy defaults, which is stricter. A new test asserts the defaults equal the demo's inputs and outputs.
- **Comparison-normalisation property test:** the "beyond the 15th digit" mantissa strategy now starts at `10**14 + 1`. Below that, `10**14 - 0.06` normalises to a different 15-digit value, so the property did not hold. Assertions are unchanged. This is the "fuzz strategy lower bound" edit.
- **Strict xfail markers removed** from the `test_review_*` tests and `test_property_*` modules as each fix landed, as the rules allow. `test_review_*.py` are untracked, so `git diff` cannot show them.

## Deferred or owner checks

- **R-25:** awaiting your Excel check of `=ROUND(123456789012345.67,1)` in Excel for the web.
- **R-20:** create real Excel-saved fixtures in `tests/fixtures/excel-saved/` (README explains how). Until then reports say "not cross-checked against Excel" and 2 tests skip.
- **R-29:** trigger the four hooks in Kiro and fill in the result table in `docs/KIRO_USAGE.md`.
- **R-15:** after you push, install the Power from the GitHub URL (checklist in `docs/KIRO_USAGE.md`).
- **Not checked:** Excel's result for the R-24 differences, the R-08 scientific-notation switch points and R-30 single-cell INDEX (all measured on LibreOffice only), and a real screen reader or browser for R-23.
- **Not done:** parsing uploads in a memory-limited subprocess (R-17 said "consider"). The cell cap plus the cache is in place.

## Deploy

Run `scripts/deploy_ecs_express.sh` yourself. Use `--dry-run` first to see the commands. The script rebuilds and pushes the image. `GHOST_SESSION_SECRET` is kept as it is unless you set it in your shell, in which case the environment is replaced (secret rotation).
