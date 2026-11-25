# Kiro surface formats

Documented formats of the four Kiro surfaces this repository configures, read from the Kiro documentation on 2026-11-25. Written before any configuration file changes (kiro-surfaces task 2, Requirement 2).

Rules for this document:

- Every format claim names its source URL and the page's "Page updated" date. Where the page shows no date, the entry says "no date shown".
- A field the documentation does not mention is written as "not documented". No field name is inferred.
- Each surface ends with a verdict, "confirmed" or "not confirmed". "Confirmed" means the layout and field names the repository needs are stated on a Kiro documentation page. It does not mean the repository's files were loaded by Kiro.
- Nothing here says a surface works in Kiro. Observed behaviour is limited to what the "Observed" lines state.

## Summary

| Surface | Format verdict | Repository matches documented format? |
|---|---|---|
| Powers (`plugin/`) | confirmed | Yes after task 4. `plugin.json` matches. `POWER.md` and `plugin/steering/` are not used (legacy format; undocumented location). |
| IDE hooks (`.kiro/hooks/*.json`) | confirmed | Yes, all five files (four `command`, one `agent`). |
| Custom agents (`.kiro/agents/*.json`) | confirmed | Yes after task 6: documented fields only, `@ghost/<tool>` selectors, `file://` resources, inline `mcpServers.ghost`. Not loaded by Kiro as far as this repository has observed. |
| Workspace MCP (`.kiro/settings/mcp.json`) | confirmed (`cwd` not documented) | File exists (created by the Owner): `ghost` server, `scripts/ghost-py -m mcp_server.server`, no `cwd`. A manual launch with the MCP Python SDK from the workspace root completed the handshake and listed 13 tools equal to `TOOLS`. Kiro loading it: Owner observed `ghost` Connected with 13 tools in the Kiro MCP panel, 2026-11-25. |

## 1. Powers

### What the documented format requires

- A power follows the Agent Plugins specification. It is a directory with a required `plugin.json` manifest and two optional parts: `skills/` and `mcp.json`.
  - Source: https://kiro.dev/docs/powers/ (Page updated: November 12, 2026) and https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026).
- `plugin.json` fields shown in the create page: `$schema` (`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`), `name` (kebab-case), `version`, `description`, `author` (object with at least `name`; may also hold `email`, `url`), `keywords` (array that triggers activation). Optional: `homepage`, `repository`, `license`.
  - Source: https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026).
- The Agent Plugins JSON Schema (copy at `tests/fixtures/agent-plugins-plugin.schema.json`, identical in content to the live file fetched 2026-11-25; no date shown):
  - Properties: `$schema`, `name`, `version`, `description`, `author` (`name`, `email`, `url`; no other keys), `homepage`, `repository`, `license`, `keywords`, `extensions`.
  - Required: `$schema`, `name`. `additionalProperties` is `false` at the top level, so any other top-level key (for example `steering`) is rejected.
  - `name`: 1 to 64 characters, pattern `^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`.
  - Source: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json.
- Skills: each skill lives in its own directory under `skills/` with a required `SKILL.md` that starts with YAML front matter `name` and `description`. Optional `scripts/` and `references/` directories.
  - Source: https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026).
- Power `mcp.json` at the power root: `$schema` (`https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`), `mcpServers.<name>` with `type` ("stdio" in the example), `command`, `args`, `env`. Kiro namespaces server names on install (example: `supabase-local` becomes `power-supabase-supabase-local`).
  - Source: https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026).
  - Whether `$schema` and `type` are required in a power's `mcp.json`: not documented (they appear in the example only). Whether `disabled` is accepted in a power's `mcp.json`: not documented (it is documented for Kiro's own MCP configuration, section 4).
- Install: Powers panel, Add Custom Power, then import from a folder or from a public GitHub or GitLab repository URL. Each power needs "a valid `plugin.json` or `POWER.md` file at its package root".
  - Source: https://kiro.dev/docs/powers/installation (no date shown).
- Install location of MCP servers: with the Agent Plugins format (`plugin.json`), the MCP servers are managed internally by Kiro and are not added to `~/.kiro/settings/mcp.json`. With the legacy format (`POWER.md`) they are registered in that file.
  - Source: https://kiro.dev/docs/powers/installation (no date shown).

### Is POWER.md required?

- **Not required** for a power created with the documented format. The create page lists `plugin.json` as the required manifest, and none of its layout examples contains a `POWER.md`.
  - Source: https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026).
- **Legacy, but still supported for install.** The install page names `POWER.md` "Legacy format" and accepts either `plugin.json` or `POWER.md` at the package root. It says Kiro reads `plugin.json` when present and otherwise reads `POWER.md` front matter.
  - Source: https://kiro.dev/docs/powers/installation (no date shown).
- When both exist, `plugin.json` is read for the metadata shown in the Installed list (same page). What Kiro does with a `POWER.md` body when `plugin.json` is also present: not documented.
- The `POWER.md` front matter field names: not documented on the Kiro pages read. A third-party repository guide describes `POWER.md` as steering instructions in a power, but it is not a Kiro page and is not relied on here (https://github.com/miroapp/miro-ai/blob/main/docs/kiro/power-development.md, found by search, not fetched).
- Relation to the Plugin_Manifest schema: the schema describes `plugin.json` only. It has no `POWER.md` field and rejects unknown keys, so `POWER.md` cannot be declared inside `plugin.json`. A `POWER.md` would be a separate file beside it.

### Is `plugin/steering/` a documented location?

- **Not documented.** Neither the powers overview, the create page, nor the install page lists a `steering/` directory in a power. The only documented parts are `plugin.json`, `skills/` and `mcp.json`. Sources: https://kiro.dev/docs/powers/ (Page updated: November 12, 2026), https://kiro.dev/docs/powers/create/ (Page updated: October 8, 2026), https://kiro.dev/docs/powers/installation (no date shown).
- The overview describes steering as a separate Kiro-specific feature ("always, auto, fileMatch, and manual modes") and does not place it inside a power. Source: https://kiro.dev/docs/powers/ (Page updated: November 12, 2026).
- Consequence for Requirement 3.4: files in `plugin/steering/` would be copies Kiro is not documented to load. The documented place to carry guardrail text inside a power is a skill under `plugin/skills/`. Task 4 should treat `plugin/steering/` as "not documented" and ask the Owner (Requirement 3.8 / task 4 stop-and-ask) before relying on it.

### What the repository has

| Item | Repository | Documented | Match |
|---|---|---|---|
| `plugin/plugin.json` | `$schema`, `name` ("ghost-in-the-macro"), `version`, `description`, `author.name`, `license`, `homepage`, `repository`, `keywords` | All listed keys are in the schema | Yes. Validated against the fixture with jsonschema in task 4 (`docs/KIRO_USAGE.md`). |
| `plugin/mcp.json` | `mcpServers.ghost` with `command` `uvx`, `args` `--from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`, `disabled: false`; no `$schema`, no `type` | `command`, `args`, `env` documented in the create example; `$schema` and `type` appear in the example; `disabled` not documented for a power's `mcp.json` | Partly. Whether the missing `$schema`/`type` or the extra `disabled` matter: not documented. |
| `plugin/skills/<name>/SKILL.md` | 8 skill directories: getting-started, guardrails, verify-migration, record-decision, write-rules-spec, route-migration, autopsy, implement-from-rules; also `plugin/skills/.gitkeep` | Skill directory with `SKILL.md` | Yes for layout. Front matter of each SKILL.md: not checked here. |
| `plugin/POWER.md` | absent | Legacy, optional | Consistent with the documented format. **Not used: legacy format.** Owner decision 2026-11-25: follow the current documented format. |
| `plugin/steering/` | absent | Not documented | Nothing to compare. **Not used: undocumented location.** Owner decision 2026-11-25: the onboarding is in the skill `plugin/skills/getting-started/SKILL.md`, and byte-identical copies of the two steering files are in `plugin/skills/guardrails/references/` (a `references/` directory is documented for skills, see section 1). |

Observed: installing the Power in the Kiro Powers panel has not been done (Requirement 9.3). Whether Kiro loads it: not checked.

### Verdict: **confirmed** for `plugin.json`, `skills/`, `mcp.json` layout. **Not confirmed** for `POWER.md` field names and for `plugin/steering/` (not documented).

## 2. IDE hooks

### What the documented format requires

- Location: `.kiro/hooks/<id>.json`, any `.json` filename. One file may hold several hooks. Global hooks in `~/.kiro/hooks/` exist for CLI V3. Hooks activate when a session starts.
  - Source: https://kiro.dev/docs/hooks/ (Page updated: November 15, 2026).
- Schema v1 fields:

| Field | Required | Notes |
|---|---|---|
| `version` | yes | `"v1"` |
| `hooks` | yes | array |
| `hooks[].name` | yes | |
| `hooks[].description` | no | documentation only |
| `hooks[].trigger` | yes | PascalCase |
| `hooks[].matcher` | no | for file events, a regex against the file path; for tool-use triggers, a tool selector or regex against the tool ID; default always match |
| `hooks[].action.type` | yes | `"command"` or `"agent"` |
| `hooks[].action.command` | when type is command | |
| `hooks[].action.prompt` | when type is agent | |
| `hooks[].timeout` | no | seconds, command actions only, default 60, 0 disables, ignored for agent actions |
| `hooks[].enabled` | no | default true |
| `hooks[].confirm` | no | Stop-trigger command hooks only |

  - Source: https://kiro.dev/docs/hooks/ (Page updated: November 15, 2026). The "what's new" page lists the same core fields: https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026).
- Action types: exactly two, `command` (runs a shell command in the project root; JSON session context on stdin) and `agent` (injects a prompt into the conversation; cannot block the trigger).
  - Sources: https://kiro.dev/docs/hooks/ (Page updated: November 15, 2026); https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026).
- Trigger names found in the sources (PascalCase):
  - "What's new" table (IDE v1 core list): `SessionStart`, `Stop`, `UserPromptSubmit`, `PreTaskExec`, `PostTaskExec`, `PreToolUse`, `PostToolUse`, `PostFileCreate`, `PostFileSave`, `PostFileDelete`. Source: https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026).
  - Hook triggers page adds `SubagentStop` (CLI V3 only), `SessionEnd` (CLI V3), `PreCompact` and `PostCompact` (IDE, CLI V3 from 3.1.0), `PermissionRequest` (IDE 1.4.236+, CLI V3 3.4.0+; command actions only). Source: https://kiro.dev/docs/hooks/types/ (no date shown). Exact JSON spelling of the compaction triggers in IDE hook files: the page shows `PreCompact` and `PostCompact` for CLI V3; the IDE spelling is "not documented" on the pages read.
  - The hooks page says the hook types page "is the authoritative trigger list". Source: https://kiro.dev/docs/hooks/ (Page updated: November 15, 2026).
- Stdin payload: a `command` action receives session context as JSON on stdin; a file hook "receives the saved file path and session context". Documented example payload keys for other triggers: `hook_event_name`, `cwd`, `session_id`, plus `tool_name` and `tool_input` for tool triggers. The exact key that carries the file path for `PostFileSave` / `PostFileCreate`: not documented on the pages read. The `{{filePath}}` template variable is documented for file triggers in command strings.
  - Sources: https://kiro.dev/docs/hooks/ (Page updated: November 15, 2026); https://kiro.dev/docs/hooks/types/ (no date shown); https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026).
- Exit codes: for a command hook, exit 0 adds stdout to the agent's context; another exit code sends stderr to the agent and reports an error. The "what's new" page says exit code 2 blocks PreToolUse, UserPromptSubmit and PreTaskExec; other non-zero codes are errors, not blocks. The two pages differ in how they describe this for the IDE, so the repository does not rely on either for the four existing hooks (they are PostFile triggers, which cannot block).
  - Sources: https://kiro.dev/docs/hooks/actions/ (no date shown); https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026).

### Manual triggers

- **v1 has no manual trigger in the IDE.** Hooks that were `userTriggered` in IDE 0.x have "no v1 equivalent" and stay runnable only as legacy hooks; "you can't create a new Manual-trigger Hook in the IDE". The recommended on-demand workflow is a manually included steering file in `.kiro/steering/`, which runs as a `/<filename>` slash command. Source: https://kiro.dev/docs/ide/whats-new-v1/hooks/ (Page updated: August 21, 2026) and https://kiro.dev/docs/hooks/types/ (no date shown).
- A `Manual` trigger appears in the CLI V3 listing (the CLI "doesn't provide an action to invoke" it) and in Kiro Web. The v1 file schema on the hooks page names no `Manual` trigger. Source: https://kiro.dev/docs/hooks/types/ (no date shown). The repository must not add a manual-trigger hook (Requirement 6.6).

### Where hook output goes

- The documentation says that on exit 0 a command's stdout is added to the agent's context (https://kiro.dev/docs/hooks/actions/, no date shown). **Observed in this IDE on 2026-11-25: hook output was not attached to the agent's tool results.** Firing was shown by side effects only (see `docs/KIRO_USAGE.md`, entry "2026-11-25: Hooks confirmed firing in the Kiro IDE (R-29)"). The documentation and the observation are not reconciled here. Do not claim hook output reached the agent.

### What the repository has

All four files in `.kiro/hooks/` use `version: "v1"`, one hook each, `trigger`, `description`, `matcher`, `action.type: "command"`, `action.command` `scripts/ghost-py scripts/ghost_hook.py <name>` and `timeout`.

| File | trigger | matcher | timeout | Match |
|---|---|---|---|---|
| `autopsy-on-graveyard-add.json` | `PostFileCreate` | `(^|/)graveyard/[^/]+\.(xlsx|xlsm)$` | 120 | Yes |
| `golden-tests-on-converter-save.json` | `PostFileSave` | `(^|/)ghost/converter/.*\.py$` | 180 | Yes |
| `regenerate-report-on-decision.json` | `PostFileSave` | `(^|/)\.kiro/specs/[^/]+/decisions\.yaml$` | 300 | Yes |
| `reverify-on-logic-save.json` | `PostFileSave` | `(^|/)\.kiro/specs/[^/]+/(logic\.py|mapping\.yaml)$` | 300 | Yes |
| `review-findings-on-create.json` (`agent` action, no timeout) | `PostFileCreate` | `(^|/)\.kiro/specs/[^/]+/findings\.yaml$` | n/a | Yes |

- Observed (2026-11-25, `docs/KIRO_USAGE.md` last entries): the four hooks fired in this Kiro IDE, shown by side effects (file times, a pytest cache update, a process watcher). The autopsy hook was seen to start; the result of that run was not visible. Pass/fail counts of the golden run were not visible.
- Not used by the four hooks: the `agent` action type, `enabled`, `confirm`, and every trigger other than `PostFileCreate` and `PostFileSave`. Task 8 added one `agent` hook, `review-findings-on-create.json`, on `PostFileCreate` for a migration's `findings.yaml`. Its prompt asks the agent to list the findings and ask the human; it forbids deciding, editing `decisions.yaml`, running macros or modifying a workbook. A second hook on `graveyard/` was not added because the autopsy command hook already owns that trigger and matcher. The matchers of the decisions and logic hooks gained a `(^|/)` prefix (an unanchored `\.kiro/specs/` matched `x.kiro/specs/...`). Not checked: that the agent hook fires in the Kiro IDE.

### Verdict: **confirmed.** The five files match the documented v1 schema. The matchers of two of them were corrected in task 8 (see above).

## 3. Custom agents

### What the documented format requires

- Format: a JSON file, or a Markdown file with YAML front matter (body is the system prompt). The reference is for IDE 1.0 and CLI V3. Source: https://kiro.dev/docs/custom-agents/configuration-reference/ (no date shown).
- File location: the page says `/upgrade-agent` scans `.kiro/agents/` in the workspace and `~/.kiro/agents/` globally, and that a file watcher watches `.kiro/agents` directories. A dedicated "file location" statement: not documented on the reference page beyond these two mentions. Source: same page; also https://kiro.dev/docs/mcp/configuration/ (no date shown).
- Field names listed on the page: `name` (optional, derived from the filename if absent), `description`, `prompt` (inline text or a `file://` URI), `mcpServers`, `tools`, `permissions`, `resources`, `hooks`, `includeMcpJson`, `includePowers`, `excludedTools`, `model`, `welcomeMessage`. CLI 2.x legacy fields: `toolAliases`, `allowedTools`, `toolsSettings`, `keyboardShortcut` (not part of the CLI V3 schema). Source: https://kiro.dev/docs/custom-agents/configuration-reference/ (no date shown).
- `tools`: selectors. Built-in names or category tags `read`, `write`, `shell`, `web`, `subagent`; `@builtin`; `@mcp`; `@server_name` for all tools of a server; `@server_name/tool_name` for one MCP tool; `*` for everything. Source: same page.
  - Consequence: a per-tool limit such as "only `analyze_workbook`" **can** be expressed as `@ghost/analyze_workbook`. Whether a server name of `ghost` is namespaced in the IDE: not documented. For a registered server the page only shows `@git`, `@fetch/fetch_url` style names.
  - The page says `tools` decides which tools the agent can see and call, and `permissions` decides what they may do.
- `excludedTools`: "Exclude specific tools even when tools allows them". The selector syntax for it beyond the example `["knowledge"]`: not documented.
- `resources`: array of `file://` URIs (relative paths resolve from the agent config file's directory for `prompt`; for `resources` "absolute or relative paths" and globs are supported), `skill://` URIs, or a `knowledgeBase` object. Example: `file://.kiro/steering/**/*.md`. Limits in IDE 1.4.86+: at most 32 `file://` files and 100,000 characters, each file at most 1 MiB and 50,000 characters. Source: same page.
- `mcpServers` inside an agent: `command`, `args`, `env` (`${VAR}` expansion), `timeout`, `requestTimeout`, `url`, `oauth`. Source: same page.
- `includeMcpJson: true` includes servers from `~/.kiro/settings/mcp.json` and `<cwd>/.kiro/settings/mcp.json`. Source: same page.
- Agent-level default resources: by default, custom agents also inherit steering files, skills and `AGENTS.md`; the CLI setting `chat.disableInheritingDefaultResources` turns that off. Source: same page.
- Per-tool limits that the format cannot express: the format has no field for "record only decisions a human dictated" (a semantic limit). It has to be carried in `prompt`. This is the gap Requirement 5.10 anticipates; with `@ghost/<tool>` selectors the tool-list limits in Requirements 5.2 to 5.4 and 5.6 are expressible.

### What the repository has (after task 6, 2026-11-25)

Each of `coroner.json`, `skeptic.json`, `clerk.json`, `medium.json` uses only documented fields: `name`, `description`, `prompt`, `tools`, `resources`, `mcpServers`.

| Agent | `tools` |
|---|---|
| `coroner` | `@ghost/analyze_workbook`, `find_inconsistencies`, `extract_vba`, `boundary_cases`, `get_dependencies`, `check_against_excel_cache`. No `read`, `write`, `shell` or wildcard. |
| `skeptic` | `read` (added 2026-11-25 by the Owner's decision), `@ghost/verify_implementation`, `mutation_check`, `evaluate_original`. No `write`, `shell` or wildcard. |
| `clerk` | `@ghost/record_decision`, `generate_proof_report` only. |
| `medium` | `read`, `write`, `@ghost/analyze_workbook`, `list_rules`, `get_dependencies`. No verification tool, no shell. |

- All four have `resources` of `file://.kiro/steering/ghost-guardrails.md` and `excel-semantics.md`, and an inline `mcpServers.ghost` (`command` `scripts/ghost-py`, `args` `["-m", "mcp_server.server"]`) (`.kiro/settings/mcp.json` has since been created by the Owner with the same command; the agents' inline entry is unchanged). Prompts name MCP tools and do not tell the agent to run the Ghost CLI. The "record only Decisions a human dictated" limit has no field and is carried in the Clerk prompt.
- Not documented: whether a relative `command` resolves from the workspace root for an agent's `mcpServers`; whether Kiro resolves the server name `ghost` in `@ghost/<tool>` selectors.
- Observed on 2026-11-25 (task 10): the `skeptic` sub-agent, invoked by the orchestrator, reported that it had no file-reading, directory or shell tool and only the three Ghost tools. That is consistent with the restricted `tools` list being applied. It is one observation of one agent and says nothing about the other three agents, the `resources` or the `mcpServers` entry.
- Observed on 2026-11-25 (front-door task 17 follow-up): after `read` was added to the `skeptic` `tools` list (Owner decision), the `skeptic` sub-agent read the first line of `web/templates/_job.html` correctly and listed its tools as `read_file`, `load_resource`, `tool_call` and `report_progress`, plus deferred `file_search`, `grep_search`, `list_directory`, `read_code`, `user_input` and the three Ghost tools. It had no write and no shell tool. One observation of one agent.
- Not checked: that Kiro lists these four files in the agent picker, or that the `coroner`, `clerk` and `medium` agents load as configured. `docs/KIRO_USAGE.md` records several earlier reviews as done "in role", not by the agent, so no earlier invocation is relied on here.

### Verdict: **confirmed** (field names, `tools` selectors, `resources`, `includeMcpJson`). The repository's files use documented fields and express the Requirement 5 tool limits as selectors. The only gap in the format is the semantic "human dictated" limit, which is carried in the Clerk prompt.

## 4. Workspace MCP configuration

### What the documented format requires

- Location: workspace `.kiro/settings/mcp.json` (this workspace only); user `~/.kiro/settings/mcp.json` (all workspaces). The two are merged and the workspace file wins. Source: https://kiro.dev/docs/mcp/configuration/ (no date shown).
- Shape: one top-level `mcpServers` object keyed by server name. Source: same page.
- Local server fields: `command` (required), `args`, `env`, `disabled` (default false), `autoApprove`, `disabledTools`. `env` values may use `${VAR}`; Kiro expands only variables the user has approved. Source: same page.
- Remote server fields: `url` (required), `headers`, `env`, `oauth`, `oauthScopes`, `disabled`, `autoApprove`, `disabledTools`. Source: same page.
- `cwd`: **not documented** for MCP server entries on this page or on the custom-agent reference. So the workspace server must be launched with a command that does not depend on a working directory field. Whether Kiro starts local servers with the workspace root as the working directory: not documented; the Owner observation of 2026-11-25 (`ghost` Connected, 13 tools, relative command) shows that Kiro launches the workspace server from the workspace root.
- How to launch a local Python server: not documented specifically. The page's local examples run `npx` or `uvx` with `args`. A `command` plus `args` pair is the documented mechanism.
- Priority when the same server name appears in several places: agent `mcpServers` first, then workspace `mcp.json`, then global `mcp.json`, replacing rather than merging. Source: same page.
- Reload: agent and MCP configs hot-reload when the file is saved. Source: same page.
- Security: the page advises environment-variable references instead of hard-coded secrets and never committing credentials.

### What the repository has

- `.kiro/settings/mcp.json` exists (created by the Owner): one server `ghost`, `command` `scripts/ghost-py`, `args` `["-m", "mcp_server.server"]`, no `cwd`. Manual launch from the workspace root: handshake OK, 13 tools equal to `TOOLS` (see `docs/KIRO_USAGE.md`). Launch with cwd `/tmp` and the relative command fails with FileNotFoundError, so the relative command needs the launcher's cwd to be the workspace root. Kiro loading it: Owner observed Connected (13 tools) in the Kiro MCP panel, 2026-11-25. The Power's `plugin/mcp.json` is a separate file with a separate role (see section 1; the install page says power MCP servers are not written to `~/.kiro/settings/mcp.json`).
- `mcp_server/server.py` holds `TOOLS`; `plugin/mcp.json` launches it with `uvx ... ghost-mcp` from GitHub. The documented workspace shape can launch a local checkout by `command` and `args`. The agents carry an inline `scripts/ghost-py -m mcp_server.server` entry; whether Kiro starts it from the workspace root: not documented, not checked in Kiro.

### Verdict: **confirmed** for location and fields. `cwd` is **not documented**. The repository's workspace file exists and was observed Connected by the Owner (2026-11-25).

## 5. Differences and open points

| # | Item | Status |
|---|---|---|
| 1 | `POWER.md` is not required by the create format; it is legacy but installable. | Documented. Owner decision 2026-11-25: not added. |
| 2 | `plugin/steering/` is not a documented power location. | Not documented. Owner decision 2026-11-25: not used; copies live in `plugin/skills/guardrails/references/`. |
| 3 | `plugin/mcp.json` has no `$schema` or `type`, and has `disabled`. | Effect not documented. |
| 4 | Agent files granted `write` and `shell` to every agent and had no MCP, resource or steering reference. | Fixed in task 6 with `@ghost/<tool>` selectors, `resources` and `mcpServers`. Not checked in Kiro. |
| 5 | Agent prompts told agents to run the Ghost CLI. | Fixed in task 6. |
| 6 | No workspace `.kiro/settings/mcp.json`. | Resolved: the Owner created it and observed `ghost` Connected with 13 tools in the Kiro MCP panel (2026-11-25). `cwd` still not documented; the observation shows the workspace root is used. |
| 7 | Hook docs and observation differ on hook output reaching the agent. | Observed: not attached to tool results. |
| 8 | Hook stdin key for the changed file path is not documented. | Not documented. |
| 9 | `agent` action type is documented and unused by the four command hooks. | Used by `review-findings-on-create.json` (task 8). Not checked in Kiro. |
| 10 | The IDE spelling of compaction triggers is not documented on the pages read. | Not documented. |

## 6. Sources

| Page | Updated date shown |
|---|---|
| https://kiro.dev/docs/hooks/ | November 15, 2026 |
| https://kiro.dev/docs/hooks/types/ | no date shown |
| https://kiro.dev/docs/hooks/actions/ | no date shown |
| https://kiro.dev/docs/ide/whats-new-v1/hooks/ | August 21, 2026 |
| https://kiro.dev/docs/custom-agents/configuration-reference/ | no date shown |
| https://kiro.dev/docs/powers/ | November 12, 2026 |
| https://kiro.dev/docs/powers/create/ | October 8, 2026 |
| https://kiro.dev/docs/powers/installation | no date shown |
| https://kiro.dev/docs/mcp/configuration/ | no date shown |
| https://agent-plugins.org/schemas/1.0.0/plugin.schema.json | no date shown |

Not checked: that a power with these files installs in the Kiro Powers panel; that Kiro loads any of the four agent files; the printed output of the four hooks inside the IDE.
