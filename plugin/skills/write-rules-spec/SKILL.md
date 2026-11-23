---
name: write-rules-spec
description: Create the migration spec folder .kiro/specs/<migration>/ with EARS business rules, traceability and findings from a workbook. Use after the autopsy skill.
---

# Write the rules spec

Follow the `guardrails` skill. Rules come from tool output only.

## Steps

1. Pick a short kebab-case `<migration>` name (for example `discount-calculator`). Create `.kiro/specs/<migration>/`.
2. Call `list_rules` with the workbook path (and `inputs` / `outputs` if the user overrode them). It returns EARS rules, each with a `rule_id` and source cell, plus findings.
3. Write these files from the returned data, unchanged in wording and IDs:
   - `rules.md`: the EARS rules, each showing its `rule_id` (`R-xxxxxxxx`) and source cell.
   - `traceability.yaml`: `rule_id` to source sheet, cell and formula (or VBA module and line).
   - `findings.yaml`: findings from `list_rules` and `find_inconsistencies` (IDs such as F-001), plus constructs "not converted" with cell and reason.
   - `decisions.yaml`: an empty list. Only `record_decision` adds entries.
4. Do not invent rules, rename IDs, or resolve a Finding yourself. If the workbook contradicts itself, leave the Finding open and ask the user.
5. Show the user the rules and open Findings. Ask them to review before implementation.

Next steps: `record-decision` for any Finding the user wants to change, then `implement-from-rules`.
