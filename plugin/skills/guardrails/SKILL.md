---
name: guardrails
description: Non-negotiable rules for every Ghost migration (no behaviour change without a Decision, Decimal for money, Excel rounding, no macros from untrusted files, no invented data). Read this before using any other Ghost skill.
---

# Ghost guardrails

These rules apply to every migration. The same text is committed in `.kiro/steering/ghost-guardrails.md`, with the rounding table in `.kiro/steering/excel-semantics.md`. Keep the two in sync.

1. **No behaviour change without a recorded Decision.** Reproduce the original workbook exactly, including quirks, unless a Decision in `decisions.yaml` says otherwise. When the workbook contradicts itself, raise a Finding and ask the human. Do not choose silently.
2. **Decimal for money.** Use `decimal.Decimal`. Convert floats with `Decimal(repr(x))`, never `Decimal(x)`. Never use binary floats for currency.
3. **Excel rounding per the Excel semantics table.** Worksheet ROUND is half away from zero, evaluated on 15 significant digits. Do not use Python `round()`. Worksheet MOD takes the sign of the divisor, so do not use `Decimal.__mod__` directly. Text comparison is case-insensitive. An empty cell is 0 in arithmetic and "" in text.
4. **No macro execution from untrusted files.** Macros run only for a bundled sample or a local file with `--trust-macros`. Web uploads never run macros. Read VBA statically (`extract_vba`).
5. **No invented data.** Rules, findings and reports contain only values the Ghost tools returned. A check you did not run is "not checked". A workbook with no Excel-saved values is "not cross-checked against Excel", never "pass".
6. **Never guess unsupported constructs.** List them as "not converted" with cell and reason.
7. **Volatile and external constructs** (NOW, TODAY, RAND, RANDBETWEEN, OFFSET, INDIRECT, external links) are "not verifiable as-is" and are excluded from comparison.
8. **Verify before claiming.** A migration is done only when `verify_implementation` or `generate_proof_report` passes against the Referee in the right mode. Faithful: zero mismatches. Intended: zero mismatches not explained by a Decision.
9. **Do not modify the uploaded workbook.** Work on a copy.
10. **No secrets in the repository.** No API keys, tokens or credentials in code, logs or reports.

## When a rule blocks you

Stop and tell the user which rule applies and why. Do not work around it. If a mismatch looks like a workbook bug, use the `record-decision` skill.
