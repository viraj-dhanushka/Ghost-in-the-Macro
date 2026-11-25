# Requirements Document

## Introduction

Feature 1 of the Kiroween build plan (`docs/KIRO_FEATURE_PROMPT_2026-11-25.md`) makes the Kiro-facing configuration of Ghost in the Macro loadable, documented and testable. The repository holds four hook files, four agent configs, a Power under `plugin/`, and an MCP server (`mcp_server/server.py`, 13 tools in `TOOLS`). A judge who opens `.kiro/` must find configuration that matches the documented Kiro formats.

Measured on 2026-11-25, the following facts supersede the stale claims in the source's problem statement:

- The four hook files already use the documented v1 schema. PostFileSave and PostFileCreate are valid v1 triggers. All four were observed firing in this Kiro IDE (last entry of `docs/KIRO_USAGE.md`). Hook output is not attached to agent tool results. The v1 schema has no manual trigger; the documentation recommends a manually included steering file as a slash command instead.
- The Power's server starts from GitHub through `uvx` and lists 13 tools. Installing it in the Kiro Powers panel is an owner step and has not been done.
- `plugin/plugin.json` validates against the agent-plugins 1.0.0 schema, which sets `additionalProperties` to false.
- The baseline before any change is 932 passed, 2 skipped, 0 xfailed, 0 failed. Demo figures: discount mutation 31/33, haunted mutation 33/35, with the demo invariants holding. The Owner measured this on HEAD 15694a9 before any change, so task 1 only logs these figures in the Usage_Log and does not need to establish them.
- The Owner confirmed on 2026-11-25 that `live-fixes-2026-11-24` is finished through task 7.7 and committed (commit 80b9add). The start gate in Requirement 10.11 is therefore satisfied.

This feature changes configuration, documentation and tests only. It does not change `ghost/`, the report schema, or the demo outputs.

## Glossary

- **Surfaces_Doc**: The file `docs/KIRO_SURFACES_FORMATS.md`, which records the documented format of each Kiro surface with source URLs.
- **Power**: The Ghost Kiro Power in `plugin/`, comprising `plugin.json`, `mcp.json`, `skills/`, and the files added by this feature.
- **Power_Manifest**: The file `plugin/POWER.md`.
- **Plugin_Manifest**: The file `plugin/plugin.json`.
- **Workspace_MCP_Config**: The file `.kiro/settings/mcp.json`.
- **Agent_Configs**: The four files `.kiro/agents/coroner.json`, `skeptic.json`, `clerk.json` and `medium.json`.
- **Hook_Files**: The files `.kiro/hooks/*.json`.
- **Steering_Originals**: `.kiro/steering/ghost-guardrails.md` and `.kiro/steering/excel-semantics.md`.
- **Steering_Copies**: `plugin/steering/ghost-guardrails.md` and `plugin/steering/excel-semantics.md`.
- **TOOLS**: The dictionary of MCP tools in `mcp_server.server`.
- **Config_Tests**: The test module `tests/test_kiro_config.py`.
- **Owner_Checklist**: The file `docs/KIRO_OWNER_CHECKLIST.md`.
- **Usage_Log**: The file `docs/KIRO_USAGE.md`.
- **Baseline**: The suite counts (932 passed, 2 skipped, 0 xfailed, 0 failed) and the demo figures recorded in the Usage_Log before any change.
- **Demo_Invariants**: The discount, haunted and haunted-with-D-001 results, default cells, seed 20261204 and the `proof-report-1` schema, as defined in ground rule 3 of the source.
- **Demo_Script**: The file `scripts/demo.sh`.
- **Owner**: The repository owner, the only person who installs the Power, observes surfaces in Kiro, commits, pushes and deploys.
- **Build_Agent**: The AI agent that carries out this feature's tasks.
- **Documented_Format**: A format recorded in the Surfaces_Doc together with its source URL.

## Requirements

### Requirement 1: Record the baseline before any change

**User Story:** As the Owner, I want the baseline recorded before anything changes, so that I can tell afterwards that this feature broke nothing.

#### Acceptance Criteria

1. WHEN the Build_Agent starts this feature, THE Build_Agent SHALL run the full test suite and the Demo_Script once, before modifying any file other than the Usage_Log.
2. WHEN the baseline run completes, THE Build_Agent SHALL write the passed, skipped, xfailed and failed counts, and the discount, haunted and haunted-with-D-001 demo figures, into the Usage_Log.
3. IF the baseline run reports a failed test, THEN THE Build_Agent SHALL halt all further actions, including later suite runs, until the Owner explicitly responds.
4. WHEN any later suite run completes during this feature, THE Build_Agent SHALL compare its counts with the Baseline and accept the run only if it shows the Baseline passes plus new tests, the Baseline skip and xfail counts, and 0 failed.

### Requirement 2: Document the Kiro formats before changing configuration

**User Story:** As a judge or maintainer, I want each Kiro format recorded with its source, so that configuration is traceable to documentation and not to guesses.

#### Acceptance Criteria

1. THE Surfaces_Doc SHALL record, for each of Powers, IDE hooks, custom agents and workspace MCP configuration, the required file layout, the field names, and the source URL the format was read from.
2. THE Surfaces_Doc SHALL be created before the Build_Agent modifies or creates any Kiro configuration file, where Kiro configuration files are those under `.kiro/hooks/`, `.kiro/agents/`, `.kiro/settings/` and `plugin/`.
3. WHERE a Documented_Format differs from what the repository contains, THE Surfaces_Doc SHALL state the difference.
4. THE Surfaces_Doc SHALL state, for the hook schema, that the v1 schema was confirmed and that PostFileSave and PostFileCreate are valid v1 triggers, with the source URLs `https://kiro.dev/docs/hooks/` and `https://kiro.dev/docs/ide/whats-new-v1/hooks/`.
5. THE Surfaces_Doc SHALL state the v1 trigger list and the two action types (`command` and `agent`) and SHALL state that v1 has no manual trigger.
6. THE Surfaces_Doc SHALL state whether a `POWER.md` is required by the Documented_Format for a Power, and how the Documented_Format relates to the Plugin_Manifest schema at `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`.
7. IF a format cannot be confirmed from a documentation source, THEN THE Surfaces_Doc SHALL mark that format "not confirmed" and the Build_Agent SHALL ask the Owner before changing the matching configuration file. The Build_Agent SHALL block changes only to that matching configuration file; changes to other files whose formats are confirmed may proceed.
8. THE Surfaces_Doc SHALL state that the hook-firing evidence comes from side effects observed on 2026-11-25 and that hook output is not attached to agent tool results.

### Requirement 3: Power layout

**User Story:** As a Kiro user installing the Ghost Power, I want a complete Power directory, so that Kiro can load its description, tools, skills and steering.

#### Acceptance Criteria

1. THE Power SHALL contain the files and folders that the format recorded in the Surfaces_Doc requires, with the field names recorded there.
2. WHERE the Surfaces_Doc records that a `POWER.md` is required or supported, THE Power_Manifest SHALL contain the name, description and keywords fields, and onboarding steps covering `uv`, LibreOffice, the MCP tools and the skill order.
3. WHERE the Power_Manifest is present, THE Power_Manifest name and keywords SHALL equal the name and keywords in the Plugin_Manifest.
4. THE Power SHALL contain `plugin/steering/ghost-guardrails.md` and `plugin/steering/excel-semantics.md` as Steering_Copies.
5. THE Steering_Copies SHALL be byte-identical to the Steering_Originals.
6. THE `plugin/skills/guardrails/SKILL.md` file SHALL contain a pointer to the Steering_Copies in place of the guardrail text that the Steering_Copies duplicate.
7. THE Plugin_Manifest SHALL continue to validate against `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, using the copy in `tests/fixtures/`.
8. IF the Documented_Format requires a field that the Plugin_Manifest schema forbids, THEN THE Build_Agent SHALL record the conflict in the Surfaces_Doc and ask the Owner before changing the Plugin_Manifest.
9. THE Power SHALL continue to launch its server with the existing `uvx` command from the GitHub URL.

### Requirement 4: Workspace MCP registration

**User Story:** As a developer working in this checkout, I want the workspace to register its own Ghost MCP server, so that Kiro agents here call the local tools.

#### Acceptance Criteria

1. THE Workspace_MCP_Config SHALL follow the format recorded in the Surfaces_Doc with its source URL.
2. THE Workspace_MCP_Config SHALL register one server that launches `mcp_server.server:main` from this checkout, and SHALL NOT reference the GitHub URL.
3. THE Workspace_MCP_Config SHALL contain no API key, token, credential or absolute path outside this workspace.
4. WHEN the registered launch command is run from the workspace root, THE server SHALL start and list the same tool names as the keys of TOOLS.
5. THE Workspace_MCP_Config SHALL parse as valid JSON.

### Requirement 5: Agent configurations

**User Story:** As a judge reviewing `.kiro/agents/`, I want each agent to carry the right tool limits and steering resources, so that each agent's role is enforced by configuration.

#### Acceptance Criteria

1. THE Agent_Configs SHALL use the field names recorded in the Surfaces_Doc for custom agents.
2. THE Coroner agent SHALL be limited to the tools `analyze_workbook`, `find_inconsistencies`, `extract_vba`, `boundary_cases`, `get_dependencies` and `check_against_excel_cache`, and SHALL have no write or shell capability.
3. THE Skeptic agent SHALL be limited to the tools `verify_implementation`, `mutation_check` and `evaluate_original`, plus the built-in read-only tool `read` (added by the Owner on 2026-11-25 so it can read files to review wording; it has no `write`, no `shell` and no wildcard).
4. THE Clerk agent SHALL be limited to the tools `record_decision` and `generate_proof_report`.
5. THE Clerk agent prompt SHALL instruct the Clerk to record only Decisions that a human dictated.
6. THE Medium agent SHALL be configured to write rules and specs, and SHALL have none of the verification tools `verify_implementation`, `mutation_check` and `evaluate_original`.
7. THE prompt of each agent SHALL name the MCP tools by name and SHALL NOT instruct the agent to call the Ghost command-line interface.
8. THE Agent_Configs SHALL reference the Steering_Originals as resources, using the resource field recorded in the Surfaces_Doc.
9. THE Agent_Configs SHALL reference the Ghost MCP server registered in the Workspace_MCP_Config, using the field recorded in the Surfaces_Doc.
10. IF the Surfaces_Doc records that the custom agent format cannot express a required tool limit, THEN THE Build_Agent SHALL state the gap in the Surfaces_Doc and SHALL enforce the limit through the agent prompt and ask the Owner to confirm.
11. THE Agent_Configs SHALL parse as valid JSON.

### Requirement 6: Hook validation and an additional hook type

**User Story:** As a maintainer, I want the four hooks checked against the documented v1 schema and one hook of another documented type, so that the repository shows more than one hook mechanism.

#### Acceptance Criteria

1. THE Hook_Files SHALL conform to the v1 schema recorded in the Surfaces_Doc, using the fields `version`, `hooks[].name`, `trigger`, `matcher`, `action.type` and `timeout`.
2. THE Hook_Files SHALL keep `scripts/ghost_hook.py` as the command of the four existing hooks.
3. WHEN the Build_Agent finds a Hook_File that conforms to the documented v1 schema, THE Build_Agent SHALL leave that file unchanged.
4. WHERE the Documented_Format supports a trigger or an action type that the four existing hooks do not use, THE Hook_Files SHALL include one additional hook that uses it. The `agent` action type is the documented candidate.
5. IF the Documented_Format supports no additional trigger or action type, THEN THE Surfaces_Doc SHALL state "not supported" for it, with the source URL.
6. THE Surfaces_Doc SHALL record that v1 has no manual trigger, and THE Build_Agent SHALL NOT add a hook with an undocumented manual trigger.
7. THE additional hook SHALL NOT use the same trigger and matcher pair as an existing hook.
8. THE additional hook SHALL NOT run a macro, write to a workbook, or change a Decision.

### Requirement 7: Configuration tests

**User Story:** As the Owner, I want automated checks of the Kiro configuration, so that a later edit cannot silently break a surface.

#### Acceptance Criteria

1. THE Config_Tests SHALL be placed in `tests/test_kiro_config.py`.
2. WHEN the Config_Tests run, THE Config_Tests SHALL assert that every tool name mentioned in `plugin/skills/*/SKILL.md` and in `.kiro/agents/*.json` is a key of TOOLS.
3. WHEN the Config_Tests run, THE Config_Tests SHALL assert that each Hook_File parses as JSON and that its matcher matches the path it is intended for.
4. WHEN the Config_Tests run, THE Config_Tests SHALL assert that the matcher of each existing hook rejects at least three near-miss paths. For the autopsy hook the near-miss paths include `graveyard/sub/x.xlsx` and `graveyard/x.csv`. For the golden hook they include `ghost/converter/notes.md`.
5. WHEN the Config_Tests run, THE Config_Tests SHALL assert that each Steering_Copy is byte-identical to its Steering_Original.
6. WHEN the Config_Tests run and a Power_Manifest exists, THE Config_Tests SHALL assert that the Power_Manifest name and keywords equal those in the Plugin_Manifest. IF no Power_Manifest exists, THEN THE Config_Tests SHALL skip this comparison silently, without a warning or a failure.
7. WHEN the Config_Tests run, THE Config_Tests SHALL assert that each Agent_Config tool limit matches the lists in Requirement 5.
8. WHEN the Config_Tests run, THE Config_Tests SHALL assert that the Workspace_MCP_Config parses and contains no GitHub URL.
9. THE Config_Tests SHALL be written and observed failing before the configuration changes they check are made, using fixtures built inside the tests.
10. THE Config_Tests SHALL require no LibreOffice and no network access.

### Requirement 8: Owner checklist

**User Story:** As the Owner, I want a checklist of what only I can verify in Kiro, so that the README claims only observed results.

#### Acceptance Criteria

1. THE Owner_Checklist SHALL contain one table with a row for each of: Power installs, tools are listed, skills are listed, each of the hooks (one row per hook), and each of the agents (one row per agent).
2. THE Owner_Checklist SHALL have an empty Result column in every row.
3. THE Build_Agent SHALL NOT write "pass", "ok", "works" or any other result into the Result column.
4. THE Owner_Checklist SHALL identify, in each row, the step the Owner performs and the evidence the Owner records.
5. THE Owner_Checklist SHALL state that a surface may be described as "works in Kiro" only in a row where the Owner has recorded an observed pass.
6. IF the Owner_Checklist contains any non-empty Result cell at the end of this feature, THEN THE Build_Agent SHALL report this as a defect in the final summary.

### Requirement 9: Honest wording

**User Story:** As a judge, I want every claim about Kiro surfaces to match observed evidence, so that the project is credited for what it does.

#### Acceptance Criteria

1. THE Build_Agent SHALL NOT state in the README, the Surfaces_Doc, the Usage_Log or any other file that the Power works in Kiro, unless the Owner_Checklist row for it holds an Owner-recorded pass.
2. THE Build_Agent SHALL describe hook firing as observed from side effects, and SHALL NOT claim that hook output reached the agent.
3. THE Build_Agent SHALL describe the Power's installation in the Kiro Powers panel as not done, until the Owner records otherwise.
4. WHEN a statement in this feature's documents cites a number, THE Build_Agent SHALL take the number from a report file, a command output or a count that can be re-run.
5. IF a check was not run, THEN THE Build_Agent SHALL write "not checked" for it in this feature's documents.
6. THE Build_Agent SHALL describe a passing test run as "no difference found" or as the number of tests passed, and SHALL NOT describe it as proof of correctness.

### Requirement 10: Guardrails, scope and demo invariants

**User Story:** As the Owner, I want this feature to stay inside the project's rules, so that the demo, the deployment and the repository history stay under my control.

#### Acceptance Criteria

1. WHEN this feature completes, THE Demo_Script and the suite SHALL show the Demo_Invariants unchanged: discount Faithful passes with mutation at least 31/33; haunted raises F-001, Faithful passes with 0 mismatches and mutation at least 33/35; haunted with D-001 in Intended mode shows exactly one "expected by decision" mismatch at quantity 50 with Referee 6.0 and new code 0.
2. THE Build_Agent SHALL leave every file under `ghost/`, `samples/`, `web/`, and `scripts/demo.sh`, and the `proof-report-1` schema, unchanged.
3. THE Build_Agent SHALL add no entry to `[project].dependencies` in `pyproject.toml`.
4. THE Build_Agent SHALL NOT weaken, delete or skip any existing test.
5. THE Build_Agent SHALL NOT run `git push`, `git commit`, any deploy command or any AWS command, and SHALL leave all changes uncommitted.
6. WHEN each task of this feature completes, THE Build_Agent SHALL append one entry to the Usage_Log that names the Kiro capability used (spec, hook, agent, MCP, power or vibe), what happened, and any surprise or failure.
7. WHEN a hook fires or fails to fire during this feature, THE Build_Agent SHALL record it in the Usage_Log.
8. THE Build_Agent SHALL write no secret, API key, token or absolute path of the developer's machine into any file created by this feature.
9. IF the Build_Agent would have to break a rule in this requirement to continue, THEN THE Build_Agent SHALL stop and ask the Owner.
10. IF this feature takes more than half a day longer than its 0.75 day estimate, THEN THE Build_Agent SHALL stop and ask the Owner before continuing.
11. THE Build_Agent SHALL NOT start this feature until the bugfix spec `live-fixes-2026-11-24` is finished through task 7.7 and committed by the Owner.

### Requirement 11: Completion criteria and handover

**User Story:** As the Owner, I want a clear definition of done and a summary, so that I can review, commit and fill in the checklist.

#### Acceptance Criteria

1. THE feature SHALL be complete only when the Surfaces_Doc exists with source URLs, the Config_Tests pass, the suite and Demo_Script match the Baseline, and the Owner_Checklist is ready for the Owner to fill in.
2. WHEN the feature completes, THE Build_Agent SHALL give the Owner a summary that lists what was built by file, the suite counts against the Baseline, the Demo_Script figures, anything measured that contradicts the source document, anything left "not checked", and the Owner_Checklist rows that need the Owner.
3. WHEN the Skeptic agent reviews this feature, THE Skeptic agent SHALL review the honesty wording of the Surfaces_Doc, the Owner_Checklist and the Usage_Log entries before the feature is called done.
