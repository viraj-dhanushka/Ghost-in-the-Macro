# Where we stopped (2026-11-26, end of day)

Features are frozen: fixes only. Nothing is pushed. No AWS or `atx` command was run.

## Done and committed earlier today
- `3f23ef5` engine fixes 1 to 5 (deadline on every start tag, `max_xml_elements`, no atx command without VBA, receipt mapping note).
- `8002b85` guard hook items 6 to 9 (quote-aware tokeniser, fail closed, hook-level `timeout`, honest limits).

## In the working tree, committed as "WIP" in the next commit (items 10 to 18)
- Screenshot: `scripts/make_verdict_screenshot.py` sizes the window to the card (720 x 580, scale 2), no crop. `docs/img/verdict-card.png` re-made and looked at: "Passed", the left edge, 311 cases, 6.0 vs 0 are visible.
- `scripts/kiro_ledger.py`: skips "not claimed" lines, binds rows on `Feature: <spec>, Property N` comments first, adds the vibe session and Skeptic lines, prints duplicate specIds as prose, reads `docs/KIRO_OWNER_NOTES.md` (new template, 8 sections) in place of placeholders, counts seeded property files (19 of 33).
- `scripts/preflight_demo.sh`: checks `GET /kiro`; `--submit` fails on `[OWNER` or `(draft)` in README.md, docs/DEVPOST_WRITEUP.md, docs/KIRO_STORY.md.
- README: first-screen note that the hosted copy is an earlier build; table of all twelve subcommands; `.venv/bin/python -m ghost.cli ...` everywhere; six hooks, "twice" for the guard; `POST /sample/{id}` and `GET /sample/{id}/workbook`; the XML element cap in the limits.
- `docs/DEMO_VIDEO_SCRIPT.md` rewritten (173 s; shots 2 to 5 "local, or live after redeploy"; Kiro shot 40 s). `docs/DEVPOST_WRITEUP.md` updated.
- Spec leftovers (item 18) done. New and changed tests: `tests/test_judge_kit_docs.py`, `test_kiro_ledger.py`, `test_guard_hook.py`, `test_xml_element_cap.py`, `test_triage.py`, and others.

## Checked today
- Demo output byte-identical to commit `6f920d3` (compared in a temporary worktree, since removed). Mutation 31/33 and 33/35.
- Sample workbook counts identical before and after the XML change (`tests/fixtures/sample_counts_2026-11-26.json`).
- Memory of the no-tree scan on a one-million-row sheet: 14.0 to 14.7 MB (was 104 MB). The test bound is 16 MB, not 15, because 15 leaves almost no margin.

## Done on 2026-11-27: full suite 2035 passed, 4 skipped; write-up count and usage-log entry written (items 1 to 3 below are finished; only the commit and the Owner's list remain)

## Was not done yet (kept for the record)
1. Run the full suite: `.venv/bin/python -m pytest -q` (about 9 minutes). The run was interrupted at 7%, so the whole suite has NOT been run on this tree. Fix anything red.
2. Put the final pass count into `docs/DEVPOST_WRITEUP.md` (it says 1922 passed, 4 skipped, which was the count before today's tests; the real number will be higher) and into the new `docs/KIRO_USAGE.md` entry.
3. Add the `docs/KIRO_USAGE.md` entry for this round (items 1 to 18), including: the memory figure 14.0 to 14.7 MB; bound 16 not 15; the guard also fired three more times later (old matcher blocked a harmless heredoc; two commands naming its approve command), not counted in "twice"; `timeout` sat inside `action` before today, so Kiro may have used the 60 s default for the 120/180/300 s hooks.
4. Re-run `scripts/ghost-py scripts/kiro_ledger.py` then `--check`, then commit.

## For the Owner by hand before Fri 4 Dec 2:00 PM PT
- Push the local commits, build the Docker image, redeploy; then run `scripts/preflight_demo.sh` and try one sample by hand (the hosted copy is an earlier build: no `/kiro`, no route card). The Docker build and `GET /kiro` in a container were never checked.
- Write your text in `docs/KIRO_OWNER_NOTES.md` (sections 1 to 8) and in the `[OWNER]` places of `docs/DEVPOST_WRITEUP.md`; complete its "pre-existing code and AI assistance" paragraph; remove "(draft)"; re-run the ledger; `scripts/preflight_demo.sh --submit` must pass.
- Record the video from `docs/DEMO_VIDEO_SCRIPT.md` (film shots 2 to 5 locally unless you redeploy first). Try `aws --version` off camera first to see the guard block.
- Rows in `docs/KIRO_OWNER_CHECKLIST.md` with an empty Result (agents, Power install, 14 MCP tools, guard hook, the AWS rows). The AWS lane has not been run at all.
- Decide: duplicate specIds (front-door/kiro-surfaces, live-fixes/review-fixes) were left alone; stale test-first statuses in front-door tasks 1.2 and 1.5 and kiro-surfaces 3.4; main-spec task 19.2 left open.
- Submit on Devpost.
