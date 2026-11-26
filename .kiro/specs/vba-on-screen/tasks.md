# Implementation Plan: vba-on-screen

## Standing rules

- Baseline: 1527 passed, 3 skipped, 0 failed (local commit `765e240`). Every later run shows this plus only the new tests.
- Demo invariants do not move (Requirement 8.1). No change under `ghost/`. No new dependency. No macro is ever run.
- Tests first for every task. Existing tests are not edited; if adding the fourth sample breaks one, stop and report it.
- No push. Commit locally when the feature is done.
- Log one entry per task in `docs/KIRO_USAGE.md`.

## Tasks

- [x] 1. Baseline recorded (suite and demo run on 2026-11-26 on this code; see the usage log).
- [x] 2. Write the failing tests
  - [x] 2.1 `tests/test_vba_blocks.py`: caps, notes, `route_view`, thresholds fallback and equality with the steering file. _Requirements: 2.5, 4.1 to 4.5_
  - [x] 2.2 `tests/test_web_vba_panel.py`: panel, escaping, caps, no panel without VBA, error with `role="alert"`, Route_Panel for three routes, no server path. _Requirements: 2.1 to 2.9, 3, 4, 5_
  - [x] 2.3 `tests/test_no_macro_run.py`. _Requirements: 6_
  - [x] 2.4 The Macro_Sample tests (card, load, autopsy, real Faithful run, download type, 503 when the Referee is missing, cache builds once). _Requirements: 1, 3, 9.1_
- [x] 3. Implement
  - [x] 3.1 `samples/make_xlsm.py` `build(path)`. _Requirements: 1.2, 1.3, 6.2_
  - [x] 3.2 `web/autopsy_view.py` helpers. _Requirements: 2.5, 4_
  - [x] 3.3 `web/app.py`: the fourth sample, the cache, the media type, the 503. _Requirements: 1_
  - [x] 3.4 `web/flow.py` and `_autopsy.html`: panels and the alert fix; CSS. _Requirements: 2, 3, 4, 5_
- [x] 4. Check legacy `.xls` conversion and report (build only if clean). _Requirements: 7_
- [x] 5. Checkpoint: new tests, `tests/test_web_*.py`, then the final step.
- [x] 6. Final checkpoint: `scripts/demo.sh`, full suite, Skeptic review, usage log, local commit. _Requirements: 8_
