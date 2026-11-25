# Kiro usage log

Running log of how Kiro is used in this repository. Add one entry per notable use. Newest entries go at the bottom.

## Entry template

```
### YYYY-MM-DD: <short title>
- Feature: spec | steering | hook | agent | power | vibe
- Goal: what I wanted
- What Kiro did: files created or changed
- Outcome: what worked, what needed correction
- Spec or task reference: e.g. tasks.md 2.1
```

## Entries

### Spec creation: ghost-in-the-macro
- Feature: spec
- Goal: turn the product idea into a requirements-first spec for the whole project.
- What Kiro did: created `.kiro/specs/ghost-in-the-macro/requirements.md`, `design.md` and `tasks.md` (P0 core engine, Kiro Power and web app; P1 mutation self-check and routing; P2 stretch VBA and TypeScript).
- Outcome: spec drives the task list that is executed task by task.
- Spec or task reference: `.kiro/specs/ghost-in-the-macro/`

### Steering files and repository setup
- Feature: steering
- Goal: give Kiro the product, technology, structure and guardrail context for every session.
- What Kiro did: workspace rules `product`, `tech`, `structure` and `ghost-guardrails` under `.kiro/steering/`.
- Outcome: generated code follows Decimal, determinism and "not converted" conventions.
- Spec or task reference: tasks.md 1.x

### 2026-11: Public deployment on ECS Express Mode (task 14)
- Feature: spec, hooks, agents
- Goal: put the web app at a public URL and check the demo flow end to end.
- What Kiro did: the first target was AWS App Runner, but it is closed to new customers, so the deployment moved to ECS Express Mode. App Runner files were deleted; `scripts/deploy_ecs_express.sh` and `docs/DEPLOY_ECS_EXPRESS.md` were added. The first deployed container could not start the Referee. Using `ldd` on LibreOffice's pyuno showed that the `python:3.11-slim` image's `/usr/local` libpython was loaded instead of the system one. The `Dockerfile` now uses `debian:bookworm-slim` with the app's Python venv kept off `PATH`, so LibreOffice uses the system Python.
- Verification on the live service: `/healthz` reports the Referee available; the haunted sample shows F-001; recording D-001 gives a Faithful run that passes (300 cases) and an Intended run with one expected difference at quantity=50; report.html, report.json and module.zip download. The web flow reports the mutation score as "not checked" because `web/flow.py` does not pass mutation cases.
- Kiro features used: the spec (`.kiro/specs/ghost-in-the-macro/`) defined and tracked the task; sub-agents (`.kiro/agents/`) were used for spec task execution; hooks in `.kiro/hooks/` (autopsy on graveyard add, regenerate report on decision, golden tests on converter save, reverify on logic save) are part of the repository workflow.
- Spec or task reference: tasks.md 14
### 2026-11-24: Fix R-12, Calculator!E5 is a PARAMETER (review-fixes task 3.2)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: stop the autopsy proposing and pre-checking "Free delivery within (km)" as an input.
- What Kiro did: in `ghost/autopsy/classify.py` added `allowance`, `within` and `free` to `_RATE_WORDS`, and a block rule (`_in_parameter_block`): an unfilled, unvalidated, labelled constant sandwiched between two rate-labelled constants is a PARAMETER. The block rule needs both neighbours so a lone input under a rate (`test_discount_shape`, `S!B4`) stays INPUT. Removed the strict xfail from `test_free_delivery_distance_is_a_parameter`; no other test changed.
- Verification: suite `201 passed, 19 xfailed`. `scripts/demo.sh` into a temp folder: haunted inputs (3) B2, B3, B4; F-001 raised; Faithful PASS 300 cases; Intended with D-001 PASS with one expected difference at quantity=50 (33 cases, as before R-01).
- Compatibility: the block rule never touches filled or validated cells, so R-05 (table blocks) and R-11 (compared constant is INPUT unless rate-labelled) can add their rules next to it.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.2

### 2026-11-24: Fix R-05, table blocks and INDEX/MATCH text are PARAMETER (review-fixes task 3.3)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: stop the autopsy pre-checking 53 inputs (scenario names and rates) for the "Scenario model" sample, so the web flow passes Faithful with the pre-checked boxes.
- What Kiro did: in `ghost/autopsy/classify.py` added `_table_block_cells` (a 4-connected group of unfilled, unvalidated constants spanning at least 3 columns and 3 rows is a table block, so its referenced cells are PARAMETER) and `_is_lookup_text` (an unmarked text constant read by a formula using INDEX/MATCH/LOOKUP is PARAMETER). Both sit next to the R-12 rate words and `_in_parameter_block`, which are unchanged. A two-column label/value list is not a table, so samples (a) and (b) are unaffected. Removed the strict xfail from `test_scenarios_sample_passes_with_default_inputs` and from the `scenarios` case in `tests/test_web_samples.py`. No assertion changed.
- Verification: suite `203 passed, 17 xfailed`. `scripts/demo.sh` into a temp folder: haunted inputs (3) B2, B3, B4 as before; F-001 raised; Faithful PASS 300 cases; Intended with D-001 PASS with one expected difference at quantity=50 (33 cases, as before R-01).
- Left for later: task 3.4 (`_inp("")` empty cell) and R-11 (a compared constant is INPUT unless rate-labelled; the new rules only touch table blocks and lookup text, so R-11 can add its own rule).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.3

### 2026-11-24: Fix R-05, `_inp("")` means an empty cell (review-fixes task 3.4)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: make generated code read a text input of `""` the way the Referee does. The Referee writes it with `setString("")`, which leaves an empty cell, so `INDEX` returns 0 and `A1+1` is 1.
- Choice: fixed the generated `_inp` and left the verifier's string strategy alone. The strategy keeps testing `""`, and the reader now agrees with the oracle. Generated code stays deterministic (one added line in the fixed header).
- What Kiro did: wrote `tests/test_empty_text_input.py` first (a workbook with `=INDEX(A1:A2,1)`, `=A1+1` and `=A1&"z"` on a text input, compared with the real Referee). It failed with generated code returning `''` for the `INDEX`. Then `_inp` in `ghost/converter/emit_python.py` returns `None` (empty cell) for `""`. No existing test changed.
- Verification: suite `205 passed, 17 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised; haunted Faithful PASS 300 cases; Intended with D-001 PASS with one expected difference at quantity=50 (33 cases, as before R-01); discount PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.4

### 2026-11-24: Fix R-05, demo and sample tests use the autopsy defaults (review-fixes task 3.5)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: make the demo and the product tests exercise the inputs and outputs the autopsy proposes, which is what the web app pre-checks.
- What Kiro did: compared the autopsy defaults for samples (a) and (b) with the demo's hard-coded `Calculator!B2,B3,B4` / `Calculator!B11`. They are identical, so `cmd_demo` in `ghost/cli.py` no longer passes `--inputs`/`--outputs`. In `tests/test_product_samples.py` the clean-sample test dropped its "fill means input" role override and uses `generate_mapping(wb)` defaults; no assertion changed. Added `test_autopsy_defaults_equal_demo_inputs_and_outputs` for samples (a) and (b).
- Verification: suite `207 passed, 17 xfailed`. `scripts/demo.sh` into a temp folder: 3 inputs B2, B3, B4 and output B11 for both samples; F-001 raised; Faithful PASS 300 cases; Intended with D-001 PASS with one expected difference at quantity=50 (33 cases).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.5
### 2026-11-24: Fix R-29, hooks use the repo venv (review-fixes task 3.7)
- Feature: agent hooks (`.kiro/hooks/*.json`), sub-agent for spec task execution
- Goal: the four hooks called system `python3`, which has no openpyxl here, so none could run.
- What Kiro did: added `scripts/ghost-py` (finds `<repo>/.venv/bin/python` from its own location, runs from the repo root, exits 127 with a message naming the missing venv) and `scripts/ghost_hook.py` (reads the hook's stdin payload, finds the path, runs `ghost.cli autopsy|report|verify` or the golden pytest run). Each hook's `action.command` is now `scripts/ghost-py scripts/ghost_hook.py <autopsy|report|verify|golden>`. Triggers, matchers, descriptions and timeouts are unchanged. This relies on Kiro running hook commands with the workspace root as cwd (not checked).
- Hand runs with a realistic payload (`{"hook_event_name":"PostFileSave","file_path":"<abs path>"}`):
  - autopsy: printed the real autopsy of a haunted copy under `graveyard/` (3 inputs, F-001 raised). A payload with no graveyard path prints "no matching path ... nothing run" and exits 0.
  - report: on a copy of the haunted migration, regenerated both reports (Intended: 1 expected difference, F-001 D-001).
  - verify: on the same copy, ran Faithful and Intended against the Referee (Intended: PASS, 33 cases, 1 mismatch, class "expected by decision"; Excel cross-check "not cross-checked against Excel").
  - golden: `224 deselected`, then the hook prints "GOLDEN HOOK: NOT CHECKED. 0 golden tests are selected" and exits 1. It no longer looks like success. It stays this way until task 9.1 adds `@pytest.mark.golden` tests.
  - no venv: copying `ghost-py` to a folder without `.venv` printed the "venv not found" message, exit 127.
- Not checked: that Kiro fires each hook and passes the payload on stdin. Use the checklist below.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.7

#### Hook checklist for the owner (run in the Kiro IDE)
For each hook, do the action, open the hook's output in Kiro, and write the result in the last column.

| Hook | Action in Kiro | Expect | Result (date, pass/fail, output) |
|---|---|---|---|
| Run autopsy when a workbook is added to graveyard | Copy `samples/` output (e.g. a generated haunted.xlsx) into `graveyard/` | The autopsy text for the file: inputs, F-001 | |
| Regenerate proof report when decisions.yaml changes | Open a migration's `decisions.yaml` (e.g. a demo copy under `.kiro/specs/<name>/`), make a harmless edit, save | "Proof report: ..." printed | |
| Re-run verification on logic.py or mapping.yaml save | Save `logic.py` or `mapping.yaml` in the same migration | `[faithful] PASS ...` and `[intended] ...` lines | |
| Run golden semantics tests when converter changes | Save any file under `ghost/converter/` | pytest result: `26 passed, 391 deselected` (expected after task 9.2). "GOLDEN HOOK: NOT CHECKED" only appears if the golden selection is empty | |

If a hook prints "ghost-py: .../.venv/bin/python not found", create the venv. If it never fires or prints nothing, record that: it means Kiro's trigger or cwd differs from what was assumed.
### 2026-11-24: Write the README (review-fixes task 3.6, R-19)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: give a fresh clone the setup and run instructions Kiroween requires (Requirement 21.7).
- What Kiro did: rewrote `README.md` and kept the "Live demo" section. It now covers the live URL, quick start (macOS and Debian LibreOffice, venv), CLI demo, tests, local web app, Docker build and run with a table of `GHOST_SOFFICE`, `GHOST_MAX_JOBS`, `GHOST_MUTATION_CASES`, `GHOST_SESSION_SECRET`, `GHOST_COOKIE_SECURE`, `GHOST_SESSION_IDLE_S` and `PORT`, the ECS deploy guide, the Kiro Power, Excel-saved fixtures via Excel for the web, safety, limits and LibreOffice-versus-Excel differences, and the note that the feasibility test bench is not in this repository. Every variable and path was checked against `web/app.py`, `web/jobs.py`, `ghost/referee/locate.py`, `ghost/ingest/limits.py`, the `Dockerfile` and `ghost/cli.py --help`.
- Verification: ran `.venv/bin/python -m ghost.cli --help`, `scripts/demo.sh /tmp/ghost-readme-demo` (F-001 raised; haunted Faithful PASS 300 cases; Intended PASS with one expected difference at quantity=50) and the web app with uvicorn (`/healthz` reports the Referee available, `/` returns 200). Docker and AWS commands were not run. `.kiro/` has 19 tracked files and `git check-ignore` reports it is not ignored.
- Known gaps (current state, 2026-11-24): none of the gaps listed at the time remain open. `plugin/mcp.json` launches `uvx ... ghost-mcp` without `toolPrefix` (R-15). `tests/fixtures/excel-saved/` exists with a README but holds no real Excel-saved workbook, so the two fixture tests skip and reports say "not cross-checked against Excel" (R-20, owner to create the files). `MAX_CELLS`, the per-session job cap, and the `-m golden` and `-m "not slow"` test commands are implemented and documented in the README. Still open for the owner: R-25 (Excel result of `=ROUND(123456789012345.67,1)`), triggering the four hooks in Kiro (R-29), and installing the Power from the GitHub URL (R-15).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 3.6

### 2026-11-24: Fix R-01, Intended mode excuses unrelated bugs (review-fixes task 4.2)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution in the Skeptic role (`.kiro/agents/skeptic.json`)
- Goal: an Intended-mode mismatch counts as "expected by decision" only when the Decision explains it on that case (clause 2.5).
- What Kiro did:
  - `ghost/verifier/classify.py`: new `explaining_decision` applies the three conditions: (a) the transpiled Faithful module matches the Referee, (b) the module under test differs from Faithful, (c) a trace hook on the Decision's patched cell (`Calculator!B9#1`) evaluates differently in the two modules. The classifier takes the verifier's answer; anything unexplained is "translation bug". Faithful-mode classification is unchanged (R-02 is task 4.4).
  - `ghost/verifier/run.py`: in Intended mode with Decisions, builds the transpiled Faithful module from the Referee's workbook (or `VerifyConfig.faithful`). If the workbook is not fully convertible, or either module has no `trace` parameter, nothing is explained. Explained mismatches are recorded and generation continues to the case budget. Only an unexplained one stops the run and is shrunk. After the run, one Hypothesis search per Decision shrinks a minimal explained example. `VerifyResult.expected_counts` holds the distinct cases per Decision. Progress is capped at the case budget.
  - Report: each expected-by-decision entry carries an optional `cases` count (`ghost/models.py`, `ghost/report/model.py`, the HTML Decision column, the CLI line "explains N distinct generated case(s)"). `proof-report-1.json` gains an optional `cases` property on `mismatch`. Old reports still validate.
  - Tests: removed the strict xfail from `test_intended_mode_does_not_excuse_unrelated_bug` and the module-level xfail from `tests/test_property_intended_classification.py`. Added a unit test for `explaining_decision`. No test weakened.
- Verification: full suite `209 passed, 16 xfailed` before the unit test was added, then `tests/test_verifier_classify.py` 6 passed. `scripts/demo.sh` into a temp folder: discount PASS; haunted F-001, Faithful PASS 300 cases; Intended PASS 300 cases (was 33) with one expected difference, F-001 D-001, minimal quantity=50, explaining 12 distinct cases. All three reports validate against the schema. `tests/test_demo_invariants.py`, `tests/test_web_flow.py` and `tests/test_web_samples.py` pass. CLI repro from the review (hand-written `logic.py` with D-001 and VAT 21%): `[intended] FAIL: 1 cases ... class: translation bug`, exit 1.
- Left for later: the MCP `verify_implementation` test (task 4.3). It calls the same `verify` and classifier, so it gets the new logic through the Referee's workbook path. R-02 Faithful labelling (task 4.4).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.2
### 2026-11-24: Fix R-01 on the MCP path (review-fixes task 4.3)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: MCP `verify_implementation` classifies Intended-mode mismatches with the same three-condition test as the CLI.
- What Kiro did:
  - Test first: `tests/unit/test_mcp_verify_intended.py` runs `verify_implementation` against the real Referee on the haunted sample with D-001 recorded. A D-001 module plus VAT 21% returns `passed: false` with a "translation bug". A correct D-001 module passes with one "expected by decision" entry (D-001, quantity 50). The file skips with a message when soffice is missing. Both tests already passed after task 4.2, because `verify` builds the Faithful module from the Referee's workbook path.
  - `mcp_server/server.py`: in Intended mode with Decisions, `verify_implementation` now builds the transpiled Faithful module itself (`emit_module`) and passes it as `VerifyConfig.faithful`. If the workbook is not fully convertible there is no Faithful module, nothing is explained, and every mismatch is a translation bug. No change to `ghost/verifier/`.
- Note: a hand-written module with no `trace` parameter cannot be explained by a Decision (condition 3 needs its trace), so its mismatches are translation bugs.
- Verification: full suite `212 passed, 16 xfailed`.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.3

### 2026-11-24: Fix R-02, label Faithful translation bugs correctly (review-fixes task 4.4)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Skeptic role
- Goal: in Faithful mode a mismatch is "original workbook inconsistency" only when the comparisons at the Finding's locations disagree on that case.
- What Kiro did:
  - `ghost/verifier/classify.py`: new `finding_active(finding, trace)`. Each cell location contributes the truth value of its first traced IF condition; the Finding is active only if two locations differ. `classify` takes an optional `trace` and, when given, keeps only active Findings. Without a trace the old reachability match is kept for direct callers. `explaining_decision` and the Intended logic are unchanged.
  - `ghost/verifier/run.py`: in non-Decision runs with Findings, the failing case's trace comes from the transpiled Faithful module (else the candidate) and is passed to the classifier. A case with no trace evidence is a translation bug.
  - Tests: removed the strict xfail from `test_faithful_translation_bug_is_labelled_translation_bug`. Added `test_faithful_inconsistency_needs_disagreeing_comparisons`. No test weakened.
- Verification: full suite `214 passed, 15 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised, Faithful PASS 300 cases, Intended PASS 300 cases with one expected difference (F-001, D-001, quantity=50).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.4

### 2026-11-24: Fix R-03, one shared type-inference function (review-fixes task 4.6)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: a `decimal`-validated input is typed decimal, so fractional values are generated and a truncating module fails.
- What Kiro did:
  - Confirmed first: with `--runxfail` on the old code, Property 5 failed on the type assertion (`validation=None, value=0.0`, mapping `decimal`, verifier `integer`).
  - New `ghost/converter/typeinfer.py` with `infer_input_type(samples, validation)`: validation first, then the sample value. `mapping._type_of` and `strategies.infer_spec` both call it. `infer_type` and the helpers moved there; `strategies` re-exports `infer_type`.
  - Whole-valued float with no validation (1.0): decimal, documented in the module docstring. Excel-saved whole numbers read as `int`, so a float is a deliberate decimal, and decimal still generates whole values. Samples (a) and (b) use `int` values and keep their types. A text sample is `string` in both paths.
  - Removed the strict xfail from `test_decimal_validation_wins_over_whole_number_sample`, `test_truncated_distance_is_caught` and `test_property_5_type_inference`. No test weakened.
- Verification: full suite `217 passed, 13 xfailed`. `scripts/demo.sh` into a temp folder: discount Faithful PASS (`delivery_distance_km` is `decimal`); haunted F-001 raised, Faithful PASS 300 cases, Intended PASS 300 cases with one expected difference (F-001, D-001, quantity=50).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.6
### 2026-11-24: Condition-flip probing module (review-fixes task 4.8, R-04 and R-10 expressions)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Skeptic role
- Goal: find where each IF condition changes truth value, including thresholds on calculated cells and expressions.
- What Kiro did:
  - New `ghost/verifier/flip.py`: `Flip` (condition_id, input_name, others, below, above, exact, `cases()`) and `find_flips(compute, mapping, base_inputs, *, tolerance, seed, max_evaluations=6000)`. For each numeric input it scans 9 grid points (min, max, base value, evenly spaced), then bisects every interval where a traced condition changes (up to 3 per condition, input and base point). Other inputs stay at the base values and at 2 seeded random points inside their min/max. Integer inputs search on integers (adjacent pair); decimals search on the tolerance's grid until the gap is <= tolerance. All Decimal; evaluation count capped.
  - `exact`: the trace only gives booleans, so the threshold is located by refining the flip pair to 1e-6 of a grid step. `exact` is the refined endpoint that lies on the input's grid (the value where the comparison flips, `>=` or `>`), else None. It is None for integer inputs (both neighbours are already cases). This is a trace-based inference, not a read of the formula.
  - Tests: removed the strict xfail from `test_property_6_condition_flip_probing_finds_boundary`; the assertions are unchanged and held for both `>=`/`>`, cell and expression thresholds.
  - Not done here (task 4.9): wiring into `_probe_boundaries`, `verify` and `mutate`.
- Verification: `tests/test_property_condition_flip.py` 5 passed; full suite `222 passed, 13 xfailed`.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.8
### 2026-11-24: Wire flip probing into verification, mutation and boundaries (review-fixes task 4.9, R-04)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Skeptic role
- Goal: make thresholds on calculated cells and expressions part of the proof.
- What Kiro did:
  - `ghost/verifier/flip.py`: added `flip_cases` (deterministic, de-duplicated, capped at 200, integer inputs as `int`) and `flip_boundaries` (one `BoundaryResult` per condition and input).
  - `ghost/cli.py`: `_probe_flips` runs `find_flips` on the transpiled Faithful module (local, no Referee). `run_verification` puts the cases into `VerifyConfig.extra_cases` for every mode and into the mutation check's `targeted` cases, so the Referee checks them like any other case. `_probe_boundaries` keeps the input-threshold search and appends the flip boundaries (the MCP `boundary_cases` tool inherits this).
  - `mcp_server/server.py`: `verify_implementation` has its own `VerifyConfig`, so it now gets the same flip cases.
  - Report: optional `BoundaryResult` fields `kind`, `condition_id`, `below`, `above`, `exact`; the schema gains the same optional properties (no new required field). The HTML boundary table shows the condition id, both sides and the exact hit.
  - Tests: removed the strict xfail from `test_gold_threshold_on_calculated_cell_is_caught` (it now passes the flip cases as extras); added `test_tier_flip_cases_kill_threshold_mutants_and_boundaries_list_b12` (flip, drop-IF and constant +-1 mutants on `Calculator!B12` are killed; the boundaries list `Calculator!B12#1`). The tier workbook only has `B12` as a condition; `B13` does not exist in it.
- Verification: full suite `224 passed, 12 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised, Faithful PASS, Intended with D-001 PASS with one expected difference at quantity=50. The reported case count rose from 300 to 309 on haunted because the 9 targeted flip cases are counted with the generated ones.
- Timing (CLI verify with mutation, default mutant cases, 8-core Mac, flips off then on): discount 4.3 s then 3.6 s; haunted 4.0 s then 3.9 s. `find_flips` alone takes 0.007 s on both samples (6 flips each). No measurable cost; I did not measure a 1 vCPU host.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.9
### 2026-11-24: Honest survivor wording (review-fixes task 4.10, R-06)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Skeptic role
- Goal: a surviving mutant must never be called equivalent.
- What Kiro did:
  - `ghost/mutation/run.py`: removed `REASON_EQUIVALENT`. Survivors now read "no difference found on N distinct cases; tested domain: ..." with each input's type, min, max and decimal places taken from the cases actually run (`tested_domains`, `no_difference_reason`, both exported). N counts distinct inputs, not repeats. `branch not reachable` and `not exercised by cases` are unchanged.
  - `.kiro/specs/ghost-in-the-macro/design.md`: survivor reasons line reworded. A repo grep found no other use of the old wording in code, templates, skills or tests (the HTML report and web panel print `survivor_reason` as stored). Historic text in `docs/TEST_REPORT_2026-11-24.md` and `docs/KIRO_FIX_PROMPT_2026-11-24.md` quotes the old label as the finding and was left.
  - Tests: new `tests/test_mutation_wording.py` (written first). No existing test asserted the old wording, so none needed changing. `test_decimal_distance_mutants_are_not_equivalent` is unchanged.
- Done-when check, real run (LibreOffice Referee): the constant +-1 mutants on `Calculator!B9` in haunted are killed. No change beyond wording was needed.
- Mutation scores (`ghost mutate`, default 100 mutant cases, on the demo output in a temp folder): discount 31/33 (94%), haunted 33/35 (94%). Survivors on both: M-3cbed5dc (B9 half-even) and M-687cf270 (B10 half-even). Earlier report figures were 27/31 and 29/33.
- Verification: full suite `229 passed, 12 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised, haunted Faithful PASS (306 and 309 cases), Intended with D-001 PASS with one expected difference ("expected by decision F-001 D-001").
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.10
### 2026-11-24: Generated versus distinct cases (review-fixes task 4.11, R-28)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: stop presenting repeated inputs as separate proof.
- What Kiro did:
  - `ghost/verifier/run.py`: `VerifyResult` gains `cases_generated`, `cases_targeted` (flip/boundary/coverage extra cases) and `distinct_cases` (distinct input combinations among all cases checked). `cases_tested` is unchanged: generated + targeted, repeats included, so `tests/test_demo_invariants.py` (`>= 300`) holds.
  - Report: optional `cases_generated`, `cases_targeted`, `distinct_cases` in `ghost/models.py`, `ghost/report/model.py` (omitted when not counted) and `proof-report-1.json` (no new required field, no version bump). `ghost/report/html.py` `describe_cases` renders "300 generated + 9 targeted, 205 distinct"; old reports render the plain total.
  - CLI `_print_result`, MCP `verify_implementation` and the web job panel (`web/flow.py`, `_job.html`) show the same text.
  - Test first: `tests/unit/test_case_counts.py` (counts separate, new report shows both, old report still validates).
- Real numbers, `scripts/demo.sh` into a temp folder: discount Faithful 300 generated + 6 targeted, 202 distinct; haunted Faithful and Intended 300 generated + 9 targeted, 205 distinct. The review's 176 counted only the 300 generated cases of an earlier run, so it is not reproduced; the figure is read from engine output.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.11

### 2026-11-24: Harden R-01 and R-02 after the Skeptic review, R-28 key normalisation (review-fixes task 4.2 reopened)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: close the Skeptic's holes: a renamed or missing trace id excused any bug (variants C, D), the candidate's output was never compared with what the Decision prescribes (E), and Faithful mode blamed the workbook for a code bug (H).
- What Kiro did (tests first, `tests/test_review_classification_soundness.py` with the real Referee, `tests/test_case_key.py`):
  - `ghost/verifier/classify.py` `explaining_decision`: new optional `intended` and `intended_trace`. A Decision explains a case only if the candidate's hook for the patched cell is present, equals the Intended module's truth value, and the Faithful module's value differs. Missing hook means no explanation. The candidate's outputs must equal the Intended module's within tolerance. Without the new arguments the old unit test behaviour holds (plus the present-hook rule).
  - `ghost/verifier/run.py`: builds the transpiled Intended module (Faithful plus Decision patches) from the Referee's workbook (or `VerifyConfig.intended`). Unconvertible workbook or a failed patch explains nothing. `VerifyResult.explain_unavailable` says why ("module has no trace hook, so Decisions cannot explain mismatches"); `ghost/cli.py` prints it as a note and MCP `verify_implementation` returns `decisions_cannot_explain`. The MCP call needs no other change, since the Intended module is built from the Referee's workbook.
  - R-02: in Faithful mode the trace given to the classifier is empty unless the transpiled Faithful module itself disagrees with the Referee on that case, so a code bug the transpiler does not share is a "translation bug". The candidate's own trace is no longer used as a fallback.
  - R-28: `case_key` in `ghost/verifier/compare.py` normalises numbers (Decimal normalised, ints and floats via `Decimal(repr(x))`) for the distinct count, the explained-case dict and the mutation run.
- Verification: full suite `242 passed, 12 xfailed`. `scripts/demo.sh` into a temp folder: haunted Faithful PASS, Intended PASS with one expected difference (F-001, D-001), explaining 26 distinct generated cases. `tests/test_demo_invariants.py` and the property tests pass.
- Left for later: `ghost/verifier/flip.py`, `_probe_flips` and `ghost/router` were not touched.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.2 (and 4.4 follow-up)
### 2026-11-24: Flip probing reports what it did not check (review-fixes task 4.9 reopened, R-04, R-06 wording)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: close the Skeptic's finding that flip probing silently dropped work (`except _Budget: pass`, the 6000-evaluation cap, case and per-search truncation, `except Exception: return []`), against the "no invented data" guardrail.
- What Kiro did (tests first, `tests/test_flip_reporting.py`, no LibreOffice needed):
  - `ghost/verifier/flip.py`: new `FlipSummary` (evaluations used, cap reached, condition/input pairs not completed, pairs with no flip and their domain, text inputs, truncations). `find_flips(..., summary=, literals=)` and `flip_cases(..., summary=)` fill it; return values are unchanged. `notes()` gives the wording: "flip probing stopped at N evaluations; M condition/input pairs not checked", "no flip found for <condition> on <input> [lo, hi]", "not probed: text input <name>".
  - Blind spots: `literals_from_workbook` reads numeric formula literals (`50%` is 0.5); each literal, its +-1 and (decimals) +-tolerance seed the first base's grid, capped at 60 points per search (reported when cut). `AND(B1>10,B1<20)` and `B3=777` are now found. Literals come from formula text, not `_CONSTS`, because inline literals are not in `_CONSTS`.
  - `ghost/cli.py`: `_probe_flips_with_summary` returns flips and summary; `_probe_flips` still returns the list (MCP server uses it). Failures give "flip probing not checked: <reason>" and a logged traceback; not-converted cells give "flip probing partial: ...". Notes are printed (first 10) and stored in the report.
  - Report: optional `boundary_notes` (string list) in the model, `proof-report-1.json`, `report_to_dict` (omitted when empty) and the Boundaries section of the HTML. Old reports still validate.
  - R-06 wording: `ghost/router/explain.py` "proves the result" became "checks the result against the original workbook". Grep of README, web, plugin, report HTML, skills and docs/KIRO_USAGE.md found no other "prove" claims.
  - Not touched: `ghost/verifier/classify.py`, `ghost/verifier/run.py`, `mcp_server/`. The MCP `verify_implementation` still uses the list-only `_probe_flips`, so it does not surface the notes yet. (Fixed in the Phase 2 checkpoint, below.)
- Verification: full suite `249 passed, 12 xfailed` (Property 6 and the tier test pass). `scripts/demo.sh` into a temp folder in about 12 s: discount Faithful PASS; haunted Faithful PASS with 0 mismatches, Intended PASS with one expected difference (F-001, D-001, quantity=50); demo reports validate against the schema and carry the "no flip found" notes for B7 and B9 on distance and unit price.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.9, 4.10
### 2026-11-24: Checkpoint Phase 2, MCP boundary notes (review-fixes task 4.12)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: MCP `verify_implementation` returns the same flip-probing notes as the CLI.
- What Kiro did: `mcp_server/server.py` calls `_probe_flips_with_summary`, passes the cases through `flip_cases(..., summary=)` and returns `boundary_notes`. Test: `tests/unit/test_mcp_verify_intended.py::test_response_carries_the_same_boundary_notes_as_the_cli`.
- Verification: full suite `250 passed, 12 xfailed`; Skeptic reproductions and `scripts/demo.sh` re-run (see the Resolution section of `docs/TEST_REPORT_2026-11-24.md`).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 4.12

### 2026-11-24: Fix R-09, truth-set comparison in findings (review-fixes task 5.2)

- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Coroner role
- Goal: stop raising an operator-conflict Finding for complementary comparisons such as `>=50` and `<50`.
- What Kiro did: `ghost/autopsy/findings.py` now gives each operator a truth set over {below, at, above} and flags a group only when some pair of operators has sets that are neither equal nor complementary. An unknown operator is still flagged, not guessed. Finding ids are still assigned in sorted (cell, constant) order. Removed the `xfail` markers from `test_complementary_operators_are_not_a_finding` and `test_property_4_operator_consistency`; no test was weakened or deleted.
- Verification: full suite `252 passed, 11 xfailed`. `scripts/demo.sh` into a temp folder: haunted F-001 raised, Faithful PASS with 0 mismatches, Intended with D-001 PASS with one expected difference at quantity=50 ("expected by decision F-001 D-001"); discount sample Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.2
### 2026-11-24: Fix R-10, threshold extraction rules (review-fixes task 5.3)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Coroner role
- Goal: stop treating an input's current value as a threshold, and record percent and expression comparisons.
- What Kiro did: `ghost/autopsy/thresholds.py` takes an optional `roles` map (default: autopsy classification) and resolves constants only from non-INPUT cells, so haunted `B2>=E2` still resolves the PARAMETER `E2` to 50. `50%` is read as 0.5. A comparison of an arithmetic or function expression with a constant is recorded with the rendered expression (for example `P!(A2*A3)`) as `cell`. `ghost/cli.py` (`_analyse`, `run_verification`) and `mcp_server/server.py` (`verify_implementation`) pass their roles; `web/flow.py` goes through `_analyse`, so thresholds are recomputed whenever inputs change, with no change to the web flow. Removed the `xfail` markers from the two R-10 tests; no test was weakened or deleted.
- Verification: full suite `254 passed, 9 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised, Faithful PASS 300 generated cases, Intended with D-001 PASS with one expected difference (F-001, D-001, quantity=50); discount Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.3
### 2026-11-24: Fix R-11, a compared constant is an INPUT (review-fixes task 5.4)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution, Coroner role
- Goal: stop demoting a real input to PARAMETER only because two formulas read it.
- What Kiro did: in `ghost/autopsy/classify.py` added `_compared_with_literal`, which walks the formula ASTs and collects cells compared directly with a numeric literal (`A1>=50`, `50<A1`). The `shared_fixed` demotion no longer applies to those cells. It reads the ASTs, not `extract_thresholds`, so classification does not depend on thresholds that task 5.3 now computes from the roles (no cycle). Rate labels, the R-12 block rule and R-05 table blocks and lookup text are unchanged and still give PARAMETER. A comparison between two cells (`B2>=E2`) does not count, so haunted `E2` stays PARAMETER. Removed the strict xfail from `test_input_shared_by_two_formulas_is_an_input`; no test was weakened or deleted.
- Verification: full suite `255 passed, 8 xfailed`. `scripts/demo.sh` into a temp folder: haunted inputs B2, B3, B4, output B11; F-001 raised; Faithful PASS 300 generated cases; Intended with D-001 PASS with one expected difference at quantity=50 (F-001, D-001); discount Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.4
### 2026-11-24: Fix R-14, reject duplicate Decisions and validate patches at record time (review-fixes task 5.6)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: stop a second Decision for the same Finding from being accepted and then breaking every verification.
- What Kiro did: `ghost/decisions/store.py` `record` raises `InvalidDecision` naming the existing `decision_id` when the `finding_id` or `rule_id` already has a Decision, before writing anything, and takes an optional `validate` callback that sees the full Decision list. `ghost/cli.py` adds `patch_validator(mdir)`, which emits the Intended module from `source.yaml` and `mapping.yaml` and turns `InvalidPatch` into `InvalidDecision`; it is used by `ghost decide` and the MCP `record_decision` and does nothing when the workbook or mapping is not known. The web flow is untouched and still answers 409 "already has a Decision". Removed the strict xfail from `test_second_decision_for_same_finding_is_rejected` and `test_property_8_decision_uniqueness`. Added `tests/test_decision_patch_validation.py` (CLI and MCP, bad patch rejected with nothing written, good patch accepted, duplicate rejected). Two fixtures in `tests/test_decisions_store.py` recorded F-001 twice only to test ID assignment; they now use F-001 and F-002, no assertion changed.
- Verification: full suite `261 passed, 7 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised; haunted Faithful PASS 300 generated cases; Intended with D-001 PASS with one expected difference at quantity=50 (F-001, D-001); discount Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.6
### 2026-11-24: Add the generated macro sample, R-13 (review-fixes task 5.7)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: give the two R-13 tests a macro workbook that exists in CI, instead of the absolute test-bench path.
- What Kiro did: `samples/make_xlsm.py` builds `discount_vba.xlsm` and `haunted_vba.xlsm` (labelled "generated") through `RefereeClient.save_with_vba` with `run_macros=False`, so no macro runs. Module `Module1` holds `Function DeliveryFee` (used as `Calculator!B13 =DeliveryFee(B2,B4)`) and `Sub AwardPoints` (points = whole tens of the total in `B14`, Gold from 500 in `B15`); the haunted twin rounds total/10. `tests/conftest.py` adds the session-scoped `macro_samples` fixture (tmp dir, skips with a message if soffice is missing). `tests/test_sample_xlsm.py` checks `xl/vbaProject.bin` is in the zip and `extract_vba` returns both modules for both files. Output `*.xlsm` is already covered by `.gitignore`. The R-13 tests are unchanged (task 5.8 re-points them).
- Note: LibreOffice lower-cases the unknown function name in `B13` when it loads the base workbook (`=deliveryfee(B2,B4)`); VBA names are case-insensitive, so behaviour is unchanged.
- Verification: full suite `264 passed, 7 xfailed`.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.7
### 2026-11-24: Fix R-13, detect VBA by content (review-fixes task 5.8)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: report VBA whatever the file extension, and show it in the upload summary.
- What Kiro did: `ghost/ingest/vba.py` gains `has_vba_project` (looks for `xl/vbaProject.bin` in the zip) and `extract_vba` returns `[]` without it, otherwise reads statically with olevba. `ghost.ingest.load_workbook` now fills `wb.vba_modules` from that, so web `_summary` (`has_vba`), autopsy metrics, CLI `_load`, routing and the MCP tools share one detection; the `.xlsm` suffix check in `ghost/cli.py` is gone. An unreadable VBA container leaves `vba_modules` empty instead of failing the load. `test_vba_found_in_renamed_macro_workbook` and `test_upload_summary_reports_vba` now use the `macro_samples` fixture (test-bench path removed, assertions unchanged, xfail markers removed), as ordered by the fix prompt.
- Macro safety: `grep` for `run_macros` and `trusted_source` in `web/` finds nothing, so uploads never enable macros; the Referee defaults to `NEVER_EXECUTE`.
- Verification: full suite `266 passed, 5 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised; haunted Faithful PASS 300 generated cases; Intended with D-001 PASS with one expected difference at quantity=50 (F-001, D-001); discount Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.8
### 2026-11-24: Fix R-26, text outputs typed `string` (review-fixes task 5.9)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: formulas that produce text get type `string` in `mapping.yaml` even when the workbook has no Excel-saved values.
- What Kiro did: `ghost/converter/typeinfer.py` gains `infer_formula_kind`, which parses the formula and decides text, number, boolean or undecided from the AST: string literals, `&`, text functions (TEXT, CONCATENATE, LEFT, UPPER and similar), `IF`/`IFERROR` only when all branches agree, `INDEX` into a range whose cells are all text, and references followed through other formulas (cycles give undecided). `ghost/converter/mapping.py` `_output_type` uses the Excel-saved value first; else `string` if the AST says text; else the old default `decimal` (commented in the code as "undecided"). Mixed branches such as `IF(x,"Gold",0)` stay `decimal`. Only text is changed; booleans are not retyped.
- Tests: new `tests/unit/test_mapping_text_outputs.py` written first (3 of 5 failed before the fix): scenarios `best_scenario` is `string` and `best_net_cost` `decimal`; haunted `total` is `decimal`; `IF(...,"Gold","Standard")`, `&` and `TEXT` give `string`; mixed branches stay `decimal`.
- Verification: full suite `271 passed, 5 xfailed`. `scripts/demo.sh` into a temp folder: F-001 raised; haunted Faithful PASS 300 generated + 9 targeted; Intended with D-001 PASS with one expected difference at quantity=50; discount Faithful PASS.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.9
### 2026-11-24: Phase 3 checkpoint and unreadable-VBA guardrail (review-fixes task 5.10)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: close Phase 3 and stop task 5.8 from silently reporting "no VBA" when `xl/vbaProject.bin` cannot be read.
- What Kiro did: `extract_vba` raises when the container exists but yields no modules; `load_workbook` sets `Workbook.vba_present` and `Workbook.vba_error` instead of swallowing it. The upload summary (`has_vba` true, `vba_error`), the autopsy page and the CLI autopsy show "VBA present but could not be read: <reason>" and "VBA: not checked".
- Tests: new `tests/test_vba_unreadable.py` (zip with a corrupt `xl/vbaProject.bin`, loader and upload).
- Verification: full suite `273 passed, 5 xfailed`; web sample and flow tests `8 passed`; demo invariants hold and the five demo reports validate against `proof-report-1.json`. The Coroner agent was not run.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 5.10
### 2026-11-24: Fix R-17 part 1, cell cap `MAX_CELLS` (review-fixes task 6.1)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: reject large but legal workbooks before openpyxl loads them.
- What Kiro did: wrote `tests/test_ingest_max_cells.py` first (failed on import of `MAX_CELLS`). Then added `MAX_CELLS = 200_000`, `Limits.max_cells` and `TooManyCells` to `ghost/ingest/limits.py`. `_check_archive` in `ghost/ingest/workbook.py` now streams each `xl/worksheets/*.xml` with defusedxml `iterparse`, counts `<c>` elements, frees each `<c>` and `<row>` as it closes (flat memory), and raises as soon as the count passes the limit. The web upload already maps `IngestError` to 422, so the message reaches the user. Documented in `.kiro/steering/tech.md` and the README limits section.
- Tests: a 250,000-cell workbook built with openpyxl write-only mode is rejected in about 0.6 s with `openpyxl.load_workbook` patched to fail if called; the web `/upload` returns 422 naming 200,000; the three bundled samples still upload and `GET /autopsy` works.
- Verification: full suite `277 passed, 5 xfailed`. `scripts/demo.sh` was not re-run for this task (checkpoint 6.7 does it). The per-session analysis cache (task 6.2) is not done, so R-17 is "partly fixed".
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.1

### 2026-11-24: Fix R-17 part 2, per-session analysis cache (review-fixes task 6.2)

- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: stop `GET /autopsy` and `POST /decision` from reparsing the workbook on every call.
- What Kiro did: wrote `tests/test_web_analysis_cache.py` first (4 of 5 failed). Added `Session.analysis_cache` in `web/sessions.py` and `_analysis()` in `web/flow.py`, used by `_describe`. One entry per session, keyed on workbook path, sha256 and confirmed inputs/outputs. Cleared in `reset_state` (new upload or sample) and in `SessionStore.delete` (session end and sweep). Decisions are loaded from the spec folder on every call, so a recorded Decision shows immediately without discarding the parse. A missing file skips the cache so the engine's "workbook not found" error still surfaces.
- Tests: `GET /autopsy` x3 calls `load_workbook` once; `POST /decision` adds no parse; new sample or upload re-parses; changed inputs re-parse; cache is cleared on session delete.
- Verification: full suite `282 passed, 5 xfailed`; web tests `27 passed`. `scripts/demo.sh` not re-run. Subprocess parsing was not added. Opinion: not needed now. The 200,000-cell cap bounds the parse, and the cache removes the repeated parse, so peak memory is one parse per request. It would only matter if several large uploads parse concurrently on the 2 GB task; ask before adding it.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.2

### 2026-11-24: Fix R-18 part 1, per-session job cap (review-fixes task 6.3)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: one visitor must not be able to queue unlimited verification jobs.
- What Kiro did: wrote the tests first (they failed on the missing `SessionBusy`). `web/jobs.py`: `JobRunner.active_job(session_id)` and `SessionBusy`; `submit` checks and registers under the runner lock, so two simultaneous requests cannot both get in. `web/flow.py`: `POST /verify` checks before preparing the run and answers 429 with the message "This session already has a verification queued or running. Wait for it to finish, then start a new run." The 429 body (`web/templates/_busy.html`) is the message plus the panel of the job that is still active, so HTMX polling continues. htmx 1.9 does not swap 4xx responses, so `web/static/htmx-errors.js` (loaded from `index.html`) lets 409, 422 and 429 bodies swap into the target. That also makes the existing 409/422 messages visible in the browser, which they were not before. The choice of 429 over replacing the queued job is documented in the README web app section.
- Existing test edited: `test_concurrency_limit_and_queue_position` in `tests/test_web_jobs.py` submitted three jobs from one session. Now it uses three sessions; the assertions are unchanged.
- Tests: runner (second submit refused while running; refused while queued; other session not blocked; finished job does not block), HTTP (second `/verify` gives 429 with the message and the running job's panel; a new run after a finished job gives 200; the swap script is present and loaded).
- Verification: full suite `288 passed, 5 xfailed`. Not tested in a real browser; the htmx swap script is covered only by a file-content test. `scripts/demo.sh` not re-run (checkpoint 6.7). R-18 is "partly fixed" until task 6.4 (jobs and artifacts removed at session end).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.3
### 2026-11-24: Fix MCP error naming (review-fixes task 6.6)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: `evaluate_original` with a non-scalar input value must name the bad argument (Requirement 12.11), not return `referee_error`.
- What Kiro did: wrote tests first (3 failed: the Referee started and the error was `referee_error`). `mcp_server/server.py` `evaluate_original` now checks every input value before starting the Referee. A dict or list returns `invalid_argument` with `argument` `inputs.<cell>` (for example `inputs.Calculator!B2`). Checked the other tools that take inputs or cases: `boundary_cases` `inputs` (list of strings) and `verify_implementation` `cases` and `mapping` already return `invalid_argument` naming the argument through pydantic validation and `_read_mapping_arg`, so they needed no change. Added tests that pin this.
- Tests: `tests/unit/test_mcp_server.py` (non-scalar input names `inputs.<cell>` with the Referee patched to fail if started; bad `boundary_cases` inputs and bad `verify_implementation` cases).
- Verification: full suite `292 passed, 5 xfailed`. `scripts/demo.sh` not re-run (checkpoint 6.7).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.6

### 2026-11-24: Fix R-18 part 2, drop jobs and artifacts at session end (review-fixes task 6.4)

- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: finished jobs and their artifact bytes must not stay in memory after the session ends.
- What Kiro did: wrote tests first (they failed: jobs stayed in the runner). `JobRunner.forget_session` (`web/jobs.py`) now removes all of a session's jobs, clears artifacts and events, dequeues queued jobs and kills running process groups; a killed job no longer re-collects artifacts. `SessionStore` got an `on_delete` hook list (`web/sessions.py`); `web/app.py` registers `runner.forget_session`, so DELETE /session, the idle sweep and store close all use it.
- Tests: `tests/test_web_session_end_jobs.py` (DELETE /session, sweep with short idle timeout, other sessions unaffected, running process killed).
- Verification: full suite `296 passed, 5 xfailed`. R-18 row in `docs/TEST_REPORT_2026-11-24.md` set to fixed.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.4
### 2026-11-24: Fix R-21 (paths), no server paths in job events (review-fixes task 6.5)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: job events and error text shown in the browser must not contain absolute server paths (tmp dirs, session folder, `/app`, home dirs).
- What Kiro did: wrote tests first (the real haunted job and a fake failing job leaked `/tmp/...` paths). Added `web/paths.py` `scrub_paths`: the run directory becomes `.`, any other absolute path becomes its last name. Applied it in `web/jobs.py` before an event is stored and to the job error text, in `web/flow.py` `page()` for `error` and `vba_error`, and in `web/app.py` for upload/sample error bodies and the `/healthz` reason. Chose to sanitise in the web layer only: `ghost/cli.py` still prints absolute paths, which is useful for local users.
- Tests: `tests/test_web_no_server_paths.py` (scrubber unit cases, failing job, 422 body, real haunted job through polling, SSE and panel; the last needs soffice).
- Verification: full suite `301 passed, 5 xfailed`. R-21 row set to partly fixed; the rest is task 8.3.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 6.5
### 2026-11-24: Document R-24, where LibreOffice differs from Excel (review-fixes task 7.5)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: list the seven LibreOffice-vs-Excel divergences, pin the Referee's current results, and record the live (7.4.7.2) and local (26.8.3.1) versions.
- What Kiro did: ran the seven formulas through the Referee locally and in `docker run --rm` on `ghost-local:cp4` (a small probe script mounted read-only; `soffice --version` gave 7.4.7.2), and ran the transpiler output for Ghost's column. Added the table and a versions note to `.kiro/steering/excel-semantics.md`. Added `tests/test_referee_libreoffice_differences.py`, with expectations keyed by LibreOffice major version (7 and 26 share one set because the results were identical). No `ghost/runtime` changes; LibreOffice not upgraded.
- Finding: the two versions gave identical results for all seven, so the version gap does not affect these cases. Excel results are "not verified" (documented behaviour from the test report; no Excel here).
- Verification: new tests `7 passed` locally. The image has no pytest, so the tests themselves were not run there; the probe output from the image matches the pinned values. Full suite `308 passed, 8 xfailed`. `scripts/demo.sh` not re-run (checkpoint 7.7).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 7.5

### 2026-11-24: Document R-25, ROUND over 15 significant digits (review-fixes task 7.6)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: record that `=ROUND(123456789012345.67,1)` is unverified against Excel. Document only; no behaviour change.
- What Kiro did: ran the formula through the Referee locally (26.8.3.1) and in `ghost-local:cp4` (7.4.7.2), and called Ghost's `xl_round`. Both Referees returned `123456789012345.7`; Ghost returned `123456789012346.0`. Added a section to `.kiro/steering/excel-semantics.md`, a sentence to the README known differences, and a "deferred: awaiting owner's Excel check" row in the Resolution table of `docs/TEST_REPORT_2026-11-24.md`. No code or test changes.
- Not checked: Excel's result (no Excel here).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 7.6

#### Owner checklist: R-25 Excel check

1. Open Excel for the web (office.com, new blank workbook).
2. In a cell, enter `=ROUND(123456789012345.67,1)`.
3. Record what the cell shows, and also the result of `=ROUND(123456789012345.67,1)-123456789012345` (shows more digits than the display).
4. Write both results in the R-25 row of `docs/TEST_REPORT_2026-11-24.md` and in the Excel row of the R-25 section of `.kiro/steering/excel-semantics.md`.
5. Decide: if Excel gives `123456789012346` the current Ghost rule stays; if it gives `123456789012345.7`, ask Kiro to change `xl_round` (new test first).

## R-07: comparisons at 15 significant digits (task 7.2)

- `ghost/runtime/excel.py`: `xl_compare` now normalises both numeric operands with `_sig15` (15 significant digits, half away from zero) before the three-way compare, so `xl_eq`, `xl_ne`, `xl_lt`, `xl_le`, `xl_gt` and `xl_ge` follow Excel. Text and boolean comparison is unchanged. Stdlib only, so the vendored copy still works.
- Tests: the two R-07 cases in `tests/test_review_semantics.py::test_transpiler_bug` no longer carry xfail (listed in `FIXED`; `index_row_zero` stays xfail for R-08). The three tests in `tests/test_property_comparison_normalisation.py` have no xfail marker. One generator fix: the "beyond the 15th digit" strategy now starts its mantissa at `10**14 + 1`, because `10**14 - 0.06` is `99999999999999.9` after normalisation (a different 15-digit value), so the property did not hold for that input. Assertions are unchanged.
- Checks: full suite twice, `313 passed, 3 xfailed` both times (no `test_web_jobs` failure seen). `scripts/demo.sh` into a temp folder: F-001 raised, haunted Faithful PASS (300 generated + 9 targeted, 0 mismatches), Intended PASS with one expected difference at quantity=50 (F-001 / D-001).

## 2026-11-24: task 7.3, R-08 INDEX 0 and number-to-text

- `ghost/converter/emit_python.py` `_index`: row or column 0 on a multi-cell range returns `#VALUE!` (was `#REF!`). `tests/test_review_semantics.py`: `index_row_zero` added to `FIXED` (xfail gone).
- `ghost/runtime/excel.py` `_decimal_text` (stdlib only): scientific notation for magnitudes >= 1E16 or < 1E-14. Switch points measured through the Referee; not verified in Excel.
- Choice: compare, not "known difference". `ghost/verifier/compare.py` treats two strings as equal only when both fully match scientific notation (`-?d(.d+)?E[+-]dd(d)`) and have the same value, so "1E+20" equals the Referee's "1E+020". Reason: the difference is only the exponent width, and the rule is too narrow to loosen ordinary text. Documented in `.kiro/steering/excel-semantics.md`.
- Tests: `tests/test_number_to_text.py` (formatting, scientific equality, ordinary strings stay exact), 7 `text_*` Referee cases in `test_review_semantics.py`.
- Checks: full suite `334 passed, 2 xfailed`; `scripts/demo.sh` into a temp folder: haunted Faithful PASS (300 + 9 targeted, 0 mismatches), Intended PASS with one expected difference at quantity=50 (F-001 / D-001).
## 2026-11-24: task 7.4, R-27 named ranges
- New `ghost/converter/names.py` (81 lines): `substitute_names` replaces a `NameRef` with the `CellRef` or `RangeRef` it names. `ghost/ingest/workbook.py` `classify_name_target` records workbook-scoped names that are one cell or one rectangle on an existing sheet in `Workbook.name_targets`; every other name goes to `Workbook.name_issues` with a reason (dynamic OFFSET/INDIRECT, multi-area, external, unknown sheet, sheet-scoped). The dependency graph already followed names and is unchanged.
- Used by `subset.py` (lists only unresolved names, with the reason), `emit_python.py`, `autopsy/thresholds.py` (`B2>=Bulk` records `B2 >= 50`; a name pointing at an INPUT cell is not resolved, per R-10), `autopsy/classify.py` (`_compared_with_literal`) and `rules/ears.py` (the defined name is the label, e.g. `Bulk [E2]`, `range Prices [G1:G3]`). Sheet-scoped names stay not converted because the same name can mean different cells on different sheets.
- Tests first (`tests/test_named_ranges.py`, failed at import before the fix): `=Bulk*2` and `SUM(Prices)*B2` match the Referee, `IF(B2>=Bulk,...)` verifies Faithful, threshold recorded at Bulk's value, OFFSET name and sheet-scoped name listed not converted with dependents, rule text, determinism.
- Checks: full suite `350 passed, 2 xfailed` (R-15, R-16 remain for task 8). `scripts/demo.sh` into a temp folder: F-001 raised, haunted Faithful PASS (300 generated + 9 targeted, 0 mismatches), Intended PASS with one expected difference at quantity=50 (F-001, D-001). Demo flow unchanged.

## 2026-11-24: task 7.3 follow-ups, R-30 and standalone module import

- R-30: probed the Referee first (`/tmp/p5_index.py` extended). `_index` in `ghost/converter/emit_python.py` rewritten: a 0 row or column on a dimension of length 1 selects it, on a longer dimension gives `#VALUE!`. This also fixed `INDEX(M1:M3,2,0)` and `INDEX(M1:O1,0,2)`, which the old code got wrong. Excel's result is not verified; noted in `.kiro/steering/excel-semantics.md`.
- Standalone import: the `_HEADER` in `emit_python.py` tries `.excel`, then `excel`, then `ghost.runtime.excel`. Output stays deterministic.
- Tests: 11 `index_*` cases in `tests/test_review_semantics.py`; new `tests/test_generated_module_standalone.py` (logic.py + excel.py in a temp dir, clean env with no PYTHONPATH, ghost not importable, haunted at quantity 50 equals the package-path result; package import still works). No test weakened or deleted.
- Checks: full suite `363 passed, 2 xfailed`. `scripts/demo.sh` into a temp folder: haunted Faithful PASS (300 + 9 targeted, 0 mismatches), Intended PASS with one expected difference at quantity=50 (F-001 / D-001), discount Faithful PASS. `docs/TEST_REPORT_2026-11-24.md` R-08 and R-30 rows updated (R-30 fixed). Not committed, no AWS.

## R-22: autopsy page text (task 8.4)

- `web/templates/_autopsy.html` now says "Unanswered findings keep the original behaviour and are listed in the report." The old sentence ("reported as mismatches") was false in Faithful mode.
- Checked the claim first: ran haunted through the web app with no Decision recorded. `report.json` has `findings` containing F-001, `decisions` is empty, `report.html` lists F-001, mode is faithful and it passes. No change to `ghost/report/html.py` was needed.
- Tests: `tests/test_web_autopsy_text.py` (page text; real job listing F-001, needs LibreOffice). Web tests: 20 passed. Not committed, no AWS.

- R-23 (task 8.5): dark `--border` changed from `#5b4f73` to `#7a6d94` in `web/static/style.css`. Computed contrast (WCAG formula, parsed from the CSS in the test): dark 3.96:1 on background, 3.65:1 on surface; light `#7a6f91` already passes (4.21:1 on background, 4.66:1 on surface). The toggle in `web/templates/index.html` now always reads "Light mode"; `web/static/theme.js` only sets `aria-pressed` (no label rewrite). Tests: `tests/test_web_accessibility.py` (static checks; no real screen reader or browser run). Not committed, no AWS.

## 2026-11-24: task 8.2, R-16 `atx` dry-run command

- Spec task executed from `.kiro/specs/review-fixes-2026-11-24/tasks.md`. Checked the AWS Transform custom CLI reference online (https://docs.aws.amazon.com/transform/latest/userguide/custom-command-reference.html and https://docs.aws.amazon.com/transform/latest/userguide/custom-workflows.html); URL cited in a code comment in `ghost/router/explain.py`.
- Changed `ghost/router/explain.py`: added `-t` after `-x`; build command is now `python3 -m compileall -q .` (the `**/*.py` glob is not recursive without globstar and not expanded without a shell); docstring and route explanation say the definition `excel-vba-to-python` must exist first (`atx custom def list`); "exact" removed. Same wording updated in `plugin/skills/route-migration/SKILL.md` and `.kiro/steering/routing-thresholds.md`. `atx` is never executed.
- Tests: removed the strict xfail on `test_atx_dry_run_includes_trust_all_tools_with_non_interactive` (passes); added one test in `tests/unit/test_router_explain.py`. No existing router test needed changes.
- Full suite: `369 passed, 3 failed`. The failures are outside this task and belong to the parallel edits: `tests/test_plugin_package.py::test_mcp_json_uses_ghost_prefix_and_real_module`, `tests/test_review_autopsy_and_packaging.py::test_plugin_manifest_has_schema` (R-15, plugin manifest in progress) and `tests/test_web_accessibility.py::test_dark_border_contrast_at_least_3_to_1` (R-23, web).
## 2026-11-24: task 8.1, R-15 Power packaging
- `plugin/plugin.json`: added `$schema`. Fetched `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` (reachable, HTTP 200; copy kept in `tests/fixtures/agent-plugins-plugin.schema.json`) and validated. The schema has `additionalProperties: false`, so `skills` and `mcpServers` were removed from the manifest (Agent Plugins discovers `skills/` and `mcp.json` by convention). Not checked: whether Kiro itself still needs those two keys; the install checklist below tests this.
- `plugin/mcp.json`: removed `toolPrefix`; command is `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`. Chosen over `python3 -m mcp_server.server` because that needs Ghost's dependencies installed in whatever `python3` Kiro finds and the repo root as working directory; `uvx` needs neither. Cost: `uv` must be installed, and the first start downloads dependencies. `pyproject.toml` gained `[project.scripts] ghost-mcp = "mcp_server.server:main"`.
- Launch check: `uvx --from <local checkout> ghost-mcp` run from `/tmp` answered `initialize` and `tools/list` over stdio (13 tools). The GitHub URL form is untested until the push, because the pushed repository lacks the `ghost-mcp` script until then.
- Test edit (flagged, removes assertions): `tests/test_plugin_package.py` no longer asserts `toolPrefix` starts with `ghost_` or `args == ["-m", "mcp_server.server"]`. It asserts no `toolPrefix`, only documented fields, command `uvx`, last arg `ghost-mcp`, the script target in `pyproject.toml`, plus a new schema validation test. `test_plugin_manifest_has_schema` lost its xfail and passes.
- Docs: Setup section in `plugin/skills/guardrails/SKILL.md` (pointer in the autopsy skill); README "Use the Kiro Power".
### Owner checklist: install the Power from the GitHub URL (after you push)
1. Push this work to `main` of `https://github.com/viraj-dhanushka/Ghost-in-the-Macro` (the `ghost-mcp` script and `plugin/` changes must be on GitHub).
2. On the Mac: `uvx --version` works (install uv if not) and LibreOffice is in `/Applications`.
3. Smoke test outside Kiro: `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp` starts and waits on stdin (Ctrl+C to stop).
4. In Kiro: Powers panel, add a custom Power from the GitHub URL (the repository, folder `plugin/` if Kiro asks for a path).
5. Check the Power appears with no manifest error. If Kiro complains about missing `skills` or `mcpServers`, re-add `"skills": "./skills"` and `"mcpServers": "./mcp.json"` to `plugin/plugin.json` and tell Kiro (the schema test will then need those keys allowed).
6. Check the `ghost` MCP server shows as running, with the tools listed (13 expected, e.g. `analyze_workbook`, `verify_implementation`).
7. Check the seven skills are listed (`autopsy` ... `guardrails`).
8. Ask the agent to autopsy the haunted sample and confirm it reports F-001.
9. Note whether tool names are prefixed by Kiro (expected, replacing `toolPrefix`) and record it in this file.

### 2026-11-24: Fix R-21 (rest), report columns, tested domains, Faithful download (review-fixes task 8.3)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: the report must not call change points "exact hits", must list what input domain was tested, and the Faithful report must be downloadable when Intended also ran.
- What Kiro did: wrote `tests/test_report_details.py` first. In `ghost/report/html.py` the old column is now "Change-point bracket" and "Exact hits" shows only the flip-probing `exact` value (else "not checked"). New `ghost/report/domains.py` builds structured per-input rows (type, min, max, decimal places, or distinct values for strings) from the cases the verifier ran (`res.cases`); `ghost/cli.py` passes them to `build_report`. Optional `tested_domains` added to `Report` (`ghost/models.py`, one field), `report_to_dict` and `proof-report-1.json`, so old reports still validate. `web/jobs.py` keeps `reports/faithful/proof-report.*` as `faithful/...` artifacts when both modes ran; `web/flow.py` serves them via `?mode=faithful` (other values 404); `_job.html` links them.
- Decision: did not reuse `ghost/mutation/run.py` `tested_domains` (returns text); the new module mirrors its rules. Touched `ghost/models.py` and `ghost/report/schema/` beyond the listed folders because the field needs them.
- Tests: `tests/test_report_details.py` (7 passed).
- Verification: full suite `377 passed, 2 failed`; both failures (`test_plugin_package.py::test_mcp_json_uses_ghost_prefix_and_real_module`, `test_review_autopsy_and_packaging.py::test_plugin_manifest_has_schema`) are in the `plugin/` area another sub-agent was editing in parallel, not from this change. `scripts/demo.sh` into a temp folder: discount Faithful PASS (300 + 6, 195 distinct); haunted F-001, Faithful PASS (300 + 9, 198 distinct), Intended with D-001 PASS (1 expected difference, 26 cases, minimal quantity=50). All 5 demo `proof-report.json` validate and carry 3 tested domains. R-21 row set to fixed.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 8.3
### 2026-11-24: Excel-saved fixtures folder (review-fixes task 9.3, R-20 fixtures part)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: a place for workbooks saved by real Excel, and a test that checks the Referee against the values Excel saved. No result is faked.
- What Kiro did: created `tests/fixtures/excel-saved/` with a `README.md` (how to make files with Excel for the web: upload a generated sample, tiny edit, File > Create a Copy > Download a Copy, name like `haunted-excel.xlsx`) and a `.gitkeep`. Added `tests/test_excel_saved_fixtures.py`: for each `.xlsx`/`.xlsm` there it loads the workbook, runs `run_sanity` against a Referee (macros off) and asserts status `matched`, listing every differing cell otherwise. A file with no Excel-saved values fails (it is not a valid fixture). With no files the test skips with a message naming the folder and how to create them. `.gitignore` already allows `tests/fixtures/**` workbooks (checked with `git check-ignore`; no change).
- Verification: with the folder empty, 1 passed, 2 skipped. A temporary generated (non-Excel) haunted workbook exercised the Referee path and failed with the "no Excel-saved values" message, as intended; it was deleted. Not checked: any real Excel-saved file, since none exists yet. Owner action: create the files with Excel for the web.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 9.3
### 2026-11-24: CLI end-to-end test for `scripts/demo.sh` (review-fixes task 9.5, R-20 CLI part)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: cover the shell script itself, not only `cli.main` in-process.
- What Kiro did: added `tests/test_cli_end_to_end.py` (only new file). It runs `bash scripts/demo.sh <tmpdir>` once per module as a subprocess and checks exit code 0; stdout has two `[faithful] PASS` lines, one `[intended] PASS` line and no `FAIL`; discount and haunted folders contain rules.md, traceability.yaml, findings.yaml, mapping.yaml, logic.py, excel.py and `reports/faithful/proof-report.{json,html}`; haunted also has decisions.yaml and `reports/intended/proof-report.{json,html}`; all three report JSONs validate against the schema; haunted findings.yaml mentions F-001; the haunted Intended report has one "expected by decision" mismatch with quantity=50. Case counts are not asserted (left to `test_demo_invariants.py`). Skips with a message if soffice is missing.
- Verification: new file 6 passed (about 9 s). Full suite `413 passed, 2 skipped`. R-20 row in the Resolution table updated to partial (CLI end-to-end done).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 9.5
### 2026-11-24: Performance test (review-fixes task 9.6, R-20 performance part)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: show that a typical sample verifies 500 cases in under 60 seconds against the real Referee.
- What Kiro did: added `tests/test_performance_slow.py` (marked `slow`). It builds the haunted sample, runs `ghost convert`, then times `ghost verify --mode faithful --cases 500 --mutation-cases <GHOST_MUTATION_CASES default, 100>` in-process (flip cases included, LibreOffice start-up inside the timed region) and asserts exit 0, at least 500 cases and under 60 s. The measured time is printed in the test output (run with `-s`). Skips with a message when soffice is missing. Registered the `slow` marker in `pyproject.toml` next to `golden`; added one sentence to the README test section on `-m "not slow"`.
- Decision: slow tests stay in the default run, because this one takes about 6 s.
- Verification: measured 5.3 s (test total 5.9 s). Full suite `415 passed, 2 skipped` in 266 s. R-20 row updated (performance part done).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 9.6
### 2026-11-24: Golden semantics tests (review-fixes task 9.1, R-20 golden part)
- Feature: spec (`.kiro/specs/review-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: give the golden hook real tests, checking each in-scope Excel_Semantics_Table row against the Referee and the generated code.
- What Kiro did: added `tests/golden/test_semantics_golden.py` (marker `golden`, already registered in `pyproject.toml`). It builds the Traps workbook from `samples/make_traps.py`, transpiles it, reads each formula cell from the Referee, and compares both values to the table's expected result (rows 1, 2, 5, 7, 8, 9, 10; 12 cases x 2 engines, plus 2 coverage checks). VBA/date rows 3, 4, 6, 11 are excluded as in the traps script. The R-24 differences stay pinned in `tests/test_referee_libreoffice_differences.py`. Skips with a message if soffice is missing. `make_traps.py` unchanged.
- Verification: `pytest -m golden`: 26 passed, 383 deselected. Full suite: 415 passed, 2 skipped (253 s).
- Spec or task reference: review-fixes-2026-11-24 tasks.md 9.1

## Task 9.4: Property 9 formula fuzzing (review-fixes-2026-11-24)

Added `tests/test_property_formula_fuzzing.py`. Hypothesis draws batches of up to 8 formulas (depth 3, literals -20..20, three input cells A1:A3) from the P0 subset: `+ - * / ^ &`, comparisons, IF, AND, OR, NOT, IFERROR, ROUND/ROUNDUP/ROUNDDOWN, INT, MOD, ABS, MIN/MAX/SUM/AVERAGE. Each batch becomes one workbook, recalculated by one module-scoped Referee and by the transpiled module, and compared with `values_equal`. The seed is 20261124 and the test runs 60 examples (about 7 s, so not marked slow). The R-24 differences and the R-25 ROUND case are kept out of the grammar by construction (literal exponents 1 to 3, like-with-like comparisons, no booleans or text in SUM/`&`, small values).

Result: no mismatches. A one-off run of 1,500 examples with seed 7 also passed. No transpiler bugs found, so no xfail. Not covered: unparenthesised operator precedence (the generator parenthesises every binary operation) and text or boolean input cells. Full suite: 415 passed, 2 skipped.
### 2026-11-24: Re-check the four hooks by hand (review-fixes task 9.2, R-29)
- Feature: agent hooks (`.kiro/hooks/*.json`), sub-agent for spec task execution
- Goal: confirm the golden hook now selects the golden tests (task 9.1) and record real exit codes for all four hooks.
- What Kiro did: ran each hook's `action.command` exactly (`scripts/ghost-py scripts/ghost_hook.py <kind>`) from the repo root with a JSON payload on stdin (`{"hook_event_name":"PostFileSave","file_path":"<abs path>"}`). For report and verify it used a scratch copy of the haunted demo migration under `.kiro/specs/_hooktest/` and a copy of the haunted workbook in `graveyard/`; both were deleted afterwards.
- Results (real output, exit codes):
  - golden (payload: save of `ghost/converter/emit_python.py`): `26 passed, 391 deselected in 4.91s`, exit 0.
  - autopsy (payload: create `graveyard/hooktest.xlsx`): autopsy text with 3 inputs, output `Calculator!B11`, F-001 (`>=` at B7, `>` at B9), exit 0. A payload with no graveyard path prints "no matching path in the hook payload; nothing run.", exit 0.
  - report (payload: save of `_hooktest/decisions.yaml`): `[faithful] PASS` 300 generated + 9 targeted, 198 distinct; `[intended] PASS` with 1 expected difference (F-001 D-001, quantity=50, explains 26 distinct cases); "Proof report: ..." printed, exit 0.
  - verify (payload: save of `_hooktest/logic.py`): same two lines as report, exit 0. Excel cross-check: "not cross-checked against Excel".
- `scripts/ghost_hook.py`: the "0 golden tests selected" branch is now a safety net only. It still prints "GOLDEN HOOK: NOT CHECKED" and exits 1 if the selection ever becomes empty; its text no longer mentions task 9.1.
- Not checked: that Kiro itself fires each hook and passes this payload. The owner checklist above covers it; the golden row now expects `26 passed, 391 deselected`.
- Spec or task reference: review-fixes-2026-11-24 tasks.md 9.2

### 2026-11-24: Bug condition exploration tests for L-02 to L-05 (live-fixes task 1)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: reproduce the live-test wrong results L-02 to L-05 as failing tests before any fix.
- What Kiro did: added `tests/test_live_findings.py`. It builds the repro workbooks `sem_index` (and its `B3` variant), `tier` and `sem_names` with openpyxl into `tmp_path`, and runs them through `report_to_json`, the generated module, the Referee and the web app (FastAPI `TestClient`). Each of the 7 tests encodes the correct behaviour and is marked `xfail(strict=True, reason="L-0n ...")`. Tests that need LibreOffice skip with a message when it is missing. No code was fixed.
- Counterexamples on the unfixed code (run with `--runxfail`, LibreOffice 26.8.3):
  - L-02 `report_to_json`: `TypeError: Object of type ExcelError is not JSON serializable` (`ExcelError('#VALUE!')`).
  - L-02 `sem_index` B4 web job: status `failed`, "Verification found mismatches.", events end with the same `TypeError`, no `report.json`.
  - L-02 panel text: a report-write crash (exit 1, `TypeError`) shows "Verification found mismatches.".
  - L-03: `B3` = `=INDEX(M1:M3,0)`: Referee `9.0`, Ghost `#VALUE!`.
  - L-04 `tier`: B5 boundaries `('price', 166.666, 166.667, exact None)` and `('quantity', 19, 20, exact None)`; `M-e39c9b66` `flip_comparison` on `Calc!B5` survives, "no difference found on 62 distinct cases".
  - L-05 defaults: offered and pre-checked outputs `Calc!C2`, `Calc!C3`, `Calc!C4`.
  - L-05 explicit `Calc!C4`: `POST /verify` returns 200; the job fails with `('translation bug', 'calc_c4', actual None)` and mutation "not checked".
- Verification: every test fails for the reason its finding describes; none passed unexpectedly. Full suite: `415 passed, 2 skipped, 7 xfailed` (236 s).
- Spec or task reference: live-fixes-2026-11-24 tasks.md 1
### 2026-11-24: Fix L-02, serialise Excel errors in reports (live-fixes task 3.2)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution, Coroner agent (`.kiro/agents/coroner.json`) for review
- Goal: a proof report (JSON, HTML, MCP payloads) must hold Excel error values as their code text instead of crashing with `TypeError: Object of type ExcelError is not JSON serializable`.
- What Kiro did:
  - `ghost/report/model.py`: new `excel_error_code(value)`. It duck-types the error (class name `ExcelError`, a string `code` starting with `#`), because a generated module imports the vendored `excel.py` next to `logic.py`, whose `ExcelError` is a different class object from `ghost.runtime.excel.ExcelError`. `_jsonable` checks it first, so every engine-value field (mismatch inputs, expected, actual; mutant `killed_by`; boundary `exact_hits`; findings, decisions, tested domains) serialises errors as text such as `"#VALUE!"`.
  - `ghost/report/html.py`: the Mutation self-check table has a new "Counterexample" column built from `killed_by`, for example "inputs: amount=4; Referee: y=7; new code: y=#REF!". It is empty for survivors.
  - `mcp_server/server.py`: `jsonable` maps Excel errors to their text, both at the top level and through a pydantic `fallback` on `model_dump(mode="json")`. Other unknown types still raise `TypeError`. Before this change, `verify_implementation` with an error in a mismatch raised `PydanticSerializationError`.
  - The CLI writes reports through `write_report` → `report_to_dict`, so it is covered by the model change. CLI console lines are unchanged.
  - `ghost/report/schema/proof-report-1.json`: unchanged. Every engine-value location (mismatch objects, `exact_hits` items, mutant items, `sanity.differences`) is an untyped object, so strings are already accepted.
- Tests: removed the strict-xfail markers from `test_property_3_excel_errors_serialise_as_text` (`tests/test_property_report_excel_errors.py`) and `test_l02_report_to_json_serialises_excel_errors` (`tests/test_live_findings.py`). `test_l02_sem_index_b4_web_job_writes_report` turned strict XPASS with this fix (task 3.4's end-to-end check), so its marker was removed too. The panel-text test (task 3.3) stays xfail. New unit tests: duck typing and both error classes (`tests/unit/test_report_model.py`), the counterexample column (`tests/unit/test_report_html.py`), MCP `jsonable` with errors and the still-rejected unknown type (`tests/unit/test_mcp_server.py`).
- Coroner verdict: approve. Its demo run in a temp dir gave haunted F-001, Faithful PASS (300 generated + 9 targeted, 198 distinct, 0 mismatches), Intended with D-001 PASS with one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0), discount Faithful PASS, and mutation 33/35 (haunted) and 31/33 (discount). Reports with no Excel errors give byte-identical JSON to HEAD. Decimal precision is kept, and the reports contain no server paths. Kiro applied its note to also require the code to start with `#`. Its other note (a boolean counterexample value shows as JSON `true`) was left as display wording.
- Verification: full suite `436 passed, 2 skipped, 5 xfailed` (250 s), run before the `#` tightening. The touched test files were re-run after it: 39 passed, 5 xfailed.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.2
### 2026-11-24: Fix L-02, report a write failure as a write failure (live-fixes task 3.3)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: a job that fails for a reason other than mismatches must not say "Verification found mismatches.". It says "The report could not be written" with the exception type, and shows no server path.
- What Kiro did:
  - `ghost/cli.py`: new `EXIT_REPORT_NOT_WRITTEN = 4` and `ReportNotWritten` (holds the original exception). `run_verification` builds and writes each report through `_build_proof_report` and `_write_proof_report`, and copies the top-level report under the same guard, so any serialisation, schema or I/O failure becomes `ReportNotWritten`. `main` prints one line, `ghost: error: <ExceptionType>: <message>`, and returns 4. Exit 1 still means mismatches not explained by a Decision (and the existing caught CLI errors, unchanged).
  - `web/jobs.py`: new `failure_message(code, lines, *run_dirs)`. Exit 1 says "Verification found mismatches." only when the job output has no uncaught Python traceback and no `ghost: error:` line. Exit 4, exit 1 with a traceback (exception type from the first unindented line after the last `Traceback (most recent call last):` header) and exit 1 with a `ghost: error:` line say "The report could not be written (<ExceptionType>: <message>)." The text goes through `scrub_paths` and is capped at 300 characters. Exit 4 with no error line falls back to "(exit code 4)". Other codes keep "Verification stopped with exit code N.".
  - `mcp_server/server.py`: `call_tool_sync` turns `ReportNotWritten` from `generate_proof_report` or `mutation_check` into `{"error": {"type": "report_not_written", "message": "The report could not be written (<ExceptionType>)."}}`. Only the type is returned, because the exception message can hold a server path.
  - `scripts/ghost_hook.py`: unchanged. It returns the CLI exit code as is; 4 is not 2, so a Kiro hook is never blocked by it.
- Existing test `test_mismatch_exit_is_failed_result` (`tests/test_web_jobs.py`) fakes `sys.exit(1)` with no output, so it is a mismatch run under the new rule and passes unchanged.
- Tests: new `tests/test_report_write_failure.py` (13 tests): panel text for exit 0, exit 1 with mismatch output, exit 1 with a traceback, exit 4 with a typed error line holding a server path, exit 4 with no line, exit 1 with a `ghost: error:` line, exit 3, chained tracebacks; CLI exit code and stderr line; the write helper wrapping `OSError`; a Referee run of the haunted sample with `write_report` failing gives exit 4 and no `proof-report.json`; both MCP report tools return `report_not_written` with no path. Removed the strict-xfail marker from `test_l02_report_write_failure_panel_text` (`tests/test_live_findings.py`); its panel now reads "The report could not be written (TypeError: Object of type ExcelError is not JSON serializable).".
- Verification: `tests/test_report_write_failure.py`, `tests/test_web_jobs.py`, `tests/test_live_findings.py`, `tests/unit/test_mcp_server.py`: 45 passed, 4 xfailed. Full suite: `450 passed, 2 skipped, 4 xfailed` (262 s), 0 failed. The demo invariant tests in the suite passed.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.3
### 2026-11-24: Verify L-02 end to end (live-fixes task 3.4)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution
- Goal: confirm the L-02 "Done when" through the web app, the CLI and MCP with the real Referee (LibreOffice 26.8.3), and log L-02 in the Live-test resolution table.
- What Kiro did:
  - The `sem_index` B4 web test (`test_l02_sem_index_b4_web_job_writes_report`) already passed without its marker after task 3.2. No change.
  - New `test_l02_mismatch_holding_excel_error_is_reported` (`tests/test_live_findings.py`): a workbook with `B2` = `=SUM("5",B1)` (R-24: Referee `#VALUE!`, Ghost 5 + B1) through `TestClient` with input `Calc!B1` and output `Calc!B2`. The job fails with "Verification found mismatches.", and `report.json` lists every mismatch as a translation bug with expected `"#VALUE!"` and actual amount + 5. `report.html` shows `#VALUE!`.
  - New `test_l02_cli_and_mcp_write_reports_with_excel_errors`: `ghost convert` and `ghost verify --mode faithful --mutation-cases 20` on `sem_index` return 0 and write `proof-report.json` (pass, with a mutant killed by a `#REF!` counterexample) and `proof-report.html`. MCP `generate_proof_report` and `verify_implementation` pass and return reports. MCP `verify_implementation` on the `SUM("5",B1)` workbook returns JSON-serialisable mismatches with Referee `"#VALUE!"`.
  - Manual CLI run on `sem_index` in a temp dir: `[faithful] PASS: 300 generated, 288 distinct cases, 0 mismatch(es)`, mutation 3/4. `M-cf558175` (`constant_minus_one`) was killed with actual `#REF!`. `M-2620f56e` (`constant_plus_one` on the R-30 zero, `INDEX(M1:M1,1)`) survived: "no difference found on 90 distinct cases". On the `SUM` workbook, `ghost verify` exits 1, writes the report and prints `referee='#VALUE!' actual=Decimal('5')  inputs: amount=0`, with mutation "not checked" because the unmutated module has a mismatch.
  - `scripts/demo.sh <temp dir>`: discount Faithful PASS (300 + 6 targeted, 195 distinct). Haunted F-001, Faithful PASS (300 + 9 targeted, 198 distinct, 0 mismatches). Intended with D-001 PASS with one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0; explains 26 distinct cases). `ghost mutate` on the demo folders: haunted 33/35, discount 31/33.
  - Added the "Live-test resolution" table to the end of `docs/LIVE_TEST_REPORT_2026-11-24.md`. L-02 is fixed (local; live not re-tested), and L-03 to L-08 are pending.
- Open question for the owner, recorded in the L-02 row: the CLI returns exit 1 with a `ghost: error:` line for errors that are not about writing the report, such as "Referee unavailable", "Referee failed" or an invalid Decision. The web panel shows these as "The report could not be written (…)". Kiro left this unchanged. The other option is to show "Verification stopped: <message>" for these.
- Verification: `tests/test_live_findings.py -k l02`: 5 passed. Full suite: `452 passed, 2 skipped, 4 xfailed` (264 s), 0 failed.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.4
### 2026-11-24: Measure `INDEX(range,0)` on the Referee (live-fixes task 3.5, L-03)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution in the Coroner role (`.kiro/agents/coroner.json`: measure, never assume)
- Goal: record what the Referee returns for `INDEX` with a 0 row or column in every placement before any code change.
- What Kiro did:
  - New probe `tests/index_zero_probe.py`: one openpyxl workbook with 69 probe cells (single column, single row and grid ranges; formula rows and columns above, below, at each edge and inside; a computed 0; `+0`; `SUM` and `AVERAGE`; ranges on another sheet in both directions; single cells). It reads each cell from the Referee and from Ghost's generated code and prints JSON. It depends only on `ghost`, so it also runs in the image.
  - Ran it locally (LibreOffice 26.8.3.1) and in `ghost-local:l03` (LibreOffice 7.4.7.2), built with `docker build --platform linux/amd64 -t ghost-local:l03 .` and run with the probe mounted read-only and `--rm`. Not pushed.
  - Wrote the table to `.kiro/specs/live-fixes-2026-11-24/measurements-l03.md` (raw JSON in `measurements-l03/`) and a summary to the spec's `design.md` ("L-03 Measurements"). The Markdown table was checked against the JSON by script: 69 of 69 rows match.
  - New `tests/test_index_zero_measurement.py` pins the Referee result of all 69 cases (major versions 7 and 26) and Ghost's agreement on the 36 cases it already gets right.
- Result: both LibreOffice versions gave identical results for all 69 cases. Ghost (unfixed) is wrong on 33. 23 are single values inside the row or column span (single column, single row, a grid with one index 0, another sheet, a computed 0, `+0`), where the Referee intersects and Ghost gives `#VALUE!`. 10 are inside `SUM` or `AVERAGE`, where the Referee aggregates the whole row, column or grid wherever the formula is and Ghost gives `#VALUE!`. A grid with both indexes 0, or a single 0, is `#VALUE!` on both sides in every placement measured.
- Found beyond the spec: grids with one non-zero index, ranges on another sheet, a computed 0 and the aggregate case are not in Property 4 or the L-03 bug condition. Task 3.7 must cover them or mark the cells "not converted". The steering line "`INDEX(range,0)` on a multi-cell range gives `#VALUE!`" is contradicted; task 3.8 replaces it.
- Not checked: Excel (Excel 365 spills instead), a formula inside both the rows and columns of a grid (circular), whole-column references, defined-name ranges, area numbers, `INDEX` with 0 inside other functions, a computed 0 inside an aggregate, array-entered formulas.
- No engine code changed.
- Verification: `tests/test_index_zero_measurement.py`: 106 passed (4 s). Full suite: `558 passed, 2 skipped, 4 xfailed` (271 s), 0 failed (452 before, plus these 106).
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.5
### 2026-11-24: Fix L-03, implicit intersection in `INDEX` (live-fixes task 3.7)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution in the Coroner role (measure, never assume). Hooks: none fired. Agents: none invoked.
- Goal: make `INDEX` with a 0 row or column match the Referee, following the rules measured in task 3.5 (`measurements-l03.md`).
- What Kiro did:
  - `ghost/converter/emit_python.py`: `_Rng` takes an optional origin (`top`, `left`), emitted only for `INDEX` ranges. The `INDEX` call site passes the formula cell's own `at=(sheet, row, column)` as constants. New `_index_pick` holds the shared argument rules. `_index` (single-value context) reduces a 0 row or column by implicit intersection with the formula's row or column number, whatever sheet the range is on (rules 1, 2, 3, 7, 8). Both indexes 0 on a grid is `#VALUE!` (rule 4). Rules 5 and 6 (R-30) are unchanged. New `_index_area` is used when `INDEX` is a direct argument of `SUM`, `AVERAGE`, `MIN`, `MAX`, `AND` or `OR`. It returns the selected row, column, grid or cell as a range (rule 9). Generated code stays deterministic and stdlib-only.
  - Aggregate context (rule 9): implemented, because the emitter already passes ranges to aggregates as `_Rng`. `INDEX` returning a sub-range was a small change, so no aggregate cell is "not converted".
  - Measured more cases on the Referee (new probe `tests/index_zero_contexts_probe.py`, 84 cells, LibreOffice 26.8.3.1 locally and 7.4.7.2 in `ghost-local:l03`, run with `--rm`, not pushed): `INDEX` with 0 inside `MIN`, `MAX`, `AND` and `OR` aggregates the selection. A computed 0 inside an aggregate behaves like a literal 0. Inside `IF`, `ROUND`, `IFERROR` and `CHOOSE` at the top level, and in arithmetic inside `SUM`, `INDEX` intersects. A defined-name range behaves like the range. On a grid an omitted column is 0, so `INDEX(Q5:R7,2)` intersects by column (the old Ghost code returned column 1 everywhere). Fractions truncate. `"0"`, FALSE and an empty cell count as 0. A negative index is `#VALUE!` (the old Ghost code gave `#REF!`). An index past the end is `#REF!` on 26.8.3.1 and `#VALUE!` on 7.4.7.2. Ghost keeps `#REF!` for that case, as it did before.
  - `ghost/converter/subset.py`: an `INDEX` that can select a whole row or column and is passed through `IF`, `IFERROR` or `CHOOSE` inside an aggregate is listed as "not converted" with reason `INDEX_PASSED_THROUGH`. The Referee keeps it as a reference (24 from row 9), and `IFERROR` gives 24 on row 6 but 0 on row 9. Ghost cannot reproduce that.
  - Owner decision (asked during the task): keep the negative-index fix. `test_l02_cli_and_mcp_write_reports_with_excel_errors` asserted that a mutant counterexample on `B4` held `#REF!`. That error came from the `constant_minus_one` mutant `INDEX(M1:M1,-1)`, which now gives `#VALUE!` like the Referee. The assertion now accepts `#REF!` or `#VALUE!` and still requires the error text in the JSON and HTML report.
- Tests: removed the strict-xfail markers from `test_l03_index_row0_inside_range_matches_referee` (`tests/test_live_findings.py`) and both Property 4 tests (`tests/test_property_index_zero.py`). New `test_ghost_agrees_with_referee_after_l03_fix` in `tests/test_index_zero_measurement.py`: Ghost now matches all 69 measured cases, and none is "not converted". New `tests/test_index_zero_contexts.py` (Referee pinned per major version, Ghost against the measured result and the installed Referee, the not-converted listing, and the emitted `at=` and `_index_area` text with determinism).
- Found, not fixed (outside L-03): `SUM(IF(TRUE,N5))` and `SUM(IF(TRUE,INDEX(N5:N7,1)))`, with text in N5, give 0 on the Referee and `#VALUE!` in Ghost, because `IF` passes a reference into `SUM`. This was true before this task as well. `INDEX` past the end differs between LibreOffice versions (see above). This also affects the existing `index_out_of_range` case in `tests/test_review_semantics.py` on 7.4.7.2. Task 3.8 should add both to the excel-semantics notes.
- Verification: the targeted files (`test_property_index_zero.py`, `test_index_zero_measurement.py`, `test_index_zero_contexts.py`, `test_live_findings.py`, `test_live_preservation.py`, `test_review_semantics.py`) all pass. Full suite: `828 passed, 2 skipped, 3 xfailed` (282 s), 0 failed. The 3 xfails left are L-04 and L-05. `scripts/demo.sh <temp dir>`: discount Faithful PASS (300 + 6 targeted, 195 distinct). Haunted F-001, Faithful PASS (300 + 9 targeted, 198 distinct, 0 mismatches). Intended with D-001 PASS with one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0). `ghost mutate` on the demo output: haunted 33/35, discount 31/33.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.7
### 2026-11-24: Golden tests, docs and web check for L-03 (live-fixes task 3.8)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agent for spec task execution in the Coroner role (measure, never assume). Hooks: none fired. Agents: none invoked; the Coroner review was done in role, not by the `coroner` sub-agent.
- Goal: meet the L-03 "Done when" (golden tests against the Referee and Ghost, the extended repro passing Faithful on the web) and correct the semantics notes.
- What Kiro did:
  - New `tests/golden/test_index_zero_golden.py` (`@pytest.mark.golden`, so the golden hook runs it): 20 cases, each checked against a pinned value twice, once for the Referee and once for the generated code. Single column `$M$5:$M$7` with row 0 from rows 5, 6, 7 and from `X6` and `INDEX(..,0,1)` (7, 8, 9, 8, 8), and from rows 4, 8, 12, 9 outside (`#VALUE!`). Single row `$E$20:$G$20` with column 0 from columns E, F, G and from `F15` (21, 22, 23, 22), and from D and H (`#VALUE!`). Single cell `T5` (R-30) from rows 5 and 9 (55). The live repro `B3` = `INDEX(M1:M3,0)` (9). The expected values are the task 3.5 measurements, identical on both LibreOffice versions.
  - New `test_l03_sem_index_b3_b4_web_job_passes_faithful` (`tests/test_live_findings.py`): the L-02 repro with `B3` = `=INDEX(M1:M3,0)`, input `Calc!B1`, outputs `Calc!B3` and `Calc!B4`, through FastAPI `TestClient` with the real Referee. Result (LibreOffice 26.8.3.1): job done, Faithful pass, 300 generated, 0 targeted, 0 mismatches, `report.html` 200, mutation 7/10. The 3 survivors are `constant_plus_one` and `constant_minus_one` on `M2` (no output reads `M2`: `B3` intersects row 3, `B4` reads `M1`) and `constant_plus_one` on `B4` (the R-30 index, as in task 3.4).
  - `.kiro/steering/excel-semantics.md`: replaced the wrong bullet ("`INDEX(range,0)` on a multi-cell range gives `#VALUE!`") with a pointer, and added the section "INDEX with a 0 row or column (L-03)": the measured rule table with a pointer to `measurements-l03.md`, the index and context rules, the `INDEX_PASSED_THROUGH` "not converted" case, "Excel: not checked; Excel 365 spills", and "Found, not fixed" for the two task 3.7 items. Cells that were never measured (a single cell or a length-1 dimension inside an aggregate) say "not measured".
  - Re-measured the two task 3.7 items with a one-off probe outside the repository (`SUM(IF(TRUE,N5))`, `SUM(IF(TRUE,INDEX(N5:N7,1)))` with "x" in N5, and `INDEX(M1:M3,5)`), locally and in `ghost-local:l03` with the working tree's `ghost` copied in (`docker run --rm`, not pushed). Both `SUM(IF(...))` cases: Referee 0, Ghost `#VALUE!` on both versions. `INDEX(M1:M3,5)`: Referee `#REF!` on 26.8.3.1 and `#VALUE!` on 7.4.7.2; Ghost `#REF!`.
  - Version check of the `#REF!` pins: ran the INDEX-related suites inside `ghost-local:l03` (LibreOffice 7.4.7.2) with the working tree copied in and pytest added from the local venv. Before the change, `tests/test_review_semantics.py::test_transpiler_matches_referee[index_out_of_range]` failed there (`values_equal('#VALUE!', ExcelError('#REF!'))`). The other `#REF!` pins are not affected: the unit tests do not use the Referee, `tests/test_index_zero_contexts.py` already keys `PAST_END` by major version, and `test_l02_cli_and_mcp_write_reports_with_excel_errors` accepts either error.
  - `tests/test_review_semantics.py`: `index_out_of_range` stays in `PASSING` (so the workbook layout and every formula's row are unchanged) but leaves the Ghost-equals-Referee parametrisation. Two new tests replace it: `test_version_dependent_ghost_result` asserts Ghost gives `#REF!` on any version, and `test_version_dependent_referee_is_pinned` pins the Referee result by major version (`VERSION_DEPENDENT_REFEREE`: 26 `#REF!`, 7 `#VALUE!`; unknown versions skip with a message) and, where the pinned value equals Ghost's (26), still asserts Ghost equals the Referee. On 26.8.3.1 the check is the same as before.
  - `docs/LIVE_TEST_REPORT_2026-11-24.md`: the L-03 row of the Live-test resolution table is filled in.
- No engine code changed in this task, so `scripts/demo.sh` was not re-run; the demo invariant tests passed in the full suite.
- Verification: `pytest -m golden`: 67 passed, 809 deselected (26 before, plus 41). Inside `ghost-local:l03` (LibreOffice 7.4.7.2): `tests/test_review_semantics.py`, `tests/golden`, `tests/test_index_zero_measurement.py`, `tests/test_index_zero_contexts.py`, `tests/test_property_index_zero.py`, `tests/test_live_preservation.py`, `tests/test_referee_libreoffice_differences.py` and the two L-03 tests in `tests/test_live_findings.py` (including the web check): 511 passed. Full suite locally: `871 passed, 2 skipped, 3 xfailed` (294 s), 0 failed. The 3 xfails are L-04 and L-05.
- Not checked: Excel; the full suite inside the 7.4.7.2 image (task 7.4).
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.8

## Task 3.10 (live-fixes-2026-11-24): L-04 integer exact hits, verified after an interrupted run

An earlier sub-agent run was interrupted before reporting. I treated its uncommitted work as unverified and reviewed it.

- `ghost/verifier/flip.py`: for an integer flip, `below` and `above` are each re-evaluated with a trace hook marked `compared = True`. An exact hit is recorded only when the module reports two equal numbers, and only when exactly one of the two points is equal. It is never inferred from the operator. When the module reports no values, `FlipSummary.exact_not_checked` records the condition and input, and a note says "exact hit not checked". If the evaluation budget runs out inside the check, the flip is kept with `exact=None` and `exact_cut_short` is set.
- `ghost/converter/emit_python.py`: `_with_sides` wraps `trace` only when it has `compared = True`. Plain `trace(cid, bool)` callers and hand-written modules are unchanged. Output is deterministic (tested). The L-03 INDEX changes were left as they were.
- `tests/test_flip_integer_exact.py` was complete and I made no changes. It covers haunted B7/B9 at quantity 50, no equality for `B1*2>=101`, a hand-written module, `AND(...)`, two-argument hooks and a budget cut. No test was weakened or deleted. The small-value retry (3.11) is not started.
- Results: exact-hit, flip-integer, condition-flip and flip-reporting tests gave 23 passed, 1 xfailed. The single-input property passes and the product property still xfails until 3.11. Full suite: 882 passed, 2 skipped, 4 xfailed, 0 failed.
- `scripts/demo.sh` (temp folder): discount Faithful pass. Haunted has F-001 and Faithful PASS with 0 mismatches (300 generated + 9 targeted, 198 distinct, same as before). Haunted with D-001 Intended PASS with exactly one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0).
- `ghost mutate` on the demo output: haunted 33/35, discount 31/33. Both survivors on each sample are the `rounding_mode` mutants M-3cbed5dc and M-687cf270, as before. Haunted ran 98 distinct cases per mutant and discount 96.
- Haunted boundaries now report quantity 50 as an exact hit for both B7 (`>=`) and B9 (`>`). Before, `exact` was None.
- Not checked: the discount demo's own case counts were not captured in this run.

### live-fixes-2026-11-24, task 3.11 (L-04: small-values retry in flip search)

- Change: `ghost/verifier/flip.py` only. When a flip has no confirmed exact hit, `_search` calls `_retry_small_values`. It reruns the search on the same input with every OTHER numeric input set to one of 1, 2, 4, 5, 10 (only where the value is inside that input's type, min and max; one variant per value). The first hit confirmed by the compared-values trace (`prober.compared`, equal numbers) is kept as a `Flip` whose `others` hold the retry values. Decimal hits from `_exact_hit` are now confirmed through the trace before a retry flip is kept; nothing is inferred. A retry that lands on an already searched point upgrades a `Flip` that has no exact hit and never duplicates one (keeps Property 6 at one flip per input and other values).
- Budget: `_RETRY_EVALS_PER_CONDITION = 600`, `_RETRY_EVALS_TOTAL = 2000`, one retry per (condition, input). Reaching a cap adds `FlipSummary.retry_cut_short` and a line in `FlipSummary.notes()` (the `boundary_notes`). Output is deterministic for a seed.
- Not done (task 3.12): exact hits are not wired into `ghost/cli.py` `flip_extra` or the mutation check. The L-04 test in `tests/test_live_findings.py` is unchanged.
- Tests: removed the strict-xfail marker from `test_property_5_product_threshold_exact_hit_confirmed` (passes). `test_property_condition_flip.py`, `test_flip_reporting.py`, `test_flip_integer_exact.py`, `test_review_proof_strength.py`: pass (32 passed with the exact-hit file).
- Full suite: `883 passed, 2 skipped, 3 xfailed`.
- `scripts/demo.sh` (temp dir): discount Faithful PASS, 300 generated + 6 targeted, 195 distinct. Haunted F-001 raised; Faithful PASS, 300 + 9 targeted, 198 distinct, 0 mismatches; Intended with D-001: 1 mismatch "expected by decision", quantity=50, Referee 6.0, new code 0. Demo took 7.7 s. Case counts are unchanged from the earlier baseline.
- `ghost mutate` on the demo output: haunted 33/35 killed, discount 31/33 killed (unchanged). Survivors are the same two `rounding_mode` mutants.
- STOP-AND-ASK conditions: none triggered.
- Skeptic note: the retry cannot raise exact hits in haunted because its conditions have a single-input threshold that already has a confirmed integer hit. The retry's value shows up only in `tier`-style product conditions.

### live-fixes-2026-11-24, task 3.12 (L-04: exact hits in verification and mutation, verified after an interrupted run)
- An earlier run was interrupted before reporting. It had removed the strict-xfail marker from `test_l04_tier_exact_hit_and_flip_mutant_killed` and logged nothing. I checked its work instead of trusting it.
- Review: `git diff` on `ghost/cli.py` and `mcp_server/server.py` holds only the L-02 changes (report-not-written handling). `ghost/verifier/flip.py` matches the 3.10 and 3.11 entries. Both `run_verification` and MCP `verify_implementation` already pass `flip_cases(flips, ...)` as `extra_cases`, and `run_verification` also passes it as the mutation check's `targeted` cases. `Flip.cases()` includes the exact value and the retry values in `others`. No code change was needed in this task; no xfail marker was re-added and no test was weakened.
- L-04 test alone: 1 passed.
- Tier repro through the web app (TestClient, real LibreOffice 26.8.3): Faithful pass, 300 generated + 16 targeted. Boundaries on Calc!B5: `price` exact 500.000, `quantity` exact 500. Mutation 5/5 killed; `flip_comparison` on B5 killed at price 500.000, quantity 1 (Total = 500).
- Exact-hit, proof-strength, flip-reporting, flip-integer and condition-flip tests: 32 passed. Full suite: `884 passed, 2 skipped, 2 xfailed` (the 2 xfails are L-05), 0 failed.
- `scripts/demo.sh` (temp dir): discount Faithful PASS (300 + 6 targeted, 195 distinct). Haunted F-001, Faithful PASS (300 + 9, 198 distinct, 0 mismatches). Intended with D-001: one "expected by decision" mismatch at quantity=50, Referee 6.0, new code 0. `ghost mutate`: haunted 33/35, discount 31/33 (survivors: the two `rounding_mode` mutants). Storyline and scores unchanged.
- Updated the L-04 row of the Live-test resolution table.
- Not done: the separate Skeptic sub-agent review of L-04 (still to do). Not checked: Excel, the live site, LibreOffice 7.4.7.2.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.12

### Task 3.14 (live-fixes-2026-11-24): L-05 defaults, Coroner role

- New shared rule `not_offerable_outputs(workbook)` in `ghost/autopsy/classify.py`: cells from `find_not_converted` (including dependents and the INDEX_PASSED_THROUGH case), cells with a `not_verifiable` feature (volatile, external link), and their transitive dependents.
- `classify()` gives such formula cells INTERMEDIATE instead of OUTPUT unless the user selected them explicitly. This covers `generate_mapping` defaults, `ghost._analyse` and the `ghost autopsy` text, and MCP `analyze_workbook`. `web/flow.py` `_describe` also removes them from the offered output boxes; they stay in the "not converted" and "not verifiable" lists.
- Tests: `test_property6_bad_cells_never_offered_as_outputs` and `test_l05_autopsy_does_not_offer_not_converted_output` pass with their xfail markers removed. The explicit-C4 test (task 3.15) is still strict xfail (1 xfailed). `tests/test_web_samples.py` default boxes unchanged.
- Full suite: 885 passed, 2 skipped, 1 xfailed, **1 failed**: `tests/unit/test_mapping_text_outputs.py::test_concatenation_and_text_function_are_string`. It builds `=TEXT(B1,"0.00")`, which `find_not_converted` lists ("function TEXT is outside the P0 subset"), and expects the default mapping to offer it as a `string` output. That contradicts L-05 (not-converted cells are not default outputs). Test left unchanged; owner decision needed (see task report).
- `scripts/demo.sh`: discount Faithful PASS (300 + 6 targeted, 195 distinct); haunted F-001, Faithful PASS 0 mismatches (300 + 9, 198 distinct); Intended PASS with 1 mismatch "expected by decision" at quantity=50, referee=6.0, actual 0. The script does not print mutation scores; the mutation floors are asserted by `tests/test_mutation_samples.py`, which passed.

### Task 3.12 follow-up (live-fixes-2026-11-24): Skeptic findings on L-04, Skeptic role
- Goal: close the gaps a Skeptic review found in the L-04 exact-hit work. Tests first in `tests/test_flip_exact_followups.py` (openpyxl into `tmp_path` or hand-written modules; no LibreOffice).
- Decimal exact hits are confirmed too (`ghost/verifier/flip.py`, decimal branch of `_search`). A hand-written module whose trace does not report the compared values now gets `exact=None` and the "exact hit not checked" note, as for integers (repro `t1b`). Transpiled modules keep their hits: haunted, discount and the tier repro (price 500.000 with quantity 1, quantity 500 with price 1).
- `flip_cases` keeps confirmed exact-hit cases first when the 200-case cap truncates, and the order is unchanged when nothing is cut. An exact-hit case still dropped is listed in `FlipSummary.exact_not_run`, its boundary row gets `exact_note = "found but not run: case limit"`, and `boundary_notes` names the count. `flip_boundaries(flips, summary=...)` takes the summary. On the Skeptic's 90-condition workbook (`t7`) 24 rows are marked and the note counts 201 hits not run; before, none were marked.
- New optional boundary fields `exact_others` (the other input values the hit needs, as text) and `exact_note`; schema backward compatible. `exact_hit_text` (in `ghost/models.py`) gives the cell text, for example `500.000 (with quantity = 1)`, used by the CLI line and the existing HTML exact-hit cell. The HTML table rework stays with task 5.2. Side effect: haunted shows `exact hit 50 (with delivery_distance_km = 12, unit_price = 19.95)`, values the hit was found with that do not matter for that condition. The probe cannot tell which others matter.
- The CLI line says `exact hit ...` instead of `off-threshold` for a row with an exact hit. Removed the duplicated `_SMALL_VALUES`, `_RETRY_*` and `retry_cut_short` definitions (no behaviour change).
- Budget note: with no condition found it says "stopped at N evaluations before any condition was found; no condition was checked", not "0 pairs". A pair searched from some but not all base points is no longer counted as not checked; it is listed as searched from only some base points. A line says conditions not yet reached are not listed.
- Report-only items: (a) a decimal literal finer than the probe step now adds the note "decimal thresholds finer than the 0.001 probe step are not checked (formula literals: ...)" when a decimal input exists (small change, done). (c) With a hand-written `logic.py`, a boundary note says flips come from the transpiled module (done, `cli._HAND_WRITTEN_FLIP_NOTE`). (b) A fully negative small-value retry shows "not checked" though it ran: deferred, not changed.
- Checks: flip and exact-hit test files, `tests/test_review_proof_strength.py`, the L-04 test in `tests/test_live_findings.py` pass; full suite 899 passed, 2 skipped, 1 xfailed with `test_concatenation_and_text_function_are_string` deselected (L-05, owner's decision). `scripts/demo.sh`: discount Faithful PASS (300 + 6, 195 distinct); haunted F-001, Faithful 0 mismatches (300 + 9, 198 distinct); Intended one "expected by decision" mismatch at quantity=50, Referee 6.0, new code 0. `ghost mutate`: haunted 33/35, discount 31/33 (unchanged).
- Not checked: Excel, the live site, a second Skeptic pass.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.12
### Task 3.14 close-out (live-fixes-2026-11-24): test edit after the owner's L-05 decision
- Owner decision: `=TEXT(B1,"0.00")` is not converted (TEXT is outside the P0 subset), so under L-05 it is no longer a default output. The test must select it explicitly instead of the default mapping offering it.
- Edit: `tests/unit/test_mapping_text_outputs.py::test_concatenation_and_text_function_are_string`. Only the TEXT case changed: it now calls `generate_mapping(wb, user_outputs=["S!B2"])` and still asserts `{"tier": "string"}`. A comment cites L-05 and the owner's decision. The `&` concatenation case still uses the default mapping with its assertion unchanged. No other assertion changed.
- Engine check: `classify()` assigns OUTPUT to any selected formula cell before consulting `not_offerable_outputs`, so an explicit selection is honoured for a not-converted cell. The edited test passing confirms it. Rejecting such a selection is task 3.15 (`test_l05_explicit_not_converted_output_is_rejected` still strict xfail). No engine change in this task beyond L-05.
- Results: the edited file, `tests/test_property_not_converted_outputs.py`, `tests/test_web_samples.py`: 12 passed. `tests/test_live_findings.py`: 9 passed, 1 xfailed (explicit C4, task 3.15). Full suite, nothing deselected: 900 passed, 2 skipped, 1 xfailed, 0 failed.
- `scripts/demo.sh` (temp dir): discount Faithful pass; haunted F-001, Faithful 0 mismatches (300 + 9, 198 distinct); haunted with D-001, Intended exactly one "expected by decision" mismatch at quantity=50, Referee 6.0, new code 0.
- Not checked: Excel, the live site, LibreOffice 7.4.7.2. Nothing committed.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.14
### Task 3.15 (live-fixes-2026-11-24): reject explicit not-converted outputs, list them in the report (L-05)
- Owner decision followed: `classify()` and `generate_mapping(user_outputs=...)` still honour an explicit not-converted selection (`tests/unit/test_mapping_text_outputs.py` relies on it). Rejection happens at verification time.
- One shared function, `require_verifiable_outputs` in `ghost/cli.py` (raises `UnverifiableOutput`, a `CliError`), built on `unverifiable_output_reasons` in `ghost/autopsy/classify.py`. The reason is the `find_not_converted` text or the not-verifiable flag; a dependant names the cell it reads. Callers: web `POST /verify` (422 before any session state is stored), MCP `verify_implementation`, `generate_proof_report`, `mutation_check` (`invalid_argument`, argument `outputs.<cell>`), `ghost rules`, `convert` and `verify`.
- Report: optional `not_converted` (`{cell, reason}`) in `Report`, `report_to_dict`, `proof-report-1.json` and a "Not converted" HTML section; omitted when empty, so existing reports are byte-identical.
- Tests: `tests/test_not_converted_rejection.py` (new); strict-xfail marker removed from `test_l05_explicit_not_converted_output_is_rejected`, whose assertions already described rejection (422, names `Calc!C4`, "not converted", no "translation bug"). The message does not contain the words "translation bug".
- Finding while testing: NOW, TODAY and similar are also outside the P0 subset, so they are reported as "not converted" (and their dependants as "depends on not-converted cell"). The "not verifiable as-is" wording only appears for a convertible cell carrying the flag; it is covered by a unit test that adds the flag.
- Repro through the web app, default boxes (B2 -> C2, C3): Faithful pass, report lists `Calc!C4` (test `test_default_boxes_pass_faithful_and_report_lists_c4`).
- Coroner review (autopsy defaults and the not-converted listing): defaults exclude C4 on the three bundled samples and the repro; the listing matches `find_not_converted` cell for cell. No separate Coroner agent run was made.
- Results: full suite 908 passed, 2 skipped, 0 failed. `scripts/demo.sh` (temp dir): discount Faithful pass; haunted F-001, Faithful 0 mismatches (300 + 9, 198 distinct); haunted with D-001, Intended exactly one "expected by decision" mismatch at quantity=50, Referee 6.0, new code 0. The demo script does not run the mutation check; the mutation sample tests in the suite pass.
- Not checked: Excel, the live site, LibreOffice 7.4.7.2, `test_live_findings.py` marker audit for task 3.16. Nothing committed.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 3.15

## Task 5.2: L-06 boundary table layout (live-fixes-2026-11-24)

- Fix in `ghost/report/html.py` (`_bracket_text`, `_threshold_text`, boundary table): brackets are text in "Change-point bracket" for both row kinds; "Owner of threshold" is only `at`/`above` (flip rows "not checked"); Threshold is the constant, "calculated", or "not checked"; "Exact hits" unchanged. Non-bracket `exact_hits` entries are flattened to plain text, so error text stays visible (`tests/test_property_report_excel_errors.py` passes).
- "calculated": `BoundaryResult` had no way to say it, so I added optional `threshold_constant` and `threshold_calculated` (models, schema, `Flip`). `find_flips` classifies each (condition, input) after the search from the compared values at below and above: a side that stays the same and does not move when another numeric input changes is the constant (a literal or a parameter cell); otherwise "calculated". Tested in `test_l06_flip_probing_reports_constant_and_calculated_thresholds`. Limit: only numeric other inputs are varied, and a condition whose compared values the module does not report stays "not checked".
- Test edit ordered by L-06: `tests/test_report_details.py::test_html_separates_change_points_from_real_exact_hits` asserted `"first_changed" in rows[0]`. Its intent is that the bracket values appear under the renamed column, so that assertion now checks `"49 → 50"` appears and `first_changed` does not. Nothing else changed in it. The 5.1 xfail markers were removed; no other test was weakened or deleted.
- exact_others trimming: not done. The graph of which inputs a condition depends on is not available to the report, and the hit's other values come from the case that was run, so I left "(with delivery_distance_km = 12, unit_price = 19.95)" on haunted.
- Results: full suite 915 passed, 2 skipped, 5 xfailed (the L-07 markers waiting for 5.4/5.5). `scripts/demo.sh` in a temp dir: haunted F-001, Faithful 0 mismatches (300 + 9, 198 distinct), Intended one expected-by-decision mismatch at quantity=50 (Referee 6.0, new 0), discount Faithful pass (300 + 6, 195); `ghost mutate` haunted 33/35, discount 31/33. Haunted report shows quantity 50 as an exact hit on B7 and B9.
- Not checked: Excel, the live site. Not touched: `coverage.py`, `mutation/run.py`, `strategies.py`. Nothing committed.

### Task 5.4 (L-07): effective domain, owner decision

- STOP-AND-ASK raised at the start of 5.4: clamping alone would drop the scenarios sample `gross_income` = 60,000 (above `default_max` 10,000) and the -1 cases. Options given: clamp as written, widen to include the sample, or label the survivor domain. **Owner decision: widen the domain to include the sample value, then clamp.**
- Definition (one function, `ghost/verifier/domain.py`: `effective_domain`, `effective_domains`, `clamp`, `in_domain`). Per numeric input: min = declared `IOSpec` min, or no lower bound; max = the largest of the declared max, `default_max` when none is declared, and the workbook's sample value. Scenarios `gross_income` is therefore 0..60,000; other inputs 0..10,000.
- Used by: the Hypothesis strategies (`VerifyConfig.sample`, applied in `verify`), `candidate_inputs(..., domains=)` (clamps every value; -1 becomes 0 where min is 0), flip probing (`_bounds` in `flip.py`, plus a `domains=` guard in `flip_cases`), the mutation check (`run_mutation` drops targeted cases outside the domain; `ghost/cli.py` passes `sample=base` and `domains`), the MCP `verify_implementation` path, and the report's "Tested domains" table (verification now generates up to the same maximum).
- Side effect: with no declared max the flip search range was `max(1000, 10 x sample)` and is now `max(10000, sample)`, so the "no flip found" note reads `[0, 10000]` instead of `[0, 1000]`. No flip results changed on the samples.
- Test 5.3 (`tests/test_property_targeted_domain.py`): docstring records the owner decision; `effective_domain` helpers take the base value as the sample; `_candidate_inputs` passes `domains`. Assertions are unchanged. All five tests XPASSed, so the `L-07` strict-xfail markers were removed. 5.5's "same case set" requirement is met by the shared function (the survivor-domain test passes for haunted, discount and scenarios), so no separate 5.5 work was done beyond what the owner asked; 5.5's docs row and its call on counts remain for the orchestrator. Added `tests/unit/test_effective_domain.py` (2 tests).
- Mutation, `ghost mutate --mode faithful`, before -> after:
  - haunted 33/35 -> 33/35. Survivors: `Calculator!B9` and `B10` `rounding_mode`, "no difference found on 98 distinct cases; ... min -1, max 10000" -> "95 distinct cases; ... min 0, max 10000".
  - discount 31/33 -> 31/33. Same two survivors; 96 -> 93 distinct cases, min -1 -> min 0.
  - scenarios 55/132 -> 54/132. 77 -> 78 survivors, all "no difference found on 78 -> 58 distinct cases"; the domain text now reads `gross_income: min 0, max 60000`, `dependants`/`other_deductions` min 0 (was min -1). The one lost kill is `M-cb3d2f05` `Model!C6` `constant_plus_one`, which only a -1 case caught. Verification: 300 generated, distinct 176 -> 152.
- Storyline unchanged: discount Faithful pass (300 + 6, 195 distinct); haunted F-001, Faithful 0 mismatches (300 + 9, 198 distinct); haunted + D-001 Intended one "expected by decision" mismatch at quantity=50 (Referee 6.0, new code 0), explains 26 distinct cases. `scripts/demo.sh` run into a temp folder.
- Full suite: 920 passed, 2 skipped, 0 xfailed (before the 2 new unit tests). Not checked: Excel, the live site. Nothing committed, no AWS.

### Task 5.5 (L-07): one case set, sample note in the report

- Checked on real output (`scripts/demo.sh` into a temp folder, `ghost mutate --mode faithful` on haunted, discount, and a scenarios convert with `Model!B2,B3,E2` -> `B19,B20` then mutate): no survivor reason names a value outside the "Tested domains" ranges. Haunted and discount: min 0, max 10000. Scenarios: `gross_income` min 0, max 60000, others min 0, max 10000.
- Case sets: verification cases (198 distinct on haunted) and mutation cases (95 on haunted, 93 on discount, 58 on scenarios) are still different sets with the same ranges. I labelled instead of merging: the table section now begins "Ranges of the verification cases. Mutation cases and their survivor reasons stay inside the same ranges." The survivor text is unchanged because `tests/test_mutation_wording.py` asserts its "N distinct cases" prefix and tests must not be weakened.
- Sample note: `tested_domain_rows(..., sample=base)` adds `max_includes_sample` to a row when the workbook's value is above the declared or default max; HTML prints "Max of gross_income includes the workbook's own value 60000." Optional field added to `proof-report-1.json`; `ghost/cli.py` passes `sample=base`. Scenarios shows it; haunted and discount do not.
- Results: haunted 33/35, discount 31/33, scenarios 54/132 (was 55/132; `M-cb3d2f05` needed a -1 case). Storyline unchanged: haunted 300 + 9, 198 distinct, Intended one expected-by-decision mismatch at quantity=50. Full suite: 922 passed, 2 skipped (before the one test added afterwards, which passes). L-07 row added to the Live-test resolution table.
- Not checked: Excel, the live site. Nothing committed, no AWS. A stray `--help` file I created by running `make_scenarios.py --help` was deleted.
### Task 5.7 (L-08): aim cases at the winning row (live-fixes-2026-11-24)
- New `ghost/verifier/selection.py` (`find_selection_cases`, `SelectionSummary`) and `_probe_selection` in `ghost/cli.py`. No change to the generated code. The search runs the transpiled Faithful module with `_max`, `_min` and `_match` wrapped, so each call reports which argument it picked (call identified by function, source line, call number). It evaluates the base point, a ladder along each numeric input, and 600 seeded random points inside the effective domains (`ghost/verifier/domain.py`). For each pair of picked positions it then bisects between the closest two points that picked them until neighbouring values differ, which can reveal a third winner. Cases are the two neighbours of each change point, plus one point for each position not seen at a change point. Bounds: 3000 module evaluations and 60 cases; hitting either adds a `boundary_notes` entry. Same seed gives the same cases.
- The cases are appended to `flip_extra`, so they reach the verifier (`extra_cases`) and the mutation check (`targeted`) and are checked against the Referee like any other case.
- Tests (`tests/test_selection_search.py`, 4 pass, no LibreOffice): a MIN/INDEX-MATCH workbook where row C wins only for x = 146..154 of 0..10000. The search finds winning cases for C, A and B, a constant mutant on C is killed by the cases, the search is deterministic, the cap is reported, a workbook without MAX/MIN/MATCH gives no cases, and the CLI helper returns the cases.
- Scenarios (`Model!B2,B3,E2` -> `B19,B20`, `ghost mutate --mode faithful`, LibreOffice 26.8.3): **before 54/132, after 70/132** (53%). Cases: 300 generated + 54 targeted (was +0), 206 distinct (was 152). Wall time of the mutate run 11.9 s (13 to 14 s before); the search itself takes about 0.5 s and 910 module evaluations. All six rows that can win (6, 7, 9, 10, 11, 14) now get cases. The best reachable score from `measurements-l08.md` is 73/132; 3 killable survivors remain, and the other 59 survivors have no separating input in the domain (44 on rows that never win, 15 equivalent).
- Haunted 33/35 and discount 31/33 unchanged. Their `MAX(0,...)` makes the search add 2 targeted cases each: haunted now 300 generated + 11 targeted, 200 distinct (was 9, 198); discount 300 + 8, 197 distinct (was 6, 195). Storyline unchanged: discount Faithful pass; haunted F-001, Faithful 0 mismatches; Intended with D-001 has one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0, explains 26 distinct cases). README line 108 still shows "300 generated + 9 targeted, 198 distinct" as an example and was not changed.
- Full suite: 926 passed, 2 skipped (before the 4 new tests, which pass separately). Not checked: Excel, the live site, the web job time on a 1 vCPU host (local CLI run only). Nothing committed, no AWS.
- Skeptic role: ran as the reviewer. Caveat found: the search cannot find a winning region narrower than the gap between two sampled points that both lie outside it and pick the same row (a one-value island). Rows are found only when sampling reaches them or when they lie between two differently-winning points.

### Task 5.8 (L-08): explain remaining survivors in the report (live-fixes-2026-11-24)
- Test first: `tests/test_survivor_explanation.py` (5 tests). The sentence appears in the report JSON (`mutation.survivor_explanation`) and HTML only when survivors are marked; it is absent otherwise; it contains no "equivalen"; the scenarios report from `ghost convert` + `ghost mutate` has it and the haunted report does not. `tests/test_mutation_wording.py` still passes.
- Engine: `run_mutation` runs the traced Faithful module over the tested cases (`unpicked_rows_observed` in `ghost/verifier/selection.py`). A survivor whose reason is "no difference found on N distinct cases" gets the optional `Mutant.survivor_kind = "no_output_change"` only when some MAX/MIN/MATCH call with 3 or more candidates never picked one of them. `ghost/report/model.py` writes `survivor_kind` and `mutation.survivor_explanation` only when set (old reports unchanged, schema accepts the new key). No mutant removed, score formula unchanged.
- Sentence: "These constants belong to rows that never become the best result on the tested inputs, or change no output on any tested input, so changing them doesn't change any output."
- Before and after, scenarios (`ghost mutate --mode faithful`, LibreOffice 26.8.3, fresh run): live 55/132, 54/132 after L-07, **70/132 after the search (5.7)**; 62 survivors, all marked, sentence shown. Best reachable 73/132. Haunted 33/35 and discount 31/33, 2 survivors each, not marked, no sentence.
- Real counts from a fresh `scripts/demo.sh`: discount Faithful PASS, 300 generated + 8 targeted, 197 distinct; haunted F-001, Faithful PASS 300 + 11 targeted, 200 distinct, 0 mismatches; Intended with D-001 one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0). Scenarios 300 + 54 targeted, 206 distinct.
- Docs: README line 108 example now "300 generated + 11 targeted, 200 distinct"; `tests/test_demo_invariants.py` docstring gained a current-numbers paragraph (no assertion change); L-08 row added to the Live-test resolution table. Historical log entries, the live evidence and `docs/REVIEW_FIXES_SUMMARY_2026-11-24.md` keep their old counts.
- Full suite: 932 passed, 2 skipped. Not checked: Excel, the live site. Nothing committed, no AWS.

### 2026-11-24: Session summary, live-fixes-2026-11-24 (L-02 to L-08)
- Feature: bugfix spec (`.kiro/specs/live-fixes-2026-11-24/`), sub-agents for spec task execution, hooks, agents
- Goal: fix the eight live-test findings from `docs/LIVE_TEST_REPORT_2026-11-24.md` (L-02 to L-08) test first, keeping the demo storyline exact.
- Spec: `bugfix.md`, `design.md`, `tasks.md`. Analyze Requirements could not be run on a bugfix spec, so the requirements were not analysed that way; the choices made in `design.md` are listed in the spec's Notes.
- Agents: the `skeptic` custom agent was invoked on the L-04 changes during task 3.12. It ran real experiments against the Referee with scripts in `/tmp/skeptic/` and reported two medium findings: decimal exact hits were inferred, not confirmed by the trace (`flip.py`, decimal branch of `_search`), and the 200-case `MAX_FLIP_CASES` cap could drop exact-hit cases the report still listed. It also reported low items: missing other-input values on exact hits, the "off-threshold" CLI wording, duplicated definitions in `flip.py`, the budget-note wording, decimal thresholds finer than the 0.001 step, a fully negative retry showing "not checked", and hand-written modules' flips coming from the transpiled module. The two medium items and most low items were fixed in the 3.12 follow-up (`tests/test_flip_exact_followups.py`). The rest are in the Open items of `docs/LIVE_TEST_REPORT_2026-11-24.md`. The `coroner` custom agent was invoked for the review of task 3.2 (L-02), whose entry records its verdict. The other Coroner and Skeptic reviews were done in role by the task sub-agents, not by invoking `.kiro/agents/coroner.json` or `skeptic.json`. Coroner role: the L-03 measurements (3.5), the L-03 fix and golden tests (3.7, 3.8, the 3.8 entry says "done in role, not by the `coroner` sub-agent"), and the L-05 defaults (3.14, 3.15: "No separate Coroner agent run was made"). Skeptic role: the L-04 follow-ups (3.11) and the L-08 search (5.7, which found the one-value-island caveat).
- Hooks: the four hooks in `.kiro/hooks/` (autopsy on graveyard add, regenerate report on decision, golden tests on converter save, reverify on logic save) are in the repository. The entries for 3.7 and 3.8 record "Hooks: none fired". No entry records a hook firing; I did not check beyond the existing entries. The new L-03 golden tests carry `@pytest.mark.golden`, so the golden hook selects them.
- Owner decisions: (1) L-05, task 3.14: `=TEXT(B1,"0.00")` is not converted, so the test selects it explicitly instead of the default mapping offering it. (2) L-07, task 5.4: widen the domain to include the workbook's own sample value, then clamp. (3) L-08, task 5.7: keep the search and update the case counts (haunted 300 + 11 targeted, 200 distinct; discount 300 + 8, 197 distinct).
- Interrupted runs: the sub-agent runs for tasks 3.10 and 3.12 were interrupted before reporting. Their uncommitted work was treated as unverified, reviewed, and finished in a second run.
- Mutation scores before and after: haunted 33/35 and discount 31/33, unchanged throughout. Scenarios (`ghost mutate --mode faithful`, LibreOffice 26.8.3): 55/132 live, 54/132 after L-07 (the -1 cases left the domain), 70/132 after L-08 (best reachable 73/132). The local Docker run (LibreOffice 7.4.7.2) gave 70/132, haunted 33/35.
- Verification: full suite 932 passed, 2 skipped, 0 failed; golden 67 passed. Details and open items: the "Live-test resolution" section of `docs/LIVE_TEST_REPORT_2026-11-24.md`. Not checked: Excel, the live site. Nothing committed, no AWS.
- Spec or task reference: live-fixes-2026-11-24 tasks.md 7.6
