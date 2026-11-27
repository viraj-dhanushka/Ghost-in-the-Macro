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
     - line 87: when the feasibility test bench was written and by whom;
     - line 88: confirm the contest start date and that all code was written in the contest period;
     - line 91: which model or agent wrote which parts.
   - Run the docs tests and the submit check, and fix anything red before you push:
     `.venv/bin/python -m pytest tests/test_kiro_ledger.py tests/test_judge_kit_docs.py tests/test_lane_docs.py tests/test_writeup_links.py -q` and `sh scripts/preflight_demo.sh --submit`. It fails on `[OWNER`, "(draft)", "Draft for the Owner" and "for the Owner to complete" in README.md, the write-up, `docs/KIRO_STORY.md` and `docs/DEMO_VIDEO_SCRIPT.md`.
   - This was tried in a temporary copy of the repository on 2026-11-27: all eight notes filled, every write-up placeholder removed, ledger regenerated; those four test files and the submit check all passed.
   - Commit: `git add -A && git commit -m "Owner text"`.
2. **Push to a non-default branch, read the Actions result, then merge to main.** For example `git push origin HEAD:final-check`, read the result of `.github/workflows/ci.yml` on GitHub, and merge to `main` only when it is green. Nothing has been pushed yet.
3. **Build and run the container.** `docker build -t ghost-in-the-macro .`, then `docker run --rm -p 8080:8080 ghost-in-the-macro`. Open `http://127.0.0.1:8080/kiro`, then click the macro sample. A local Docker check was done on 2026-11-27 (image built for linux/amd64 on an arm64 Mac, 590 MB; `/`, `/kiro`, `/healthz`, the haunted sample, the macro sample, an over-limit upload and `routing-thresholds.md` in the image all checked; see `docs/KIRO_USAGE.md`). It was not repeated on Linux hardware.
4. **Redeploy from your own terminal** with `scripts/deploy_ecs_express.sh` (see `docs/DEPLOY_ECS_EXPRESS.md`). The guard hook blocks the agent from running it.
5. **Preflight and one sample by hand.** `scripts/preflight_demo.sh` against the live URL (it checks `/healthz`, `/` and `/kiro`), then load the haunted sample in a browser and run it to a verdict.
6. **Only then remove the "earlier build" wording and its tests.** Every place (line numbers as of this commit; earlier edits in the same file move later ones, so work from the bottom up):
   - `README.md` line 9: delete "The hosted copy is an earlier build; the screenshot is from a local run of this commit."
   - `README.md` line 48: delete " (on the live site after the next deploy)".
   - `README.md` line 257: delete " (after the next deploy; the live site does not have it yet)".
   - `README.md` line 319: change "gets a route card after the next deploy," to "gets a route card,".
   - `docs/DEMO_VIDEO_SCRIPT.md` line 5: delete the "Which build to film" paragraph; lines 10 to 13: delete the prefix "local, or live after redeploy: " in each shot; line 10: the Check cell "Local run, or live `/` after redeploy" becomes "Live `/`"; line 23: delete the note "If you do not redeploy, shoot shots 2 to 5 locally and say so in the write-up."
   - `tests/test_judge_kit_docs.py` lines 301 to 304: delete `test_the_readme_says_the_hosted_copy_is_an_earlier_build` (line 303 is the assertion); lines 351 to 352: delete the `for i in (1, 2, 3, 4):` loop that asserts "local, or live after redeploy".
   - `tests/test_lane_docs.py` line 55: change the assertion to `assert "route card" in lane_section()`; the function name at line 52 can keep or lose "_after_deploy".
   - Then run the four test files above and `sh scripts/preflight_demo.sh --submit`. Tried in the temporary copy on 2026-11-27: after exactly these edits all four test files and the submit check passed. The copy found two lines the first list missed (README 48 and the video Check cell), now included.
7. **Record the video** from `docs/DEMO_VIDEO_SCRIPT.md` (173 s). In the Kiro shot, try `aws --version` off camera first and film the guard hook only if it blocks. Do not show an AWS console or run any `atx` or `aws` command.
8. **Fill the rows** of `docs/KIRO_OWNER_CHECKLIST.md` that have an empty Result (agents load in the IDE, Power install, 14 MCP tools in the panel, the guard hook on a real `aws` command, the AWS Transform rows). Leave a row empty rather than guess.
9. **Final suite run, commit, push.** `.venv/bin/python -m pytest -q` (about 10 minutes). Put its pass line and the date in `docs/DEVPOST_WRITEUP.md` line 76 (now 2155 passed, 4 skipped on 2026-11-27), in the form "(N passed, M skipped on YYYY-MM-DD". The test pins the form and a floor of 2035 passed.
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
