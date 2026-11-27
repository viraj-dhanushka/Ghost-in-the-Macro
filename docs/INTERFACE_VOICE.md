# Interface voice

Every error, empty state and waiting message in `web/`. Each error card has two lines: a short ghost line, then the plain line that says what happened and what to do. The plain line is the text the code already produced; no fact was removed from it. The ghost line is new and sits in `web/templates/_failure_card.html` (class `failure-ghost`).

Rules: no joke on a verdict, a mismatch, a counterexample or the "expected by decision" box. The words "correct" and "proven" are not used. Nothing mocks the user or the workbook. No meaning is carried by an emoji.

## Errors (shown as a failure card)

| Where it shows | Ghost line (new) | Plain line (unchanged) |
|---|---|---|
| Upload over 5 MB (413) | This one is too heavy to lift. | File is larger than the 5 MB limit: too large for the public demo; run Ghost locally with: ghost route <file> |
| Upload that cannot be read, or over a limit (422) | This workbook would not come out of its crypt. | The loader's own message, with paths removed |
| No workbook or sample chosen (409) | This session has slipped back into the mist. | Choose a workbook or a sample first. |
| Verification failed | The séance did not take. | The job's own message (exit code, or "Verification did not produce a report.") |
| Verification timed out | The spirits took too long to answer. | Verification exceeded the N s timeout. |
| LibreOffice Referee could not start | The Referee is not answering the summons. | The LibreOffice Referee could not start, so this sample could not be built. Try again in a minute. |
| Unknown page, sample or run (404) | Nothing haunts this address. | The page you asked for was not found. / That sample was not found. / Unknown verification run. |
| Any other rejected request (409, 422, 429) | Something went bump. | The message from `web/flow.py` or `web/jobs.py`, for example: "{id} already has a Decision.", "No output cells are selected. Choose at least one output.", "This session already has a verification queued or running. Wait for it to finish, then start a new run." |

## Empty states

| Where | Text | Voice |
|---|---|---|
| Autopsy, no operator conflicts | No operator conflicts found. | Plain, unchanged. A finding or its absence is a result. |
| Autopsy, no rules | No rules were generated. | Plain, unchanged. |
| Decisions, none recorded | No decisions recorded: verification runs in Faithful mode. | Plain, unchanged. |
| `/kiro`, facts file missing | The Kiro facts file is not available in this build, so no numbers are shown. | Plain, unchanged. |

## Waiting

| Where | Old text | New text (names the real step) |
|---|---|---|
| Upload, after the file is accepted | Reading the workbook... | Reading the workbook for conflicts, rules and decisions... |
| Verification, queued | Queued. Position N. | The Referee is busy with another workbook. Queued, position N. |
| Verification, running | Running against LibreOffice (the Referee)... | Waking the Referee: running the original workbook in LibreOffice to compare answers... |
| Verification, progress rail | Queued, Starting verification, Mutation self-check, Cases compared, Proof written | Unchanged. These come from the engine's progress and are pinned by property tests. |

## Not changed on purpose

Verdict headline, mismatch list, counterexample, "What was not checked" and the "expected by decision" box in `web/verdict.py` and `_verdict_card.html`. They state results, so they carry no joke.
