# Requirements Document

## Introduction

Feature 3 of the Kiroween feature set (source: `docs/KIRO_FEATURE_PROMPT_2026-11-25.md`, "Feature 3: the ten-second verdict and a readable autopsy"). Today the result of a run is one bold sentence above an iframe, and the autopsy lists checkboxes labelled `Model!B2` with no label, value or formula, under a Finding title that is hard-coded as "operator conflict". Someone watching a video cannot tell what is being checked or what was found.

This feature gives the Web_App:

- **Part A, a Verdict_Card** built by a new pure module `web/verdict.py` from the parsed Proof_Report and nothing else: a headline, three tiles, the minimal counterexample when there is a mismatch, a "What was not proven" strip, a Reproduce_Line and a collapsed glossary;
- **Part B, a readable autopsy**: labelled input and output choices, a Finding_Card that names its kind and shows each conflicting location, Decision options as radio cards, and a panel for cells that were not converted.

Facts from the current code and reports that these requirements rely on (read on 2026-11-25 and 2026-11-26, not assumed):

- The Proof_Report JSON (`ghost/report/schema/proof-report-1.json`) requires `schema_version`, `ghost_version`, `seed`, `versions`, `mode`, `cases_tested`, `passed`, `mismatches`, `boundaries`, `rule_coverage`, `mutation`, `sanity`, `findings` and `decisions`. It may also hold `cases_generated`, `cases_targeted`, `distinct_cases`, `boundary_notes`, `tested_domains` and `not_converted` (each entry has `cell` and `reason`). This feature adds no field to it.
- A mismatch holds `inputs`, `expected`, `actual` and `class`, and may hold `output`, `cell`, `rule_id`, `finding_id`, `decision_id`, `minimal` and `cases`. `class` is one of `translation bug`, `original workbook inconsistency` and `expected by decision`. In the recorded haunted Intended run, `expected` is `{"total": 6.0}` (the value the Referee, the original workbook recalculated by LibreOffice, returned), `actual` is `{"total": "0"}` (the new code), `output` is `total`, `inputs` has `quantity` 50, `finding_id` is `F-001` and `decision_id` is `D-001`.
- `mutation` is either `{"mutants": [...], "killed": k, "total": t}` (with an optional `survivor_explanation`, and a `survivor_reason` on a surviving mutant record) or `{"status": "not checked"}`. `sanity` is either `{"status": "matched" | "differences" | "not cross-checked against Excel", ...}` or `{"status": "not checked"}`.
- `tested_domains[]` rows carry `input`, `type` and optional `min`, `max`, `decimal_places`, `distinct_values`, `not_tested` (boolean) and `max_includes_sample`. `rule_coverage[]` rows carry `rule_id`, `condition_id`, `seen_true` and `seen_false`. `boundary_notes` is a list of strings. A Finding location in the report is `{"cell", "line", "module"}` plus an operator.
- The result page is rendered by `web/templates/_job.html`. It already prints a verdict paragraph (built by `verdict_text` in `web/flow.py`; class `verdict pass|fail|unavailable`, `role="status"`) and "Mutation self-check: K/T mutants killed." (class `mutation-summary`) above an iframe. Existing tests pin that markup and text. The only Finding kind the engine creates is `operator_conflict` (`ghost/autopsy/findings.py`).
- The autopsy is rendered by `web/templates/_autopsy.html` from `_describe` in `web/flow.py`. Tests match each checkbox with the pattern `<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>` (`tests/test_web_samples.py`) and pin the default selection of the scenarios sample (`Model!B2`, `Model!B3`, `Model!E2` and `Model!B19`, `Model!B20`).
- `POST /decision` with an empty reason returns 422 today. The Finding title is built in the template as "{id}: operator conflict on {cell} against {constant}".
- Two label helpers exist in the engine, `_left_label` in `ghost/autopsy/classify.py` and `_label` in `ghost/converter/mapping.py`. They are equivalent: the same logic (the immediately left-adjacent constant text cell, stripped, none in column A), and they gave identical results for all 1365 cells of the three sample workbooks. Both are private.

Baseline for this feature: after the small web fixes (local commit `a28c8a4`, on top of `front-door` `0804b20`), the full suite reports 1321 passed, 3 skipped, 0 xfailed, 0 failed (332 s). The demo invariants were last run on 2026-11-25 and nothing under `ghost/` has changed since.

## Glossary

- **Web_App**: The FastAPI application in `web/`. It contains no business logic and calls `ghost.*`.
- **Proof_Report**: The `proof-report-1` JSON file produced by the engine, parsed into a dict.
- **Verdict_Module**: The new pure Python module `web/verdict.py`. It has no I/O.
- **Verdict_Card**: The new Jinja partial, rendered from the dict returned by `build_verdict`, placed above the report iframe in the result page.
- **Headline**: The one sentence at the top of the Verdict_Card.
- **Claims_Agreement**: The boolean field `claims_agreement` of the `build_verdict` result. It is true only when the Headline claims that the new code and the workbook agree.
- **Numbers_Field**: The field `numbers` of the `build_verdict` result: a mapping from a name to a non-negative integer, holding every number the Verdict_Card prints. The template prints numbers only by reading it.
- **Tile**: One of the three summary boxes: Inputs_Tile, Disagreements_Tile and Planted_Bugs_Tile.
- **Counterexample**: The mismatch shown as the centre of the Verdict_Card: its inputs, the value the workbook gives, the value the new code gives, its class in plain words and its linked Decision or Finding id.
- **Not_Proven_Strip**: The strip titled "What was not proven", with the same visual weight as a Tile.
- **Reproduce_Line**: One line showing the CLI command that repeats the run, without a server path, with its fixed caption.
- **Glossary_Block**: A collapsed `<details>` element defining Referee, mutant, Faithful and Intended.
- **Detail_Paragraph**: The existing verdict paragraph (`<p class="verdict ...">`), kept below the Verdict_Card in smaller type.
- **Cell_Label**: The text label the workbook has for a cell, returned by the public label function of Requirement 8. A cell without a label has none.
- **Finding_Card**: The autopsy element showing one Finding.
- **Decision_Card**: One selectable option of a Finding, shown as a radio card.
- **Not_Converted_Panel**: The autopsy element listing each cell that was not converted, with its reason.
- **Referee**: Headless LibreOffice used as the oracle.
- **Baseline**: See the Introduction.
- **Demo_Invariants**: The demo results fixed by the feature prompt (Requirement 12).

## Owner decisions

Recorded from the Owner's review of the first draft (2026-11-26). The requirements below already reflect them.

1. The Headline claims agreement only when `passed` is true and `mismatches` is empty, as in the feature prompt. The Intended sentence ("No unexplained difference ... K expected by decision") is a separate state and is not an agreement claim. `build_verdict` returns `claims_agreement`, and Properties 1 and 5 are tested on it.
2. Property 2 also allows "the number of entries of one report array that share a recorded field value". Ids, cell addresses and the seed are not numbers for that property. `build_verdict` returns the numbers as fields so the test checks the dict, not scraped text.
3. The Reproduce_Line has no `--cases`: `python -m ghost.cli verify <migration-dir> --mode <mode> --seed <seed>`, with a fixed caption.
4. One public label function in `ghost/autopsy/classify.py` with the exact body of `_left_label`; `_left_label` delegates to it. `mapping._label` and the rules namer are not touched.
5. The current value of an input is the constant in the workbook cell as loaded, escaped, worded "value in the workbook".
6. The boundary number line is out of scope.
7. Mismatch class names in plain words are fixed (Requirement 4), with the engine's class string shown beside them.
8. The tasks follow the build order below, so that the last items can be cut.

Open: **Analyze Requirements.** The feature prompt asks for Kiro's Analyze Requirements before design. It is a Kiro IDE action and has not been run; the Owner runs it on this file.

## Build order

`tasks.md` SHALL order the work as follows, so that the later steps can be cut if time runs out. Requirement 12 applies to every step. Items marked "(optional)" are built last within their step and may be cut.

1. **Part A:** Requirements 1 to 7, with the Requirement 13 properties and examples that belong to them.
2. **Requirements 8 and 9:** the public label function, labelled inputs and outputs, and the Finding_Card.
3. **Requirements 10 and 11:** Decision_Cards and the Not_Converted_Panel.

## Known limits

Recorded now, not to be fixed by this feature.

- **Labels come only from the constant text cell directly to the left of a cell** (Requirement 8). Most cells of the scenarios table (columns C to H of rows 6 to 15) have a number or a formula on their left, or no left neighbour, and so show the address alone. The cells of column B in that table take the scenario name from column A as their label.
- **`Model!E3` in the scenarios sample** feeds `B19` and `B20` but is classified as a parameter because its label contains "allowance", so it is not checked by default. No engine change is made.

## Requirements

### Requirement 1: The Verdict_Module is pure

**User Story:** As a reviewer, I want the verdict built from the proof file alone, so that every statement on the card can be traced to a field in that file.

#### Acceptance Criteria

1. THE Verdict_Module SHALL provide `build_verdict(report: dict) -> dict` that takes the parsed Proof_Report and no other argument.
2. THE Verdict_Module SHALL perform no file, network or process I/O, SHALL NOT read the clock or a random source, and SHALL NOT import the Referee, the verifier or the web framework.
3. THE `build_verdict` function SHALL NOT modify its argument.
4. WHEN called twice with equal arguments, THE `build_verdict` function SHALL return equal results.
5. IF a field it reads is missing or has the wrong type, THEN THE `build_verdict` function SHALL show that item as "not checked" and SHALL NOT raise.
6. THE Web_App SHALL add no field to the Proof_Report and SHALL leave `ghost/report/` and the `proof-report-1` schema unchanged.
7. THE result of `build_verdict` SHALL include the boolean `claims_agreement` and the mapping `numbers` (Numbers_Field). Every number the Verdict_Card prints SHALL equal an entry of the Numbers_Field, and THE template SHALL compute no number. (Amended during the build, 2026-11-26: the tiles print item text that the builder makes from the same value as its `numbers` entry, and a test on the rendered card checks that each printed number is in the Numbers_Field.)

### Requirement 2: Headline

**User Story:** As a viewer, I want one sentence that says what the run found, so that I can read the result in ten seconds.

#### Acceptance Criteria

1. THE Headline SHALL be built only from values in the Proof_Report and the lengths of its arrays, by the logic of the existing `verdict_text` function, which SHALL move to the Verdict_Module (`web/flow.py` imports it from there) so that the Headline and the Detail_Paragraph cannot differ.
2. THE Headline SHALL claim agreement only when `passed` is `true` and `mismatches` is empty, and THE `claims_agreement` field SHALL be true when, and only when, that holds.
3. WHEN `passed` is `true` and `mismatches` is empty, THE Headline SHALL read "Passed: no difference found on N cases", with N taken from `cases_tested`.
4. WHEN `passed` is `true`, the mode is `intended`, `mismatches` is not empty and every mismatch has class `expected by decision`, THE Headline SHALL read "Passed: no unexplained difference found on N cases; K expected by decision" followed by the Decision ids. This is a separate state and not an agreement claim, so `claims_agreement` SHALL be false. The existing `verdict_text` SHALL be changed only so that this state requires the mode to be exactly `intended`; all its other outputs and the existing tests stay as they are.
5. WHEN `passed` is `false`, THE Headline SHALL read "Not passed: K difference(s) found", with K the number of mismatches that are not `expected by decision`, or "Not passed" when K is 0, and `claims_agreement` SHALL be false.
6. IF `passed` is missing or is not a boolean, THEN THE Headline SHALL read "Verdict not available".
7. IF `passed` is `true` and neither state of criteria 3 and 4 holds (a mismatch that is not `expected by decision`, mismatches with a mode other than `intended`, or a mismatch list that is missing, is not a list, or cannot be counted: only an empty list means "no mismatches", amended after the Skeptic's review), THEN THE Headline SHALL be the bare label "Passed" and `claims_agreement` SHALL be false.
8. IF `cases_tested` is missing or is not a positive integer, THEN THE Headline SHALL write "number of cases: not checked" in place of "on N cases".
9. THE Headline SHALL NOT contain the words "correct", "proven", "proved" or "verified".

### Requirement 3: Tiles

**User Story:** As a viewer, I want three numbers with their meaning, so that I know how hard the run looked and how well it was tested.

#### Acceptance Criteria

1. THE Verdict_Card SHALL show an Inputs_Tile with the counts `cases_generated`, `cases_targeted` and `distinct_cases`; a count that is missing from the Proof_Report SHALL read "not checked".
2. THE Verdict_Card SHALL show a Disagreements_Tile with the number of mismatches and the number in each class.
3. THE Verdict_Card SHALL show a Planted_Bugs_Tile reading "K of T" with `killed` and `total`, and a determinate bar for the ratio when `total` is greater than 0.
4. WHEN `total` is 0, THE Planted_Bugs_Tile SHALL read "0 of 0" and SHALL show no bar.
5. WHEN the Mutation_Block has no `total` (it is `{"status": "not checked"}`), THE Planted_Bugs_Tile SHALL read exactly "not checked" and SHALL show no bar.
6. THE Planted_Bugs_Tile SHALL show the recorded `killed` and `total` as they are. IF `killed`, `total` and the `mutants` list disagree, THEN THE Planted_Bugs_Tile SHALL still show the recorded numbers and SHALL NOT correct them.
7. THE Planted_Bugs_Tile SHALL list every mutant of the `mutants` list whose `killed` flag is false, with its `mutant_id` and its recorded `survivor_reason`, and SHALL NOT hide, merge or drop any of them.
8. WHEN a surviving mutant has no recorded reason, THE Planted_Bugs_Tile SHALL show "no reason recorded" for it.
9. THE Planted_Bugs_Tile SHALL show `survivor_explanation` when the Mutation_Block has one.
10. THE state of each Tile SHALL be shown by text or an icon as well as by colour.

### Requirement 4: Counterexample

**User Story:** As a viewer, I want to see the one input where the new code and the workbook differ, so that I can check it by hand.

#### Acceptance Criteria

1. WHEN the Proof_Report holds at least one mismatch, THE Verdict_Card SHALL show a Counterexample as its central element.
2. THE Counterexample SHALL be the mismatch with `minimal` true; IF several have it, THEN THE first in report order; IF none has it, THEN THE first mismatch.
3. THE Counterexample SHALL show the mismatch's `inputs` by name and value and the output name or cell. It SHALL show "workbook says X" with X = `expected[output]` and "new code says Y" with Y = `actual[output]`, copied as recorded. IF `output` is missing, or is not a key of `expected` or of `actual`, THEN THE Counterexample SHALL show every entry that differs between `expected` and `actual`, each with its key.
4. THE Counterexample SHALL show the mismatch's class in these plain words, with the engine's class string beside them, and the `decision_id` or `finding_id` when the mismatch has one:
   - `translation bug`: "the new code differs from the workbook, and no Finding or Decision accounts for it";
   - `original workbook inconsistency`: "the new code differs from the workbook where the workbook's own formulas disagree (Finding <id>)", leaving out "(Finding <id>)" when the mismatch has no `finding_id`;
   - `expected by decision`: "expected by decision", shown once, with the Decision id.
5. (Optional) WHEN the mismatch has `cases` greater than 1, THE Counterexample SHALL say how many generated cases it stands for.
6. WHEN `passed` is `false`, THE Verdict_Card SHALL use the failure style of the existing `.verdict.fail` (a heavy edge, the "not equal" icon and the words "Not passed"), so that the state is not shown by colour alone.
7. WHEN the Proof_Report holds no mismatch, THE Verdict_Card SHALL show no Counterexample and SHALL NOT invent one.

### Requirement 5: What was not proven

**User Story:** As a sceptical viewer, I want the limits of the check stated as prominently as its result, so that a pass is not read as more than it is.

#### Acceptance Criteria

1. THE Verdict_Card SHALL show a Not_Proven_Strip with the same container style and heading level as a Tile, not collapsed and not in smaller type.
2. THE Not_Proven_Strip SHALL list every entry of `boundary_notes`, verbatim.
3. THE Not_Proven_Strip SHALL list every `tested_domains` row whose `not_tested` is true, by input name.
4. THE Not_Proven_Strip SHALL list every `rule_coverage` row whose `seen_true` or `seen_false` is false, naming the rule, the condition and the side not seen.
5. THE Not_Proven_Strip SHALL show the Excel cross-check from `sanity.status`. WHEN the status is "not cross-checked against Excel", THE Strip SHALL print it alone as the sentence "Not cross-checked against Excel." and SHALL NOT put the label "Excel cross-check:" before it, so that the phrase does not appear twice. For the statuses "matched" and "differences" it SHALL print "Excel cross-check: <status>.", and when `sanity` has no status it SHALL print "Excel cross-check: not checked."
6. (Optional) WHEN none of the lists of criteria 2 to 4 and 8 has an entry, THE Not_Proven_Strip SHALL say so in words for each list and SHALL NOT be omitted.
7. THE word "Excel" SHALL NOT appear in a sentence that claims agreement (the Headline while `claims_agreement` is true) unless `sanity.status` is "matched".
8. THE Not_Proven_Strip SHALL list each entry of the report's `not_converted` array with its `cell` and its `reason`, and SHALL NOT supply a reason that an entry lacks.

### Requirement 6: Reproduce line and glossary

**User Story:** As a viewer, I want to repeat the run and understand the terms, so that I do not have to trust the page.

#### Acceptance Criteria

1. THE Reproduce_Line SHALL read `python -m ghost.cli verify <migration-dir> --mode <mode> --seed <seed>`, with `<mode>` and `<seed>` taken from the Proof_Report, `<migration-dir>` left as the literal placeholder, and no `--cases` argument. IF `mode` or `seed` is missing, THEN THE Reproduce_Line SHALL show "not checked" in its place.
2. THE Reproduce_Line SHALL be followed by the fixed caption "Run from the migration folder; add --mutation-cases to repeat the planted-bug check."
3. THE Reproduce_Line SHALL contain no server path, no session id and no job id.
4. THE Glossary_Block SHALL be a `<details>` element, closed by default, with one sentence each for Referee, mutant, Faithful and Intended.
5. THE glossary sentences SHALL describe what each term does and SHALL NOT claim that a passing run shows correctness.

### Requirement 7: Placement and existing text

**User Story:** As a maintainer, I want the new card to sit with the old result without breaking it.

#### Acceptance Criteria

1. THE Web_App SHALL render the Verdict_Card in `_job.html` for a finished job that has a Proof_Report, above the report iframe.
2. THE Web_App SHALL keep the Detail_Paragraph (class `verdict pass`, `verdict fail` or `verdict unavailable`, `role="status"`) and the line "Mutation self-check: K/T mutants killed." with their current text and class names, and SHALL place them below the Verdict_Card as small detail text.
3. THE Web_App SHALL keep the report iframe, its caption and the download links unchanged.
4. THE `build_verdict` result SHALL be computed in the Web_App's view layer from the Proof_Report JSON the job already holds, and the templates SHALL contain no business logic.
5. IF the Proof_Report is missing or cannot be parsed, THEN THE Web_App SHALL show no Verdict_Card and the existing error text.

### Requirement 8: Labelled inputs and outputs

**User Story:** As someone choosing what to verify, I want to see what each cell means and holds, so that I can choose without opening the workbook.

#### Acceptance Criteria

1. EACH input checkbox SHALL read "label (address), value in the workbook: V" when the cell has a Cell_Label and a stored value, with V the constant stored in the workbook cell as loaded.
2. EACH output checkbox SHALL read "label (address)" followed by the cell's formula.
3. WHEN a cell has no Cell_Label, THE Web_App SHALL show the address alone in place of "label (address)".
4. WHEN an input cell has no stored value, THE Web_App SHALL omit ", value in the workbook: V".
5. THE engine SHALL provide one public label function in `ghost/autopsy/classify.py` with the exact body of `_left_label`, and `_left_label` SHALL delegate to it. THE Web_App SHALL take labels from that function and SHALL NOT duplicate label logic in `web/`. `ghost/converter/mapping._label` and the rules namer SHALL NOT be changed.
6. THE checkbox `<input>` element SHALL keep its current attribute set and order (`type`, `name`, `value`, then `checked` when selected), so that `tests/test_web_samples.py` still matches it.
7. THE default selection SHALL NOT change.
8. EVERY label, value and formula from the workbook SHALL be HTML-escaped; a label of `<script>alert(1)</script>` SHALL appear as text.

### Requirement 9: Finding_Card

**User Story:** As someone reading a finding, I want to see what conflicts with what, so that I can decide what the new code should do.

#### Acceptance Criteria

1. THE Finding_Card title SHALL come from the Finding's `kind` (for `operator_conflict`, "Operator conflict"), not from a fixed string in the template.
2. THE Finding_Card SHALL show each location of the Finding, with the conflicting operator marked by markup and by a non-colour cue. A cell location SHALL show that cell's formula as loaded. A macro location (a module and a line) SHALL show the module and the line and no formula.
3. THE Finding_Card SHALL show one consequence sentence built only from the Finding's own fields, naming each location with its operator, of the form "at exactly 50, B7 uses >= and B9 uses >" for two locations.
4. THE consequence sentence SHALL NOT contain a computed outcome, because nothing has been evaluated at the autopsy stage.
5. THE Finding_Card SHALL keep the Finding id (for example "F-001") and the cell and constant it names in its heading.

### Requirement 10: Decision options

**User Story:** As the person who decides, I want clear options and I want to be the one who writes the reason.

#### Acceptance Criteria

1. THE Decision options SHALL be shown as Decision_Cards, each a radio input inside a labelled card, with the same `name`, `value` and `required` attributes as today.
2. THE Web_App SHALL remember the author name in the browser only (for example `localStorage`), SHALL NOT store it on the server, and SHALL NOT send it anywhere until the form is submitted.
3. THE reason field SHALL stay required and SHALL be empty when the page is served; the server SHALL NOT pre-fill it.
4. WHEN `POST /decision` receives an empty reason, THE Web_App SHALL still return status 422.
5. THE Decision_Cards SHALL show the first option selected by default as today and SHALL be operable by keyboard with a visible focus indicator.

### Requirement 11: Not_Converted_Panel

**User Story:** As someone checking coverage, I want the cells Ghost did not convert in one place, with the reason.

#### Acceptance Criteria

1. THE Web_App SHALL show a Not_Converted_Panel listing each entry of `not_converted` with its cell and its reason, and each `not_verifiable` entry with its cell, kind and detail.
2. THE Not_Converted_Panel SHALL be a panel of its own with a heading, not a list inside another section.
3. WHEN there are no such entries, THE Web_App SHALL show no panel.
4. THE Web_App SHALL NOT guess a reason for an entry that has none and SHALL write "no reason recorded".

### Requirement 12: Constraints and invariants

**User Story:** As the Owner, I want this feature to leave the proven behaviour and the other rules alone.

#### Acceptance Criteria

1. THE Web_App SHALL leave the Demo_Invariants unchanged: discount Faithful passes with mutation at least 31/33; haunted raises F-001, Faithful passes with 0 mismatches and mutation at least 33/35; haunted with D-001 in Intended mode passes with exactly one "expected by decision" mismatch at quantity 50 (Referee 6.0, new code 0); seed 20261204; default cells `Calculator!B2,B3,B4` to `B11` and scenarios `Model!B2,B3,E2` to `B19,B20`.
2. THE feature SHALL leave all existing tests passing without editing them (the change to `verdict_text` in Requirement 2.4 must make none fail) and SHALL add only new tests; the full suite SHALL show the Baseline plus only this feature's new tests, with 0 failed.
3. THE feature SHALL add no runtime dependency and no web font or remote asset.
4. THE feature SHALL make no change under `ghost/` other than the public label function and the delegation of Requirement 8.5, and SHALL make no change to `ghost/report/`.
5. EVERY number the Verdict_Card prints SHALL be an entry of the Numbers_Field, and each entry SHALL be one of: a numeric value of the Proof_Report (for example `cases_tested`, `killed`, `total`); the length of one of its arrays; or the number of entries of one of its arrays that share a recorded field value, or that do not share it (for example the mismatches of one class, the mismatches of every other class, or the mutants whose `killed` is not true). The "do not share it" form was added during the build (2026-11-26), because the Headline prints K, the number of mismatches that are not `expected by decision`, and the card prints the number of survivors; both are the complement of a shared value. Ids, cell addresses and the seed are not numbers for this rule, and the inputs, `expected` and `actual` values of a Counterexample are copied as recorded.
6. A check that was not run SHALL read "not checked", never "pass".
7. THE new markup SHALL keep the skip link, labels, visible focus, `role="alert"` on errors, the reduced-motion guard for every animation and the 360 px layout, and SHALL NOT use colour as the only signal for any state.
8. THE new text SHALL NOT use the words "correct", "proven", "proved" or "verified" as a claim about the workbook.
9. THE feature SHALL leave its changes uncommitted until the Owner asks for a commit, and SHALL NOT push.

### Requirement 13: Correctness properties

**User Story:** As a reviewer, I want the claims on the card tested against generated reports, so that no report can make the card say something its fields do not support.

#### Acceptance Criteria

1. THE test suite SHALL include Hypothesis property tests, with the explicit seed 20261204, over generated schema-valid Proof_Reports, each tagged `# Feature: readable-proof, Property N: <title>`, and each testing the dict returned by `build_verdict`, not text scraped from HTML.
2. Property 1: `claims_agreement` is true only when `passed` is true and `mismatches` is empty.
3. Property 2: every value of the Numbers_Field is a numeric value of the report, the length of one of its arrays, or the number of entries of one array that share, or do not share, a recorded field value (Requirement 12.5).
4. Property 3: WHEN the Mutation_Block is `{"status": "not checked"}`, THE Planted_Bugs_Tile reads exactly "not checked" and has no bar.
5. Property 4: every surviving mutant in the report's `mutants` list is listed in the Planted_Bugs_Tile; none is hidden.
6. Property 5: WHEN `claims_agreement` is true, the Headline contains the word "Excel" only if `sanity.status` is "matched".
7. (Optional) Property 6: `build_verdict` is deterministic and does not modify its argument.
8. THE test suite SHALL include example tests that: a failing report renders the failure style with the Counterexample; the haunted Intended card shows quantity 50, "workbook says 6.0", "new code says 0", D-001 and F-001; `total` of 0 reads "0 of 0" with no bar; the Reproduce_Line has no `--cases` and carries the fixed caption; the haunted autopsy shows each location of F-001 with its formula; `POST /decision` with an empty reason returns 422; and a label containing `<script>` is escaped.

## Out of scope

- A free "ask both" form that evaluates arbitrary inputs. It needs a new job type.
- Changing the Proof_Report schema, `ghost/report/` or the report HTML the engine writes.
- The boundary number line.
