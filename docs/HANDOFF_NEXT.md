# Handoff: the Owner's ordered list (2026-11-27)

Features are frozen. Nothing is pushed. No AWS or `atx` command was ever run. Submission closes Fri 4 Dec 2026 2:00 PM PT. Do the steps in this order.

1. **Write your text, regenerate, check.**
   - Write your own words under the eight headings of `docs/KIRO_OWNER_NOTES.md` (headings at lines 8, 11, 14, 17, 20, 23, 26, 29). Then run `scripts/ghost-py scripts/kiro_ledger.py` and `scripts/ghost-py scripts/kiro_ledger.py --check`. `docs/KIRO_STORY.md` is generated: do not edit it by hand.
   - Fill the placeholders in `docs/DEVPOST_WRITEUP.md` (all are `[OWNER ...]` unless noted):
     - line 1: "(draft)" in the title; line 3: the "Draft for the Owner to edit." paragraph; delete both when done;
     - line 13: who had this problem, and any real person or case;
     - lines 56 to 63: one `[OWNER: your experience.]` per Kiro topic (surfaces, agents, hooks, specs, steering, MCP, property tests, Powers);
     - line 65: "What I would not have attempted without Kiro";
     - line 81: what you want to say under "What is next";
     - line 83: the heading ends "(for the Owner to complete)"; remove that phrase;
     - line 88: confirm the contest start date and that all code was written in the contest period;
     - line 91: which model or agent wrote which parts.
   - `scripts/preflight_demo.sh --submit` must pass. It fails on `[OWNER`, "(draft)", "Draft for the Owner" and "for the Owner to complete" in README.md, the write-up, `docs/KIRO_STORY.md` and `docs/DEMO_VIDEO_SCRIPT.md`.
2. **Commit and push** (`git push`). Nothing has been pushed yet.
3. **Build and run the container.** `docker build -t ghost-in-the-macro .`, then `docker run --rm -p 8080:8080 ghost-in-the-macro`. Open `http://127.0.0.1:8080/kiro`, then click the macro sample. The Docker build was never run (the daemon was not running in any session), so expect to fix something.
4. **Redeploy from your own terminal** with `scripts/deploy_ecs_express.sh` (see `docs/DEPLOY_ECS_EXPRESS.md`). The guard hook blocks the agent from running it.
5. **Preflight and one sample by hand.** `scripts/preflight_demo.sh` against the live URL (it checks `/healthz`, `/` and `/kiro`), then load the haunted sample in a browser and run it to a verdict.
6. **Only then remove the "earlier build" wording and its test.**
   - `README.md` line 9: "The hosted copy is an earlier build; the screenshot is from a local run of this commit."
   - `docs/DEMO_VIDEO_SCRIPT.md` line 5 (the "Which build to film" paragraph) and the "local, or live after redeploy" wording in the shot table.
   - `tests/test_judge_kit_docs.py` line 303 pins the README sentence. Remove the sentence and that assertion together.
   - `README.md` also says "after the next deploy" for the route card (the large-workbook section); `tests/test_lane_docs.py` pins "after the next deploy". Change both together, or leave them.
7. **Record the video** from `docs/DEMO_VIDEO_SCRIPT.md` (173 s). In the Kiro shot, try `aws --version` off camera first and film the guard hook only if it blocks. Do not show an AWS console or run any `atx` or `aws` command.
8. **Fill the rows** of `docs/KIRO_OWNER_CHECKLIST.md` that have an empty Result (agents load in the IDE, Power install, 14 MCP tools in the panel, the guard hook on a real `aws` command, the AWS Transform rows). Leave a row empty rather than guess.
9. **Final suite run, commit, push.** `.venv/bin/python -m pytest -q` (about 10 minutes). Put its pass line and the date in `docs/DEVPOST_WRITEUP.md` line 76 (now 2142 passed, 4 skipped on 2026-11-27, from the run after the last code change), in the form "(N passed, M skipped on YYYY-MM-DD". The test pins the form and a floor of 2035 passed.
10. **Submit on Devpost.**

## Not checked (so far)
- The Docker build and a container serving `/kiro`.
- The hosted site (an earlier build, without `/kiro` or the route card).
- The guard hook blocking a real `atx` or `aws` command, and the new `scripts/ghost_guard.sh` wrapper command run inside Kiro. The wrapper's logic is tested from the shell only.
- Memory of the upload scan on Linux (measured on macOS only).
- Any Kiro surface other than the IDE; any Kiro custom agent loading in the IDE; Power installation.

## Decisions waiting for you
- Duplicate specIds (front-door and kiro-surfaces; live-fixes-2026-11-24 and review-fixes-2026-11-24) were left alone.
- Stale test-first statuses in front-door tasks 1.2 and 1.5 and kiro-surfaces task 3.4 need a decision; main-spec task 19.2 is left open.
