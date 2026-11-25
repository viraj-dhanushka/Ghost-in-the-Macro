---
name: guardrails
description: Non-negotiable rules for every Ghost migration (no behaviour change without a Decision, Decimal for money, Excel rounding, no macros from untrusted files, no invented data). Read this before using any other Ghost skill.
---

# Ghost guardrails
These rules apply to every migration, whether the code is written by the transpiler or by you. Read both reference files in this skill's folder before you start, and follow them throughout:
- `references/ghost-guardrails.md`: the ten guardrails (no behaviour change without a recorded Decision, Decimal for money, no macros from untrusted files, no invented data, verify before claiming, and the rest).
- `references/excel-semantics.md`: the Excel semantics table (ROUND, MOD, text comparison, empty cells).
Both files are byte-for-byte copies of `.kiro/steering/ghost-guardrails.md` and `.kiro/steering/excel-semantics.md`. Do not edit the copies; change the originals and copy them again.
## When a rule blocks you

Stop and tell the user which rule applies and why. Do not work around it. If a mismatch looks like a workbook bug, use the `record-decision` skill.

## Setup (prerequisites for every Ghost skill)
- **LibreOffice Calc** must be installed on the machine that runs the Ghost MCP server. It is the Referee; without it `evaluate_original`, `verify_implementation`, `mutation_check` and `generate_proof_report` cannot run. On macOS it is `/Applications/LibreOffice.app`; set `GHOST_SOFFICE` if `soffice` lives elsewhere.
- **`uv`** must be installed. The Power starts the server with `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`, which fetches Python 3.11+ and Ghost's Python dependencies (openpyxl, oletools, defusedxml, hypothesis, pydantic, pyyaml, jsonschema, mcp). No `python` command is needed.
- If a tool fails with a missing-LibreOffice or server-start error, tell the user which prerequisite is missing. Do not report a check as passed when it did not run.
