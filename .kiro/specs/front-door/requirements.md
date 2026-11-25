# Requirements Document

## Introduction

Feature 2 of the Kiroween feature set (source: `docs/KIRO_FEATURE_PROMPT_2026-11-25.md`, "Feature 2: front door and live progress"). Today the Web_App landing page is a title, a privacy note, a file input and three sample buttons. During a verification run the user sees the last 12 raw CLI lines, re-announced to screen readers every second.

This feature gives the Web_App:

- a landing page that says what Ghost does and who it is for;
- a five-step Stepper shared by every screen;
- Sample_Cards with a workbook download;
- a Progress_Rail driven only by lines the CLI actually prints, with a Graveyard_Grid for the mutation self-check;
- designed Failure_Cards;
- a Theme_Pass done as a deliberate vibe session.

Facts from the current code that these requirements rely on:

- The CLI prints `mutation check: mutant i/n` after each mutant, with i from 1 to n (`ghost/cli.py`, `ghost/mutation/run.py`). When the mutation self-check cannot run it prints `mutation check: not checked (<reason>)`.
- The CLI prints `[faithful] PASS|FAIL: ...` and `[intended] PASS|FAIL: ...` result lines after each mode is compared, and `Proof report: <path>` as the last line when the proof is written.
- The line `Starting verification` is emitted by the Job_Runner (`web/jobs.py`) before the CLI process is spawned. The CLI prints no line when the Referee starts or when boundaries are probed. Indented boundary notes appear in that interval but are not a stable marker.
- The Job_Runner scrubs server paths from each event line. A Job reports status `queued`, `running`, `done`, `failed` or `timeout`. The queued state comes from the status, not from an event line.
- The Proof_Report JSON holds a `mutation` block with `total`, `killed` and a `mutants` list. Each mutant record has a `killed` flag. The block is `{"status": "not checked"}` when the self-check did not run. The web layer reads it through `_report_summary` in `web/flow.py`.
- `DELETE /session` and `POST /sample/{id}` already exist. `GET /sample/{id}/workbook` does not.

Deployment finding (read from `Dockerfile`, `scripts/deploy_ecs_express.sh` and `web/jobs.py`): `mutation_cases_from_env()` reads `GHOST_MUTATION_CASES` and falls back to `DEFAULT_MUTATION_CASES = 100`; the value `0` turns the self-check off, and the job command adds `--mutation-cases` only when the value is non-zero. The Dockerfile sets `GHOST_SOFFICE`, `GHOST_MAX_JOBS=2`, `PORT` and `PYTHONUNBUFFERED`. The ECS container definition written by the deploy script sets `GHOST_MAX_JOBS`, `GHOST_COOKIE_SECURE`, `GHOST_SESSION_SECRET` and `GHOST_SOFFICE`. Neither sets `GHOST_MUTATION_CASES`, so the deployed web app uses the default of 100 and the mutation self-check runs. Open Question 1 below records the remaining owner action.

Baseline for this feature: after `kiro-surfaces`, the full suite reports 1061 passed, 3 skipped, 1 xfailed, 0 failed.

## Glossary

- **Web_App**: The FastAPI application in `web/` that serves the Ghost pages. It contains no business logic and calls `ghost.*`.
- **Landing_Page**: The page served by `GET /`, rendered from `web/templates/index.html`.
- **Stepper**: The Jinja partial showing the five steps Exhume (Upload), Autopsy (Findings), Verdict of the living (Decisions), Trial (Verification) and Resurrection (Proof). Each step shows its themed name together with its plain name.
- **Sample**: One of the three generated workbooks `discount`, `haunted` and `scenarios`, defined in `SAMPLES` in `web/app.py`.
- **Sample_Card**: The Landing_Page element presenting one Sample.
- **Measured_Duration**: A run time taken from a real earlier run of the same Sample and stored in a file in the repository, never an estimate.
- **Job**: One verification run managed by the Job_Runner.
- **Job_Runner**: The `JobRunner` in `web/jobs.py` that runs the CLI as a subprocess and collects Event_Lines.
- **Event_Line**: One scrubbed line of CLI output stored in a Job's event list, including the `Starting verification` line the Job_Runner adds.
- **Progress_Module**: The pure Python module `web/progress.py`. It maps Event_Lines and a Job status to presentation data and has no I/O.
- **Phase**: One of the ordered stages Queued, Verification started, Mutation self-check, Cases compared and Proof written.
- **Phase_Marker**: The single Event_Line pattern that proves a Phase was reached:
  - Verification started: the line `Starting verification`.
  - Mutation self-check: the first line matching `mutation check: mutant <i>/<n>`.
  - Cases compared: the first line starting `[faithful]` or `[intended]`.
  - Proof written: a line starting `Proof report:`.
  - Queued: the Job status `queued`.
- **Progress_Rail**: The Web_App element that shows the current Phase, the Mutation_Bar and the Graveyard_Grid.
- **Mutation_Bar**: The determinate progress bar driven by `mutant i/n` lines.
- **Mutant_Counts**: The pair `mutant_done` (the largest `i` seen) and `mutant_total` (the `n` of the latest matching line).
- **Graveyard_Grid**: The grid of Tombstones, one per mutant.
- **Tombstone**: One cell of the Graveyard_Grid. Its state is neutral, killed or survived.
- **Proof_Report**: The `proof-report-1` JSON and HTML files produced by the engine.
- **Mutation_Block**: The `mutation` object of the Proof_Report.
- **Status_Line**: A small element carrying `aria-live` that announces only the current Phase name.
- **Raw_Log**: The full list of Event_Lines shown inside a `<details>` element.
- **Failure_Card**: A designed error panel with a title, an explanation and a next step. The failure cases are session expired, job failed, job timed out, Referee unavailable, file rejected and page not found.
- **Pinned_Error_Text**: An error string asserted by an existing test. The strings are those emitted by `web/app.py`, `web/flow.py` and `web/jobs.py`. Examples are "Choose a workbook or a sample first.", "Unknown verification run.", the 30-minute privacy sentence and "Verification exceeded the N s timeout.".
- **Theme_Pass**: The visual styling work on stepper, cards, tombstones and verdict colours, done as one vibe session.
- **Baseline**: 1061 passed, 3 skipped, 1 xfailed, 0 failed.
- **Demo_Invariants**: The demo results fixed by the feature prompt, listed in Requirement 14.
- **Referee**: Headless LibreOffice used as the oracle.
- **Mutation_Cases_Setting**: The environment variable `GHOST_MUTATION_CASES`, read by `mutation_cases_from_env()` in `web/jobs.py`. Default 100; `0` disables the self-check.
- **Result_Container**: The `#result` element on the Landing_Page. It carries `tabindex="-1"`.

## Open Questions

1. **Mutation self-check on the live site.** The deployed configuration does not set `GHOST_MUTATION_CASES`, so the self-check runs with the default of 100 cases per mutant. Owner action, no deploy by this feature: if the owner sets `GHOST_MUTATION_CASES=0` at deploy time, the Graveyard_Grid does not appear and the Web_App shows "Mutation self-check: not checked". The owner decides the value at deploy time, and should also confirm that a run with mutation finishes inside the Job timeout on the 1 vCPU container, because no such timing from the live host is recorded in this spec.

   Owner decision, 2026-11-25: leave `GHOST_MUTATION_CASES` unset, so the default of 100 applies on the live site. Live timing: not checked. No run with mutation has been timed on the deployed 1 vCPU container, and nothing in this feature changes that.

## Requirements

### Requirement 1: Landing page content and order

**User Story:** As a first-time visitor, I want the landing page to say what Ghost does and who it is for, so that I can decide whether to upload a workbook.

#### Acceptance Criteria

1. WHEN a client requests `GET /`, THE Web_App SHALL render the Landing_Page elements in this order: tagline, two-sentence explanation, upload form, three Sample_Cards, privacy note.
2. THE Landing_Page SHALL show a one-line tagline in an `<h2>` or `<p>` element directly below the site header.
3. THE Landing_Page SHALL show an explanation of exactly two sentences stating what Ghost does and who it is for.
4. THE Landing_Page SHALL render the privacy note text from `PRIVACY_NOTE` below the upload form and below the Sample_Cards.
5. THE Landing_Page SHALL link to the Ghost repository.
6. THE Landing_Page SHALL render no link, placeholder or text for a Kiro page, because Feature 6 (`judge-kit`) adds that link.
7. WHILE the owner has not supplied a real video URL, THE Landing_Page SHALL render no video link and no placeholder for one.
8. WHERE the owner supplies a real video URL in the configuration, THE Landing_Page SHALL render a link to that URL.
9. THE Landing_Page SHALL include a favicon link, a `<meta name="description">` element and the Open Graph tags `og:title`, `og:description`, `og:type` and `og:url`.
10. THE Landing_Page SHALL render no "coming soon" label for the video or for the Kiro page.

### Requirement 2: Shared five-step Stepper

**User Story:** As a user, I want to see where I am in the process on every screen, so that I can follow the story from upload to proof.

#### Acceptance Criteria

1. THE Web_App SHALL render the Stepper from a single Jinja partial included by the Landing_Page and by every result partial under `web/templates/`.
2. THE Stepper SHALL list the steps in this order: Exhume (Upload), Autopsy (Findings), Verdict of the living (Decisions), Trial (Verification), Resurrection (Proof).
3. THE Stepper SHALL show for each step both the themed name and the plain name as visible text.
4. THE Stepper SHALL mark exactly one step with `aria-current="step"` on every screen that renders it.
5. WHEN no workbook is selected, THE Stepper SHALL mark Exhume as current.
6. WHEN a workbook is selected and the Autopsy is shown, THE Stepper SHALL mark Autopsy as current.
7. WHEN the Decisions form is shown, THE Stepper SHALL mark Verdict of the living as current.
8. WHILE a Job is queued or running, THE Stepper SHALL mark Trial as current.
9. WHEN a Job has finished, THE Stepper SHALL mark Resurrection as current.
10. THE Stepper SHALL distinguish the current step from other steps by a text or shape cue in addition to colour.

### Requirement 3: Sample cards

**User Story:** As a visitor without a workbook, I want each sample explained before I run it, so that I know what to expect.

#### Acceptance Criteria

1. THE Landing_Page SHALL render one Sample_Card for each of `discount`, `haunted` and `scenarios`, in that order.
2. THE Sample_Card SHALL contain one sentence describing what the Sample workbook holds and what result to expect.
3. THE Sample_Card SHALL contain a Run button that posts to `POST /sample/{id}` and keeps the existing target and result behaviour.
4. THE Sample_Card SHALL contain a link labelled "Download the workbook" whose target is `/sample/{id}/workbook`.
5. THE Sample_Card SHALL keep the existing label text ending in "(generated)".
6. WHERE a Measured_Duration exists for a Sample, THE Sample_Card SHALL show it labelled "measured" together with the date and the case count of the run it came from.
7. IF no Measured_Duration exists for a Sample, THEN THE Sample_Card SHALL show no duration.
8. THE Web_App SHALL read Measured_Duration values from a committed data file and SHALL NOT compute or estimate them while serving a request.
9. THE Sample_Card text SHALL describe a run only as "no difference found on N cases" or "difference found", and SHALL NOT say a result is "correct" or "proven".

### Requirement 4: Sample workbook download

**User Story:** As a visitor, I want to download a sample workbook, so that I can open it in a spreadsheet and compare it with the result.

#### Acceptance Criteria

1. WHEN a client requests `GET /sample/{id}/workbook` with `id` equal to `discount`, `haunted` or `scenarios`, THE Web_App SHALL respond with status 200 and the workbook bytes.
2. THE Web_App SHALL send the download with the file name from `SAMPLES` and an `.xlsx` content type.
3. IF a client requests `GET /sample/{id}/workbook` with an `id` that is not a Sample, THEN THE Web_App SHALL respond with status 404 and a Failure_Card for page not found.
4. THE Web_App SHALL build the downloaded workbook with the committed generator script in `samples/` and SHALL NOT serve a hand-edited file.
5. THE Web_App SHALL build the download in a temporary location and SHALL NOT modify any workbook in the session folder, in `samples/` or in `graveyard/`.
6. THE Web_App SHALL NOT include any server file-system path in the body or headers of the response, including error responses.
7. FOR ALL downloads of the same Sample, THE Web_App SHALL return workbooks whose cell contents and formulas are identical (idempotence).

### Requirement 5: Interaction behaviour

**User Story:** As a user, I want clear feedback when I act, so that I know the page is working and where the result appears.

#### Acceptance Criteria

1. WHILE an htmx request triggered by a button or form is in flight, THE Web_App SHALL set `aria-busy="true"` and `disabled` on that control and show a text busy cue.
2. WHEN the request ends, THE Web_App SHALL remove the busy state from the control.
3. WHEN an htmx swap into `#result` completes and the swapped content contains a heading, THE Web_App SHALL move keyboard focus to the first heading of the swapped content.
4. IF the swapped `#result` content contains no heading, THEN THE Web_App SHALL move keyboard focus to the Result_Container.
5. THE Landing_Page SHALL provide a "Start over" button that sends `DELETE /session`.
6. WHEN `DELETE /session` succeeds, THE Web_App SHALL return the page to the state of a fresh `GET /` with the Stepper on Exhume and an empty result area.
7. THE Web_App SHALL show the busy cue and the "Start over" button without any change to the `DELETE /session` route behaviour.
8. WHEN JavaScript is unavailable, THE Landing_Page SHALL still submit the upload form and the Sample forms as plain HTTP requests.

### Requirement 6: Progress_Module phase mapping

**User Story:** As a user watching a run, I want the page to show which stage the run has reached, so that I am not left reading raw logs.

#### Acceptance Criteria

1. THE Progress_Module SHALL provide a function `phase_of(events, status)` that returns the current Phase for a list of Event_Lines and a Job status.
2. THE Progress_Module SHALL perform no file, network or process I/O and SHALL import nothing from the Referee or the verifier.
3. THE Progress_Module SHALL identify Phases only by their Phase_Markers.
4. WHEN the Job status is `queued`, THE `phase_of` function SHALL return Queued. WHEN the Job status is `running` and no Phase_Marker is present, `phase_of` SHALL still return Queued as its floor, and THE Status_Line SHALL read "Starting", not "Queued" (owner decision, 2026-11-25).
5. WHEN the events contain the line `Starting verification`, THE `phase_of` function SHALL return at least Verification started.
6. WHEN the events contain a line matching `mutation check: mutant <i>/<n>`, THE `phase_of` function SHALL return at least Mutation self-check.
7. WHEN the events contain a line starting `[faithful]` or `[intended]`, THE `phase_of` function SHALL return at least Cases compared.
8. WHEN the events contain a line starting `Proof report:`, THE `phase_of` function SHALL return Proof written.
9. THE `phase_of` function SHALL return the highest Phase whose Phase_Marker is present, in the order Queued, Verification started, Mutation self-check, Cases compared, Proof written.
10. IF an Event_Line matches no Phase_Marker, THEN THE `phase_of` function SHALL leave the returned Phase unchanged.
11. IF the events hold no line for a Phase, THEN THE Progress_Rail SHALL NOT show that Phase as reached.
12. WHERE the self-check did not run (no `mutation check: mutant` line), THE Progress_Rail SHALL skip the Mutation self-check Phase without marking it reached.
13. IF a `mutation check: not checked (<reason>)` line is present, THEN THE `phase_of` function SHALL treat it as an unrecognised line for Phase purposes.
14. WHEN the events are cleared because the session ended, THE `phase_of` function SHALL return the Phase derived from the empty list and the supplied status.
15. FOR ALL event lists, THE `phase_of` function SHALL return the same Phase when the same list is supplied again (determinism).

### Requirement 7: Mutation_Bar

**User Story:** As a user, I want a real progress bar for the mutation self-check, so that I can see how far it is.

#### Acceptance Criteria

1. THE Progress_Module SHALL provide a function that returns Mutant_Counts from a list of Event_Lines.
2. WHEN the events contain one or more `mutation check: mutant <i>/<n>` lines, THE Progress_Module SHALL return `mutant_done` equal to the largest `i` and `mutant_total` equal to the `n` of the latest such line.
3. WHEN Mutant_Counts exist, THE Progress_Rail SHALL render the Mutation_Bar as a `<progress>` or `role="progressbar"` element with `value`, `max`, `aria-valuenow` and `aria-valuemax` taken from Mutant_Counts, and SHALL show the text "mutant i of n".
4. IF the events hold no `mutation check: mutant` line, THEN THE Progress_Rail SHALL render no Mutation_Bar and no percentage.
5. THE Progress_Rail SHALL show no percentage, time estimate or completion forecast other than `mutant_done` and `mutant_total` as counts.
6. IF a parsed `i` is greater than its `n`, THEN THE Progress_Module SHALL ignore that line.
7. FOR ALL event lists, THE Progress_Module SHALL return `mutant_done` less than or equal to `mutant_total` whenever `mutant_total` exists.

### Requirement 8: Graveyard_Grid

**User Story:** As a user, I want to see each mutant as a tombstone that turns killed or survived only when the report says so, so that the picture is trustworthy.

#### Acceptance Criteria

1. WHEN Mutant_Counts exist, THE Progress_Rail SHALL render a Graveyard_Grid with exactly `mutant_total` Tombstones.
2. WHILE the Job status is `queued` or `running`, THE Graveyard_Grid SHALL render every Tombstone in the neutral state.
3. WHEN the Job status is `done` and the Proof_Report Mutation_Block holds `total` and a `mutants` list, THE Graveyard_Grid SHALL render exactly `total` Tombstones and SHALL mark each Tombstone killed or survived from that mutant's `killed` flag.
4. WHEN the Job has finished, THE number of killed Tombstones SHALL equal `mutation.killed` and THE number of survived Tombstones SHALL equal `mutation.total` minus `mutation.killed`.
5. THE Graveyard_Grid SHALL give each Tombstone a text label naming its mutant id and state, and SHALL distinguish killed from survived by a shape or text cue in addition to colour.
6. IF the finished Proof_Report has no Mutation_Block, or has a Mutation_Block without a `total` field (including `{"status": "not checked"}`), or no report was produced, THEN THE Progress_Rail SHALL show the text "Mutation self-check: not checked" and no Graveyard_Grid.
7. IF the Job ends in status `failed` or `timeout`, THEN THE Graveyard_Grid SHALL keep every Tombstone neutral and SHALL NOT mark any as killed or survived.
8. THE Graveyard_Grid SHALL list survivors by mutant id, operator and location from the Proof_Report and SHALL add no mutants and drop none.
9. FOR ALL finished Jobs with a Mutation_Block, THE Tombstone count SHALL equal `mutation.total` (invariant).

### Requirement 9: Raw log and live announcements

**User Story:** As a screen-reader user, I want announcements only when the stage changes, so that I am not interrupted every second.

#### Acceptance Criteria

1. THE Progress_Rail SHALL show the full list of Event_Lines inside a `<details>` element labelled "Raw log".
2. THE Raw_Log element SHALL NOT carry an `aria-live` attribute.
3. THE polled Job panel root element SHALL NOT carry an `aria-live` attribute.
4. THE Progress_Rail SHALL contain one Status_Line with `aria-live="polite"` that holds only the current Phase name.
5. THE Status_Line text SHALL be a pure function of the current Phase and the Job status, so that an identical Phase and status always yield identical text and a poll that returns the same Phase and status leaves the text unchanged. The only case where the text is not the Phase name is Phase Queued with status `running`, which reads "Starting".
6. THE Status_Line SHALL keep its DOM identity across polls so that screen readers announce it only when its text changes.
7. THE Progress_Rail SHALL show only Phases and counts derived from Event_Lines and the Job status.

### Requirement 10: Failure cards

**User Story:** As a user whose run or request failed, I want a clear card that tells me what to do next, so that I am not stuck.

#### Acceptance Criteria

1. WHEN a session cookie is missing, unknown or expired and an action needs a session, THE Web_App SHALL render a "session expired" Failure_Card with a link or button to start over.
2. WHEN a Job ends in status `failed`, THE Web_App SHALL render a "job failed" Failure_Card containing the existing failure message and a next step.
3. WHEN a Job ends in status `timeout`, THE Web_App SHALL render a "job timed out" Failure_Card containing the existing timeout message and a next step.
4. IF the Referee is unavailable (`GET /healthz` returns 503, or the failure message names the Referee), THEN THE Web_App SHALL render a "Referee unavailable" Failure_Card with a next step.
5. WHEN an upload is rejected with status 413 or 422, THE Web_App SHALL render a "file rejected" Failure_Card containing the existing rejection text.
6. WHEN a request matches no route or names an unknown Sample, THE Web_App SHALL render a "page not found" Failure_Card with a link to the Landing_Page.
7. THE Failure_Card SHALL keep `role="alert"` on the element holding the error text.
8. THE Failure_Card SHALL keep every Pinned_Error_Text unchanged and SHALL add the title and next step as separate elements.
9. THE Failure_Card SHALL contain no server file-system path.
10. THE Failure_Card SHALL distinguish its severity by an icon or text label in addition to colour.
11. IF a Job ended with status `timeout`, THEN THE Progress_Rail SHALL show the Phase reached before the timeout and no later Phase.
12. IF a Job ended with status `timeout` before any Phase_Marker was reached, THEN THE Progress_Rail SHALL show a not-started state with no Phase highlighted.

### Requirement 11: Theme pass as a vibe session

**User Story:** As a judge, I want the product to look coherent and haunted-lab themed, so that the story from autopsy to resurrection is easy to follow.

#### Acceptance Criteria

1. THE Theme_Pass SHALL style the Stepper, Sample_Cards, Tombstones and verdict colours in `web/static/style.css`.
2. THE Theme_Pass SHALL be carried out as one Kiro vibe session and not through the spec task list.
3. WHEN the Theme_Pass is done, THE repository SHALL contain an entry in `docs/KIRO_USAGE.md` with Feature `vibe` and two or three honest sentences comparing the vibe session with the spec-driven parts, including anything that went wrong.
4. WHERE the dark theme is active, THE Web_App SHALL render the report iframe without a white slab, using only changes to `web/static/style.css`, `web/templates/` or the iframe element attributes.
5. THE Theme_Pass SHALL NOT edit the content of the Proof_Report HTML produced by the engine.
6. THE verdict, killed, survived and failure states SHALL each carry a text label in addition to colour.
7. THE existing border contrast assertions in `tests/test_web_accessibility.py` SHALL continue to pass unchanged in both themes.

### Requirement 12: Accessibility preserved

**User Story:** As a keyboard or screen-reader user, I want every new element to be accessible, so that the redesign does not exclude me.

#### Acceptance Criteria

1. THE Landing_Page SHALL keep the skip link targeting `#main` as the first focusable element.
2. THE Web_App SHALL give every form control, including the upload input and the "Start over" button, a visible label or accessible name.
3. THE Web_App SHALL show a visible focus indicator on every focusable element, including Sample_Card links and buttons.
4. THE Web_App SHALL keep `role="alert"` on every error message element.
5. THE Web_App SHALL wrap every animation or transition added by this feature in a `prefers-reduced-motion: reduce` guard that disables it.
6. WHILE the viewport is 360 CSS pixels wide, THE Landing_Page, Stepper, Sample_Cards and Graveyard_Grid SHALL show all content without horizontal page scrolling.
7. THE Web_App SHALL NOT use colour as the only signal for any state introduced by this feature.
8. THE Theme toggle SHALL keep a constant label and `aria-pressed`, as asserted by `tests/test_web_accessibility.py`.

### Requirement 13: Honest wording

**User Story:** As a reader of the interface, I want every statement to come from measured engine output, so that I can trust it.

#### Acceptance Criteria

1. THE Web_App SHALL show every number on the Landing_Page, Progress_Rail and Graveyard_Grid only if it comes from a Proof_Report, an Event_Line or a committed measurement file.
2. WHERE a check was not run, THE Web_App SHALL show the text "not checked" for that check.
3. THE Web_App SHALL describe a passing run as "no difference found on N cases" with N from the Proof_Report, and SHALL NOT use the words "correct", "proven" or "verified correct".
4. THE Progress_Rail SHALL NOT show a fake percentage, an invented Phase or an estimated remaining time.
5. IF a Measured_Duration is shown, THEN THE Web_App SHALL label it "measured" and SHALL show the date of the run it came from.
6. THE Web_App SHALL leave the `proof-report-1` schema unchanged and SHALL add no field to the Proof_Report for this feature.

### Requirement 14: Constraints and invariants

**User Story:** As the owner, I want this feature to leave the engine and the demo untouched, so that the demo still works.

#### Acceptance Criteria

1. WHEN the feature is complete, THE full test suite SHALL report the Baseline counts plus only new tests, with 0 failed.
2. THE feature SHALL NOT weaken, delete or skip any existing test, and every existing web test SHALL pass with its assertions unchanged, including the accessibility and no-server-paths tests.
3. THE feature SHALL add each new behaviour with a failing test written first, using workbooks and event lists built inside the tests.
4. THE Demo_Invariants SHALL hold after the feature:
   - discount: Faithful passes and mutation kills at least 31 of 33.
   - haunted: Finding F-001 is raised, Faithful passes with 0 mismatches, and mutation kills at least 33 of 35.
   - haunted with Decision D-001: Intended passes with exactly one expected-by-decision mismatch at quantity = 50 (Referee 6.0, new code 0).
   - Default cells: `Calculator!B2,B3,B4` to `B11`; scenarios `Model!B2,B3,E2` to `B19,B20`.
   - Seed 20261204.
5. THE feature SHALL add no runtime dependency to `[project].dependencies`.
6. THE Web_App SHALL contain no business logic, and THE Progress_Module SHALL only parse Event_Lines and Job status into presentation data.
7. THE feature SHALL run no macro from an upload and SHALL NOT change macro handling.
8. THE feature SHALL leave all changes uncommitted, SHALL NOT push or deploy, and SHALL run no AWS command.
9. THE feature SHALL add one entry to `docs/KIRO_USAGE.md` for each task, naming the Kiro feature used, what happened and anything that went wrong.
10. WHEN all tasks are done, THE Skeptic sub-agent SHALL review the honesty wording and attempt to break the correctness properties before the feature is called done.
11. IF the work runs more than half a day over the 1.25-day estimate, THEN THE owner SHALL be asked before work continues.

### Requirement 15: Recorded-run regression

**User Story:** As a maintainer, I want the phase mapping tested against a real run, so that the Progress_Module matches what the CLI prints.

#### Acceptance Criteria

1. THE repository SHALL contain a fixture holding the Event_Lines recorded from a real haunted run, including the `Starting verification` line.
2. WHEN the fixture lines are fed to `phase_of` one line at a time, THE returned Phases SHALL appear in this order: Verification started, Mutation self-check, Cases compared, Proof written.
3. WHEN the recorded run is finished, THE Mutant_Counts SHALL equal the mutant total of that run's Proof_Report.
4. THE fixture SHALL contain only lines produced by the engine and the Job_Runner, with no server paths.

### Requirement 16: Correctness properties for later design

**User Story:** As a maintainer, I want the universal properties of the Progress_Module stated up front, so that the design can turn them into property-based tests.

#### Acceptance Criteria

1. FOR ALL lists of Event_Lines and every appended line, THE Phase index returned by `phase_of` SHALL be greater than or equal to the index returned before the line was appended (monotonicity).
2. FOR ALL lists of Event_Lines and every appended line that matches no Phase_Marker, THE Phase returned by `phase_of` SHALL equal the Phase returned before the line was appended.
3. FOR ALL lists of Event_Lines, THE Mutant_Counts SHALL satisfy `mutant_done` less than or equal to `mutant_total` whenever `mutant_total` exists.
4. FOR ALL finished Proof_Reports with a Mutation_Block, THE Graveyard_Grid Tombstone count SHALL equal `mutation.total`, the killed count SHALL equal `mutation.killed` and the survived count SHALL equal `mutation.total` minus `mutation.killed`.
5. THE correctness properties SHALL be implemented with Hypothesis using an explicit seed and SHALL need no LibreOffice.
6. THE test file for each property SHALL carry the comment `# Feature: front-door, Property N: <title>`.
