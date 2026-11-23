---
name: implement-from-rules
description: Write logic.py and mapping.yaml for a migration from its rules spec, as a pure Python compute(inputs) function. Use after write-rules-spec.
---

# Implement from the rules spec

Follow the `guardrails` skill. The spec in `.kiro/specs/<migration>/` is the source of truth. Read `rules.md`, `traceability.yaml`, `findings.yaml` and `decisions.yaml` first.

## Contract

- `logic.py` exposes `compute(inputs: dict) -> dict`. It is a pure function: no I/O, no globals that change, no clock or randomness.
- `mapping.yaml` maps input and output names to cells (`Sheet!A1`):

```yaml
inputs:
  quantity: Sheet1!B2
outputs:
  total: Sheet1!B9
```

## Rules for the code

- Reproduce the original workbook exactly, quirks included, unless `decisions.yaml` has a Decision that changes the behaviour. Cite the `rule_id` in a comment next to each implemented rule.
- Money uses `decimal.Decimal`, with floats converted by `Decimal(repr(x))`.
- Worksheet ROUND: normalise to 15 significant digits, then quantize with `ROUND_HALF_UP`. Never use Python `round()`. Worksheet MOD follows the divisor's sign. Text comparison ignores case. Empty is 0 in arithmetic and "" in text. TRUE is 1 and FALSE is 0 in arithmetic.
- Excel errors propagate as errors and are compared by error type.
- Do not implement constructs listed as "not converted" or volatile/external ones. Leave them out and say so.
- If a rule is ambiguous, ask the user. Do not guess.

## Check your own work

Use `evaluate_original` to get the original workbook's value for a few inputs, and compare with your `compute`. Then run the `verify-migration` skill. Do not say the migration is done before it passes.
