# Requirements Document
## Introduction
Feature 7 (source: `docs/KIRO_FEATURE_PROMPT_2026-11-25.md`, "Feature 7: large-workbook lane with a refereed AWS Transform custom hand-off"). Facts about AWS Transform custom come from `docs/AWS_TRANSFORM_FACTS.md` (Step 0, read 2026-11-26), not from memory. Nothing in this feature runs `atx` or any AWS command, and nothing has been run against AWS.

**What this feature is, stated honestly.** AWS Transform custom migrates VBA code. Its documentation says nothing about worksheet formulas, cell counts or workbook size. "Large" is therefore handled in two separate ways, and every screen and document keeps them apart:
- **Large in VBA:** the VBA goes to AWS Transform custom. Ghost prepares the hand-off kit and referees the formula-fed outputs of the Python that comes back (the check covers only outputs calculated by worksheet formulas; a pass says nothing about the migrated VBA).
- **Large in cells or formulas:** Ghost does not convert the formulas at that size. It gives a route and says what is and is not covered, instead of a bare ingest error. (A kit for a workbook that was loaded carries `rules.md`, which restates the formulas in English and is uploaded with the kit; the workbook file and its cell values are never in it.)

Owner decisions made on 2026-11-26 that shape this spec:
- `ghost challenge` already exits 0, 1 (a difference, including a raising `compute()`) or 2. This feature adds an engine-written repair brief to it and a receipt runner; it adds no `--trust-macros` (see Requirement 9).
- The `.dockerignore` gap for `routing-thresholds.md` is fixed here with a negated pattern for that one file only.
- Part E (Kiro surfaces) is optional.

## Glossary
- **Triage**: Reading the size of a workbook without loading it.
- **Size profile**: Bytes, cells and formulas counted by streaming the sheet XML, the limits exceeded, and the static VBA facts.
- **Kit**: The folder written by `ghost handoff`.
- **Stand-in**: A hand-written module used in tests in place of AWS Transform output. It is never presented as AWS output.
- **Receipt**: `transform-receipt.json`, written by `ghost receipt`.
- **Referee**: The original workbook recalculated by headless LibreOffice.

## Requirements
### Requirement 1: Size triage without loading
**User Story:** As someone with a big workbook, I want a route and the measured sizes, not an ingest error.
#### Acceptance Criteria
1. A function `scan_sizes(path)` SHALL return the file size in bytes, the number of cells, the number of formulas, and the list of ingest limits exceeded (file size, cells, formulas), reading the sheet XML as a stream with defusedxml and never loading the workbook with openpyxl.
2. THE formula count SHALL count `<f>` elements in the sheets. IF counting stops (the 60 s processing limit, or an archive that expands past 200 MB) THEN THE profile SHALL say "at least N" or "not counted" and the reason, and SHALL NOT guess a number.
3. THE VBA figures (lines, modules, UserForms, Declares) SHALL come from the static VBA read alone. IF the VBA project cannot be read THEN THE profile SHALL say "VBA: not readable" and carry on.
4. Metrics that need a loaded workbook (calculator shape, external links, volatile and unsupported constructs) SHALL be reported as "not checked" for a workbook that was triaged without loading.
5. A file that is not a workbook archive SHALL still be an error (the existing ingest message), because no route can be made.
### Requirement 2: Routing uses the sizes
#### Acceptance Criteria
1. `ghost route` and the MCP tool `recommend_route` SHALL run triage first. WHEN a limit is exceeded THEY SHALL return a route with the measured sizes and reasons and exit 0, and SHALL NOT load the workbook.
2. WHEN no limit is exceeded THE route, reasons and metrics SHALL be identical to today's (the workbook is loaded as before).
3. FOR any size profile and thresholds THE router SHALL return exactly one route, and every limit exceeded SHALL appear in the reasons.
4. IF an over-limit workbook has VBA above the VBA threshold, or UserForms or Declares above theirs, THEN THE route SHALL be "AWS Transform custom" for the VBA part. OTHERWISE it SHALL be a new route, "Over Ghost's limits", which says Ghost does not convert this workbook here and that the formulas are not sent to AWS Transform.
5. THE route output SHALL always say what happens to each part: "VBA: N lines, goes to AWS Transform custom (suggested command, not run)" (or "VBA: N lines, read statically, not converted by Ghost" / "VBA: none" / "VBA: not readable"), and, whichever is true, "Formulas: N, converted by Ghost where it can; the kit's rules.md restates them in English and is uploaded with the kit" (an AWS route within the limits), "Formulas: N, converted by Ghost (supported functions only; ...)" (Ghost converts), "Formulas: N, not converted by Ghost (over the limit); a kit for this workbook has no rules.md, so they are not in it" (over the limits) or "Formulas: not counted".
6. THE size thresholds SHALL be optional keys of the YAML block in `.kiro/steering/routing-thresholds.md` (`max_file_bytes`, `max_cells`, `max_formulas`, `transform_definition`) with defaults, and a file with only the four original keys SHALL load with the defaults. A size threshold above Ghost's ingest limit SHALL NOT raise the limit: the effective value is the smaller one.
### Requirement 3: The web app
#### Acceptance Criteria
1. WHEN an upload under 5 MB exceeds the cell or formula limit, THE autopsy area SHALL show a route card with the sizes, the route and the reasons where the error text is today.
2. WHEN an upload exceeds 5 MB THE message SHALL read "too large for the public demo; run Ghost locally" with the command `ghost route <file>`. THE upload cap SHALL NOT be raised.
3. THE web app SHALL NOT import `ghost.challenge`, `ghost.handoff` or `ghost.receipt`, run `atx`, or offer a hand-off download.
### Requirement 4: A truthful AWS Transform command
#### Acceptance Criteria
1. THE command builder in `ghost/router/explain.py` SHALL name the definition from configuration (`transform_definition`, default `AWS/vba-to-python-migration`, the AWS-managed Early-access definition), SHALL carry `-g <config file>`, `-p <directory>`, `-c <build command>`, `-x` and `-t`, and SHALL never be printed without the label "suggested command, not run".
2. (Superseded by 11.5, 2026-11-26.) THE builder no longer checks the workbook's folder for a Git repository: `-p` is always `<kit-folder>`, the folder that `ghost handoff` writes, and the CLI hint says to run `ghost handoff` first. `RUN.md` tells the owner to run `git init` in the kit.
3. THE text SHALL say that `-t` approves all tool calls, that a non-interactive run exits 0 even when the transformation failed (CLI 3.22.1 or later), and that Node.js 22 or later is required.
4. `plugin/skills/route-migration/SKILL.md` and the steering file SHALL match.
5. THE text SHALL NEVER say that AWS Transform converts formulas or handles workbook size.
### Requirement 5: The hand-off kit
#### Acceptance Criteria
1. `ghost handoff <workbook> --out DIR` and the MCP tool `prepare_handoff` SHALL write, without executing anything and without calling AWS: `vba/` (each module as text, read statically), `GHOST_CONTRACT.md`, `mapping.yaml`, `rules.md`, `excel-semantics.md`, `atx-config.yaml` (with `additionalPlanContext` pointing at the contract) and `RUN.md`.
2. THE kit SHALL be byte-identical across two runs, SHALL contain no absolute path, and SHALL contain every VBA module the static read returns exactly once (module names are made safe as file names, and two modules that would collide get different names).
3. `RUN.md` SHALL start with a warning: review `vba/` for passwords, connection strings and file paths before uploading, and AWS's documented position that it may use content, including generated code, for service improvement, with the link and the opt-out route.
4. `RUN.md` SHALL give the steps: `git init` and the first commit, the suggested command (labelled "suggested command, not run"), how to tell whether the run failed (the exit code is 0 even on failure, so read the log and judge by `ghost challenge`), the price per agent minute ($0.035) and the `ghost challenge` command to run afterwards.
5. FOR an over-limit workbook the kit SHALL hold `vba/`, the contract and `RUN.md` and SHALL say that `mapping.yaml` and `rules.md` were not written because the workbook was not loaded.
6. THE command SHALL refuse an `--out` that exists and is not empty.
### Requirement 6: Refereeing what comes back
#### Acceptance Criteria
1. `ghost challenge` SHALL exit 0 (no difference found on N cases), 1 (a difference, including a raising `compute()`) or 2 (could not be refereed, with the reason). It SHALL write `repair-brief.json` in the `--out` folder when it exits 1 or 0, written by the engine from the proof report (the same content as Feature 5's brief).
2. A foreign module for an output fed by a VBA function SHALL be refused with exit 2 and the engine's reason ("not converted" or "not verifiable"). The check SHALL NOT be weakened for generated code or for foreign code.
3. THE macro spike SHALL be a LibreOffice-marked test on the macro sample that opens the Referee with macros trusted and evaluates the cell that calls the VBA function, and the observed result SHALL be recorded in the spec and the README.
### Requirement 7: The receipt
#### Acceptance Criteria
1. `ghost receipt <workbook> --kit DIR --definition NAME --log PATH` SHALL run `ghost challenge` as a subprocess on the kit's `logic.py` and `mapping.yaml` and write `transform-receipt.json` in a receipt folder it owns, beside the report.
2. IT SHALL pass an absolute `--out` under the receipt's own folder and run from a working directory the command owns.
3. IT SHALL record a pass only when ALL of these hold: the exit code is 0; the report's mode is `faithful` and it names a LibreOffice version; `<out>/reports/faithful/proof-report.json` exists; its `passed` is true; `cases_tested` is above 0; the seed is the expected one. An exit code of 0 with no report is an error, never a pass.
4. IT SHALL wrap the call in a timeout. Any exit status other than 0, 1 or 2, or a timeout, SHALL be recorded as an error.
5. IT SHALL read the exit code and the report only, never the candidate's printed output.
6. THE receipt SHALL state: the definition name and the log path as "stated by the owner, not verified by Ghost"; that the candidate runs in the verifier's own process, so the result holds for code that is not trying to defeat the check; whether the mapping was given or derived; and "not checked in Excel".
7. THE receipt and the README SHALL list the known limits: no sandbox; a candidate must be one self-contained file; recorded Decisions are not consulted by `ghost challenge`.
### Requirement 8: The Docker image
#### Acceptance Criteria
1. `.dockerignore` SHALL keep excluding `.kiro` and SHALL add a negated pattern for `.kiro/steering/routing-thresholds.md` only, so that `load_thresholds()` works in the image. A test SHALL check the patterns and that no other file under `.kiro` is let in.
### Requirement 9: Macro workbooks
#### Acceptance Criteria
1. WHEN the macro spike shows that the Referee cannot calculate a cell that calls a VBA function (even with macros trusted), THEN THE kit, the README and the web text SHALL say that VBA-fed outputs are "not verifiable by the Referee", and `--trust-macros` SHALL NOT be added to `ghost challenge`.
### Requirement 10: Honesty and records
#### Acceptance Criteria
1. EVERY screen, README line and caption that mentions an AWS Transform command SHALL say "suggested command, not run" until the Owner completes a real run.
2. NO test SHALL create a pretend AWS Transform output; a stand-in is a hand-written module labelled as one.
3. THE rows for the Owner SHALL be added to `docs/KIRO_OWNER_CHECKLIST.md` with the Result left empty.
4. `docs/KIRO_USAGE.md` SHALL record every task, including failures.

### Requirement 11: Corrections of 2026-11-26
#### Acceptance Criteria
1. `RUN.md` SHALL say "Review vba/, rules.md and mapping.yaml before you upload anything" and "The workbook file and its cell values are not in this kit. rules.md restates the worksheet formulas in English so the agent can meet the contract; it is uploaded with the rest."
2. THE README, `RUN.md`'s limits and the receipt's known limits SHALL say: "The check covers only outputs calculated by worksheet formulas. Values produced by the VBA itself are not refereed, so a pass says nothing about the migrated VBA."
3. THE receipt SHALL record `mapping_sha256`, the output (and input) name-to-cell pairs and `mapping_equals_ghost_derived`; IF the mapping differs from the one Ghost derives, THEN THE result SHALL be an error, not a pass. `RUN.md` SHALL tell the owner that the `git diff` of `mapping.yaml` and `GHOST_CONTRACT.md` against the first commit must be empty before refereeing.
4. `route_for_sizes` SHALL send VBA to "AWS Transform custom" only when VBA exists; an over-limit workbook with no VBA and a batch at the threshold SHALL be "Over Ghost's limits" with no command.
5. THE suggested command SHALL always use `-p <kit-folder>`, and the CLI hint SHALL say to run `ghost handoff` first.
6. THE pre-scan of the loader and of triage SHALL build no tree (a counting target through defusedxml).
7. A candidate's exception text SHALL be on one line in the challenge output and the repair brief; the "repair brief:" line SHALL be printed only on a failure.
8. A `--definition` other than the default SHALL be "the definition you named; Ghost has not checked it exists".
