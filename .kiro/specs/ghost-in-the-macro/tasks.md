# Implementation Plan: Ghost in the Macro

## Overview

Implementation language: Python 3.11+ (design uses Python throughout). Build order follows the demo-first rule: repo setup and steering, ingestion, referee (ported from the prototype findings, since `reference/testbench/` is not in this workspace), sample workbooks, autopsy and rules, converter, verifier with boundary probing, proof report, then **DEMO CHECKPOINT 1 (CLI end-to-end on samples a and b)**, then Power and MCP server, web app, Docker deployment, **DEMO CHECKPOINT 2 (public URL)**, then mutation self-check, routing, VBA and TypeScript export.

Legend: **[P0]** must ship, **[P1]** should ship, **[P2]** nice to have, **[STRETCH]** droppable without harming the demo, **[PBT]** property-based test (Hypothesis). Tasks marked `*` are optional test sub-tasks.

Note on order: the formula parser (6.1) is built early because threshold extraction (5.2) and the dependency graph property tests need the AST.

## Day Plan (10 working days, last day reserved)

Dates are indicative; Day 10 is Thu 3 Dec 2026. Submissions close Fri 4 Dec 2026 2:00 PM PT.

| Day | Date | Focus | Tasks |
|---|---|---|---|
| 1 | Fri 20 Nov | Repo, steering, hooks, ingestion | 1.x, 2.1 to 2.4 |
| 2 | Mon 23 Nov | Referee port, sample workbooks | 3.1 to 3.4, 4.1 to 4.4 |
| 3 | Tue 24 Nov | Autopsy, findings, rules, decisions | 5.x, 6.1 |
| 4 | Wed 25 Nov | Converter and Excel semantics | 6.2 to 6.6, golden tests |
| 5 | Thu 26 Nov | Verifier, boundary probing, proof report; **DEMO CHECKPOINT 1** | 7.x, 8.x, 9.x |
| 6 | Fri 27 Nov | MCP server, Power, web app skeleton and job runner | 11.x, 12.1, 12.2 |
| 7 | Mon 30 Nov | Web app UI and theme, Docker, **DEMO CHECKPOINT 2** (public URL) | 12.3, 12.4, 13.x |
| 8 | Tue 1 Dec | Mutation self-check, routing (P1) | 15.x, 16.x |
| 9 | Wed 2 Dec | VBA and TypeScript if on schedule [STRETCH]; bug fixing; PBT tasks backlog | 17.x, 18.x |
| 10 | Thu 3 Dec | README, `docs/KIRO_USAGE.md`, demo video, submission (no feature work) | 19.x |

Cut line if behind: drop 18.x first, then 17.x, then 16.x, then 15.x. Never drop checkpoints 1 and 2.

## Tasks

- [x] 1. Repo setup and steering [P0]
  - [x] 1.1 Scaffold project, licence and CI [P0]
    - Create `pyproject.toml` (package `ghost`, deps: openpyxl, oletools, defusedxml, hypothesis, pydantic, pyyaml, jsonschema, fastapi, uvicorn, jinja2, mcp, pytest, httpx), `ghost/` package layout from the design, `tests/` skeleton, MIT `LICENSE`, `.gitignore` that does NOT list `.kiro/`
    - Add `.github/workflows/ci.yml` on Ubuntu installing `libreoffice-calc-nogui` and `libreoffice-script-provider-python`, creating a venv and running `pytest`
    - _Requirements: 20.10, 21.5, 21.6_

  - [x] 1.2 Write steering files [P0]
    - Create `.kiro/steering/product.md`, `tech.md`, `structure.md`, `ghost-guardrails.md`, `excel-semantics.md` (the Excel_Semantics_Table), `routing-thresholds.md` (fenced YAML thresholds)
    - _Requirements: 21.1, 15.1, 16.5_

  - [x] 1.3 Add Kiro hooks [P0]
    - Add `.kiro/hooks/` entries: re-run verification when generated logic files or `mapping.yaml` are saved; autopsy when a workbook is added to `/graveyard`; golden semantics tests when `converter/` changes; regenerate proof report when `decisions.yaml` changes
    - Create `graveyard/` with a `.gitkeep`
    - _Requirements: 21.2_

  - [x] 1.4 Create docs log and optional custom agents [P1]
    - Create `docs/KIRO_USAGE.md` with the running-log template and first entries (spec creation)
    - Add optional agent definitions Coroner, Medium, Skeptic, Clerk under `.kiro/agents/` [STRETCH]
    - _Requirements: 21.3, 21.4_

- [x] 2. Core ingestion [P0]
  - [x] 2.1 Define core data models [P0]
    - Implement dataclasses and pydantic models for Workbook, Cell, Threshold, Finding, Rule, Mapping, Case, Mismatch, Decision, Mutant, Report, Route in `ghost/models.py`
    - _Requirements: 1.1, 2.7, 3.1, 4.1, 8.10, 9.3, 10.3, 16.1_

  - [x] 2.2 Implement workbook loader with safety limits [P0]
    - Implement `load_workbook` in `ghost/ingest/workbook.py` and `limits.py`: extension check for `.xlsx`/`.xlsm`, 5 MB limit, 20,000-formula limit, processing timeout, defusedxml, formulas plus `data_only=True` saved values, named ranges, cross-sheet refs, dependency graph
    - Raise `UnsupportedFormat`, `TooLarge`, `TooManyFormulas`, `ProcessingTimeout`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.8, 1.9, 1.10, 1.11_

  - [x] 2.3 Implement VBA extraction [P0]
    - Implement `ghost/ingest/vba.py` using oletools/olevba, static only, returning module name, source and line count
    - _Requirements: 1.5_

  - [x] 2.4 Implement feature scanner [P0]
    - Flag volatile functions as "not verifiable as-is", external links, data tables, array and dynamic formulas, unsupported functions, each with cell reference
    - _Requirements: 1.6, 1.7_

  - [ ]* 2.5 [PBT] Write property tests for ingestion
    - **Property 1: Ingestion read-back**
    - **Property 2: Non-workbook inputs are rejected**
    - **Property 3: Dependency graph equals references**
    - **Property 4: Volatile functions are always flagged**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.6**

  - [ ]* 2.6 Write unit tests for limits and safety
    - Test 5 MB and 20,000-formula boundaries (limit and limit+1), billion-laughs XML fixture rejected, timeout with patched clock, olevba never executes macros
    - _Requirements: 1.5, 1.8, 1.9, 1.10, 1.11_

- [x] 3. Referee (port from prototype findings) [P0]
  - [x] 3.1 Implement soffice locator and LO profile builder [P0]
    - `ghost/referee/locate.py`: search `GHOST_SOFFICE`, `~/Applications/LibreOffice.app`, `/Applications/LibreOffice.app`, Linux paths; error naming searched paths and required apt packages
    - `ghost/referee/profile.py`: temp user profile, copy script to `user/Scripts/python/`, write `registrymodifications.xcu` (VBA Load, Executable, Save true; UpdateDocMode NO_UPDATE; MacroExecutionMode NEVER_EXECUTE default)
    - _Requirements: 5.1, 5.4, 5.5, 5.10, 1.12_

  - [x] 3.2 Implement the referee script running inside LibreOffice [P0]
    - `ghost/referee/script/ghost_referee.py` exposing `serve`: connect to 127.0.0.1 on the given port, line-delimited JSON commands `open`, `eval`, `read`, `macros`, `run_macro`, `save_with_vba`, `quit`; always `calculateAll()`; value encoding number/string/null/`{"error": ...}`
    - Macro mode NEVER_EXECUTE unless `run_macros` true; refuse `run_macro` otherwise
    - `save_with_vba` applies VBACompatibilityMode, ProjectName "VBAProject", library VBAProject, ModuleInfo NORMAL, filter "Calc MS Excel 2007 VBA XML"
    - _Requirements: 5.3, 5.6, 5.7, 5.8, 5.11, 5.12, 5.13, 5.15_

  - [x] 3.3 Implement `RefereeClient` [P0]
    - `ghost/referee/client.py`: context manager, listening socket on port 0, launch `soffice --headless` with macro URL `vnd.sun.star.script:ghost_referee.py$serve?language=Python&location=user`, work on a copy of the upload, per-command timeout, liveness watchdog, kill process group on failure, `run_macros` rejected for non-trusted sources
    - _Requirements: 5.2, 5.9, 5.14, 5.16_

  - [x] 3.4 Implement the Excel sanity check [P0]
    - `ghost/referee/sanity.py`: compare Referee values with Excel-saved values for every formula cell; report matched/total; "not cross-checked against Excel" when no saved values; list differing cells
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 3.5 Write referee fidelity tests
    - Hand-calculated values, VBA Round probe (needs sample d later; skip until then), macros-off default (`#MACRO?`), `run_macro` refused, Excel-saved check against `tests/fixtures/excel-saved/` skipped with a clear message if missing, never faked
    - _Requirements: 5.11, 5.13, 20.2, 20.3_

  - [ ]* 3.6 [PBT] Write property tests for referee and sanity check
    - **Property 14: Referee leaves upload untouched**
    - **Property 15: Excel sanity comparison**
    - **Validates: Requirements 5.9, 6.1, 6.2, 6.3, 6.4**

- [x] 4. Sample workbooks (generated by committed scripts, labelled generated) [P0]
  - [x] 4.1 Sample (a) discount calculator [P0]
    - `samples/make_discount.py`: inputs quantity, unit price, distance; 10% bulk discount at 50+, delivery 5.00 up to 10 km plus 0.40/km beyond, free at 50+, 20% VAT, ROUND; Tests sheet of 200 fixed rows; "generated" label; no Excel-saved values
    - _Requirements: 19.1, 19.2_

  - [x] 4.2 Sample (b) haunted discount calculator [P0]
    - `samples/make_haunted.py`: free delivery uses `>50`, discount uses `>=50`
    - _Requirements: 19.1, 19.3_

  - [x] 4.3 Sample (c) multi-scenario model [P0]
    - `samples/make_scenarios.py`: 4 inputs, 10 scenarios, best via MAX plus INDEX/MATCH, P0 subset only
    - _Requirements: 19.1, 19.4_

  - [x] 4.4 Sample (e) Traps workbook [P0]
    - `samples/make_traps.py`: one row per Excel_Semantics_Table entry (ROUND, MOD negatives, empty cells, booleans, case-insensitive compare, floating noise)
    - _Requirements: 19.1, 19.6, 15.1, 15.2, 15.5, 15.7, 15.8, 15.9_

- [x] 5. Autopsy, rules and decisions [P0]
  - [x] 5.1 Implement cell classification [P0]
    - `ghost/autopsy/classify.py`: INPUT/OUTPUT/INTERMEDIATE/PARAMETER with fill colour, data validation and left-label scoring, user-selected outputs
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 5.2 Implement threshold extraction [P0]
    - `ghost/autopsy/thresholds.py` from formula ASTs and VBA comparisons, recording cell, operator, constant and source location
    - _Requirements: 2.7_

  - [x] 5.3 Implement inconsistency detector and metrics [P0]
    - `ghost/autopsy/findings.py` (F-NNN ids, same cell and constant with different operators) and `metrics.py` (formula, VBA lines, modules, UserForms, Declares, external links, volatile, unsupported, calculator shape)
    - _Requirements: 2.8, 2.9_

  - [x] 5.4 Implement rules generator [P0]
    - `ghost/rules/ears.py`, `ids.py`: EARS templates (IF to WHEN/OTHERWISE, ROUND, lookups, labels with cell-ref fallback), stable `rule_id`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 5.5 Implement migration spec writer [P0]
    - `ghost/rules/spec_writer.py`: write `rules.md`, `traceability.yaml`, `findings.yaml` under `.kiro/specs/<migration>/`
    - _Requirements: 3.8, 3.9_

  - [x] 5.6 Implement decisions store [P0]
    - `ghost/decisions/store.py`: validate required fields, assign D-NNN, write `decisions.yaml`, update decision summary in migration `design.md`, machine-applicable `patch` field
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [ ]* 5.7 [PBT] Write property tests for autopsy
    - **Property 5: Cell role partition**
    - **Property 6: Threshold extraction completeness**
    - **Property 7: Inconsistency findings**
    - **Validates: Requirements 2.1, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

  - [ ]* 5.8 [PBT] Write property tests for rules
    - **Property 8: Rule text patterns**
    - **Property 9: Rule determinism and stable identifiers**
    - **Property 10: Traceability completeness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**

  - [ ]* 5.9 [PBT] Write property tests for decisions and spec round trips
    - **Property 11: Spec file round trip**
    - **Property 12: Incomplete decisions are rejected**
    - **Validates: Requirements 4.1, 4.2, 4.5, 7.10**

- [x] 6. Converter [P0]
  - [x] 6.1 Implement formula tokenizer, parser and AST [P0]
    - `ghost/converter/parser.py`, `ast.py`: P0 grammar (operators `+ - * / ^ &`, unary minus, comparisons, percent, function calls, ranges, named ranges, cross-sheet refs)
    - _Requirements: 7.2, 7.4_

  - [x] 6.2 Implement Excel runtime semantics [P0]
    - `ghost/runtime/excel.py`: Decimal conversion via `Decimal(repr(x))`, `xl_round` (15 significant digits, half away from zero), ROUNDUP/ROUNDDOWN, INT, worksheet MOD, empty/boolean/text coercion, case-insensitive compare, Excel error values; vendored into generated module folder
    - _Requirements: 7.5, 7.6, 15.1, 15.2, 15.5, 15.7, 15.8, 15.9_

  - [x] 6.3 Implement Python emitter (Faithful mode) [P0]
    - `ghost/converter/emit_python.py`: generate `compute(inputs) -> dict` for the P0 function set, deterministic output, condition trace hooks for coverage
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 7.11_

  - [x] 6.4 Implement subset check and "not converted" listing [P0]
    - `ghost/converter/subset.py`: list unsupported cells with reason, emit no code for them, dependent outputs flagged
    - _Requirements: 7.7_

  - [x] 6.5 Generate `mapping.yaml` [P0]
    - Map input and output names to cell refs, with inferred types and ranges
    - _Requirements: 7.10, 8.3_

  - [x] 6.6 Implement Intended mode [P0]
    - Apply Decision patches on the AST before emission; with no decisions output equals Faithful
    - _Requirements: 4.4, 7.9_

  - [ ]* 6.7 [PBT] Write property tests for converter determinism and subset
    - **Property 17: Unsupported constructs are never guessed**
    - **Property 18: Decimal conversion and emit determinism**
    - **Validates: Requirements 7.5, 7.7, 7.11**

  - [ ]* 6.8 [PBT] Write property tests for Excel semantics against the referee
    - **Property 19: Excel rounding semantics**
    - **Property 20: Excel arithmetic coercion and comparison**
    - **Property 21: Worksheet MOD sign**
    - **Validates: Requirements 7.6, 15.1, 15.2, 15.5, 15.7, 15.8, 15.9**

  - [ ]* 6.9 [PBT] Write formula fuzzing property tests
    - **Property 13: No decision means no behaviour change**
    - **Property 16: Faithful conversion matches the referee**
    - Hypothesis grammar of the P0 subset; compare Referee and generated code, shrink to the smallest formula
    - **Validates: Requirements 4.4, 7.1, 7.2, 7.3, 7.4, 7.8, 7.9, 8.1**

  - [ ]* 6.10 Write golden semantics tests
    - Table-driven test of every Excel_Semantics_Table row (excluding VBA and date rows until implemented) against both Referee and generated code using sample (e)
    - _Requirements: 15.12, 20.4_

- [x] 7. Verifier with boundary probing [P0]
  - [x] 7.1 Implement value comparison [P0]
    - `ghost/verifier/compare.py`: abs tolerance 1e-6, exact strings, errors by type
    - _Requirements: 8.5, 15.10_

  - [x] 7.2 Implement input strategies and type inference [P0]
    - `ghost/verifier/strategies.py`: threshold-weighted generation (t-1, t, t+1, t±0.1), zero, negatives where allowed, large, decimals; type and range inference with user overrides
    - _Requirements: 8.2, 8.3_

  - [x] 7.3 Implement boundary probing [P0]
    - `ghost/verifier/boundary.py`: binary search on one numeric input for each threshold on a calculated cell; report exact hits (for example 1 × 411.67 and 7 × 58.81 reaching 500.00)
    - _Requirements: 8.4_

  - [x] 7.4 Implement verification run [P0]
    - `ghost/verifier/run.py`: Hypothesis run with explicit seed, batched Referee evals, progress callback, shrinking to minimal counterexamples
    - _Requirements: 8.1, 8.6, 8.7_

  - [x] 7.5 Implement rule coverage [P0]
    - `ghost/verifier/coverage.py`: observe each condition true and false, targeted generation for gaps, report uncovered
    - _Requirements: 8.8, 8.9_

  - [x] 7.6 Implement mismatch classification and verdict [P0]
    - `ghost/verifier/classify.py`: rule_id and cell linking, Mismatch_Class, pass/fail per mode
    - _Requirements: 8.10, 8.11, 8.12, 8.13, 8.14_

  - [ ]* 7.7 [PBT] Write property tests for compare and strategies
    - **Property 22: Tolerance comparison**
    - **Property 23: Input generation reaches thresholds**
    - **Validates: Requirements 8.2, 8.3, 8.5, 15.10**

  - [ ]* 7.8 [PBT] Write property tests for boundary probing, shrinking and seed
    - **Property 24: Boundary probing finds the exact change point**
    - **Property 25: Shrinking preserves failure**
    - **Property 26: Seed reproducibility**
    - **Validates: Requirements 8.4, 8.6, 8.7**

  - [ ]* 7.9 [PBT] Write property tests for coverage and classification
    - **Property 27: Rule coverage accounting**
    - **Property 28: Mismatch classification and verdict**
    - **Validates: Requirements 8.8, 8.9, 8.10, 8.11, 8.12, 8.13, 8.14**

  - [x] 7.10 Write product tests on samples [P0] [PBT]
    - Clean samples (a) and (c) zero Mismatches over at least 300 Cases in Faithful mode
    - Haunted (b): autopsy raises F-001; Faithful mode passes; with D-001 Intended mode shows one expected-difference class with minimal counterexample quantity=50
    - Boundary probing lands exactly on 500.00 for the Gold threshold fixture
    - _Requirements: 8.15, 19.7, 19.8, 20.5_

- [x] 8. Proof report [P0]
  - [x] 8.1 Define report model and JSON schema [P0]
    - `ghost/report/model.py` and `ghost/report/schema/proof-report-1.json`; "not checked" for absent checks; versions of LibreOffice, Python and Ghost; seed
    - _Requirements: 10.2, 10.3, 10.4, 10.5_

  - [x] 8.2 Implement HTML renderer and regeneration [P0]
    - `ghost/report/html.py`; JSON validated against schema before writing; regenerate when `decisions.yaml` changes
    - _Requirements: 10.1, 10.6_

  - [ ]* 8.3 [PBT] Write property test for report integrity
    - **Property 30: Report integrity**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5**

- [x] 9. CLI and end-to-end demo script [P0]
  - [x] 9.1 Implement the CLI [P0]
    - `ghost/cli.py` commands `autopsy`, `rules`, `convert`, `verify`, `mutate`, `report`, `decide`, `route`, `demo`; `--trust-macros` for local files only; non-zero exit codes with cause; `mutate` and `route` print "not yet implemented" until tasks 15 and 16
    - _Requirements: 11.1, 11.2, 11.4_

  - [x] 9.2 Write the demo script for samples (a) and (b) [P0]
    - `scripts/demo.sh` and `ghost demo`: generate samples, autopsy, rules, record D-001, verify faithful and intended, write proof reports
    - _Requirements: 11.3, 19.7, 19.8_

  - [ ]* 9.3 Write CLI end-to-end tests
    - Run the demo script in a subprocess and assert reports exist and statuses are as expected
    - _Requirements: 11.3, 20.8_

  - [ ]* 9.4 Write performance test
    - Verify 500 Cases on sample (a) in under 60 seconds
    - _Requirements: 20.9_

- [x] 10. DEMO CHECKPOINT 1 - CLI end-to-end on samples (a) and (b)
  - Ensure all tests pass, ask the user if questions arise.
  - Confirm the demo script produces proof reports for samples (a) and (b) with the expected storyline (F-001, D-001, minimal case at exactly 50 units).

- [x] 11. Kiro Power and MCP server [P0]
  - [x] 11.1 Implement the MCP server [P0]
    - `mcp_server/server.py` over stdio exposing analyze_workbook, list_rules, get_dependencies, find_inconsistencies, extract_vba (read-only), evaluate_original, boundary_cases, check_against_excel_cache, verify_implementation, mutation_check, record_decision, generate_proof_report, recommend_route; pydantic argument validation with structured errors; `mutation_check` and `recommend_route` return "not available" until tasks 15 and 16
    - _Requirements: 12.3, 12.4, 12.5, 12.6, 12.11_

  - [x] 11.2 Package the Power [P0]
    - `plugin/plugin.json` (name "ghost-in-the-macro", keywords excel, xlsx, xlsm, vba, macro, spreadsheet, workbook migration), `plugin/mcp.json` with `ghost_` tool prefix, installable from the GitHub URL
    - _Requirements: 12.1, 12.2, 12.10_

  - [x] 11.3 Write the Power skills and guardrails [P0]
    - `plugin/skills/` for autopsy, write-rules-spec (creates `.kiro/specs/<migration>/`), implement-from-rules, verify-migration, record-decision, guardrails (no behaviour change without Decision; Decimal for money; Excel rounding per table; no macros from untrusted files; no invented data); mirror guardrails in repo steering
    - _Requirements: 12.7, 12.8, 12.9_

  - [ ]* 11.4 Write MCP and plugin tests
    - Tool list, extract_vba is read-only, invalid arguments return structured error, plugin.json keywords, tool-name prefix uniqueness
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.10, 12.11_

- [x] 12. Web application [P0]
  - [x] 12.1 Build FastAPI skeleton and session handling [P0]
    - `web/app.py`: upload endpoint with Ingestor validation errors shown, `POST /sample/{id}`, signed session cookie, per-session temp folder, idle-timeout sweeper, `/healthz`; macros flag never exposed
    - _Requirements: 13.9, 13.10, 13.12, 13.14, 14.5_

  - [x] 12.2 Implement the job runner [P0]
    - `web/jobs.py`: background jobs, one Referee per job, semaphore from `GHOST_MAX_JOBS`, queue position, progress events (polling endpoint plus SSE), Session_Folder deletion at job end or timeout
    - _Requirements: 13.4, 13.5, 13.6, 13.10_

  - [x] 12.3 Build the single-page flow [P0]
    - Jinja2 plus HTMX templates: upload or Try a sample, autopsy summary with findings and rules, confirm inputs and outputs, answer findings (records Decision), verification with live progress, proof report view, downloads (HTML, JSON, generated module), privacy note
    - _Requirements: 13.1, 13.2, 13.3, 13.11, 13.13_

  - [x] 12.4 Apply the haunted-lab theme and accessibility [P0]
    - CSS custom properties, dark and light modes with toggle, AA contrast, keyboard navigation, 360 px layout
    - _Requirements: 13.7, 13.8_

  - [ ]* 12.5 Write API tests
    - httpx tests for upload rejection, sample flow, decision recording, concurrency queueing, session deletion, macros never enabled for uploads
    - _Requirements: 13.2, 13.5, 13.6, 13.10, 13.12, 13.14, 20.8_

- [x] 13. Docker deployment [P0]
  - [x] 13.1 Write the Dockerfile [P0]
    - Debian slim, `libreoffice-calc-nogui`, `libreoffice-script-provider-python`, non-root user, health check, samples generated at build time
    - _Requirements: 14.1, 14.2, 14.3, 14.6_

  - [x] 13.2 Deploy to a public URL [P0]
    - Add `scripts/deploy_ecs_express.sh` and `docs/DEPLOY_ECS_EXPRESS.md` (Amazon ECS Express Mode, 1 vCPU / 2 GB, one pinned task, `GHOST_MAX_JOBS`); no secrets; health endpoint reports Referee availability
    - _Requirements: 14.4, 14.5, 14.6_

  - [ ]* 13.3 Write Playwright smoke test [P1]
    - Load page, try sample, run verification, see report link
    - _Requirements: 20.8_

- [x] 14. DEMO CHECKPOINT 2 - public URL
  - Ensure all tests pass, ask the user if questions arise.
  - Confirm the public URL runs the haunted sample flow end to end.

- [x] 15. Mutation self-check [P1]
  - [x] 15.1 Implement mutant generation [P1]
    - `ghost/mutation/mutants.py`: flip `>=`/`>`, constant ±1, rounding mode swap, drop IF branch
    - _Requirements: 9.1_

  - [x] 15.2 Run mutants and report score [P1]
    - `ghost/mutation/run.py`: verify each Mutant, score killed/total, survivor reasons; wire into CLI `mutate`, MCP `mutation_check`, report and web flow
    - _Requirements: 9.2, 9.3, 9.4, 10.3_

  - [ ]* 15.3 [PBT] Write property test for mutation accounting
    - **Property 29: Mutation score accounting**
    - **Validates: Requirements 9.1, 9.3, 9.4**

  - [x]* 15.4 Write mutation tests on samples
    - Gold `>` versus `>=` Mutant caught by boundary probing; half-even rounding Mutant caught at 235 × 0.03
    - _Requirements: 20.7_

- [x] 16. Migration routing [P1]
  - [x] 16.1 Implement the Router [P1]
    - `ghost/router/route.py`, `thresholds.py`: parse thresholds from `routing-thresholds.md`; Ghost converts, AWS Transform custom, Split
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [x] 16.2 Add dry-run command and design explanation [P1]
    - Output exact `atx custom def exec ...` string (never executed); write plain-English route explanation into migration `design.md`; wire into CLI `route` and MCP `recommend_route`; document hand-off to the official AWS Transform power in the skill
    - _Requirements: 16.6, 16.7, 16.8, 16.9_

  - [ ]* 16.3 [PBT] Write property test for routing
    - **Property 31: Routing is deterministic and total**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

- [ ] 17. VBA conversion [P2] [STRETCH]
  - [ ] 17.1 Sample (d) xlsm pair [P2] [STRETCH]
    - `samples/make_xlsm.py` using Referee `save_with_vba`: `=DeliveryFee(B2,B4)` function, button macro AwardPoints (whole tens of total, Gold from 500), haunted twin rounding total/10; labelled generated
    - _Requirements: 19.5, 5.15_

  - [ ] 17.2 Map VBA functions and subs to cells [P2] [STRETCH]
    - Call-site mapping and `ws.Range("B11").Value` mapping; VBA thresholds into autopsy
    - _Requirements: 17.1, 17.2_

  - [ ] 17.3 Convert simple VBA to Python [P2] [STRETCH]
    - Subset converter; VBA Round half-even, Int/Fix, Mod semantics; "not converted" for the rest; macro runs only for trusted sources
    - _Requirements: 17.3, 17.4, 17.5, 15.3, 15.4, 15.6_

  - [ ]* 17.4 Write VBA tests [P2] [STRETCH]
    - Referee VBA Round probe, golden rows for VBA semantics, haunted xlsm minimal counterexample total 6.00 (1 point vs 0)
    - _Requirements: 15.3, 15.4, 15.6, 20.5_

- [ ] 18. TypeScript export [P2] [STRETCH]
  - [ ] 18.1 Emit TypeScript module [P2] [STRETCH]
    - `ghost/converter/emit_ts.py` with decimal library and same semantics
    - _Requirements: 18.1_

  - [ ] 18.2 Verify TypeScript output [P2] [STRETCH]
    - Run the TS module through Node and compare with Referee via the Verifier
    - _Requirements: 18.2_

  - [ ]* 18.3 [PBT] Write TypeScript parity property test [P2] [STRETCH]
    - **Property 32: TypeScript parity**
    - **Validates: Requirements 18.1, 18.2**

- [ ] 19. Documentation and release [P0]
  - [ ] 19.1 Write the README [P0]
    - Setup (LibreOffice, venv), running locally, Docker, using the Power in Kiro, creating real-Excel fixtures with Excel for the web, safety, note that `reference/testbench/` was a feasibility spike before this spec
    - _Requirements: 21.7_

  - [ ] 19.2 Finalise `docs/KIRO_USAGE.md` [P0]
    - Complete the running log: spec workflow, steering, hooks, agents, Analyze Requirements usage, PBT usage
    - _Requirements: 21.4_

  - [ ] 19.3 Final checkpoint - Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.
    - The demo video (30 s on how Kiro built it) and the hackathon submission are manual steps done on Day 10 and are not coding tasks.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; the demo-critical product tests (7.10) are not optional.
- Each task references specific requirements for traceability.
- Property tests validate universal correctness properties; unit and example tests cover specifics.
- `reference/testbench/` is absent; the referee is re-implemented from the verified prototype findings in the requirements.
- Optional test tasks still appear in the dependency graph.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.2", "3.1", "4.1", "4.4", "6.1"] },
    { "id": 3, "tasks": ["2.3", "2.4", "3.2", "4.2", "4.3"] },
    { "id": 4, "tasks": ["2.5", "2.6", "3.3", "5.1", "5.2", "6.2"] },
    { "id": 5, "tasks": ["3.4", "3.5", "5.3", "5.4", "6.3", "6.4"] },
    { "id": 6, "tasks": ["3.6", "5.5", "5.6", "5.7", "6.5", "6.7", "6.8", "6.10", "7.1"] },
    { "id": 7, "tasks": ["5.8", "5.9", "6.6", "7.2", "7.3"] },
    { "id": 8, "tasks": ["6.9", "7.4", "7.5", "7.7"] },
    { "id": 9, "tasks": ["7.6", "7.8", "8.1"] },
    { "id": 10, "tasks": ["7.9", "7.10", "8.2", "8.3"] },
    { "id": 11, "tasks": ["9.1"] },
    { "id": 12, "tasks": ["9.2", "9.3", "9.4"] },
    { "id": 13, "tasks": ["11.1", "12.1"] },
    { "id": 14, "tasks": ["11.2", "12.2", "13.1", "15.1", "16.1"] },
    { "id": 15, "tasks": ["11.3", "11.4", "12.3", "15.2", "15.3"] },
    { "id": 16, "tasks": ["12.4", "12.5", "13.2", "15.4", "16.2", "16.3"] },
    { "id": 17, "tasks": ["13.3", "17.1"] },
    { "id": 18, "tasks": ["17.2"] },
    { "id": 19, "tasks": ["17.3"] },
    { "id": 20, "tasks": ["17.4", "18.1"] },
    { "id": 21, "tasks": ["18.2"] },
    { "id": 22, "tasks": ["18.3", "19.1", "19.2"] }
  ]
}
```
