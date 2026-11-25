# Implementation Plan: front-door

## Overview

Build the designed landing page, shared Stepper, Sample_Cards, the pure Progress_Module
and Progress_Rail, the sample-workbook download route, Failure_Cards and the theme pass,
in the order the ground rules require: failing tests first, then the pure module, then
templates and routes, then the JS busy/focus wiring, then the theme pass as a dedicated
vibe session, then a Skeptic review, then a final checkpoint against the baseline and
the demo invariants.

## Standing rules for every task

- Baseline: 1061 passed, 3 skipped, 1 xfailed, 0 failed (measured after `kiro-surfaces`).
  Every later suite run in this feature must show this baseline's passes plus only new
  tests, the same skip/xfail counts, and 0 failed.
- Demo invariants must not move: discount Faithful passes, mutation ≥ 31/33; haunted
  F-001 raised, Faithful 0 mismatches, mutation ≥ 33/35; haunted with Decision D-001
  Intended passes with exactly one "expected by decision" mismatch at quantity = 50
  (Referee 6.0, new code 0); default cells `Calculator!B2,B3,B4` → `B11` and scenarios
  `Model!B2,B3,E2` → `B19,B20`; seed 20261204. The `proof-report-1` schema gains no field.
- No push, no commit, no deploy, no AWS command. Leave all changes uncommitted.
- Log one entry per task in `docs/KIRO_USAGE.md`: Kiro capability used, what happened,
  any surprise or failure.
- No change to `ghost/`, `samples/`, `scripts/demo.sh`, the `proof-report-1` schema, or
  `[project].dependencies`. `web/progress.py` stays pure (no I/O, no import from
  `ghost.*` or the Referee).
- Every new behaviour gets a failing test, built from workbooks and event lists
  constructed inside the test, before the implementing code.
- **STOP-AND-ASK** if this feature runs more than half a day over the 1.25-day estimate.

## Tasks

- [x] 1. Write failing tests for the Progress_Module and its correctness properties
  - [x] 1.1 Write unit tests for `phase_of`, `mutant_counts`, `status_line_text` on hand-built event lists (queued, each Phase_Marker, a `not checked` line, an out-of-order `i>n` line)
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14, 7.1, 7.2, 7.6_
  - [x]* 1.2 Write property test: phase index monotone under append
    - **Property 1: Phase index is monotone under append**
    - **Validates: Requirements 6.9, 16.1**
  - [x]* 1.3 Write property test: unrecognised lines never change the phase
    - **Property 2: Unrecognised lines never change the phase**
    - **Validates: Requirements 6.10, 16.2**
  - [x]* 1.4 Write property test: mutant counts stay within bounds and tombstone count matches the total
    - **Property 3: Mutant counts stay within bounds and tombstone count matches the total**
    - **Validates: Requirements 7.6, 7.7, 8.1, 8.9, 16.3**
  - [x]* 1.5 Write property test: Status_Line text is a pure function of Phase
    - **Property 4: Status_Line text is a pure function of Phase**
    - **Validates: Requirements 9.4, 9.5, 16.5, 16.6**
  - [x]* 1.6 Write property test: killed/survived tombstone counts match the finished report
    - **Property 5: Killed and survived tombstone counts match the finished report**
    - **Validates: Requirements 8.3, 8.4, 16.4**
  - [x]* 1.7 Write property test: determinism of `phase_of`
    - **Property 6: Determinism of `phase_of`**
    - **Validates: Requirements 6.15**
  - Run the new test module and confirm every test fails only because `web/progress.py` does not exist yet.
  - _Requirements: 14.3_

- [x] 2. Write failing tests for landing page structure, Stepper and Sample_Cards
  - Write assertions on `GET /` for element order (tagline, explanation, upload form, three Sample_Cards, privacy note), the favicon/meta/Open Graph tags, absence of any Kiro-page or video link/placeholder, and the Stepper's single `aria-current` for each of the five states by rendering `_stepper.html` directly with each `current_step`.
  - Write assertions for each Sample_Card's blurb sentence, Run button target, "Download the workbook" link target, "(generated)" label, and the measured-duration text present/absent cases from a fixture duration file.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.9, 1.10, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 3. Write failing tests for the sample workbook download route
  - Assert `GET /sample/{id}/workbook` returns 200, the right filename and content type for each of the three samples, 404 with a Failure_Card for an unknown id, no server path in the response, and that two downloads of the same id parse to identical cells and formulas.
  - Assert the route writes to a temporary directory only (mock or inspect the path passed to the build helper), never into `session.folder`, `samples/` or `graveyard/`.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 4. Write failing tests for Failure_Cards and the 404 page
  - For each of the six kinds (session expired, job failed, job timed out, Referee unavailable, file rejected, not found), assert the rendered card keeps its Pinned_Error_Text verbatim inside `role="alert"`, adds a title and next step as separate elements, and contains no server path.
  - Assert a request to an unmatched route renders the not-found Failure_Card with a link to `/`.
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_

- [x] 5. Write the recorded-run regression fixture and its test
  - Run `scripts/demo.sh` or the CLI locally against the haunted sample, capture the real scrubbed event lines (including `Starting verification`), and save them as `tests/fixtures/front_door/haunted_run_events.json`, containing only lines the engine or Job_Runner actually produced.
  - Write the test that feeds the fixture lines to `phase_of` one at a time and asserts the Phase order (Verification started, Mutation self-check, Cases compared, Proof written), and that the finished Mutant_Counts equal that run's Proof_Report mutant total.
  - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 6. Implement `web/progress.py`
  - Implement `Phase`, `PHASE_LABELS`, `phase_of`, `MutantCounts`, `mutant_counts`, `status_line_text`, `Tombstone`, `tombstones`, `has_mutation_total`, `rail_context` exactly as designed, with no I/O and no import from `ghost.*`.
  - Make tasks 1 and 5's tests pass.
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14, 6.15, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 9.4, 9.5, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

- [x] 7. Checkpoint — Progress_Module tests pass
  - Run `.venv/bin/python -m pytest -q tests/test_property_progress_module.py tests/test_web_progress*.py` and confirm 0 failed.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Build the Stepper, Sample_Card and Failure_Card partials
  - [x] 8.1 Create `web/templates/_stepper.html` and wire it into `index.html`, `_autopsy.html`, `_upload_result.html`, `_job.html` with the correct `current_step` per screen
    - _Requirements: 2.1, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_
  - [x] 8.2 Create `web/templates/_sample_card.html`, a committed `web/measured_runs.json` (or equivalent) duration file, and wire three cards into `index.html`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_
  - [x] 8.3 Create `web/templates/_failure_card.html` and a `404.html` page, and switch every existing error response to render through it while keeping each Pinned_Error_Text unchanged
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_
  - Make task 2 and task 4's tests pass.

- [x] 9. Rewrite `index.html` content and meta tags
  - Add the tagline, two-sentence explanation, favicon link, meta description, Open Graph tags, repository link, and reorder content per Requirement 1.1; omit any Kiro-page or video link.
  - Add the `tabindex="-1"` `#result` container and the "Start over" button calling `DELETE /session`.
  - Make the remaining task 2 assertions pass.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8, 1.9, 1.10, 5.5, 5.6, 5.7, 5.8_

- [x] 10. Implement `GET /sample/{id}/workbook` in `web/app.py`
  - Build the workbook into a `tempfile.TemporaryDirectory`, stream it with the filename and content type from `SAMPLES`, and return the not-found Failure_Card for an unknown id.
  - Make task 3's tests pass.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 11. Build `web/templates/_progress_rail.html` and wire `rail_context` into `/run/{id}/panel`
  - Render the Status_Line (stable id, `aria-live="polite"`), the Mutation_Bar as a `<progress>`/`role="progressbar"` element driven by `MutantCounts`, the Graveyard_Grid of Tombstones (or the "Mutation self-check: not checked" text when `has_mutation_total` is false), and the raw log inside `<details>` with no `aria-live` on it or on the polled root.
  - Update `web/app.py`'s panel handler to call `progress.rail_context(job.events, job.status, mutation_block)` and pass the result to the partial.
  - _Requirements: 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 9.1, 9.2, 9.3, 9.4, 9.6, 9.7, 10.11, 10.12_

- [x] 12. Checkpoint — templates and routes tests pass
  - Run the full suite and confirm baseline passes plus only this feature's new tests so far, 0 failed.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Add busy-state and focus-movement JS to `web/static/htmx-errors.js`
  - Add the `htmx:beforeRequest`/`afterRequest` busy-state toggling and the `htmx:afterSwap` focus-to-heading-or-`#result` handler, with no new `<script>` tag and no new dependency.
  - Write a test asserting the static file is served, is referenced from `index.html`, and contains both handlers and the `#result` fallback selector.
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 14. Checkpoint — full feature tests pass before the theme pass
  - Run the full suite, confirm baseline passes plus only this feature's new tests, 0 failed.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Theme pass — vibe session
  - Carry the haunted-lab look through the Stepper, Sample_Cards, Tombstones and verdict colours in `web/static/style.css`, and fix the dark-theme report-iframe white slab using only `web/static/style.css`, `web/templates/` or the iframe element's own attributes, without editing the Proof_Report HTML the engine writes.
  - This task is done as one Kiro vibe session outside the spec task workflow, not by following a task-by-task prompt from this file.
  - Add a `docs/KIRO_USAGE.md` entry with Feature `vibe` and two or three honest sentences comparing this vibe session with the spec-driven tasks above, including anything that went wrong.
  - Confirm the existing border-contrast and theme-toggle assertions in `tests/test_web_accessibility.py` still pass unchanged, and that no animation added lacks a `prefers-reduced-motion: reduce` guard.
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 12.5_

- [x] 16. Checkpoint — accessibility and theme tests pass
  - Run `tests/test_web_accessibility.py` and the full suite; confirm 0 failed and the Requirement 12 assertions (skip link, labels, focus indicator, `role="alert"`, reduced motion, 360 px, no colour-only signal, theme toggle label/`aria-pressed`) all hold.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Skeptic review of honesty wording and properties
  - Invoke the `skeptic` sub-agent to review the honesty wording of the Landing_Page, Sample_Cards, Progress_Rail and Failure_Cards (no "correct"/"proven"/"verified correct", every number traced to a report, event line or measurement file), and to try to break Property 1 through Property 6 (for example, event-line orderings or near-duplicate marker lines the generators might miss).
  - Apply any correction the Skeptic's review substantiates; record the Skeptic's verdict in `docs/KIRO_USAGE.md`.
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 14.10_

- [x] 18. Final checkpoint — full suite, demo invariants, owner summary
  - Run the full suite and confirm: baseline (1061 passed, 3 skipped, 1 xfailed) plus only this feature's new tests, 0 failed.
  - Run `scripts/demo.sh <temp dir>` and confirm the demo invariants are unchanged (discount Faithful pass, mutation ≥ 31/33; haunted F-001 raised, Faithful 0 mismatches, mutation ≥ 33/35; haunted with D-001 Intended mode exactly one "expected by decision" mismatch at quantity 50, Referee 6.0, new code 0; seed 20261204).
  - Append a final `docs/KIRO_USAGE.md` entry with the suite counts, the demo figures, and the mutation scores observed for discount and haunted.
  - Give the owner a summary: what was built by file, suite counts against the baseline, demo figures, the `GHOST_MUTATION_CASES` deployment finding from Open Question 1 in `requirements.md` and that it needs an owner decision at deploy time, anything left "not checked", and confirmation that all changes remain uncommitted.
  - _Requirements: 14.1, 14.2, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.11_

## Notes

- Tasks marked with `*` are property-based tests; they are required, not optional — the
  `*` marks them as property tests per repository convention, not as skippable.
- Property 1–6 bodies are defined in `design.md`; this plan restates only their titles
  and the requirements they validate.
- Task 15 (the theme pass) is deliberately not broken into sub-tasks with requirement
  references for individual CSS rules, because it is a vibe session by design
  (Requirement 11.2) rather than a spec-driven implementation task.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "1.7"] },
    { "id": 2, "tasks": ["2", "3", "4", "5"] },
    { "id": 3, "tasks": ["6"] },
    { "id": 4, "tasks": ["7"] },
    { "id": 5, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 6, "tasks": ["9", "10", "11"] },
    { "id": 7, "tasks": ["12"] },
    { "id": 8, "tasks": ["13"] },
    { "id": 9, "tasks": ["14"] },
    { "id": 10, "tasks": ["15"] },
    { "id": 11, "tasks": ["16"] },
    { "id": 12, "tasks": ["17"] },
    { "id": 13, "tasks": ["18"] }
  ]
}
```
