# Requirements Document

## Introduction

Feature 4 of the Kiroween feature set (source: `docs/KIRO_FEATURE_PROMPT_2026-11-25.md`, "Feature 4: the dead technology on screen"). The category is Resurrection. The web app offers three `.xlsx` samples and shows no VBA, although the engine already reads it statically. The thing being resurrected is not visible.

This feature gives the Web_App:

- a fourth sample, a macro workbook built by the existing `samples/make_xlsm.py`;
- a VBA_Panel on the autopsy screen: each extracted VBA module in a collapsed, escaped code block under the heading "VBA source: read, never run", for samples and for uploads;
- the router's recommendation with its reasons and, when the engine produces one, the suggested `atx` command labelled as not run;
- one honest sentence on the sample card about what Ghost does and does not do with macro workbooks;
- the `role="alert"` fix on the VBA read error, carried over from Feature 2.

Facts read from the code and from a real run (2026-11-26), not assumed:

- `ghost.ingest.vba.extract_vba` reads `xl/vbaProject.bin` statically with oletools and returns `VbaModule(name, source, line_count)` sorted by name; it runs nothing. `Workbook.vba_modules`, `vba_present` and `vba_error` carry the result; `_describe` in `web/flow.py` already computes the metrics (`compute_metrics`) the router needs.
- `ghost.router.recommend_route(metrics)` returns a `Route` with `route` ("Ghost converts", "AWS Transform custom" or "Split"), `reasons` and `atx_command`; `with_atx_command(route, workbook)` sets the command for the AWS and Split routes. With no workbook path the command carries the placeholder `<workbook-directory>`; with one it carries the workbook's parent folder, which on the server is a path.
- `samples/make_xlsm.py` builds `discount_vba.xlsm` and `haunted_vba.xlsm` through the Referee (`RefereeClient(..., run_macros=False)` and `save_with_vba`) with macros off. It has `build_pair` and no single-file `build`. Building both took 5.8 s on this Mac in three runs, about 2.9 s per file (one LibreOffice start each). The container is a 1 vCPU host and was not measured.
- On `discount_vba.xlsm` the engine reports: 7 formulas, 23 VBA lines in 1 module (`Module1.bas`), thresholds found in the VBA (for example `quantity >= 50` at `Module1.bas:4`), `Calculator!B13` not converted ("function DELIVERYFEE is outside the P0 subset"), default inputs `Calculator!B2,B3,B4` and output `B11`, and the route "Ghost converts" (23 VBA lines within the threshold of 2000).
- The same run raises Finding F-001, "operator conflict on extraKm vs 0", with locations `Module1.bas:9 uses '<'` and `Module1.bas:9 uses '='`. The VBA line is `If extraKm < 0 Then extraKm = 0`: the `=` is an assignment, not a comparison. This looks like an engine false positive. This feature does not change the engine and shows the Finding as the engine reports it (Known limits).
- The autopsy template renders the VBA read error as `<li class="error">` without `role="alert"`. That line is identical in HEAD.
- Web uploads never run macros: `web/` contains no `run_macros` or trust option, and the Referee is opened with macros off.

Baseline for this feature: after the readable-proof follow-up (local commit `765e240`), the full suite reports 1527 passed, 3 skipped, 0 failed (348 s). `scripts/demo.sh` was run on the same code (2026-11-26): discount 31/33, haunted 33/35, D-001 Intended with one expected-by-decision mismatch at quantity 50.

## Glossary

- **Web_App**: The FastAPI application in `web/`. It contains no business logic and calls `ghost.*`.
- **Macro_Sample**: The fourth sample, id `macros`, file `discount_vba.xlsm`, built by `samples/make_xlsm.py`.
- **VBA_Panel**: The autopsy element listing the VBA modules of the workbook.
- **VBA_Module_Block**: One `<details>` element, closed by default, holding one module's source in `<pre><code>`.
- **Route_Panel**: The autopsy element showing the router's recommendation.
- **Route_Command**: The `atx` command string the engine produces for the AWS and Split routes. It is only ever text.
- **Referee**: Headless LibreOffice used as the oracle and, here, to build the Macro_Sample.
- **Baseline**: See the Introduction.
- **Demo_Invariants**: The demo results fixed by the feature prompt (Requirement 8).

## Requirements

### Requirement 1: The Macro_Sample

**User Story:** As a visitor, I want a sample that has macros in it, so that I can see what Ghost does with VBA without having a macro workbook of my own.

#### Acceptance Criteria

1. THE Landing_Page SHALL show a fourth Sample_Card for the Macro_Sample, labelled "Macro workbook (generated)", with the same card parts as the other samples (blurb, Run button, download link, and the measured-run line only when `web/measured_runs.json` has an entry for it).
2. THE Macro_Sample SHALL be built by `samples/make_xlsm.py` through the Referee with macros off, and SHALL be a generated file, never a committed binary.
3. THE `make_xlsm.py` script SHALL gain a function `build(path)` that builds `discount_vba.xlsm` alone at `path` with one Referee start; `build_pair` and its output SHALL NOT change.
4. THE Web_App SHALL build the Macro_Sample once per server process and reuse the bytes for later requests (the alternative the feature prompt allows to building on every request), and SHALL NOT start a second build while one is running.
5. WHEN the Macro_Sample is chosen, THE Web_App SHALL load it like the other samples: copy it into the session folder, read it with macros off, and show the autopsy.
6. THE download route SHALL serve the Macro_Sample with the macro-enabled media type and its own file name.
7. IF the Referee cannot start while the Macro_Sample is built, THEN THE Web_App SHALL show the existing "Referee unavailable" Failure_Card with status 503 and SHALL leave the other samples working.
8. THE Macro_Sample blurb SHALL be one sentence that says what Ghost does with a macro workbook today (reads the VBA, finds thresholds in it, converts the formulas it supports, recommends a migration route) and what it does not do (translate VBA to Python), and SHALL NOT use "correct", "proven", "proved" or "verified" as a claim.
9. THE Macro_Sample SHALL pass a Faithful run with its default cells if, and only if, a real run shows it; the blurb SHALL promise only what a real run showed.

### Requirement 2: VBA source on the autopsy screen

**User Story:** As a viewer, I want to see the macro code that Ghost read, so that the dead technology is visible and I can see that nothing ran.

#### Acceptance Criteria

1. WHEN the workbook has extracted VBA modules, THE autopsy SHALL show a VBA_Panel with the heading "VBA source: read, never run".
2. THE VBA_Panel SHALL show each module in a VBA_Module_Block whose summary names the module and its line count, closed by default.
3. THE module source SHALL be HTML-escaped: a module that contains `<script>alert(1)</script>` SHALL appear as text and SHALL NOT be inserted as markup.
4. THE VBA_Panel SHALL apply to uploaded workbooks as well as samples.
5. THE VBA_Panel SHALL show at most 400 lines of a module and at most 2000 lines in all. WHEN a module is cut, THE block SHALL say "Showing the first N of M lines." and a module that gets no lines SHALL say that the display limit was reached; the full module SHALL NOT be silently shortened.
6. THE VBA_Panel SHALL say, in one sentence, that Ghost reads this VBA without running it and does not translate VBA to Python, and that a cell that calls a VBA function is listed as not converted.
7. WHEN the workbook has no VBA modules and no VBA read error, THE autopsy SHALL show no VBA_Panel and SHALL NOT invent one.
8. WHEN the VBA could not be read (`vba_error`), THE autopsy SHALL show the error and SHALL NOT show a VBA_Panel.
9. THE VBA source SHALL come only from `Workbook.vba_modules`; the Web_App SHALL NOT run, import or evaluate any of it.

### Requirement 3: Not converted

**User Story:** As someone checking coverage, I want the cell that calls the macro function listed with its reason.

#### Acceptance Criteria

1. THE autopsy SHALL list a cell that calls a VBA function in the Not_Converted_Panel with the reason the engine reports (for the Macro_Sample, `Calculator!B13` and "function DELIVERYFEE is outside the P0 subset").
2. THE Web_App SHALL NOT supply or rephrase that reason.

### Requirement 4: The route

**User Story:** As someone with a macro workbook, I want to know which path the router recommends and why.

#### Acceptance Criteria

1. THE autopsy SHALL show a Route_Panel with the route name from `recommend_route` ("Ghost converts", "AWS Transform custom" or "Split") and each reason it returns, computed from the same metrics the autopsy already uses.
2. WHEN the route has a Route_Command, THE Route_Panel SHALL show it in a code element with the label "suggested command, not run", and SHALL NOT run it.
3. THE Route_Command SHALL use the placeholder `<workbook-directory>` and SHALL contain no server path, session id or file name.
4. THE Route_Panel SHALL say that the route is a recommendation computed from counts in the workbook.
5. WHEN the route has no Route_Command, THE Route_Panel SHALL show no command and no label for one.

### Requirement 5: Error alert carry-over

**User Story:** As a screen-reader user, I want the VBA read error announced.

#### Acceptance Criteria

1. THE element that shows the VBA read error SHALL carry `role="alert"`, with its visible text and its "(VBA: not checked)" suffix unchanged.
2. EVERY element with class `error` in the rendered autopsy SHALL carry `role="alert"`.

### Requirement 6: No macro runs

**User Story:** As the Owner, I want to be sure this feature cannot run a macro.

#### Acceptance Criteria

1. THE Web_App SHALL NOT run a macro from any upload or sample: no code under `web/` SHALL pass `run_macros=True`, a trust option or an equivalent to the Referee, the verifier or the engine.
2. THE Macro_Sample SHALL be built with `run_macros=False`.
3. THE existing tests that check that no trust option appears on any page SHALL pass unchanged.
4. A test SHALL read the source of `web/` and `samples/make_xlsm.py` and assert that `run_macros=True` and `trust_macros` appear nowhere in them.

### Requirement 7: Legacy `.xls` files

**User Story:** As the Owner, I want to know whether old `.xls` files could be accepted.

#### Acceptance Criteria

1. THE feature SHALL check, with a real conversion, whether the Referee can convert a legacy `.xls` file to `.xlsx` or `.xlsm` with macros off, whether formulas and VBA survive, and whether the conversion adds a way to run macros.
2. THE answer SHALL be written in the usage log and the final summary, with what was measured and what was not.
3. THE feature SHALL build `.xls` upload only if the check shows it adds no way to run macros and it fits within two hours; otherwise it SHALL leave uploads as they are.

### Requirement 8: Constraints and invariants

**User Story:** As the Owner, I want this feature to leave the proven behaviour and the other rules alone.

#### Acceptance Criteria

1. THE Web_App SHALL leave the Demo_Invariants unchanged: discount Faithful passes with mutation at least 31/33; haunted raises F-001, Faithful passes with 0 mismatches and mutation at least 33/35; haunted with D-001 in Intended mode passes with exactly one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0); seed 20261204; default cells `Calculator!B2,B3,B4` to `B11` and scenarios `Model!B2,B3,E2` to `B19,B20`.
2. THE feature SHALL make no change under `ghost/`, SHALL add no field to the Proof_Report, and SHALL add no dependency.
3. THE feature SHALL leave all existing tests passing and SHALL add only new tests; the full suite SHALL show the Baseline plus only this feature's new tests, with 0 failed. The one exception is a test that hard-codes the number or the file type of the samples: it MAY be extended to cover the fourth sample, and no assertion in it MAY be weakened or removed. (Amended after the Skeptic's review: four existing tests were extended this way and are listed in the usage log.)
4. A check that was not run SHALL read "not checked"; no invented value SHALL appear in the VBA_Panel, the Route_Panel or the blurb.
5. THE new markup SHALL keep the skip link, labels, visible focus, `role="alert"` on errors, the reduced-motion guard for every animation, the 360 px layout, and SHALL NOT use colour as the only signal.
6. THE new text SHALL NOT use "correct", "proven", "proved" or "verified" as a claim about a workbook.
7. THE feature SHALL leave its changes uncommitted until it is done, then commit locally and SHALL NOT push.

### Requirement 9: Tests

**User Story:** As a reviewer, I want the claims tested.

#### Acceptance Criteria

1. THE test suite SHALL include a test that the Macro_Sample loads from its card and the autopsy shows its module, its line count and the heading "VBA source: read, never run" (skipped when LibreOffice is not installed).
2. THE test suite SHALL include a test that module source containing `<script>` renders escaped, built without LibreOffice from a hand-made autopsy context, and a test with a real `.xlsm` built by `save_with_vba` (skipped when LibreOffice is not installed).
3. THE test suite SHALL include tests for the line caps and the "Showing the first N of M lines." statement.
4. THE test suite SHALL include tests for the Route_Panel (route name, reasons, command label, the placeholder, no server path) for the three routes.
5. THE test suite SHALL include the `role="alert"` test of Requirement 5 and the no-macro test of Requirement 6.4.

## Known limits

- **The engine may raise a false Finding on VBA.** On the Macro_Sample the engine reports F-001 "operator conflict on extraKm vs 0" because `If extraKm < 0 Then extraKm = 0` has an assignment that is read as a comparison. This feature does not change the engine; the Finding is shown as reported, and the only option the form offers for a macro location is to keep the original behaviour. Reported to the Owner as an engine question.
- **The route says "Ghost converts" for a small VBA module although Ghost does not translate VBA.** It follows the router's thresholds (`ghost/router`), which this feature does not change. The VBA_Panel sentence of Requirement 2.6 states what Ghost does not do.
- **The first request for the Macro_Sample pays the build.** It takes about 3 s on a Mac and was not measured on the container.
- **The VBA display is capped** (Requirement 2.5); a larger module is shown in part, and says so.

## Out of scope

- Translating VBA to Python, running any macro, UserForm recreation.
- Verifying cells that call VBA functions against the Referee (the Referee runs with macros off).
- Changing the router thresholds or the engine's threshold extraction.
