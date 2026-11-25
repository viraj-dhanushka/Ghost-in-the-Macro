# Implementation Plan: kiro-surfaces

## Overview

Make the Kiro-facing configuration real and tested, in the order the ground rules require: baseline, then documentation of the Kiro formats (before any configuration file changes), then failing tests, then configuration (Power layout, workspace MCP, agents, hooks), then the owner checklist, then a Skeptic review, then a final checkpoint against the baseline. Every task is required (none optional); there are no property-based test sub-tasks marked with `*` because this feature's property tests are small and integral to task 5.

## Standing rules for every task

- Baseline: 932 passed, 2 skipped, 0 xfailed, 0 failed (measured on HEAD 15694a9, before any change in this feature). Discount mutation 31/33, haunted mutation 33/35, demo invariants hold. Every later suite run in this feature must show this baseline's passes plus only new tests, the same skip/xfail counts, and 0 failed.
- **STOP-AND-ASK**: if the baseline run (task 1) reports a failed test, halt everything until the Owner responds. If a format cannot be confirmed from a documentation source (task 2), block edits only to the matching configuration file and ask the Owner before touching it. If the documented Power format requires a field the Plugin_Manifest schema (`additionalProperties: false`) forbids (task 4), ask the Owner before changing `plugin/plugin.json`. If the documented custom-agent format cannot express one of Requirement 5's per-tool limits, state the gap in the Surfaces_Doc, enforce it through the agent's prompt, and ask the Owner to confirm (task 6).
- No push, no commit, no deploy, no AWS command. Leave all changes uncommitted.
- Log one entry per task in `docs/KIRO_USAGE.md`: Kiro capability used, what happened, any surprise or failure. Record every hook fire or failure-to-fire.
- Guardrails win: no invented values, "not checked" for anything not run, no change to `ghost/`, `samples/`, `web/`, `scripts/demo.sh`, the `proof-report-1` schema, or `[project].dependencies`.

## Tasks

- [x] 1. Log the baseline
  - Append one entry to `docs/KIRO_USAGE.md` recording the already-measured baseline (932 passed, 2 skipped, 0 xfailed, 0 failed on HEAD 15694a9; discount mutation 31/33; haunted mutation 33/35; demo invariants held) and noting that `live-fixes-2026-11-24` is finished through task 7.7 and committed at 80b9add, satisfying the Requirement 10.11 start gate.
  - Do not re-run the suite or `scripts/demo.sh` for this task; the figures are already measured and given by the Owner.
  - _Requirements: 1.1, 1.2, 10.11_

- [x] 2. Research current Kiro documentation and write the Surfaces_Doc
  - Read `https://kiro.dev/docs/hooks/`, `https://kiro.dev/docs/custom-agents/configuration-reference/`, `https://kiro.dev/docs/powers/create/`, `https://kiro.dev/docs/powers/installation`, and `https://kiro.dev/docs/mcp/configuration/`.
  - Write `docs/KIRO_SURFACES_FORMATS.md` recording, for each of Powers, IDE hooks, custom agents and workspace MCP configuration: the required file layout, the field names, and the source URL. State explicitly that v1 hooks have no manual trigger, and that `agent` and `command` are the two action types.
  - State whether `POWER.md` is required or supported by the documented Power format, and how it relates to the Plugin_Manifest schema; state the hook-firing-is-observed-from-side-effects fact and that hook output is not attached to agent tool results.
  - **STOP-AND-ASK** if any of the four formats cannot be confirmed from a documentation source: mark it "not confirmed" in the Surfaces_Doc and ask the Owner before editing the matching configuration file in later tasks.
  - Do not create or modify any file under `.kiro/hooks/`, `.kiro/agents/`, `.kiro/settings/` or `plugin/` until this file exists.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 3. Write the failing configuration tests
  - [x] 3.1 Write `tests/test_kiro_config.py` skeleton and the tool-name coverage check
    - Build a helper that extracts tool-name tokens from `plugin/skills/*/SKILL.md` and `.kiro/agents/*.json`.
    - Assert every extracted token is a key of `mcp_server.server.TOOLS`.
    - _Requirements: 5.1, 7.1, 7.2, 7.9, 7.10_
  - [x]* 3.2 Write property test for tool-name coverage (PBT)
    - **Property 3: Every mentioned tool name is a declared MCP tool**
    - **Validates: Requirements 5.1, 7.2**
    - Use `st.sampled_from` over the extracted token set; minimum 100 iterations; explicit seed; tag `# Feature: kiro-surfaces, Property 3: Every mentioned tool name is a declared MCP tool`.
  - [x] 3.3 Write hook JSON-parse and intended-match assertions
    - For each of the four existing hook files, assert it parses as JSON and its matcher matches its documented intended path.
    - Assert the three near-miss paths from Requirement 7.4 (`graveyard/sub/x.xlsx`, `graveyard/x.csv`, `ghost/converter/notes.md`) are rejected by the relevant hooks.
    - _Requirements: 6.1, 7.3, 7.4, 7.9, 7.10_
  - [x]* 3.4 Write property tests for hook matcher accept/reject (PBT)
    - **Property 1: Hook matcher accepts every path matching its intended shape**
    - **Validates: Requirements 6.1, 6.3, 7.3**
    - **Property 2: Hook matcher rejects every generated near-miss path**
    - **Validates: Requirements 6.1, 6.7, 7.4**
    - Parameterise both properties over the four existing hook files in this task; task 8 extends the parameterisation to the fifth (new) hook. Minimum 100 iterations each; explicit seed; tag each test `# Feature: kiro-surfaces, Property 1: ...` / `Property 2: ...`.
  - [x] 3.5 Write steering byte-identity, Power_Manifest/Plugin_Manifest, agent tool-limit and workspace-MCP assertions (all expected to fail or skip for now)
    - Assert each `plugin/steering/*.md` is byte-identical to its `.kiro/steering/*.md` original (expected to fail: files do not exist yet).
    - Assert `plugin/POWER.md` name/keywords equal `plugin.json`'s, using `pytest.skip` when `plugin/POWER.md` does not exist.
    - Assert each agent's declared tools equal the lists in Requirement 5.2–5.6 (expected to fail against the current `tools: ["read","write","shell"]` configs).
    - Assert `.kiro/settings/mcp.json` parses as JSON and contains no GitHub URL (expected to fail: file does not exist yet).
    - _Requirements: 3.3, 3.5, 4.3, 4.5, 5.2, 5.3, 5.4, 5.6, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_
  - [x] 3.6 Run the new test module and confirm the expected failures
    - Run `.venv/bin/python -m pytest -q tests/test_kiro_config.py` and record in `docs/KIRO_USAGE.md` which assertions failed and why, confirming they fail for the right reason (missing file or wrong field) and not a typo in the test.
    - _Requirements: 7.9_

- [x] 4. Power layout: POWER.md, steering copies, plugin.json check
  - Create `plugin/POWER.md` with `name`, `description`, `keywords` equal to `plugin.json`'s, and onboarding steps covering `uv`, LibreOffice, the MCP tools and the skill order.
  - Create `plugin/steering/ghost-guardrails.md` and `plugin/steering/excel-semantics.md` as byte-identical copies of the originals under `.kiro/steering/`.
  - Edit `plugin/skills/guardrails/SKILL.md` to point at the steering copies instead of repeating the guardrail text.
  - Re-validate `plugin/plugin.json` against `tests/fixtures/agent-plugins-plugin.schema.json`.
  - **STOP-AND-ASK** if the documented Power format needs a `plugin.json` field the schema's `additionalProperties: false` forbids.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 5. Workspace MCP registration
  - Create `.kiro/settings/mcp.json` registering one `ghost` server that launches `mcp_server.server:main` (or the package's documented equivalent) from this checkout, with no GitHub URL, no credential, and no absolute path outside the workspace.
  - Manually run the registered launch command from the workspace root and confirm it starts and lists the same tool names as the keys of `TOOLS`; record the result in `docs/KIRO_USAGE.md`.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6. Rewrite the four agent configurations
  - Rewrite `.kiro/agents/coroner.json` limited to `analyze_workbook`, `find_inconsistencies`, `extract_vba`, `boundary_cases`, `get_dependencies`, `check_against_excel_cache`, with no write or shell tool, referencing the two steering files as resources and the `ghost` workspace MCP server.
  - Rewrite `.kiro/agents/skeptic.json` limited to `verify_implementation`, `mutation_check`, `evaluate_original`.
  - Rewrite `.kiro/agents/clerk.json` limited to `record_decision`, `generate_proof_report`; prompt instructs the Clerk to record only Decisions a human dictated.
  - Rewrite `.kiro/agents/medium.json` with no verification tool (`verify_implementation`, `mutation_check`, `evaluate_original` excluded).
  - Every prompt names its MCP tools by name and does not instruct the agent to call the Ghost CLI.
  - **STOP-AND-ASK** if the documented format cannot express one of these limits as a selector; record the gap in the Surfaces_Doc, enforce it through the prompt instead, and ask the Owner to confirm.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11_

- [x] 7. Checkpoint — configuration tests pass
  - Run `.venv/bin/python -m pytest -q tests/test_kiro_config.py` and the full suite; confirm 0 failed, baseline passes plus the new tests, baseline skip/xfail counts unchanged.
  - Ask the Owner if anything is unclear.

- [x] 8. Hook validation and the additional hook
  - Confirm the four existing hook files conform to the v1 schema recorded in the Surfaces_Doc; leave them unchanged.
  - Add one new hook file using the `agent` action type (or record "not supported" in the Surfaces_Doc with its source URL if research in task 2 found no safe, in-scope use), on a trigger/matcher pair distinct from the four existing hooks, that does not run a macro, write to a workbook, or change a Decision.
  - Extend the Property 1 / Property 2 parameterisation from task 3.4 to cover the new (fifth) hook file.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 9. Owner checklist
  - Create `docs/KIRO_OWNER_CHECKLIST.md` with one table: a row for Power installs, tools are listed, skills are listed, each hook (one row per hook, five rows after task 8), and each agent (one row per agent).
  - Leave the Result column empty in every row; do not write "pass", "ok", "works" or any other result.
  - State in the document that a surface may be called "works in Kiro" only in a row where the Owner has recorded an observed pass.
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 10. Skeptic review of honesty wording and properties
  - Invoke the `skeptic` sub-agent to review the honesty wording of `docs/KIRO_SURFACES_FORMATS.md`, `docs/KIRO_OWNER_CHECKLIST.md`, and this feature's `docs/KIRO_USAGE.md` entries, and to try to break Property 1, Property 2 and Property 3 (for example, by proposing near-miss paths or tool-name tokens the test generators might miss).
  - Apply any correction the Skeptic's review substantiates; record the Skeptic's verdict in `docs/KIRO_USAGE.md`.
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 11.3_

- [x] 11. Final checkpoint — full suite, demo invariants, handover
  - Run the full suite and confirm: baseline passes plus only this feature's new tests, baseline skip/xfail counts, 0 failed.
  - Run `scripts/demo.sh <temp dir>` and confirm the demo invariants are unchanged (discount Faithful pass, mutation ≥ 31/33; haunted F-001 raised, Faithful 0 mismatches, mutation ≥ 33/35; haunted with D-001 Intended mode exactly one "expected by decision" mismatch at quantity 50, Referee 6.0, new code 0).
  - Append a final `docs/KIRO_USAGE.md` entry with the suite counts, the demo figures, and confirmation that `docs/KIRO_OWNER_CHECKLIST.md` contains no non-empty Result cell.
  - Give the Owner a summary: what was built by file, suite counts against the baseline, demo figures, anything measured that contradicts `docs/KIRO_FEATURE_PROMPT_2026-11-25.md` (for example, the `POWER.md` finding from task 2), anything left "not checked", and which Owner_Checklist rows need the Owner.

## Notes

- Tasks are listed in dependency order; task 2 must finish before any of tasks 4–6 and 8 touch configuration files, and task 3 must produce failing tests before those same tasks make them pass.
- No task in this plan is optional except the two PBT sub-tasks marked `*` (3.2, 3.4), which are still required to be implemented — the `*` marks them as property tests per repository convention, not as skippable.
- Properties 1–3 are defined in `design.md`; this plan does not restate their bodies, only their titles and the requirements they validate.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3"] },
    { "id": 4, "tasks": ["3.4", "3.5"] },
    { "id": 5, "tasks": ["3.6"] },
    { "id": 6, "tasks": ["4", "5"] },
    { "id": 7, "tasks": ["6"] },
    { "id": 8, "tasks": ["7"] },
    { "id": 9, "tasks": ["8"] },
    { "id": 10, "tasks": ["9"] },
    { "id": 11, "tasks": ["10"] },
    { "id": 12, "tasks": ["11"] }
  ]
}
```
