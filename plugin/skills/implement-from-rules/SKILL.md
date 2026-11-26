---
name: implement-from-rules
description: Write logic.py and mapping.yaml for a migration from its rules spec, as a pure Python compute(inputs) function. Use after write-rules-spec.
---

# Implement from the rules spec

Follow the `guardrails` skill. The spec in `.kiro/specs/<migration>/` is the source of truth. Read `rules.md`, `traceability.yaml`, `findings.yaml` and `decisions.yaml` first.

## Contract

- `logic.py` exposes `compute(inputs: dict) -> dict`. It is a pure function: no I/O, no globals that change, no clock or randomness.
- `mapping.yaml` maps input and output names to cells (`Sheet!A1`) and declares each input's domain:

```yaml
inputs:
  quantity:
    cell: Sheet1!B2
    type: integer
    min: 0
  unit_price:
    cell: Sheet1!B3
    type: decimal
    min: 0
outputs:
  total:
    cell: Sheet1!B9
    type: decimal
```
- `type` is `integer` or `decimal`. An input with no `min` is searched over very large negative values, where the Referee's binary floating-point arithmetic drifts from exact `Decimal` arithmetic by more than the tolerance. Ask the user for each input's type and minimum (the autopsy proposes them); do not narrow a domain to hide a difference.

## Rules for the code

- Reproduce the original workbook exactly, quirks included, unless `decisions.yaml` has a Decision that changes the behaviour. Cite the `rule_id` in a comment next to each implemented rule.
- Money uses `decimal.Decimal`, with floats converted by `Decimal(repr(x))`.
- Worksheet ROUND: normalise to 15 significant digits, then quantize with `ROUND_HALF_UP`. Never use Python `round()`. Worksheet MOD follows the divisor's sign. Text comparison ignores case. Empty is 0 in arithmetic and "" in text. TRUE is 1 and FALSE is 0 in arithmetic.
- Excel errors propagate as errors and are compared by error type.
- Do not implement constructs listed as "not converted" or volatile/external ones. Leave them out and say so.
- If a rule is ambiguous, ask the user. Do not guess.

## Check your own work

Use `evaluate_original` to get the original workbook's value for a few inputs, and compare with your `compute`. Then run the `verify-migration` skill. Do not say the migration is done before it passes.

## Repair loop
Use this when you wrote or changed a hand-written `logic.py` in a migration folder and the Referee may disagree. Saving `logic.py` runs the verification, and the hook then writes `repair-brief.json` and appends a block to `repair-log.md` in the migration folder.
1. Read `repair-brief.json`. `{"status": "passed"}` means stop: there is nothing to repair. Otherwise it holds one smallest failing input, the Referee's value, your value, the output cell, whether it was a targeted boundary case or found by the search, and the rule with its text and source formula.
2. Change only what the brief demonstrates: the code that implements that rule. Do not make other changes because they look wrong; ask the user.
3. Never touch the workbook, `decisions.yaml`, `rules.md`, the proof reports, `repair-brief.json`, `repair-log.md` or the tests. Change `mapping.yaml` only when the user tells you to (it is the contract: the inputs, their types and minimums come from the autopsy and the user, never from a repair). The log is written by the hook from the proof report; do not edit it, and do not describe a round it does not show.
4. Save `logic.py` and let the verification run again. Read the new brief.
5. Stop at "not converged" (five failed rounds in a row). Tell the user what the last brief showed and do not try a sixth change on your own.
