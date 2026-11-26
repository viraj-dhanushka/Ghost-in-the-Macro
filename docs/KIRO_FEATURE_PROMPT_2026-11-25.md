# Task: build the Kiroween feature set for Ghost in the Macro (25 November 2026)

You are working in this repository. Submissions close on **4 December 2026, 14:00 Pacific Time**. This file lists the features to build before then, in order. Work through them one at a time. Stop and ask me whenever a section says STOP-AND-ASK, or whenever you would have to break a ground rule to continue.

## Why these features

Judges score five criteria, 20% each. The rules also say judges "are not required to test the Project and may choose to judge based solely on the text description, images, and video". So each feature below must either show up in a three-minute video or be evidence in the repository.

| Criterion | What the rules ask | Where the project stands today |
|---|---|---|
| Potential impact | "Would someone actually use this?" | Strong idea; the web page does not explain it |
| Technological implementation | "How thoroughly and skillfully does the project use Kiro? ... a variety of Kiro tools ... experimentation" | Specs are deep. Hooks have never been seen firing in Kiro, the Power has never been installed, agents are six-line configs, no migration has been done by a Kiro agent |
| Design | "a complete, coherent product experience, not just a technical proof of concept" | Weakest area: bare landing page, raw log as progress, cell addresses with no labels |
| Innovation | "does the project differ from existing concepts?" | The live Referee and mutation self-check are real differences, but nothing shows the Referee judging someone else's code |
| Presentation | "Does the video clearly demonstrate the project working end-to-end?" | No README pitch, no images, no video script |

## Ground rules (they apply to every feature)

1. **Start gate.** Do not start until the bugfix spec `live-fixes-2026-11-24` is finished through task 7.7 and I have committed it. If it is still open, finish it first.
2. **Record the baseline first.** Run the full suite and `scripts/demo.sh <temp dir>` once before any change, and write the pass, skip and xfail counts into `docs/KIRO_USAGE.md`. Every later run must show that baseline plus only new tests, with 0 failed. Never weaken, delete or skip an existing test.
3. **Demo invariants must not move.**
   - discount: Faithful passes; mutation at least 31/33.
   - haunted: F-001 is raised; Faithful passes with 0 mismatches; mutation at least 33/35.
   - haunted with D-001: Intended passes with exactly one "expected by decision" mismatch at quantity = 50 (Referee 6.0, new code 0).
   - Default cells: `Calculator!B2,B3,B4` → `B11`; scenarios `Model!B2,B3,E2` → `B19,B20`.
   - Seed 20261204. Report schema stays `proof-report-1`; do not add fields to it for these features. New outputs go in their own files.
4. **Guardrails stay in force** (`.kiro/steering/ghost-guardrails.md`): no invented values; write "not checked" for anything not run; "not converted" always carries the cell and the reason; no hidden or dropped mutants; no server paths in any output; macros are never run from uploads.
5. **Honest wording.** A passing run is "no difference found on N cases", never "correct" or "proven correct". Every number shown on screen or in a document must come from a report file or a count you can re-run.
6. **No push, no deploy, no AWS commands.** Leave changes uncommitted at the end of each feature and give me a summary; I commit, push and redeploy.
7. **No new runtime dependencies** in `[project].dependencies` without asking. The container is 1 vCPU and 2 GB.
8. **Accessibility is kept.** Skip link, labels, visible focus, `role="alert"` on errors, reduced-motion guard and the 360 px layout must still work after every web change. Colour is never the only signal.
9. **Test first.** For each feature, write the failing tests before the code, using workbooks built inside the tests.
10. **Log as you go** in `docs/KIRO_USAGE.md`: one entry per task with the Kiro feature used (spec, hook, agent, MCP, power, vibe), what happened, and anything that surprised you or went wrong. Failures are worth logging; do not tidy them away.

## How to use Kiro for this work

Use a different Kiro capability on purpose for each piece, so the repository shows range:

- **One feature spec per feature** (requirements-first), named as given in each section. Requirements in EARS, a design with numbered correctness properties, then tasks. Run Analyze Requirements on each before design.
- **Property-based tests** for every correctness property that needs no LibreOffice. Tag each test file with `# Feature: <spec name>, Property N: <title>`.
- **Sub-agents:** the Skeptic reviews each feature's honesty wording and tries to break its properties before you call it done. The Coroner is used in Feature 5.
- **One vibe session, on purpose:** the visual theme pass in Feature 2 (colours, spacing, tombstone drawing) is done as a vibe session, not through a spec. Log it as `vibe` and write two or three honest sentences comparing it with the spec-driven parts. The write-up needs that comparison and there is no `vibe` entry in the log today.
- **Hooks and MCP:** from Feature 1 on, use the workspace's own Ghost MCP tools and let the hooks run, and log each time one fires or fails to.

## Build order

| Order | Feature | Spec name | Estimate | Main criterion |
|---|---|---|---|---|
| 1 | Make the Kiro surfaces real | `kiro-surfaces` | 0.75 day | Implementation |
| 2 | Front door and live progress | `front-door` | 1.25 days | Design, Presentation |
| 3 | The ten-second verdict and a readable autopsy | `readable-proof` | 1.25 days | Design, Impact |
| 4 | The dead technology on screen | `vba-on-screen` | 0.5 day | Category fit, Impact |
| 5 | Trial by Workbook, with a migration done by a Kiro agent | `trial-by-workbook` | 1.5 days | Innovation, Implementation |
| 6 | Judge kit | `judge-kit` | 1 day | Presentation, Implementation |
| 7 | Large-workbook lane with a refereed AWS Transform custom hand-off (build after 5) | `large-workbook-lane` | 1.5 days | Impact, Implementation, Innovation |
| Stretch | S1 to S4, only if 1 to 7 are finished by 30 November | | | |

The estimates come from a code review, not from a trial build. If a feature runs more than half a day over, STOP-AND-ASK before continuing; I would sooner cut scope than lose the video days.

**Feature freeze: end of 30 November.** After that only fixes, the redeploy, the README and the video.

---

## Feature 1: make the Kiro surfaces real (`kiro-surfaces`)

**Problem.** The repository claims four hooks, four agents, an MCP server and a Power, but:

- `docs/KIRO_USAGE.md` says "Hooks: none fired. Agents: none invoked."
- The hook files use a `{"version":"v1","hooks":[{"trigger":"PostFileSave", ...}]}` shape. Whether the Kiro IDE loads that shape has never been checked.
- `plugin/` has `plugin.json`, `mcp.json` and seven skills, but no `POWER.md` and no steering folder. Whether Kiro needs a `POWER.md` has never been checked.
- There is no `.kiro/settings/mcp.json`, so this workspace does not register its own MCP server.
- Each agent config is name, description, one paragraph of prompt and `tools: [read, write, shell]`. None references the MCP server or the steering files, and they call the CLI.

A judge who opens `.kiro/` and finds config that cannot load will score this criterion down, so it goes first.

**Build.**

1. **Read the current Kiro documentation first** for Powers, IDE hooks, custom agents and workspace MCP configuration. Write what each format requires, with the source URL, into a new `docs/KIRO_SURFACES_FORMATS.md`. Change no configuration file until that document exists. If a format differs from what the repository has, say so there.
2. **Power.** Add whatever the documented layout requires (expected: `plugin/POWER.md` with name, description, keywords and onboarding steps covering `uv`, LibreOffice, the tools and the skill order). Add `plugin/steering/` holding copies of `ghost-guardrails.md` and `excel-semantics.md`, and cut the duplicated text in `plugin/skills/guardrails/SKILL.md` down to a pointer.
3. **Workspace MCP.** Add `.kiro/settings/mcp.json` registering the local server (launching `mcp_server.server:main` from this checkout, not from the GitHub URL).
4. **Agents.** Rewrite the four configs using the documented field names:
   - Coroner: read-only. Tools limited to `analyze_workbook`, `find_inconsistencies`, `extract_vba`, `boundary_cases`, `get_dependencies`, `check_against_excel_cache`. Its prompt names those tools, not the CLI.
   - Skeptic: `verify_implementation`, `mutation_check`, `evaluate_original`.
   - Clerk: `record_decision` and `generate_proof_report` only, and only for Decisions a human dictated.
   - Medium: writes rules and specs; no verification tools.
   - All four reference the two steering files as resources.
5. **Hooks.** Validate the four hook files against the documented format and convert them if they are wrong, keeping `scripts/ghost_hook.py` as the command. If the documentation supports another trigger or action type (for example an agent-prompt action or a manual trigger), add one hook of that type. If it does not, say so in `KIRO_SURFACES_FORMATS.md`.
6. **Tests** in a new `tests/test_kiro_config.py`:
   - every tool name mentioned in `plugin/skills/*/SKILL.md` and `.kiro/agents/*.json` is a key of `mcp_server.server.TOOLS`;
   - each hook file parses, its matcher matches its intended path and rejects at least three near-miss paths (for example `graveyard/sub/x.xlsx`, `graveyard/x.csv`, `ghost/converter/notes.md`);
   - the steering copies under `plugin/steering/` are byte-identical to the originals;
   - `POWER.md` name and keywords equal those in `plugin.json`.
7. **Owner checklist.** Add `docs/KIRO_OWNER_CHECKLIST.md`: one table with a row per surface (Power installs, tools are listed, skills are listed, each hook fires, each agent runs) and an empty Result column. Never pre-fill a row with "pass".

**Honesty.** The README and write-up may say a hook or the Power "works in Kiro" only for rows where I have filled in an observed pass.

**Done when** `KIRO_SURFACES_FORMATS.md` exists with source URLs; the new tests pass; the suite and `scripts/demo.sh` match the baseline; the checklist is ready for me to fill in.

---

## Feature 2: front door and live progress (`front-door`)

**Problem.** The landing page is a title, a privacy note, a file input and three sample buttons labelled "(generated)". Nothing says what the tool does. During a run the user watches the last 12 lines of raw CLI output, re-read by screen readers every second.

**Build.**

1. **Landing page** (`web/templates/index.html`):
   - A one-line tagline and two plain sentences saying what the tool does and who it is for.
   - Links to the repository, the video (add the link only once I give you a real URL) and the Kiro page from Feature 6.
   - A five-step stepper, shared by every screen as a partial: Exhume (upload), Autopsy (findings), Verdict of the living (decisions), Trial (verification), Resurrection (proof). Each themed name is shown with its plain name, and the current step carries `aria-current`.
   - Sample cards instead of buttons. Each card has one sentence on what is in the workbook and what to expect, a measured duration note, a Run button, and a "Download the workbook" link (new `GET /sample/{id}/workbook`).
   - The privacy note moves below the form.
   - Favicon, meta description and Open Graph tags.
   - Buttons show a busy state while a request is in flight, and focus moves to the result after each swap.
   - A "Start over" button that calls the existing `DELETE /session`.
2. **Progress** (new pure module `web/progress.py`, used by `_job.html`):
   - A function `phase_of(events, status)` that maps the real event lines to a phase. Use only lines the CLI prints today, in the order the code runs: queued → Referee started and boundaries probed ("Starting verification") → mutation self-check (`mutation check: mutant i/n`) → cases compared (the first `[faithful]` or `[intended]` result line) → proof written. Do not show a phase that has no matching line. An unrecognised line leaves the phase unchanged.
   - A determinate bar driven by `mutant i/n`.
   - A "graveyard" grid with one tombstone per mutant. Tombstones stay neutral while the job runs and are marked killed or survived only from the finished report. If the report has no mutation block, show "Mutation self-check: not checked" and no grid.
   - The raw log stays available inside a `<details>` element.
   - Move `aria-live` off the polled panel to a small status line that changes only when the phase changes.
3. **Failure states.** Designed cards, each with a next step, for: session expired, job failed, job timed out, Referee unavailable, file rejected, and a 404 page. Keep the existing error texts that tests pin.
4. **Theme pass (the vibe session).** Carry the haunted-lab look through: stepper, cards, tombstones, verdict colours. Keep it restrained; the theme should help the user follow the story from autopsy to resurrection. Fix the white slab the report iframe leaves in the dark theme if that can be done without editing the report's own content.

**Honesty.** The progress rail shows measured state only. No fake percentages, no invented phases, no estimated time unless it is a measured duration from a previous real run labelled as such.

**Correctness properties (Hypothesis, no LibreOffice).**
- Over any list of event lines, the phase index never goes backwards as lines are appended.
- Unrecognised lines never change the phase.
- `mutant_done <= mutant_total` whenever a total exists, and the tombstone count equals the total.

**Done when**
- `GET /` shows, in order: tagline, explanation, upload form, three sample cards, privacy note; the stepper has exactly one `aria-current` item.
- `GET /sample/{id}/workbook` returns the workbook for the three samples and 404 for an unknown id.
- A unit test feeds the recorded event lines of a real haunted run to `phase_of` and gets the phases in execution order.
- After a finished run, killed tombstones equal `mutation.killed` in the report and survivors equal total minus killed.
- All existing web tests pass with their assertions unchanged, including the accessibility and no-server-paths tests.

---

## Feature 3: the ten-second verdict and a readable autopsy (`readable-proof`)

**Problem.** The result is one bold sentence above an iframe. The autopsy shows checkboxes labelled `Model!B2` with no label, value or formula, and a Finding title hard-coded as "operator conflict". Someone watching a video cannot tell what is being checked or what was found.

**Build, part A: verdict card** (new pure module `web/verdict.py`, new partial above the report iframe; no change to `ghost/report/`):

- `build_verdict(report: dict) -> dict` takes the parsed proof-report JSON and nothing else.
- A headline sentence built only from numbers in the JSON.
- Three tiles: inputs tried (generated, targeted, distinct), disagreements (count, split by class), planted bugs caught (killed/total with a bar; survivors listed with their recorded reason).
- If there is a mismatch, the minimal counterexample is the centre of the card: the inputs, "workbook says X, new code says Y", its class in plain words, and the linked Decision or Finding id.
- A "What was not proven" strip with the same visual weight as the tiles: every `boundary_notes` entry, every tested domain marked not tested, every rule not seen both ways, and the Excel cross-check status copied verbatim.
- A "Reproduce" line: the CLI command with mode and seed, no server path.
- A collapsed glossary with one sentence each for Referee, mutant, Faithful and Intended.
- Keep the existing verdict paragraph and the "K/T mutants killed" text that tests pin.

**Build, part B: readable autopsy** (`web/templates/_autopsy.html` and its view model):

- Each input checkbox reads "label (address) = current value". Each output reads "label (address)" with its formula. Take labels from the existing label helpers; where there is none, show the address alone. The checkbox markup that tests match with a regex must not change.
- Finding card: the title comes from the Finding's kind; both conflicting formulas are shown with the operators highlighted; one consequence sentence built only from the Finding's fields ("at exactly 50, B7 uses >= and B9 uses >"). No computed outcomes, because nothing has been evaluated at this stage.
- Decision options as radio cards. The author name is remembered in the browser. The reason stays required and typed by a human: never pre-fill it on the server.
- "Not converted" cells get their own panel listing cell and reason.

**Optional, only if parts A and B are done within the estimate:** a read-only boundary number line per `boundaries[]` row, showing the threshold, an open or closed dot, and only the input points the proof measured. Output values may appear only for points that match a recorded mismatch; otherwise write "agreed here (values not recorded in the report)".

**Do not build** a free "ask both" form that evaluates arbitrary inputs. It needs a new job type and does not fit the time.

**Correctness properties (Hypothesis over generated schema-valid reports).**
- The headline claims agreement only when `passed` is true and `mismatches` is empty.
- Every number shown in the card appears in the report JSON or is the length of one of its arrays.
- When the mutation block is "not checked", the tile reads exactly "not checked" with no bar.
- Every survivor in the report is listed; none is hidden.
- The word "Excel" never appears in a sentence claiming agreement unless the cross-check status says it matched.

**Done when** the properties pass; a failing report renders a red card with the counterexample; the haunted autopsy shows both formulas for F-001; `POST /decision` with an empty reason still returns 422; all existing web tests pass unchanged.

---

## Feature 4: the dead technology on screen (`vba-on-screen`)

**Problem.** The category is Resurrection: "Bring your favorite dead technology back to life." The web app offers three `.xlsx` samples. No VBA is ever shown, although `extract_vba` already reads it. The thing being resurrected is not visible.

**Build.**

1. A fourth web sample: a macro workbook built by the existing `samples/make_xlsm.py`. STOP-AND-ASK if building it at request time takes more than a few seconds in the container; the alternative is building it once at container start.
2. On the autopsy screen, show each extracted VBA module in a collapsed code block, escaped, under the heading "VBA source: read, never run". This applies to uploads too.
3. The cell that calls the VBA function is listed as "not converted" with its reason, as the engine already reports it.
4. Show the router's recommendation ("Ghost converts", "AWS Transform custom" or "Split") with the reasons it gives. If it produces the `atx` command string, show it labelled "suggested command, not run".
5. One honest sentence on the card: what Ghost does with macro workbooks today (reads the VBA, finds thresholds in it, converts the formulas, routes the macro logic) and what it does not do (translate VBA to Python).

**Carried over from Feature 2 (owner decision, 2026-11-25 session):** the VBA read error on the autopsy screen (`web/templates/_autopsy.html`, the `<li class="error">` that prints `vba_error` followed by "(VBA: not checked)") has no `role="alert"`. Requirement 12.4 of `front-door` says every error message element keeps `role="alert"`. Feature 2 left it unchanged because that line is identical in HEAD and Feature 2 does not own it. Fix it in this feature, where the autopsy VBA block is rebuilt, and keep the visible text and the "(VBA: not checked)" suffix as they are. Add a test that every element with class `error` in the rendered autopsy page carries `role="alert"`.
**Check and report, do not assume:** whether the Referee could convert a legacy `.xls` file to `.xlsx` safely so old files can be uploaded. Write the answer in the summary. Build it only if it is under two hours and adds no way to run macros.

**Done when** the macro sample loads from its card; a module source containing `<script>` renders escaped; no code path runs a macro from an upload (existing tests still pass); the suite and `demo.sh` match the baseline.

---

## Feature 5: Trial by Workbook, with a migration done by a Kiro agent (`trial-by-workbook`)

**Why.** This is the innovation claim: the workbook can referee *anyone's* rewrite, including code an AI agent wrote. The engine can already verify a hand-written `logic.py` and the MCP tool `verify_implementation` exists, but there is no named command, no example, and no migration in this repository that a Kiro agent carried out.

**Build, part A: `ghost challenge`** (new module `ghost/challenge.py`, one new subcommand):

- `ghost challenge <workbook> --code candidate.py [--mapping mapping.yaml]` verifies a foreign `compute()` against the Referee in Faithful mode and prints a verdict: cases generated, targeted and distinct; seed; LibreOffice version; and either "no difference found on N cases" or one counterexample with the inputs, the Referee value, the candidate value, the output cell, the rule id and the EARS rule text.
- Exit 0 for no difference, 1 for a difference.
- Say "shrunk" only when the counterexample came from the Hypothesis phase. When a targeted boundary case failed first, say "targeted boundary case, not shrunk".
- `samples/suspects/haunted/` and `samples/suspects/discount/` each hold a pinned `mapping.yaml` and three or four candidate modules: an honest hand translation, a `>` versus `>=` slip, float rounding in place of Excel rounding, a dropped branch. Each file's header says truthfully how it was written.
- **Measure before labelling.** Run every suspect first. A suspect the Referee does not catch is reported as "no difference found on N cases" and its label is corrected to say so. Ship no label a run contradicts.
- The line-up writes its own small `lineup.json`. It never writes into a migration's `reports/` folder.

**Build, part B: a migration done by a Kiro agent and corrected by the workbook.**

1. A repair brief: after a failed Faithful run, a small script (new file; reads the existing `proof-report.json`, changes no engine code) writes `repair-brief.json` with the minimal failing inputs, the Referee value, the actual value, the output cell, and the rule id with its EARS text and source formula. `rule_text` is "not available" when the rule id is missing. A passing run writes `{"status": "passed"}`.
2. A `repair` kind in `scripts/ghost_hook.py`, wired to the existing save hook for `logic.py` in a migration folder (do not add a second hook on the same path). Each run appends one block to `repair-log.md`: round number, time, seed, cases, pass or fail, the counterexample. After five failed rounds the status is "not converged". It does nothing extra when `logic.py` is Ghost-generated.
3. A "Repair loop" section in `plugin/skills/implement-from-rules/SKILL.md`: read the brief, change only what it demonstrates, never touch the workbook, `mapping.yaml`, `decisions.yaml` or the tests, stop at "not converged".
4. **The run itself.** Put the haunted sample workbook in `graveyard/` (add a `.gitignore` exception so it is committed). Then, inside Kiro, using only the Power's skills and the Ghost MCP tools: autopsy → write rules spec → the agent writes `logic.py` from the rules alone → verify → repair if the Referee disagrees. Commit the whole folder `.kiro/specs/haunted-delivery-migration/`: rules, traceability, findings, the agent-written `logic.py` and `mapping.yaml`, `repair-log.md`, `repair-brief.json` and the proof report.
5. Keep this migration **Faithful only**. An agent-written module has no trace hook, so Intended mode cannot attribute a mismatch to a Decision. The D-001 story stays with the generated-module demo.

**Honesty, and this is the part that matters most.**
- `repair-log.md` records what really happened. Never edit it by hand and never script the outcome.
- If the agent's first attempt passes, write that down; it is a fine result. To show the loop working, then plant one bug, label it "planted" in the log and on screen, and let the loop find it.
- A suspect header may claim it was written by an AI only if the prompt that produced it is committed beside it.

**Stretch within this feature, only if time remains:** a read-only "Line-up" panel on the web that runs only the suspects shipped in the repository, says so on the page, and returns 409 for uploaded workbooks. The public server must never run code supplied by a visitor.

**Correctness properties.**
- An honest suspect is never convicted, across several seeds.
- Every reported counterexample reproduces when the same inputs are re-evaluated on the Referee and on the suspect.
- The brief contains no value that is absent from the report it was built from, and no absolute path.

**Done when** the honest suspect exits 0 and each caught suspect exits 1 with a counterexample that reproduces; the word "correct" does not appear in the command's output; the migration folder is complete and its `logic.py` has no generated marker; `scripts/demo.sh` and the invariant tests match the baseline.

---

## Feature 6: judge kit (`judge-kit`)

**Problem.** The README is 224 lines of plain text with no pitch, picture, diagram, category or Kiro section, and the first substantial thing a reader meets is a list of caveats. `docs/KIRO_USAGE.md` is an honest 578-line log that no judge will read. The rules ask the write-up to cover eight specific topics.

**Build.**

1. **`scripts/kiro_ledger.py`** (read-only): counts from the working tree the specs and their type, requirements, correctness properties, tasks done and open, steering files by inclusion mode, hooks by trigger and action, agents, MCP tools, Power skills and property-test files. It writes `docs/KIRO_STORY.md` and a small `web/kiro_facts.json`. A `--check` mode exits non-zero when the committed output is stale. Every number in the story is followed by the path it was counted from.
2. **`docs/KIRO_STORY.md`** has one section per topic the rules ask about:
   - which Kiro surfaces were used (IDE, CLI, Web, Crew) and how they differed;
   - custom agents;
   - agent hooks;
   - spec-driven development compared with vibe coding;
   - steering documents;
   - MCP;
   - property-based testing, including whether it caught issues unit tests missed;
   - Kiro Powers.

   Each section has generated facts plus a short paragraph drawn only from entries in `docs/KIRO_USAGE.md`. Where something was not used or not verified, the section says so. Leave a clearly marked `[OWNER: ...]` placeholder for anything only I can know (how it felt, which surface I preferred). Do not write my opinions for me.
3. **A property ledger** in the same script or a second one: one row per (spec, property number) across all specs, with the test file that covers it or "not covered". The specs each number properties from 1, so key by spec and number; mark a row "ambiguous" if you cannot tell. A "caught" column holds a bug id only when the bugfix specs or the usage log already record that the property caught it; otherwise "none recorded". The L-04 history is the candidate story; confirm it from the log before using it.
4. **A "Built with Kiro" page** at `GET /kiro`, rendered from `web/kiro_facts.json` (the container has no `.kiro/` or `docs/`, so it cannot count at runtime) and linked from the landing page.
5. **README, first screen:** one-sentence tagline; the line "Kiroween 2026, category: Resurrection" with one sentence on what is being resurrected; the live URL; a Mermaid architecture diagram (workbook → autopsy → rules → code → Referee → proof); one screenshot of the verdict card; a short Kiro table generated from the ledger; quick start. Move the limits into a section titled "Limits, stated honestly" further down. Keep every limit that is there today.
6. **`docs/DEVPOST_WRITEUP.md`**: a draft covering the problem, who has it, what the tool does, what is different from existing tools, and the eight Kiro topics, with `[OWNER]` placeholders as above. Include a "pre-existing code and outside tools" paragraph for me to complete; the rules require disclosure.
7. **`docs/DEMO_VIDEO_SCRIPT.md`**: a timed shot list that adds up to under 3:00. Suggested arc: the problem in one sentence (15 s) → drop the haunted workbook, autopsy finds F-001 (30 s) → record the decision (15 s) → the trial with the mutant graveyard (30 s) → the verdict card with the quantity = 50 counterexample (25 s) → Trial by Workbook: a suspect is caught, or the agent is corrected (35 s) → inside Kiro: a spec, a hook firing, the Power's tools (25 s) → close (5 s). Every shot must be something the deployed build really does.
8. **`scripts/preflight_demo.sh`**: GET-only checks of `/healthz` and `/` on the live URL, to run before recording.
9. **Housekeeping in the specs:** tick or explain the stale task 19 in the main spec; report the duplicated `specId` in the two bugfix specs to me rather than changing it; correct the stale "failed" status for Property 5 in `tasks.meta.json` if Kiro lets you, or tell me.
10. **More properties covered:** implement eight of the main spec's uncovered optional property tasks that need no LibreOffice (rule-id stability, emit determinism, spec file round trip, incomplete decisions rejected, tolerance, mutation accounting, report integrity against the schema, routing is total and deterministic) as new test files, and tick those tasks. They must add no more than 30 seconds to the suite.

**Done when** the ledger is byte-identical across two runs and `--check` passes; `GET /kiro` works in a container built from the Dockerfile; the README's first screen has the items listed and no link that returns an error; nothing under `ghost/`, `samples/` or `scripts/demo.sh` changed for this feature.

---

## Feature 7: large-workbook lane with a refereed AWS Transform custom hand-off (`large-workbook-lane`)

Added 25 November. Build it after Feature 5, because it reuses `ghost challenge` and the repair brief. Estimate: 1.5 days for parts A to D; part E is optional. STOP-AND-ASK before starting if Features 3 to 5 are not finished, so I can choose what to drop.

**Carried over from Feature 4 (Owner decision, 2026-11-26).** (1) `.dockerignore` excludes `.kiro`, so the deployed image has no `.kiro/steering/routing-thresholds.md`; `ghost.router.load_thresholds()` raises there, which would break `ghost route` and the MCP route tool in the container. The web app already falls back to `DEFAULT_THRESHOLDS` (a test pins that they equal the file). Decide in this feature whether to ship the file in the image or read the thresholds from the package. (2) The `atx` command builder (`ghost/router/explain.py`) uses a placeholder definition name, `excel-vba-to-python`, that must already exist in the user's AWS Transform registry, and the command is unverified. The web page now says so beside the suggested command; the builder itself is left for this feature.

**Problem.**

- A workbook over the ingest limits (5 MB, 200,000 cells, 20,000 formulas, 60 s) never reaches the router. `ghost route` and the MCP tool `recommend_route` load the workbook first, so the user gets an ingest error, not a route.
- The router ignores size. It looks only at VBA lines, UserForms, Declares and batch size.
- The AWS Transform custom command Ghost prints cannot work as written:
  - it names a definition, `excel-vba-to-python`, that exists nowhere;
  - it has no `-g` configuration, which a non-interactive run of a managed definition requires;
  - it passes the workbook's folder without checking that it is a Git repository.
- Nothing prepares the input for AWS Transform custom, and nothing checks what comes back.

**What this feature is, stated honestly.** AWS Transform custom migrates VBA code. Its documentation says nothing about worksheet formulas, cell counts or workbook size. So "large" is handled in two ways, and every screen and document must keep them apart:

- **Large in VBA** (macro-heavy): the VBA goes to AWS Transform custom. Ghost prepares the hand-off and referees the Python that comes back.
- **Large in cells or formulas:** Ghost does not send formulas to AWS Transform. It gives a route and a clear statement of what is and is not covered, and stops rejecting the file with a bare error.

**Step 0: check the facts first.** These came from the AWS documentation on 25 November. Re-read the pages, and write what you find, with URLs, into `docs/AWS_TRANSFORM_FACTS.md` before any code. If a fact below is wrong, follow the documentation and tell me.

- AWS lists a managed definition `AWS/vba-to-python-migration` (Early access) for `.bas`, `.cls`, `.frm` and VBA embedded in `.xlsm`.
- `atx custom def exec` flags: `-n`, `-p`, `-c`, `-x`, `-t`, `-g/--configuration` (a JSON or YAML file, or key=value pairs). The key `additionalPlanContext` carries extra instructions. A managed definition run with `-x` fails without it.
- `-p` must be a Git repository.
- Since CLI 3.22.1 a failed transformation still exits 0. The exit code is not a verdict; the log line `Execution was not successful` is the failure signal the official Kiro power checks.
- A definition on disk is a folder with `SKILL.md` and optional `references/` and `scripts/`.
- Price: $0.035 per agent minute. Node.js 22 or later is required.
- The official Kiro power `aws-transform` runs Transform custom through the `atx` CLI with ordinary AWS credentials.

**Build, part A: size triage, so an oversize workbook gets a route.**

1. A new function that reads sizes without loading the workbook: file bytes and the cell count from the existing streaming pre-scan (it counts cells today and throws the number away), plus the list of limits exceeded. The pre-scan does not count formulas. Either add a streaming formula count or report "formulas: over the limit, not counted". Do not guess a number.
2. `ghost route` and `recommend_route` run triage first. For an over-limit workbook they return a route with the measured sizes and reasons, not an ingest error. VBA figures come from the static VBA read alone; handle its errors so an unreadable VBA project gives "VBA: not readable", not a crash. Metrics that need a loaded workbook are reported as "not checked".
3. Size thresholds become optional keys in the YAML block of `.kiro/steering/routing-thresholds.md`. The parser today requires exactly four integer keys, so make the new keys optional with defaults; an existing file must still load.
4. The route output always says what happens to each part: "VBA: N lines, sent to AWS Transform custom" and "Formulas: N, not sent, converted by Ghost" or "not converted, not checked", whichever is true.
5. Web: a file under 5 MB that exceeds the cell or formula limit shows a route card where the error text is today. A file over 5 MB is cut off during upload, so the server cannot route it; that message becomes "too large for the public demo; run Ghost locally" with the command. Do not raise the upload cap.

**Build, part B: a truthful AWS Transform command.** Rewrite the command builder in `ghost/router/explain.py` from what Step 0 found: the definition name read from configuration (default the AWS managed one), a `-g` configuration file, and a check that the target is a Git repository. It is still only printed, labelled "suggested command, not run". Update `plugin/skills/route-migration/SKILL.md` and the steering file to match.

**Build, part C: the hand-off kit.** New command `ghost handoff <workbook> --out DIR`, and the same as an MCP tool. It executes nothing and calls no AWS service. It writes a folder ready to become a Git repository:

- `vba/`: each VBA module as a text file, read statically.
- `GHOST_CONTRACT.md`: the shape the returned Python must have so the workbook can referee it. One `logic.py` with `compute(inputs) -> dict`, the input and output names from `mapping.yaml`, the Excel error values, the tolerance, the rounding rules.
- `mapping.yaml`, `rules.md` and a copy of the Excel-semantics table.
- `atx-config.yaml`: the `-g` file, with `additionalPlanContext` pointing the agent at the contract.
- `RUN.md`: the exact steps for the owner. `git init`, the command, how to tell whether the run failed (the log line, not the exit code), the price per agent minute, and the `ghost challenge` command to run afterwards.
- A warning at the top of `RUN.md`: review `vba/` for passwords, connection strings and file paths before uploading, and note AWS's documented position on using content for service improvement, with its link.

**Build, part D: referee what comes back.**

1. `ghost challenge <workbook> --code <kit>/logic.py --mapping <kit>/mapping.yaml` gains a third exit code: 0 = no difference found on N cases; 1 = a difference was found, with the repair brief written as in Feature 5; 2 = could not be refereed, with the reason (for example no `compute()`, or outputs the Referee cannot calculate).
2. The existing check that rejects not-converted outputs was written for Ghost's own generator. Decide, and STOP-AND-ASK if unsure, how a foreign module may be refereed on an output fed by a VBA function. Never weaken the check for generated code.
3. **Macro spike, local only.** No test runs the Referee with macros on today. Write one LibreOffice-marked test on the macro sample that opens the Referee with macros trusted and evaluates the cell that calls the VBA function. Report what really happens.
   - If it calculates: `ghost challenge --trust-macros` may referee VBA-fed outputs on the user's own machine. Every verdict on such an output adds "agrees with LibreOffice's reading of the VBA; not checked in Excel".
   - If it does not: VBA-fed outputs are "not verifiable by the Referee", and the kit, the README and the Feature 4 wording say so.
4. A `transform-receipt.json` beside the report records the definition name and the log path as "stated by the owner, not verified by Ghost". Ghost cannot prove where a file came from.

**Part E, optional: how Kiro speeds this up.** Build only what the Kiro documentation supports; note the source in `docs/KIRO_SURFACES_FORMATS.md`.

- **Two powers together.** A new skill in the Ghost power, `large-workbook-lane`: autopsy → route → hand-off kit → pass the kit folder to the official `aws-transform` power, which runs `atx` → `ghost challenge` → repair loop. The skill never hardcodes a definition name; the official power lists definitions itself.
- **A guard hook.** A `PreToolUse` hook on shell commands that blocks any command starting with `atx` or `aws` unless I have approved it in that session. It turns ground rule 6 into something Kiro enforces.
- **Steering as configuration.** The size thresholds from part A live in the steering file the router already reads.
- **The repair hook from Feature 5, reused.** When `ghost challenge` exits 1 on returned code, the same brief drives the fix, and `repair-log.md` records each round.
- **Sub-agents for a batch.** An orchestrating agent builds one kit per workbook in parallel and referees each return, grouping workbooks as the AWS post advises (calculation-focused, data processing, UI-heavy). Kiro's maximum parallel count is not documented, so measure before stating one.

**Do not build in this feature.**

- A mode that converts or verifies an over-limit workbook in Ghost. The Referee recalculates every cell for every case with a fixed 60 s command timeout, and nothing has been measured at that size.
- The Referee as the `atx` build command. The build command also runs before any `logic.py` exists, so it would fail the baseline build.
- A wall-clock cut-off on case generation. It would make the case count depend on the machine and break reproducibility.
- Any AWS credentials, `atx` or macro execution on the public server.

**Honesty.**

- Nothing in this feature has been run against AWS. Until I complete a real run and fill in the checklist, every screen, README line and video caption says "suggested command, not run".
- Do not create a pretend AWS Transform output. Tests use a hand-written module labelled as a stand-in.
- Never say AWS Transform converts formulas or handles workbook size.

**Correctness properties (no AWS, no LibreOffice).**

- Triage never loads the workbook, and the route for a workbook within the limits is identical to today's.
- For any size profile and thresholds, exactly one route is returned, and every limit exceeded appears in the reasons.
- The kit is byte-identical across two runs, contains no absolute path, and every VBA module the static read returns appears exactly once.
- The printed command always carries `-g`, and never appears without the "not run" label.
- A thresholds file with only the four original keys loads with the defaults.

**Done when**
- `ghost route` on a generated over-limit workbook returns a route with sizes and reasons, and exits 0.
- `ghost handoff` on the macro sample writes the kit, and `git init` in it succeeds.
- `ghost challenge` on a stand-in `logic.py` in the kit exits 0, 1 and 2 in the three cases.
- The macro spike result is written down as observed.
- Routes for the existing samples are unchanged, and the suite and `scripts/demo.sh` match the baseline.

**What I must do (add these rows to `docs/KIRO_OWNER_CHECKLIST.md`, Result left empty).** Install `atx` (it is not on this machine); attach the IAM policy; install the official `aws-transform` power; run one pilot on the macro sample; record the agent minutes and the cost; run `ghost challenge` on the result and keep the real output, whatever it is.

---

## Stretch features (only if 1 to 6 are finished by 30 November; ask me which one)

**S1. Regression test pack.** `ghost verify --testpack` writes the verified cases with the Referee's answers, a pytest file that runs with no LibreOffice, and a note stating that expected values came from LibreOffice, not Excel. It answers "what is left when the workbook is retired?" Trap: `VerifyResult.cases` holds inputs only, so it needs an optional recorder in `verify()` that must not change the case sequence or any count.

**S2. Drift detection.** `ghost drift <migration> --workbook new.xlsx` reports which rules and constants changed since the proof and marks the proof stale, with a counterexample from the old code against the new workbook. Trap: never call `run_verification` for this, because it regenerates and overwrites `logic.py` from the new workbook. Also, a constant-only change alters no rule id, so constants must be compared separately.

**S3. Kiro-format spec for the migrated workbook.** Ghost writes `requirements.md`, a design block with correctness properties, and `tasks.md` for the migration, so a workbook comes back as a native Kiro spec. First spend 30 minutes checking whether Kiro's spec panel accepts a machine-written folder. If it does not, call the output "Kiro-format spec files" and do not show the panel.

**S4. Instant sample proofs.** `/proof/haunted` and the other samples are computed on the server at start-up and served without a session, labelled with the time, seed and LibreOffice version. Traps: it must be off unless an environment variable is set, or every test starts LibreOffice; jobs must run one at a time after the first healthy check, or the health check may fail and restart the only task.

## Do not build

| Idea | Why not |
|---|---|
| More Excel functions (VLOOKUP, SUMIF and so on) | About 3.5 days in the converter, depends on LibreOffice version behaviour, and risks the demo invariants. State the 18-function limit honestly |
| TypeScript output | Does not fit the time |
| Running visitor-supplied code on the public server | Unsafe |
| Share links for uploaded workbooks | The privacy note promises deletion and there is no storage |
| Proof seal or certificate, portfolio survey, a second Finding kind, a self-playing tour | Low score for the effort |

## What to give me at the end of each feature

1. What was built, by file.
2. Suite counts against the baseline, and the `scripts/demo.sh` figures.
3. Anything measured that contradicts this document.
4. Anything left "not checked".
5. Rows of `docs/KIRO_OWNER_CHECKLIST.md` that now need me.
