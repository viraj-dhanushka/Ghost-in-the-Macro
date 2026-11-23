---
name: verify-migration
description: Verify a migrated compute(inputs) module against the original workbook recalculated by LibreOffice (the Referee) and write the proof report. Use after implement-from-rules or whenever the code or a Decision changes.
---

# Verify a migration

Follow the `guardrails` skill. The original workbook is the referee, and the same verifier checks AI-written and transpiled code.

## Steps

1. Run `verify_implementation` with `workbook`, `module` (source or path to `logic.py`), `mapping` (object or path to `mapping.yaml`), `mode: "faithful"`, and `migration_dir` set to `.kiro/specs/<migration>`. Keep the default `seed` so runs are reproducible.
2. Read the result. Each mismatch has inputs, the Referee value and the module value. Report the smallest counterexample.
3. Triage each mismatch:
   - Your code is wrong: fix `logic.py` and re-run.
   - The workbook looks wrong (for example a threshold used with two different operators): do not change the code. Use `record-decision`.
4. If Decisions exist, also run with `mode: "intended"`. Mismatches explained by a Decision are expected differences. Report them as such.
5. When verification passes, call `generate_proof_report` with `migration_dir`. It writes the HTML and JSON proof report.

## Completion

- Faithful mode: zero mismatches.
- Intended mode: zero mismatches not explained by a Decision.
- State only what the tools returned. Anything not run is "not checked". If the workbook has no Excel-saved values, write "not cross-checked against Excel".
- Cells excluded as volatile, external or not converted are listed as "not verifiable as-is" or "not converted". Do not count them as passed.
