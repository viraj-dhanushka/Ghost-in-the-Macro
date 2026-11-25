---
inclusion: always
---

# Ghost guardrails

These rules apply to every migration, whether code is written by the transpiler or by an AI agent.

1. **No behaviour change without a recorded Decision.** Reproduce the original workbook exactly (including quirks) unless a Decision in `decisions.yaml` says otherwise. When the workbook contradicts itself, raise a Finding and ask the human. Do not choose silently.
2. **Decimal for money.** Use `decimal.Decimal`, converting floats with `Decimal(repr(x))`. Never use binary floats for currency.
3. **Excel rounding per the Excel semantics table.** Worksheet ROUND is half away from zero on 15 significant digits. Do not use Python `round()`. See `excel-semantics.md`.
4. **No macro execution from untrusted files.** Macros run only for a bundled sample or a local file with `--trust-macros`. Web uploads never run macros. Read VBA statically only.
5. **No invented data.** Reports, rules and findings contain only values produced by the engine. A check that was not run is reported as "not checked". A workbook with no Excel-saved values is reported as "not cross-checked against Excel", never "pass".
6. **Never guess unsupported constructs.** List them as "not converted" with cell and reason.
7. **Volatile and external constructs** (NOW, TODAY, RAND, RANDBETWEEN, OFFSET, INDIRECT, external links) are flagged "not verifiable as-is" and excluded from comparison.
8. **Verify before claiming.** A migration is done only when the verifier passes against the Referee in the right mode (Faithful: zero mismatches; Intended: zero mismatches not explained by a Decision).
9. **Do not modify the uploaded workbook.** Work on a copy.
10. **No secrets in the repository.** No API keys, tokens or credentials in code, logs or reports.
