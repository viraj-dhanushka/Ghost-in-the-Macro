---
name: record-decision
description: Record a human Decision on a Finding or Mismatch (for example a workbook inconsistency) in decisions.yaml. Use only after the user has chosen the correct behaviour.
---

# Record a human Decision

Follow the `guardrails` skill. A mismatch can be a bug in the original workbook. Only a human decides the correct behaviour. You must not decide for them and must not change code behaviour without the Decision.

## Steps

1. Show the user the evidence: the Finding or Mismatch ID, cells, the minimal counterexample and what each option would produce.
2. Ask which behaviour is correct. Do not proceed on your own judgement.
3. Call `record_decision` with:
   - `migration_dir`: `.kiro/specs/<migration>`
   - `behaviour`: the chosen behaviour in plain words (for example "bulk means 50 or more")
   - `reason`: the user's reason
   - `author`: the user's name
   - `finding_id` or `rule_id`: what the Decision refers to (one is required)
   - `patch`: the Intended-mode change, when the user wants one
4. Confirm the returned Decision ID (such as D-001) to the user.
5. Run `verify-migration` in both modes. Faithful still reproduces the original. Intended should show only differences explained by the Decision.

Never edit `decisions.yaml` by hand or invent an author, date or reason.
