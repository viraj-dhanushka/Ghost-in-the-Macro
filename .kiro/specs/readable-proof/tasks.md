# Implementation Plan: readable-proof

## Overview

Build the Verdict_Card (Part A), then the readable autopsy (Part B), in the order the Owner set so that the last steps can be cut: Part A (Requirements 1 to 7), then Requirements 8 and 9, then Requirements 10 and 11. Every task writes its failing tests first, then the code. Optional criteria are built last within their step.

## Standing rules for every task

- Baseline: 1321 passed, 3 skipped, 0 xfailed, 0 failed (after local commit `a28c8a4`). Every later suite run shows these passes plus only this feature's new tests, the same skip count, and 0 failed.
- Demo invariants do not move: discount Faithful passes with mutation at least 31/33; haunted raises F-001, Faithful has 0 mismatches, mutation at least 33/35; haunted with D-001 in Intended mode has exactly one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0); default cells `Calculator!B2,B3,B4` to `B11` and scenarios `Model!B2,B3,E2` to `B19,B20`; seed 20261204. The `proof-report-1` schema gains no field.
- The only change under `ghost/` is the public label function and its delegation (task 4.2). Nothing under `ghost/report/` changes. No new dependency.
- No push. Commit locally only when the whole feature is done (Owner instruction of 2026-11-26).
- Log one entry per task in `docs/KIRO_USAGE.md`: the Kiro capability used, what happened, anything that surprised or failed.
- Existing tests are never edited. If one fails, stop and say why.
- Time box: finish by the end of 27 November. If behind at midday on 27 November, cut in this order: the optional criteria, then Requirements 10 and 11, and report what was cut.
- Accessibility holds after every web change: skip link, labels, visible focus, `role="alert"` on errors, reduced-motion guard for every animation, the 360 px layout, no colour-only state.

## Tasks

- [x] 1. Record the baseline
  - Run the full suite and `scripts/demo.sh <temp dir>` once before any change and write the counts and the demo figures into `docs/KIRO_USAGE.md`.
  - _Requirements: 12.1, 12.2_

### Part A: the Verdict_Card (Requirements 1 to 7)

- [x] 2. Write the failing tests for the Verdict_Module
  - [x] 2.1 `tests/test_verdict.py`: `verdict_text` for every state of the design table (passed missing or not boolean; uncountable mismatches; agreement; intended with all explained, with the mode exactly `intended`; other modes and unexplained mismatches giving the bare "Passed"; `Not passed: K difference(s) found`; case count missing, zero, a string or a boolean); the existing `tests/test_web_verdict_text.py` stays untouched and must still pass.
    - _Requirements: 2.1 to 2.9_
  - [x] 2.2 `build_verdict` unit tests: tiles (missing counts read "not checked"; classes counted; `K of T`; `0 of 0` with no bar; `not checked` with no bar; disagreeing numbers shown as recorded; every survivor listed with its reason or "no reason recorded"; `survivor_explanation`), counterexample (minimal first, else first; `expected[output]` and `actual[output]`; the fallback to every differing entry when `output` is missing or not a key; plain words for each class with the class string beside them; haunted Intended values 50, 6.0, 0, D-001, F-001; no counterexample when there is no mismatch), not-proven strip (each list, the Excel sentence for each status, each `not_converted` entry), reproduce line and fixed caption (no `--cases`, no path), glossary of four terms.
    - _Requirements: 3.1 to 3.10, 4.1 to 4.4, 4.6, 4.7, 5.1 to 5.5, 5.7, 5.8, 6.1 to 6.5_
  - [x] 2.3 Purity and robustness tests: the module source imports only the standard library; `build_verdict({})`, a report of `None` values and a report of wrong types return a dict with the headline "Verdict not available" and do not raise; no banned word ("correct", "proven", "proved", "verified") in any string of any state.
    - _Requirements: 1.1, 1.2, 1.5, 2.9, 12.8_

- [x] 3. Implement `web/verdict.py`
  - [x] 3.1 Move `verdict_text` from `web/flow.py` into `web/verdict.py`; `web/flow.py` imports it. Apply the mode rule of Requirement 2.4. `tests/test_web_verdict_text.py` passes unchanged.
    - _Requirements: 2.1, 2.4_
  - [x] 3.2 `build_verdict`: headline, `claims_agreement`, `state`, `numbers`, tiles, counterexample, not-proven strip, reproduce line, glossary.
    - _Requirements: 1.1 to 1.7, 2.2 to 2.8, 3.1 to 3.9, 4.1 to 4.4, 4.7, 5.2 to 5.5, 5.8, 6.1 to 6.5_

- [x] 4. Property tests for Part A
  - [x] 4.1 `tests/test_property_verdict.py`: a generator of schema-valid reports and a test that each draw validates against `proof-report-1.json`.
    - _Requirements: 13.1_
  - [x] 4.2 Property 1: `claims_agreement` only for `passed` true and no mismatches (and always in that case). **Validates: 2.2, 2.3, 13.2**
  - [x] 4.3 Property 2: every `numbers` value is traceable (a report value, an array length, or a count sharing a field value). **Validates: 1.7, 12.5, 13.3**
  - [x] 4.4 Property 3: `not checked` mutation block gives exactly "not checked" and no bar. **Validates: 3.5, 13.4**
  - [x] 4.5 Property 4: every surviving mutant is listed. **Validates: 3.7, 13.5**
  - [x] 4.6 Property 5: when `claims_agreement` is true, "Excel" appears in the Headline only for `sanity.status` matched. **Validates: 5.7, 13.6**

- [x] 5. Render the card
  - [x] 5.1 Write `tests/test_web_verdict_card.py` first: a failing report shows the failure style and the Counterexample; the haunted Intended card shows quantity 50, "workbook says 6.0", "new code says 0", D-001 and F-001; `0 of 0` has no bar; the Reproduce_Line has no `--cases` and carries the caption; the glossary is a closed `<details>`; the Detail_Paragraph and the mutation line are below the card with their classes and text unchanged and without `aria-hidden`; no card when there is no report; the card itself has no `role="status"`.
    - _Requirements: 4.6, 6.2 to 6.5, 7.1 to 7.5, 13.8_
  - [x] 5.2 `_load_report` and the `verdict` key in `_job_ctx` (`web/flow.py`); `_verdict_card.html`; `_job.html` places the card above the iframe and the Detail_Paragraph and mutation line below the card; CSS: the Headline is the large line of the card, the Detail_Paragraph is small secondary text, the state is shown by icon and words as well as colour, animations only inside `prefers-reduced-motion: no-preference`, 360 px layout.
    - _Requirements: 3.10, 4.6, 5.1, 7.1 to 7.5, 12.7_

- [x] 6. Optional criteria of Part A (build last)
  - [x] 6.1 Counterexample `cases` line for a mismatch with `cases` above 1 (tests first).
    - _Requirements: 4.5_
  - [x] 6.2 "None" wording in the Not_Proven_Strip for an empty list (tests first).
    - _Requirements: 5.6_
  - [x] 6.3 Property 6: determinism and no mutation of the argument. **Validates: 1.3, 1.4, 13.7**

- [x] 7. Checkpoint A
  - Run the new tests and `tests/test_web_*.py`; confirm 0 failed. Log the counts.

### Requirements 8 and 9: labelled autopsy and Finding_Card

- [x] 8. Write the failing tests
  - [x] 8.1 `tests/test_cell_label.py`: `cell_label` exists in `ghost.autopsy.classify`, is in `__all__`, and agrees with `_left_label` and `ghost.converter.mapping._label` for every cell of the three sample workbooks.
    - _Requirements: 8.5_
  - [x] 8.2 `tests/test_autopsy_view.py`: finding title, short refs, the consequence sentence for two and three locations and for a macro location, formula segments (marks the operator next to the constant, falls back to the first matching operator, none when absent, every piece plain text), checkbox text (label and value, label and formula, address alone, no value).
    - _Requirements: 8.1 to 8.4, 9.1 to 9.5_
  - [x] 8.3 `tests/test_web_autopsy_readable.py`: labelled checkboxes for the bundled samples with the default selection unchanged and the markup still matching the pattern of `tests/test_web_samples.py`; a label, a value and a formula containing `<script>` are escaped; the haunted autopsy shows each location of F-001 with its formula, the marked operators and the consequence sentence with no computed outcome; a macro location shows module and line and no formula.
    - _Requirements: 8.1 to 8.8, 9.1 to 9.5, 13.8_

- [x] 9. Implement
  - [x] 9.1 `cell_label` in `ghost/autopsy/classify.py` with the exact body of `_left_label`; `_left_label` delegates; `__all__` updated. `ghost/converter/mapping.py` and the rules namer are not touched.
    - _Requirements: 8.5, 12.4_
  - [x] 9.2 `web/autopsy_view.py` (pure helpers).
    - _Requirements: 8.1 to 8.4, 9.1 to 9.4_
  - [x] 9.3 `_describe` adds labels, values, formulas and finding details; `_autopsy.html` shows them; CSS for the Finding_Card and the operator mark (a non-colour cue beside the colour).
    - _Requirements: 8.1 to 8.8, 9.1 to 9.5, 12.7_

- [x] 10. Checkpoint B
  - Run the new tests, `tests/test_web_*.py` and `tests/test_kiro_config.py`; confirm 0 failed. Log the counts.

### Requirements 10 and 11: Decision_Cards and Not_Converted_Panel

- [x] 11. Write the failing tests
  - [x] 11.1 Decision_Cards keep `name`, `value` and `required` and the first option selected; the reason input has no `value`; `POST /decision` with an empty reason returns 422; `author-name.js` is served, uses `localStorage` only, does not touch the reason field and is referenced once from `index.html`.
    - _Requirements: 10.1 to 10.5_
  - [x] 11.2 The Not_Converted_Panel is its own section with a heading, lists cell and reason (or "no reason recorded") and the not-verifiable entries, and is absent when both lists are empty; built from a workbook constructed in the test.
    - _Requirements: 11.1 to 11.4_

- [x] 12. Implement
  - [x] 12.1 Decision_Cards in `_autopsy.html`, `web/static/author-name.js`, its script tag in `index.html`, CSS with a visible focus ring.
    - _Requirements: 10.1 to 10.5_
  - [x] 12.2 The Not_Converted_Panel in `_autopsy.html`, with CSS.
    - _Requirements: 11.1 to 11.4_

- [x] 13. Checkpoint C
  - Run the new tests and `tests/test_web_*.py`; confirm 0 failed. Log the counts.

### Final

- [x] 14. Final checkpoint
  - Run `scripts/demo.sh <temp dir>` and the full suite; confirm the demo invariants and the Baseline plus only the new tests, with 0 failed. Run it twice if the first run shows a failure that passes alone.
  - Invoke the Skeptic on the honesty wording of the card and the autopsy text and on Properties 1 to 5, apply what it substantiates, and record its verdict.
  - Show the Owner the card text for haunted Faithful, haunted Intended with D-001, and one failing report.
  - Write the final `docs/KIRO_USAGE.md` entry and commit locally (no push).
  - _Requirements: 12.1, 12.2, 12.9_

## Notes

- Tasks marked optional (6.1 to 6.3) are built last in Part A and are the first to be cut. Property tests 4.2 to 4.6 are required.
- Requirements 10 and 11 (tasks 11 to 13) are the next to be cut.
- Task 3.1 changes `verdict_text` in one case only (Requirement 2.4); the existing tests build their reports with mode `intended` for that state and must pass unchanged.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "4.1"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "5.1"] },
    { "id": 5, "tasks": ["5.2"] },
    { "id": 6, "tasks": ["6.1", "6.2", "6.3"] },
    { "id": 7, "tasks": ["7"] },
    { "id": 8, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 9, "tasks": ["9.1"] },
    { "id": 10, "tasks": ["9.2"] },
    { "id": 11, "tasks": ["9.3"] },
    { "id": 12, "tasks": ["10"] },
    { "id": 13, "tasks": ["11.1", "11.2"] },
    { "id": 14, "tasks": ["12.1", "12.2"] },
    { "id": 15, "tasks": ["13"] },
    { "id": 16, "tasks": ["14"] }
  ]
}
```
