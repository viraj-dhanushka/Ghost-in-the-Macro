---
name: getting-started
description: Onboarding for the Ghost Power. Lists the prerequisites (uv, LibreOffice), the 13 MCP tools and the order of the Ghost skills. Use first when the user asks how to start a workbook migration or what Ghost can do.
---
# Getting started with Ghost
Ghost migrates business logic out of an Excel workbook into plain-English EARS rules and a pure Python module, then proves the new code matches the original workbook recalculated by headless LibreOffice (the Referee). Follow the `guardrails` skill throughout, always.
## Prerequisites
- **`uv`** provides `uvx`. The Power starts the `ghost` MCP server with `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`. `uvx` fetches Python 3.11+ and the dependencies, so no `python` command is needed.
- **LibreOffice Calc** is the Referee. On macOS install it to `~/Applications/LibreOffice.app` or `/Applications/LibreOffice.app`. On Debian install `libreoffice-calc-nogui` and `libreoffice-script-provider-python`. Set `GHOST_SOFFICE` if `soffice` lives elsewhere.
- If a tool fails with a missing-LibreOffice or server-start error, tell the user which prerequisite is missing. Do not report a check as passed when it did not run.
## The 13 MCP tools (server `ghost`)
- Inspect: `analyze_workbook`, `list_rules`, `get_dependencies`, `find_inconsistencies`, `extract_vba`, `boundary_cases`, `check_against_excel_cache`
- Referee: `evaluate_original`
- Verify: `verify_implementation`, `mutation_check`
- Record and report: `record_decision`, `generate_proof_report`
- Route: `recommend_route`; hand-off kit for AWS Transform custom (writes files, runs nothing): `prepare_handoff`
## Skill order
1. `autopsy`: examine the workbook first.
2. `write-rules-spec`: write the EARS rules, each traced to a source cell.
3. `record-decision`: when the workbook contradicts itself, ask the human and record the Decision.
4. `implement-from-rules`: write `logic.py` with `compute(inputs)` and `mapping.yaml`.
5. `verify-migration`: check the implementation against the Referee.
6. `route-migration`: decide whether the workbook fits Ghost or a larger migration service.
`guardrails` applies at every step.
