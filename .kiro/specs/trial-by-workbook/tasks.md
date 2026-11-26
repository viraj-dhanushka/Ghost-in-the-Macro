# Implementation Plan: trial-by-workbook

## Standing rules

- Baseline: 1603 passed, 3 skipped, 0 failed (local commit `1caf372`). Demo invariants do not move. No push. Commit locally when the feature is done.
- **Engine gate:** nothing under `ghost/` is written for this feature until the Owner approves `ghost/challenge.py` and one `challenge` subparser in `ghost/cli.py` (tasks 9 and 10). Everything else is outside `ghost/`.
- Tests first for every task. Existing tests are not edited. Log one entry per task in `docs/KIRO_USAGE.md`, including every failed or discarded attempt.
- The repair log and the agent's files are never edited by hand.

## Tasks

- [x] 1. Baseline recorded (suite and demo on this code).
- [x] 2. Suspects and their measurement (no engine change)
  - [x] 2.1 Write the Suspect modules and pinned mappings for haunted and discount.
  - [x] 2.2 `scripts/lineup.py` measures each Suspect through `ghost verify`; record `samples/suspects/MEASURED.md` and `lineup.json`.
  - [x] 2.3 Correct every header label to the measurement; `tests/test_suspects.py` pins labels to the measured results.
- [x] 3. The repair brief: tests first, then `scripts/repair_brief.py`, including Property 3.
- [x] 4. The repair step: tests first, then the `repair` kind in `scripts/ghost_hook.py`, chained from `verify`.
- [x] 5. The skill: "Repair loop" section in `implement-from-rules/SKILL.md`.
- [x] 6. `graveyard/haunted.xlsx` and the `.gitignore` exception.
- [x] 7. The agent migration: rules spec, a fresh agent writes `logic.py` and `mapping.yaml`, verification, the log; record the prompt and what happened.
- [x] 8. The repair demonstration: if the first attempt passed, plant one labelled bug and let the loop find and repair it.
- [ ] 9. **Gated:** `ghost/challenge.py` and the `challenge` subparser; tests first.
- [ ] 10. **Gated:** switch `scripts/lineup.py` to `ghost challenge`; Properties 1 and 2.
- [ ] 11. Stretch: read-only web line-up (only if time remains).
- [ ] 12. Final checkpoint: `scripts/demo.sh`, full suite, Skeptic review, usage log, local commit.
