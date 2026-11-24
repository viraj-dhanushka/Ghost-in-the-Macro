# Ghost in the Macro: live test report, 24 November 2026

Reviewer: Claude (Claude Code), at the owner's request. Target: https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws, tested at 12:21 UTC (17:51 IST). The goal was to check the deployed site against the fixes committed as `aa49828`. No repo code was changed, nothing was committed or pushed, and only read-only AWS calls were made.

## Step 0 result: the live site runs the old build

Two of the three markers are missing, so testing stopped here, as the task requires.

| Marker | Expected (new build) | Live | Result |
|---|---|---|---|
| 1. Autopsy text after `POST /sample/haunted` | "Unanswered findings keep the original behaviour and are listed in the report." | "1 finding(s) still unanswered. They are reported as mismatches, not silently resolved." | **Missing** |
| 2. Report HTML | contains "Change-point bracket" and "Tested domains" | neither string is present; the report still says "equivalent on tested domain" and has no distinct-case count | **Missing** |
| 3. Theme toggle | label "Light mode" with `aria-pressed` | `<button ... id="theme-toggle" class="theme-toggle" aria-pressed="false">Dark mode`, and `/static/theme.js` still switches the label between "Light mode" and "Dark mode" | **Missing** (`aria-pressed` is present; the label is not constant) |

### More evidence

- **Served files still hold the old code.**
  - Live `/static/style.css` line 5 has `--border: #5b4f73`. The repo at `aa49828` has `#7a6d94`.
  - The live home page (`GET /`) serves the label "Dark mode". The repo has "Light mode" (`web/templates/index.html:16`).
- **Old behaviour seen in the one job run.**
  - Job `RRqjpgAEjqICYX_8`: the haunted sample, no Decision, verified with the autopsy's default boxes. It finished `done` in 5.1 s.
  - **R-12:** the autopsy still pre-checks `Calculator!E5`. The default inputs are `Calculator!B2`, `B3`, `B4` and `E5`.
  - **R-21:** job events still contain absolute server paths, such as `module: /tmp/ghost-sessions-kaf0_mkf/I9Eq-…/run-1/logic.py`.
- **The same container has been running all day.** The server's session folder is `/tmp/ghost-sessions-kaf0_mkf`, the same name seen during the morning review between 10:18 and 10:28 IST, so the web process hasn't restarted since then.
- **What AWS shows (read-only calls only):**
  - `aws ecs describe-services --cluster default --services ghost-in-the-macro`:
    - one deployment, `PRIMARY`, rollout `COMPLETED`;
    - task definition `default-ghost-in-the-macro:3`, created 2026-11-24 09:38:07 IST;
    - `runningCount` 1.
  - `aws ecs describe-task-definition --task-definition default-ghost-in-the-macro:3`: image `…/ghost-in-the-macro:latest`, registered 09:38:05 IST.
  - `aws ecr describe-images --repository-name ghost-in-the-macro`:
    - The newest image is `latest`, `sha256:7287103f…0fe0a`, pushed 09:37:52 IST.
    - There is no newer image.
  - `git show aa49828`: committed 2026-11-24 17:23:15 IST.
  - **Conclusion:** the running image was pushed about 7 h 45 min before the fix commit, so it can't contain the fixes.

## Pass/fail table for items 1 to 10

| # | Item | Result |
|---|---|---|
| 1 | Demo storyline (haunted) | not checked: old build live |
| 2 | Every sample passes Faithful with default boxes | not checked: old build live |
| 3 | Proof strength on the live Referee | not checked: old build live |
| 4 | Semantics on LibreOffice 7.4.7.2 | not checked: old build live |
| 5 | Autopsy and Decisions | not checked: old build live |
| 6 | Uploads and safety | not checked: old build live |
| 7 | Sessions and jobs | not checked: old build live |
| 8 | Downloaded module runs standalone | not checked: old build live |
| 9 | Accessibility | not checked: old build live. Markers 3 and the old dark border show R-23 is not deployed. |
| 10 | CloudWatch logs | not checked: stopped at Step 0 |

## Finding

### L-01: the fixes are not deployed (demo blocker)

- **Steps:** see Step 0 above.
  - `curl -c jar -b jar -X POST $B/sample/haunted`, then `curl -b jar $B/autopsy`, then grep for the marker text.
  - `curl $B/` and `curl $B/static/style.css`.
  - Read-only `aws ecs describe-services`, `aws ecs describe-task-definition` and `aws ecr describe-images` in us-east-1.
- **Expected:** the site serves `aa49828`.
- **Actual:**
  - The site serves the image pushed at 09:37:52 IST.
  - R-05, R-12, R-21, R-22, R-23 and the other fixes are absent from what judges will see.
- **Likely cause:** `scripts/deploy_ecs_express.sh` hasn't been run since `aa49828`. `docs/REVIEW_FIXES_SUMMARY_2026-11-24.md` says to run it yourself, and no image newer than 09:37 IST exists in ECR.
- **Suggested fix:**
  1. Run `scripts/deploy_ecs_express.sh --dry-run` to review the commands, then run it without the flag.
  2. Confirm that a new image digest and a new task-definition revision appear.
  3. Then re-run this test plan.

## Job durations on the live host

| Job | What | Status | Time |
|---|---|---|---|
| `RRqjpgAEjqICYX_8` | haunted sample, Faithful, autopsy defaults (B2, B3, B4, E5 → B11) | done | 5.1 s |

- `/healthz` returned 200 with `{"status":"ok","referee":{"available":true}}` in 3.8 s.
- That health check starts a LibreOffice at most once a minute, so the first call is slow.

## What I couldn't test, and why

- **Items 1 to 10:** all not checked. The live site runs the build from before the fixes, and the task says to stop at Step 0 in that case.
- **CloudWatch logs:** not checked, for the same reason. Read-only AWS credentials do work from this Mac.

## Scripts and files

No script files were written. The checks were inline `curl` and Python commands. Their outputs are in `/tmp/ghost-live/`:

| File | Contents |
|---|---|
| `home.html` | the live home page |
| `autopsy.html` | the haunted autopsy |
| `s0-report.html` | the report for job `RRqjpgAEjqICYX_8` |
| `s0.jar` | the cookie jar used |
