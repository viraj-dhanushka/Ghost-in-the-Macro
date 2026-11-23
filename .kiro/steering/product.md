---
inclusion: always
---

# Product: Ghost in the Macro

Kiroween 2026, Resurrection category. Ghost takes business logic trapped in an Excel workbook (formulas first, VBA as stretch) and produces three things:

1. Plain-English EARS business rules, each traced to a source cell or macro line.
2. A modern implementation: a pure-function Python module (TypeScript as stretch) plus a simple web UI.
3. A proof report showing the new implementation matches the original workbook. The proof uses property-based testing with the original workbook recalculated by headless LibreOffice as referee ("the ghost is the oracle").

A mismatch may be a bug in the ORIGINAL workbook. A human decides the correct behaviour and the decision is recorded in the migration spec (`decisions.yaml`).

One-liner: AWS Transform migrates VBA portfolios for enterprises; Ghost brings proof-checked migration to everyone else: one workbook, formulas included, original workbook as referee.

## Two migration paths, one proof

- Web app: deterministic transpiler, no AI, no API keys.
- Kiro Power: an AI agent writes code from the rules spec.
- Both are checked by the same verifier. Large VBA portfolios are routed to AWS Transform custom.

## Priorities

- P0: core engine, Kiro Power, deployed web app at a public URL.
- P1: mutation self-check, migration routing.
- P2 / STRETCH: VBA conversion, TypeScript export.

A working deployed end-to-end public-URL demo beats every other piece of work. Submissions close Fri 4 Dec 2026 2:00 PM PT. One developer, about 10 working days.

## Out of scope

- Automating real Excel.
- Running macros from uploaded files.
- Payments, a mobile app, full UserForm recreation, LLM calls from the web app.

## Demo storyline

Sample (b) "haunted discount calculator": free delivery uses `>50` while the discount uses `>=50`. Autopsy raises F-001. Faithful mode passes. With Decision D-001 "bulk means 50 or more", Intended mode shows one expected difference with minimal counterexample quantity=50.
