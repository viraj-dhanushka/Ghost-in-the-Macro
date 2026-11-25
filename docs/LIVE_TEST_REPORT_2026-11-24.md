# Ghost in the Macro: live test report, 24 November 2026

Reviewer: Claude (Claude Code), at the owner's request.

- **Target:** https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws
- **Test window:** 13:03 to 13:30 UTC, which is 18:33 to 19:00 IST.
- **What was checked:** whether the deployed site behaves like commit `aa49828`.
- **What was not done:** no repo code was changed, nothing was committed or pushed, and only read-only AWS calls were made. Requests were sent one at a time.

The deployed build reports `LibreOffice 7.4.7.2 40(Build:2)` and Ghost `0.1.0`.

**Earlier attempt (12:21 UTC):** Step 0 failed because the site still ran the image pushed at 09:37 IST. Kiro redeployed it afterwards. This report covers the run on the new build.

## Step 0: the new build is live

| Marker | Live | Result |
|---|---|---|
| 1. Autopsy text after `POST /sample/haunted` | contains "Unanswered findings keep the original behaviour and are listed in the report." | Pass |
| 2. Report HTML | contains "Change-point bracket" and "Tested domains" (job `zBkkB8Vok9fwCW0q`) | Pass |
| 3. Theme toggle | `<button ... id="theme-toggle" ... aria-pressed="false">Light mode`; the label stays "Light mode" when toggled, and only `aria-pressed` changes | Pass |

Read-only AWS evidence:
- The ECR image `latest` is `sha256:f22ce6f6…944a`, pushed 2026-11-24 18:08:51 IST.
- The service runs task definition `default-ghost-in-the-macro:4`. Its one deployment is `PRIMARY`, rollout `COMPLETED`, created 18:08:59 IST, with `runningCount` 1.
- The dark `--border` served in `/static/style.css` is `#7a6d94`.

## Results for items 1 to 10

| # | Item | Result | Findings |
|---|---|---|---|
| 1 | Demo storyline (haunted) | **Pass** | L-06 (polish, boundary table) |
| 2 | Every sample passes Faithful with default boxes | **Pass** | L-08 (polish, scenarios mutation score) |
| 3 | Proof strength: tier rule on a calculated cell | **Fail** | L-04 |
| 4 | Semantics on LibreOffice 7.4.7.2 | **Fail** (R-07, `1E+20` and the `Bulk` name pass) | L-02, L-03, L-05 |
| 5 | Autopsy and Decisions | **Pass** | none |
| 6 | Uploads and safety | **Pass** | none |
| 7 | Sessions and jobs | **Pass** | none |
| 8 | Downloaded module runs standalone | **Pass** | none |
| 9 | Accessibility | **Pass** | none |
| 10 | CloudWatch logs | **Pass** (no 5xx, no tracebacks) | L-02 (job crashes don't appear in the logs) |

## Findings

| ID | Severity | Summary | Live | Local (LibreOffice 26.8.3) |
|---|---|---|---|---|
| L-02 | **Wrong result** | The report writer crashes when an Excel error value reaches a mismatch or a mutant's counterexample. The job fails and no report can be downloaded. | yes | yes |
| L-03 | **Wrong result** | `=INDEX(M1:M3,0)` in a cell on row 3: the Referee gives 9 (implicit intersection), Ghost gives `#VALUE!` | yes | yes |
| L-04 | **Wrong result** (proof strength, R-04 not met) | Tier rule `IF(Total>=500,…)` on a calculated cell: no exact hit at 500, and the `>=`→`>` mutant survives | yes | yes |
| L-05 | **Wrong result** | The default boxes pre-check an output that was "not converted" (an `OFFSET` name). Verify then fails with "translation bug". | yes | not checked |
| L-06 | Polish | The boundary table puts values in the wrong columns, shows raw JSON, and says "not checked" for exact hits that exist | yes | same code |
| L-07 | Polish | Survivor text gives a different tested domain (min -1, max 60000) from the report's "Tested domains" table (min 0, max 10000) | yes | same code |
| L-08 | Polish (demo) | The scenarios sample shows mutation "55 of 132 killed" | yes | not checked |

### L-02: the report crashes on Excel error values (wrong result)

**Steps:**
1. Upload `sem_index.xlsx`:
   - `Calc!A1` "Amount", `B1` = 4, `B2` = `=B1*2`;
   - `M1:M3` = 7, 8, 9;
   - `B3` = `=INDEX(M1:M3,0)`, `B4` = `=INDEX(M1:M1,0)`.
2. `POST /verify` with `inputs=Calc!B1`, and outputs `Calc!B3` (job `_wl241QgcLA4-GAU`) or `Calc!B4` (job `Q9AJ-lpaRwgwaabm`).

**Expected:**
- B3: a report showing the mismatch.
- B4: a pass. Ghost and the Referee both give 7.

**Actual:**
- Both jobs end `failed`, "Verification found mismatches.", and `report.json` and `report.html` return 404.
- The job events end with a Python traceback: `TypeError: Object of type ExcelError is not JSON serializable`.
- For B4 the baseline passed. The crash comes from the mutation check: a mutant such as `INDEX(M1:M1,1+1)` gives `#REF!`, its counterexample holds an `ExcelError`, and the report can't be written. So the message "found mismatches" is wrong.
- The same thing happens locally through `TestClient`.
- An output that is an Excel error on both sides (`=10/B1` at 0, job `I_gq7peCOkZqvyMk`) passes, so it only fails when the error value appears in a mismatch or a counterexample.
- CloudWatch shows no trace of it, because the traceback stays in the job's events.

**Likely cause:** `ghost/report/model.py:144-148`. `report_to_json` calls `json.dumps` on data that can contain `ghost.runtime` `ExcelError` objects, and there is no converter.

**Suggested fix:**
- Convert `ExcelError` to its text (for example `"#VALUE!"`) in `report_to_dict`, for mismatch values and mutant counterexamples.
- Add a test with an `INDEX` mutant that returns `#REF!`.

### L-03: `INDEX(range,0)` ignores implicit intersection (wrong result)

**Steps:** same workbook as L-02. B3 is `=INDEX(M1:M3,0)` and sits on row 3, inside the rows of `M1:M3`.

**Measured with input `amount=4`:**

| | Ghost | Referee, LibreOffice 26.8.3 (local) | Referee, LibreOffice 7.4.7.2 (live) |
|---|---|---|---|
| B3 | `#VALUE!` | `9.0` | job fails |

- The live job fails as described in L-02, so the value can't be read from a live report.
- Ghost's `#VALUE!` is only right when the formula's row is outside the range.
- Legacy Excel also intersects implicitly here. Excel 365 spills instead. Excel's result was not checked.

**Likely cause:** the R-08 change in `_index` (`ghost/converter/emit_python.py`) returns `#VALUE!` for row 0 whatever the formula cell's position.

**Suggested fix:**
- Apply implicit intersection: when the formula cell's row (for a single-column range) or column (for a single-row range) lies inside the range, return that element. Otherwise return `#VALUE!`.
- Add both placements to the golden tests.

### L-04: tier rule on a calculated cell is not proved at the boundary (wrong result, R-04)

**Steps:**
1. Upload `tier.xlsx`:
   - `A2` "Quantity", `B2` = 3;
   - `A3` "Price", `B3` = 25.5;
   - `B4` = `=B2*B3`;
   - `B5` = `=IF(B4>=500,"Gold","Standard")`.
2. Verify with the default boxes: inputs `Calc!B2`, `Calc!B3`, output `Calc!B5`. This was job `rWR5ZAGFf_qnh3q5`, 7.2 s.

**Expected:**
- The boundaries list B5's condition with an exact hit at 500.
- The mutation check kills the `>=`→`>` mutant.

**Actual:**
- Boundaries:
  - `('Calc!B5', 'price', below 166.666, above 166.667, exact None)`
  - `('Calc!B5', 'quantity', below 19, above 20, exact None)`
  - No exact hit, and the HTML says "not checked".
- Mutation: 4 of 5 killed. The survivor is `M-e39c9b66 Calc!B5 flip_comparison`, "no difference found on 62 distinct cases; tested domain: price: decimal, min -1, max 10000, up to 3 decimal places; quantity: integer, min -1, max 10000, 0 decimal places".
- It passes Faithful because the planted `>` is never tested at exactly 500. Local `TestClient` gives the same boundaries and the same survivor.

**Likely cause:**
- `ghost/verifier/flip.py:324-372` varies one input at a time from the sample values.
- With quantity 3, no 3-decimal price gives exactly 500 (500/3). With price 25.5, no whole quantity gives 500.
- `flip.py:370` never records an exact hit for integer inputs (`exact = None if integer`).

**Suggested fix:**
- When a condition flips, also search with the other numeric inputs set to small values such as 1, 2, 4, 5 and 10, so that the threshold can be hit exactly (for example 1 × 500).
- Record an integer exact hit when `above` makes the comparison an equality.

**Planted bug through the web flow:** not checked live, because the web flow can't take user code. This is covered by local tests.

### L-05: a not-converted output is pre-checked and then fails as a "translation bug" (wrong result)

**Steps:**
1. Upload `sem_names.xlsx`:
   - `A2` "Quantity", `B2` = 30;
   - `D1` "Bulk level", `E1` = 50;
   - workbook names `Bulk` = `Calc!$E$1` and `Dyn` = `OFFSET(Calc!$E$1,0,0)`;
   - `C2` = `=Bulk*2`, `C3` = `=IF(B2>=Bulk,"bulk","small")`, `C4` = `=Dyn*2`.
2. Verify with the default boxes: inputs `Calc!B2`, `Calc!E1`, outputs `Calc!C2`, `C3`, `C4`. This was job `Pl8wPBBeITA8UvIV`, 3.7 s.

**Expected:**
- C4 is listed as "not converted" and left out of the comparison (guardrails 6 and 7).
- C2 and C3 verify.

**Actual:**
- The autopsy correctly says: "Not converted: Calc!C4: named reference Dyn is not supported: dynamic name (formula such as OFFSET or INDIRECT)".
- C4 is still pre-checked as an output. Verify fails on the first case:
  - `{'class': 'translation bug', 'output': 'calc_c4', 'expected': {... 'calc_c4': 60.0}, 'actual': {... 'calc_c4': None}}`
  - mutation is "not checked".
- With outputs C2 and C3 only, it passes Faithful (job `2L7MNt2bKErBRJRJ`, 300 + 2 targeted, 280 distinct, mutation 7/7). So the `Bulk` conversion (R-27) works on the live Referee.

**Likely cause:** the autopsy default outputs (`web/flow.py`, `_describe`) don't exclude not-converted cells, and the verifier doesn't skip them.

**Suggested fix:**
- Don't offer or pre-check not-converted cells as outputs.
- If one is chosen anyway, report it as "not converted" rather than as a translation bug.

### L-06: boundary table layout (polish)

`ghost/report/html.py:191-201`, seen in the haunted report for job `zBkkB8Vok9fwCW0q`:
- **Wrong column:** on flip rows the text "condition flip: 49 (one side), 50 (other side)" sits under "Owner of threshold", and "Change-point bracket" is empty.
- **Raw JSON:** on threshold rows "Change-point bracket" shows `[{"first_changed": 50, "last_unchanged": 49}]`.
- **Missing exact hits:** "Exact hits" says "not checked" on every row, even though quantity 50 is an exact hit for `B7`'s `>=50`. This follows from the integer case in L-04.
- **Threshold column:** the `B9` flip row shows Threshold `51`, which is really the change point.

**Fix:** put the flip text in the bracket column, render brackets as "49 → 50", and fill exact hits for integer flips.

### L-07: two different tested domains in one report (polish)

- In the haunted report, "Tested domains" says `quantity: integer, min 0, max 10000`.
- Every survivor reason says `quantity: integer, min -1, …`.
- For scenarios, the survivor reason says `gross_income … max 60000`, while the table says `max 10000`.

**Cause:** `ghost/verifier/coverage.py:86` always adds 0 and -1 as targeted values, and the sample value (60000) as a base, even when the input's minimum is 0. The mutation check runs those cases (`ghost/mutation/run.py:211`).

**Fix:** clamp targeted values to the `IOSpec` min and max, or label the survivor domain as "mutation cases".

### L-08: the scenarios sample shows 55 of 132 mutants killed (polish, demo)

- Job `PTGz_4QP4TtdgXDU`: Faithful passes, 300 generated, 176 distinct, but mutation is 55/132.
- The 77 survivors are `constant_plus_one` (36), `constant_minus_one` (31) and `rounding_mode` (10). Most are on rows F6 to F15 and B6 to E15.
- These are rates and fees of scenarios that never become the cheapest on the tested inputs, so `MIN` and `INDEX`/`MATCH` hide the change.
- The wording is honest ("no difference found on 78 distinct cases"). Judges may still read 42% as a weak proof.
- `cases_targeted` is 0 and there are no boundaries, because `MAX` and `MATCH` have no `IF` to flip.

**Fix:** either explain in the report why survivors happen, or aim cases at each scenario becoming the best one (vary gross income across its range).

## Item details

### 1. Demo storyline (haunted)
- `/healthz`: 200 `{"status":"ok","referee":{"available":true}}` (1.0 s).
- Autopsy defaults: inputs `Calculator!B2`, `B3`, `B4`; output `Calculator!B11`. `E5` is not pre-checked.
- F-001: "operator conflict on Calculator!B2 against 50 Calculator!B7 uses >= Calculator!B9 uses >".
- D-001 recorded (`set|Calculator!B9|>|>=`).
- Verify, job `zBkkB8Vok9fwCW0q`, done in 6.9 s:
  - Intended passes.
  - 309 cases: 300 generated + 9 targeted, 198 distinct.
  - Exactly one mismatch: `total`, "expected by decision", F-001 / D-001. Minimal inputs `quantity 50, unit_price 0, delivery_distance_km 0`, Referee 6.0, new code 0. It explains 26 distinct cases.
- Mutation: 33 of 35 killed. The survivors are `M-3cbed5dc` (B9) and `M-687cf270` (B10), both `rounding_mode`, worded "no difference found on 98 distinct cases; tested domain: …". The word "equivalent" doesn't appear.
- `report.html` shows:
  - "300 generated + 9 targeted, 198 distinct";
  - Tested domains;
  - Change-point bracket and Exact hits columns;
  - boundary notes;
  - "not cross-checked against Excel";
  - Seed 20261204.
- The panel links `?mode=faithful`. `report.html?mode=faithful` and `report.json?mode=faithful` return 200 and show Faithful passing with 0 mismatches.
- No absolute server paths in events, the panel or the reports. The events now read `module: ./logic_intended.py`.

### 2. Every sample with default boxes

| Sample | Default inputs → outputs | Job | Result | Time |
|---|---|---|---|---|
| discount | B2, B3, B4 → B11 | `VGgUCdFskyjl5jDW` | Faithful pass, 300 + 6, 195 distinct, mutation 31/33 | 7.2 s |
| haunted | B2, B3, B4 → B11 | `tMBRSOmFqzY8-53a` | Faithful pass, 300 + 9, 198 distinct, mutation 33/35 | 7.0 s |
| scenarios | `Model!B2`, `B3`, `E2` → `B19`, `B20` | `PTGz_4QP4TtdgXDU` | Faithful pass, 300 + 0, 176 distinct, mutation 55/132 (L-08) | 30.5 s |

- Scenarios now pre-checks 3 inputs instead of 53 (R-05 fixed live).
- `mapping.yaml` in the scenarios `module.zip` has `best_scenario: {cell: Model!B19, type: string}` (R-26 fixed live).

### 3. Proof strength
Fail: see L-04. A planted bug through the web flow was not checked live; it is covered by local tests.

### 4. Semantics on LibreOffice 7.4.7.2

| Formula | Job | Result |
|---|---|---|
| `=IF(10/3*3>=10,"ok","low")`, `=1/3*3=1` (R-07) | `r2yUh20b2cJhVWWn` | Pass, 300 cases, 0 mismatches |
| `=INDEX(M1:M3,0)` (R-08) | `_wl241QgcLA4-GAU` | Fail, L-02 and L-03 |
| `=INDEX(M1:M1,0)` (R-30) | `Q9AJ-lpaRwgwaabm` | Values match (7), but the job fails on the report crash (L-02) |
| `=1E+20&""` (R-08) | `jF9nqmQAwQe0a82a` | Pass, 300 cases, 0 mismatches |
| `Bulk` name in `=Bulk*2` and `IF(B2>=Bulk,…)` (R-27) | `2L7MNt2bKErBRJRJ` | Pass. Converted, with flip boundaries on C3 |
| `OFFSET` name `Dyn` | `Pl8wPBBeITA8UvIV` | Listed as "not converted" with a reason (pass); the default boxes then fail (L-05) |

### 5. Autopsy and Decisions
- A second `POST /decision` for F-001 returns **409** "F-001 already has a Decision.". It also shows on the page (item 9).
- `complementary.xlsx` (`A1>=50` and `A1<50`) raises no Finding. Job `7OHJRrYI6tvQcESK` passes with mutation 18/18.
- `input_threshold.xlsx` (`A9`=90, `E9`=`=40+10`, `IF(A9>=E9,…)`): no threshold of 90 anywhere. The only boundary is the flip at 49/50 against `E9`. Job `7xbKtaJvHq6awrvw` passes with mutation 11/11.

### 6. Uploads and safety

| Upload | Response | Time |
|---|---|---|
| `wrong.csv` | 422 "Unsupported file type. Accepted formats: .xlsx and .xlsm." | 0.27 s |
| `big.xlsx` (6 MB) | 413 "File is larger than the 5 MB limit." | 9.87 s (upload time) |
| zip bomb | 422 "Workbook expands to too much data; rejected." | 0.72 s |
| billion laughs | 422 "Workbook XML rejected as unsafe: EntitiesForbidden(name='lol', …)" | 0.32 s |
| XXE on `/etc/passwd` | 422 "…EntitiesForbidden(name='xxe', system_id='file:///etc/passwd', …)" | 0.35 s |
| 20,001 formulas | 422 "Workbook has more than 20,000 formulas; the limit is 20,000." | 3.28 s |
| 250,000 cells (openpyxl write-only, 874 KB) | 422 "Workbook has more than 200,000 cells; the limit is 200,000 cells." | **4.22 s**, including the upload (under 5 s) |
| `make_xlsm.py` `discount_vba.xlsm` renamed `.xlsx` | 200, `has_vba: true`; autopsy "VBA lines: 23 in 1 module(s)" | 0.51 s |
| same file with a corrupt `xl/vbaProject.bin` | 200, `has_vba: true`, `vba_error`: "VBA present but could not be read: ValueError: xl/vbaProject.bin is present but holds no readable VBA modules"; autopsy shows it with "(VBA: not checked)" | 0.43 s |

- No macro was run.
- **Escaping:** sheet `<img src=x>`, label `<script>alert(1)</script>` and output text `<script>alert(2)</script>` are escaped in the autopsy, the panel and `report.html` (job `4F5oo93ZRfo5Va5T`). The raw text appears only in the `/jobs/{id}` JSON, which is `application/json`, not HTML.
- **Server paths:** none found in any saved event, error body, report or module. I searched for `/tmp/`, `/app/`, `/home/`, `/opt/`, `/usr/` and `/var/`.

### 7. Sessions and jobs
- A second `/verify` while scenarios job `iSG_GE4gXK0n8SSd` was running returned **429** with "This session already has a verification queued or running. Wait for it to finish, then start a new run." It showed the running job's panel.
- After that job finished (50.6 s), a new `/verify` returned 200 (job `k6ELs0ENzTJLi-At`).
- **Another session:**
  - It gets 404 on `/jobs/{id}`, `/panel`, `report.json`, `report.html`, `module.py` and `module.zip`.
  - Forged-MAC, garbage and sid-only cookies get 404 and a fresh `ghost_session` cookie.
- **`DELETE /session`:**
  - It returns 200 `{"ok":true}` and clears the cookie (`Max-Age=0`).
  - The old job id then returns 404 on `/jobs` and `report.json`.

### 8. Downloaded module
- I unzipped the haunted Faithful `module.zip` (`logic.py`, `excel.py`, `mapping.yaml`, `rules.md`) into an empty folder.
- I ran it with `/usr/bin/python3 -I` (Python 3.9.6, which has neither `openpyxl` nor `ghost`).
- `logic.compute({'quantity': 50, 'unit_price': 0, 'delivery_distance_km': 0})` gives `{'total': Decimal('6.00')}`, which matches the report.

### 9. Accessibility
Checked in the browser pane at 360 × 780.
- **Layout:** `scrollWidth` is 360 in dark and light themes, on the home page and on the autopsy and job panel.
- **Theme toggle:** the label stays "Light mode", and `aria-pressed` changes between false and true.
- **Contrast:**
  - Dark border `rgb(122,109,148)`: **3.96:1** on the background and **3.65:1** on the surface.
  - Light border: 4.21:1. Light text: 15.48:1.
- **Keyboard only:** the order is Skip link → toggle → file → Upload → samples → decision radios (arrow keys) → author → reason → Record decision → Run verification. Every control shows `outline: solid 3px`. The whole haunted flow (sample, D-001, verify) was done with Tab, arrow keys, typing and Enter. It ended "Passed (intended mode, 300 generated + 9 targeted, 198 distinct cases, 1 mismatch(es), seed 20261204)".
- **Errors on the page:** 429 (Run verification pressed twice), 409 (a second decision submitted) and 422 (a `.csv` upload) each appear in a `role="alert"` element.
- **Not checked:** a real screen reader.

### 10. Logs
- Log group `/aws/ecs/default/ghost-in-the-macro-8bf8`, from 13:00 UTC: 510 lines.
- Status codes: 200 × 472, 304 × 1, 404 × 23, 409 × 2, 413 × 1, 422 × 9, 429 × 2.
- No 5xx, no `Traceback`, no `ERROR`.
- The L-02 crashes happen inside job subprocesses and don't reach the service log.

## Job durations on the live host

| Job | Workbook | Status | Time |
|---|---|---|---|
| `zBkkB8Vok9fwCW0q` | haunted + D-001 (Intended and Faithful) | done | 6.9 s |
| `VGgUCdFskyjl5jDW` | discount | done | 7.2 s |
| `tMBRSOmFqzY8-53a` | haunted, Faithful | done | 7.0 s |
| `PTGz_4QP4TtdgXDU` | scenarios | done | 30.5 s |
| `iSG_GE4gXK0n8SSd` | scenarios (item 7) | done | 50.6 s |
| `rWR5ZAGFf_qnh3q5` | tier | done | 7.2 s |
| `r2yUh20b2cJhVWWn` | sem_div | done | 6.9 s |
| `fhRnTMrb5tPnC2RP` | sem_index, default boxes | failed | 3.6 s |
| `mEFMoh4ML8r17MZL` | sem_index, input B1 only | failed | 3.7 s |
| `_wl241QgcLA4-GAU` | sem_index B3 | failed | 6.9 s |
| `Q9AJ-lpaRwgwaabm` | sem_index B4 | failed | 7.2 s |
| `jF9nqmQAwQe0a82a` | sem_sci | done | 7.1 s |
| `Pl8wPBBeITA8UvIV` | sem_names, default boxes | failed | 3.7 s |
| `2L7MNt2bKErBRJRJ` | sem_names C2, C3 | done | 6.8 s |
| `7OHJRrYI6tvQcESK` | complementary | done | 6.9 s |
| `7xbKtaJvHq6awrvw` | input_threshold | done | 7.4 s |
| `4F5oo93ZRfo5Va5T` | xss | done | 6.9 s |
| `I_gq7peCOkZqvyMk` | div0 | done | 7.0 s |

The time is from submit to the final status, polled every 3 s. Three more jobs were not timed: `MMwrP8-qxUhawHdj` (a debug rerun of xss), `k6ELs0ENzTJLi-At`, and the keyboard run in the browser.

The two scenarios runs differ: 30.5 s versus 50.6 s, with no other job of mine running. The cause was not checked.

## What I couldn't test, and why
- **A planted bug through the web flow (item 3):** the web app can't take user code. This is covered locally by `tests/test_review_proof_strength.py`.
- **Excel's result for L-03:** no Excel here.
- **A real screen reader:** not checked.
- **The 5-minute job timeout on the live host:** not checked, because it needs a long job.
- **Memory headroom under the cell cap:** not checked. A file just under 200,000 cells was not uploaded, to keep load modest.

## Scripts and files (all in `/tmp/ghost-live/`)

**Scripts:**

| File | What it does |
|---|---|
| `lib.py` | HTTP helpers (cookie jar per session, verify, poll, download) |
| `item1_2.py` | items 1, 2 and the R-14 check |
| `build.py` | builds the upload workbooks into `wb/`; run from the repo root with `.venv/bin/python` |
| `item3_5.py` | items 3 to 5 |
| `rerun.py` | isolates L-02 and L-05 |
| `item6_7.py` | items 6 and 7 |
| `local_web.py` | the same web flow run locally through FastAPI `TestClient` |

**Outputs:**

| Path | Contents |
|---|---|
| `out/` | logs, downloaded reports and modules, `cw.json` (CloudWatch messages) |
| `mod/` | the unzipped module used for item 8 |

The attack files in `wb/` were copied from the earlier review's scratchpad.

## Live-test resolution

Fixes made locally under the bugfix spec `.kiro/specs/live-fixes-2026-11-24/`. Nothing has been redeployed, so the live site still shows the findings above until the owner redeploys and re-runs this test.

| Finding | Status | What changed | Test that proves it |
|---|---|---|---|
| L-02 | fixed (local and local Docker 7.4.7.2; live not re-tested) | `ghost/report/model.py` writes every Excel error in a report as its text (for example `"#VALUE!"`), in mismatches, mutant counterexamples and boundary cases. The HTML report shows the same text and has a new "Counterexample" column in the mutation table. The MCP tools serialise errors the same way. The schema was already open enough and is unchanged. A failure while writing a report now gives `ghost: error: <ExceptionType>: <message>` and exit code 4 in the CLI, the panel text "The report could not be written (<ExceptionType>: …)" with server paths removed, and an MCP `report_not_written` error. "Verification found mismatches." now appears only for exit 1 with no traceback and no `ghost: error:` line. Local runs (LibreOffice 26.8.3): the repro gives Faithful pass and mutation 3/4 through `ghost verify`, and the report lists a mutant killed with `#REF!`. MCP `generate_proof_report` and `verify_implementation` return reports. `=SUM("5",B1)` gives a report listing the mismatch with Referee `"#VALUE!"`. Open question for the owner: an exit 1 with a `ghost: error:` line that is not about writing the report (for example "Referee unavailable") also shows "The report could not be written (…)". This was left unchanged. | `tests/test_live_findings.py`: `test_l02_report_to_json_serialises_excel_errors`, `test_l02_sem_index_b4_web_job_writes_report`, `test_l02_report_write_failure_panel_text`, `test_l02_mismatch_holding_excel_error_is_reported`, `test_l02_cli_and_mcp_write_reports_with_excel_errors`; `tests/test_property_report_excel_errors.py` (Property 3); `tests/test_report_write_failure.py` |
| L-03 | fixed (local and local Docker 7.4.7.2; live not re-tested) | Measured `INDEX` with a 0 row or column on the Referee first: 69 cases plus 84 contexts, identical on LibreOffice 26.8.3.1 and 7.4.7.2 (`.kiro/specs/live-fixes-2026-11-24/measurements-l03.md`). `ghost/converter/emit_python.py` now gives the range origin and the formula cell's sheet, row and column to `INDEX`. A 0 row (single column) or 0 column (single row) picks the element on the formula's row or column when it lies in the range's span, and gives `#VALUE!` otherwise. A grid with one index 0 does the same on the selected column or row. A direct `INDEX` argument of `SUM`, `AVERAGE`, `MIN`, `MAX`, `AND`, `OR` aggregates the whole selection. R-30 (single cell) is unchanged. A negative index is now `#VALUE!` like the Referee. An `INDEX` passed through `IF`, `IFERROR` or `CHOOSE` inside an aggregate is "not converted" (`INDEX_PASSED_THROUGH`). The repro with `B3` = `=INDEX(M1:M3,0)` and `B4` as outputs passes Faithful through the web app (300 cases, 0 mismatches, mutation 7/10; the 3 survivors change `M2`, which neither output reads, or the R-30 index). `.kiro/steering/excel-semantics.md` has the measured rules. Excel was not checked; Excel 365 spills instead. Found, not fixed: an index past the end is `#REF!` on 26.8.3.1 but `#VALUE!` on 7.4.7.2, and Ghost gives `#REF!`, so such a workbook shows a mismatch on the live site. `SUM(IF(TRUE,N5))` with text in N5 is 0 on the Referee and `#VALUE!` in Ghost (both versions). | `tests/golden/test_index_zero_golden.py` (20 cases, each against the Referee and the generated code); `tests/test_live_findings.py`: `test_l03_index_row0_inside_range_matches_referee`, `test_l03_sem_index_b3_b4_web_job_passes_faithful`; `tests/test_property_index_zero.py` (Property 4); `tests/test_index_zero_measurement.py`; `tests/test_index_zero_contexts.py`; `tests/test_review_semantics.py` (`index_out_of_range` pinned per LibreOffice version) |
| L-04 | fixed (local and local Docker 7.4.7.2; live not re-tested) | `ghost/verifier/flip.py` now confirms an exact hit from the values the module compares (integer and decimal flips alike: a decimal hit the bisection infers is kept only when the module's compared values confirm it, otherwise it is dropped and "exact hit not checked" is noted), never from the operator, and retries a flip with the other numeric inputs set to 1, 2, 4, 5 or 10 when no exact hit was confirmed. `Flip.cases()` (below, above, exact) feed both the verifier's extra cases and the mutation check's targeted cases, in `ghost/cli.py` `run_verification` and MCP `verify_implementation`. Local repro (B2 = 3, B3 = 25.5, B4 = `=B2*B3`, B5 = `=IF(B4>=500,"Gold","Standard")`, default boxes, real LibreOffice 26.8.3, web app): Faithful pass, 300 generated + 16 targeted, 0 mismatches. Calc!B5 boundaries: `price` exact hit 500.000 (below 499.999, above 500.000) and `quantity` exact hit 500 (499, 500). Mutation 5/5; the `flip_comparison` mutant on B5 is killed at price 500.000, quantity 1 (Total = 500). Demo unchanged: haunted 33/35, discount 31/33. Excel was not checked. | `tests/test_live_findings.py::test_l04_tier_exact_hit_and_flip_mutant_killed`; `tests/test_property_exact_hits.py`; `tests/test_flip_integer_exact.py`; `tests/test_flip_reporting.py`; `tests/test_property_condition_flip.py`; `tests/test_review_proof_strength.py` |
| L-05 | fixed (local and local Docker 7.4.7.2; live not re-tested) | Not-converted and not-verifiable cells are no longer offered or pre-checked as outputs (task 3.14, `not_offerable_outputs`). An explicit choice is now rejected at verification time, not inside `classify()` or `generate_mapping`, which still honour it. One shared check, `ghost.cli.require_verifiable_outputs` (reasons from `unverifiable_output_reasons` in `ghost/autopsy/classify.py`), is called by web `POST /verify` (422, shown on the page, nothing stored), the MCP tools `verify_implementation`, `generate_proof_report` and `mutation_check` (`invalid_argument`, argument `outputs.<cell>`), and `ghost convert`, `rules` and `verify` (a `CliError` message). The message names the cell and the reason and never says "translation bug". The report has an optional `not_converted` list of `{cell, reason}` (model, schema, HTML section "Not converted"), filled from `find_not_converted` on every run and omitted when empty, so old reports stay valid and identical. Default boxes B2 -> C2, C3 on the repro: Faithful pass, report lists `Calc!C4`. Excel and the live site: not checked. | `tests/test_live_findings.py::test_l05_explicit_not_converted_output_is_rejected` (strict-xfail marker removed, assertions unchanged), `tests/test_not_converted_rejection.py` (web 422 for C4 and for a volatile cell and its dependant, MCP, CLI, `not_converted` in the report, default-boxes run), `tests/test_property_not_converted_outputs.py` |
| L-06 | fixed (local and local Docker 7.4.7.2; live not re-tested) | `ghost/report/html.py` builds the boundary table cell by cell: "Change-point bracket" shows readable text (`49 → 50`, `499.999 → 500`) for threshold rows (from `last_unchanged`/`first_changed`) and flip rows (below → above), with no raw JSON; "Owner of threshold" holds only `at`/`above` (flip rows: "not checked"); "Threshold" shows the real constant, or "calculated" when no constant exists, or "not checked" when flip probing could not tell, never the change point; "Exact hits" keeps the task 3.12 text. New optional fields `threshold_constant` and `threshold_calculated` on `BoundaryResult` (schema backward compatible), set by `find_flips` from the compared values at below/above and with each other numeric input changed (own allowance of 1500 evaluations, not counted in `evaluations_used`). Haunted: B7 `49 → 50`, B9 `50 → 51`, Threshold 50, quantity 50 an exact hit (with delivery_distance_km = 12, unit_price = 19.95). Demo unchanged: haunted 300 + 9 targeted, 198 distinct, Intended one expected-by-decision mismatch at quantity=50; mutation haunted 33/35, discount 31/33. Excel and the live site were not checked. | `tests/test_report_boundary_table.py` (7 tests, markers removed); `tests/test_report_details.py::test_html_separates_change_points_from_real_exact_hits` (assertion updated, see KIRO_USAGE) |
| L-07 | fixed (local and local Docker 7.4.7.2; live not re-tested) | **Owner decision (task 5.4): widen the domain to include the workbook's own sample value, then clamp.** One definition, `ghost/verifier/domain.py`: min = declared `IOSpec` min (no lower bound if none), max = largest of the declared max, `default_max` 10,000 and the sample value. Targeted cases (`candidate_inputs`), flip probing, the mutation check's targeted list and the Hypothesis strategies all stay inside it, so -1 is dropped where min is 0 and the scenarios sample `gross_income` 60,000 is kept (domain 0..60,000). Survivor reasons and the "Tested domains" table now show the same ranges (haunted and discount: min 0, max 10000; scenarios `gross_income` max 60000). The table says so when the max was widened ("Max of gross_income includes the workbook's own value 60000.", optional `max_includes_sample` per row, schema backward compatible) and states that it lists the verification cases, with mutation cases inside the same ranges. The case counts still differ (verification vs mutation cases), so the survivor wording `no difference found on N distinct cases` is unchanged and the table is labelled instead. Demo unchanged: haunted 300 + 9 targeted, 198 distinct, Intended one expected-by-decision mismatch at quantity=50; mutation haunted 33/35, discount 31/33 (survivors now "95" and "93 distinct cases", min 0). **Scenarios 55/132 -> 54/132**: mutant `M-cb3d2f05` (`Model!C6`, `constant_plus_one`) was only killed by a -1 case, which is now outside the domain. Excel and the live site: not checked. | `tests/test_property_targeted_domain.py` (5 tests, strict-xfail markers removed, assertions unchanged); `tests/unit/test_effective_domain.py` (3 tests, incl. the sample note) |
| L-08 | fixed (local and local Docker 7.4.7.2; live not re-tested) | Score on the scenarios sample (`Model!B2`, `B3`, `E2` → `B19`, `B20`, `ghost mutate --mode faithful`, LibreOffice 26.8.3): **55/132 live, 54/132 after L-07** (the -1 cases were dropped), **70/132 after the targeted search** (53%); best reachable 73/132 (`.kiro/specs/live-fixes-2026-11-24/measurements-l08.md`). Task 5.7: new `ghost/verifier/selection.py` finds inputs where the row picked by `MAX`, `MIN` or `MATCH` changes and feeds them to the verifier and the mutation check (300 generated + 54 targeted, 206 distinct, was 300 + 0, 152). The same search adds 2 cases each for `MAX(0,...)`: haunted is now 300 + 11 targeted, 200 distinct and discount 300 + 8, 197 distinct (the owner accepted these counts; mutation 33/35 and 31/33 unchanged). Task 5.8: of the 62 remaining scenarios survivors, 44 are constants on rows that never win on the tested inputs and 15 change no output on any tested input on rows that can win (mostly `rounding_mode` and `ROUND` digits), and 3 more are killable in principle but the search did not find a separating input. No mutant was removed and the score formula is unchanged. The mutation section now says: "These constants belong to rows that never become the best result on the tested inputs, or change no output on any tested input, so changing them doesn't change any output." It is shown only when a survivor changed no output on any tested input and the module's selection never picked some row (optional `survivor_kind` on a mutant and `survivor_explanation` in `mutation`, schema unchanged for old reports); it is absent for haunted and discount. It states what was seen and does not claim equivalence. | `tests/test_survivor_explanation.py` (sentence in JSON and HTML only when marked; scenarios report has it, haunted has none; no equivalence wording), `tests/test_selection_search.py`, `tests/test_mutation_wording.py` |

Phase 1 checkpoint (L-02 to L-05): full suite `908 passed, 2 skipped, 0 failed, 0 xfailed` (baseline was `415 passed, 2 skipped`). `scripts/demo.sh`: discount Faithful pass (300 generated + 6 targeted, 195 distinct, 0 mismatches); haunted F-001 raised, Faithful pass (300 + 9 targeted, 198 distinct, 0 mismatches); haunted with D-001 Intended pass with one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0). The demo does not run the mutation check, so mutation scores come from `tests/test_mutation_samples.py` (floors haunted 33/35, discount 31/33), which passed. All five demo `proof-report.json` files validate against `proof-report-1.json`. L-06 to L-08 are still pending.

Phase 2 checkpoint (L-06 to L-08): full suite `932 passed, 2 skipped, 0 failed, 0 xfailed` (Phase 1: 908 passed, 2 skipped; baseline 415 passed, 2 skipped). Fresh `scripts/demo.sh` reports (3 migration reports plus 2 top-level copies) and the scenarios report (`convert` then `mutate --mode faithful`, mutation 70/132, survivor explanation present) all validate against `proof-report-1.json`. The schema diff against HEAD only adds optional properties (`not_converted`, `max_includes_sample`, `exact_others`, `exact_note`, `threshold_constant`, `threshold_calculated`, `survivor_explanation`); the `required` lists are unchanged, apart from the new optional `not_converted` item shape (`cell`, `reason`). `survivor_kind` is not a schema property: mutant items allow extra fields. L-06 to L-08 rows are present above. LibreOffice 26.8.3 locally; Excel and the live site: not checked.

Status basis for "local Docker 7.4.7.2": the container run in task 7.4 (`.kiro/specs/live-fixes-2026-11-24/docker_runs.results.json`, LibreOffice 7.4.7.2, web app, default boxes) gave these results. Haunted: F-001, decision recorded, Faithful pass (300 + 11 targeted, 200 distinct, 0 mismatches), Intended pass with one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0), mutation 33/35. L-02 `sem_index`: job done, report written, Faithful pass, mutation 3/4. L-03 `sem_index` with B3: Faithful pass, mutation 7/8. L-04 `tier`: Faithful pass (300 + 16 targeted), mutation 5/5, exact hits at 500.000 (price) and 500 (quantity). L-05 `sem_names`: Faithful pass, `Calc!C4` listed under not converted and not offered as an output, mutation 5/5. Scenarios sample: Faithful pass (300 + 54 targeted, 206 distinct), mutation 70/132. L-06 is confirmed from the report data (threshold constant, exact hits, `exact_others`); the HTML boundary table was not inspected in the container. The live site and Excel: not checked.

### Open items

- (a) An exit 1 with a `ghost: error:` line that is not about the report (for example Referee unavailable) also shows "The report could not be written". Left unchanged.
- (b) `INDEX` past the end of the range: `#REF!` on LibreOffice 26.8.3, `#VALUE!` on 7.4.7.2. Ghost gives `#REF!`, so such a workbook shows a mismatch on 7.4.7.2.
- (c) `SUM(IF(TRUE,N5))` with text in N5: the Referee gives 0, Ghost gives `#VALUE!`.
- (d) Decimal thresholds finer than the 0.001 probe step are not checked (a note in the report says so).
- (e) A fully negative small-value retry shows "not checked".
- (f) For haunted, the exact hit lists other inputs (`delivery_distance_km` 12, `unit_price` 19.95) that the condition does not depend on.
- (g) Three scenarios survivors are killable in principle, but the search found no separating input.

Final checkpoint (tasks 7.1 to 7.4): full suite 932 passed, 2 skipped, 0 failed; golden 67 passed; demo storyline unchanged (discount Faithful pass; haunted F-001, Faithful 0 mismatches, Intended pass with one expected difference at quantity 50, Referee 6.0, new code 0; mutation haunted 33/35, discount 31/33); Docker run on LibreOffice 7.4.7.2 as listed above. Excel and the live site: not checked.
