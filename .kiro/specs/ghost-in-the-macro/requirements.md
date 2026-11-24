# Requirements Document

## Introduction

Ghost in the Macro (Kiroween 2026, Resurrection category) takes business logic trapped in an Excel workbook (formulas first, VBA as stretch) and produces three things:

1. Plain-English business rules, each traced to a source cell or macro line.
2. A modern implementation: a pure-function Python module (TypeScript as stretch) plus a simple web UI.
3. A proof report showing the new implementation matches the original workbook outputs. The proof uses property-based testing, with the original workbook recalculated by LibreOffice as referee ("the ghost is the oracle").

A mismatch may be a bug in the ORIGINAL workbook. A human decides what the correct behaviour is, and the decision is recorded in the migration spec.

There are two ways to migrate and one way to prove. The web app uses a deterministic transpiler with no AI and no API keys. The Kiro Power has an AI agent write code from the rules spec. Both use the same verifier. Large enterprise VBA portfolios are routed to AWS Transform custom.

One-liner: AWS Transform migrates VBA portfolios for enterprises; Ghost brings proof-checked migration to everyone else: one workbook, formulas included, original workbook as referee.

Constraints: about 10 working days, one developer, submissions close Fri 4 Dec 2026 2:00 PM PT. A working deployed end-to-end public-URL demo takes priority over all other work. Priorities: P0 core engine, Kiro Power, deployed web app; P1 mutation self-check, migration routing; P2 VBA conversion, TypeScript export.

Prototype findings (verified in a feasibility spike, `reference/testbench/`, which is not present in this workspace) are treated as given facts and are listed in the Glossary and in requirements 5 and 6.

## Glossary

- **Ghost**: The overall product, comprising the Core_Engine, CLI, MCP_Server, Kiro_Power and Web_App.
- **Core_Engine**: The shared Python library implementing ingestion, autopsy, rules, referee, converter, verifier, mutation check, proof report and decisions.
- **CLI**: The command-line interface to the Core_Engine.
- **Workbook**: An uploaded `.xlsx` or `.xlsm` file.
- **Ingestor**: The Core_Engine component that reads a Workbook with openpyxl and extracts VBA with oletools/olevba.
- **Autopsy**: The analysis that classifies cells, extracts thresholds, detects inconsistencies and computes metrics.
- **Cell_Role**: One of INPUT, OUTPUT, INTERMEDIATE, PARAMETER.
- **Threshold**: A constant compared against a cell in a formula or VBA comparison (for example `B2>=50`).
- **Finding**: A detected issue with a `finding_id` (for example F-001), such as an inconsistency between operators on the same cell and constant.
- **Rule**: A deterministic EARS-style business rule derived from a formula pattern, with a stable `rule_id`.
- **Rules_Generator**: The component that produces Rules and the migration spec files `rules.md`, `traceability.yaml`, `findings.yaml`.
- **Migration_Spec**: The directory `.kiro/specs/<migration>/` holding `rules.md`, `traceability.yaml`, `findings.yaml`, `decisions.yaml`, `design.md`, `mapping.yaml`.
- **Referee**: The LibreOffice process that recalculates the original Workbook and serves as the oracle.
- **Referee_Client**: The Core_Engine component that starts, drives and stops one Referee per job.
- **Referee_Protocol**: The line-delimited JSON protocol over 127.0.0.1 between Referee_Client and the Referee script.
- **Macro_Mode**: The LibreOffice macro execution setting: NEVER_EXECUTE (default) or ALWAYS_EXECUTE_NO_WARN.
- **Trusted_Source**: A bundled sample, or a local CLI invocation with `--trust-macros`. Web uploads are never a Trusted_Source.
- **Converter**: The deterministic transpiler from formula AST to a pure Python module.
- **Implementation_Contract**: A Python module exposing `compute(inputs: dict) -> dict` plus a `mapping.yaml` mapping input and output names to cell references.
- **Faithful_Mode**: Converter mode that mirrors the original workbook including quirks; zero mismatches are expected.
- **Intended_Mode**: Converter mode that applies recorded Decisions; zero UNEXPECTED mismatches are expected.
- **Verifier**: The Hypothesis-based component that compares the Implementation_Contract against the Referee.
- **Case**: One set of input values and the resulting outputs from Referee and implementation.
- **Mismatch**: A Case where implementation output differs from Referee output beyond tolerance.
- **Mismatch_Class**: One of "translation bug", "original workbook inconsistency", "expected by decision D-xxx".
- **Boundary_Probing**: Binary search over one numeric input to find the exact value where a calculated cell changes at a Threshold.
- **Decision**: A recorded human choice with `decision_id` (for example D-001), `finding_id` or `rule_id`, chosen behaviour, reason, author and date, stored in `decisions.yaml`.
- **Mutant**: A deliberately altered copy of the implementation used by the mutation self-check.
- **Mutation_Checker**: The component that generates Mutants and runs the Verifier on each.
- **Proof_Report**: The HTML and JSON report of verification results, conforming to a versioned JSON schema.
- **Sanity_Check**: The comparison of Referee recalculated values with Excel-saved values for every formula cell of an Excel-saved Workbook.
- **MCP_Server**: The Model Context Protocol server exposing Ghost tools to Kiro.
- **Kiro_Power**: The Agent Plugins package (`plugin.json`, `skills/`, `mcp.json`) named "ghost-in-the-macro".
- **Web_App**: The FastAPI application with a light frontend, deployed at a public URL.
- **Job_Runner**: The Web_App background job component that runs one Referee per job under a concurrency limit.
- **Session_Folder**: The per-session temporary directory holding uploads and outputs.
- **Router**: The component implementing `recommend_route`.
- **Route**: One of "Ghost converts", "AWS Transform custom", "Split".
- **Routing_Thresholds**: The configurable values in `routing-thresholds.md`.
- **Sample**: A Workbook generated by a committed script and labelled "generated".
- **Excel_Semantics_Table**: The golden table of Excel and VBA behaviours in requirement 15.

## Requirements

### Requirement 1: Workbook Ingestion

**User Story:** As a small-business owner, I want to upload an Excel file and have Ghost read everything in it safely, so that I can start a migration without exposing my data or risking my machine.

#### Acceptance Criteria

1. WHEN a file with extension `.xlsx` or `.xlsm` is provided, THE Ingestor SHALL read all sheets, cell values, formulas, named ranges and cross-sheet references.
2. IF a file with any other extension or content is provided, THEN THE Ingestor SHALL reject the file with an error message naming the accepted formats `.xlsx` and `.xlsm`.
3. WHEN a Workbook is ingested, THE Ingestor SHALL build a dependency graph between formula cells and their referenced cells.
4. WHEN a Workbook contains Excel-saved results, THE Ingestor SHALL load them using openpyxl `data_only=True` and keep them separate from formula text.
5. WHEN a Workbook contains VBA, THE Ingestor SHALL extract module source with oletools/olevba without executing any macro.
6. WHEN a Workbook contains NOW, TODAY, RAND, RANDBETWEEN, OFFSET or INDIRECT, THE Ingestor SHALL report each occurrence as "not verifiable as-is" with its cell reference.
7. WHEN a Workbook contains external links, data tables, array formulas, dynamic-array formulas or unsupported functions, THE Ingestor SHALL report each with its cell reference.
8. IF the file size exceeds 5 MB, THEN THE Ingestor SHALL reject the file with an error stating the 5 MB limit.
9. IF the Workbook contains more than 20,000 formulas, THEN THE Ingestor SHALL reject the Workbook with an error stating the 20,000-formula limit.
10. IF processing of a Workbook exceeds the configured processing timeout, THEN THE Ingestor SHALL abort processing and report a timeout error.
11. THE Ingestor SHALL parse all XML with defusedxml.
12. THE Referee_Client SHALL open Workbooks with external-link updating disabled (UpdateDocMode NO_UPDATE).

### Requirement 2: Autopsy Classification and Metrics

**User Story:** As an accountant, I want Ghost to tell me which cells are inputs, outputs and parameters, so that I can confirm what the spreadsheet actually does.

#### Acceptance Criteria

1. WHEN a cell holds a constant that at least one formula references, THE Autopsy SHALL classify the cell as INPUT or PARAMETER.
2. WHEN a constant cell has an input fill colour, data validation or a left-adjacent text label, THE Autopsy SHALL increase its INPUT score.
3. WHEN a constant cell is used as a rate or fixed value across formulas (for example a VAT rate), THE Autopsy SHALL classify the cell as PARAMETER.
4. WHEN a formula cell has no dependents, THE Autopsy SHALL classify the cell as OUTPUT.
5. WHEN a user selects a cell as output, THE Autopsy SHALL classify the cell as OUTPUT.
6. WHEN a formula cell has dependents and is not user-selected as output, THE Autopsy SHALL classify the cell as INTERMEDIATE.
7. WHEN formulas or VBA compare a cell with a numeric literal, THE Autopsy SHALL record a Threshold with cell, operator, constant and source location.
8. WHEN the same cell is compared with the same constant using different operators in different locations, THE Autopsy SHALL create a Finding with a unique `finding_id` listing every location and operator.
9. WHEN Autopsy completes, THE Autopsy SHALL report formula count, VBA line count, module count, UserForm count, Declare call count, external link count, volatile function count, unsupported function count and a "calculator shape" indicator.

### Requirement 3: Rules Specification

**User Story:** As a developer inheriting the workbook, I want plain-English rules traced to source cells, so that I can understand and review the business logic.

#### Acceptance Criteria

1. WHEN a formula pattern is recognised, THE Rules_Generator SHALL produce one EARS-style Rule in the form "WHEN <condition> THE SYSTEM SHALL <response>".
2. WHEN a formula is an IF, THE Rules_Generator SHALL produce a WHEN branch and an OTHERWISE branch.
3. WHEN a formula uses ROUND, THE Rules_Generator SHALL state "rounded to N decimals (half away from zero)".
4. WHEN a formula uses a lookup (INDEX, MATCH, CHOOSE), THE Rules_Generator SHALL phrase the Rule as "SHALL look up ...".
5. WHEN a neighbouring text cell labels a referenced cell, THE Rules_Generator SHALL use the label in the Rule text; otherwise THE Rules_Generator SHALL use the cell reference.
6. THE Rules_Generator SHALL derive each `rule_id` from sheet name, cell address and normalised formula so that identical inputs yield identical `rule_id` values.
7. THE Rules_Generator SHALL produce identical Rule text for identical Workbook input.
8. WHEN rules generation completes, THE Rules_Generator SHALL write `rules.md`, `traceability.yaml` and `findings.yaml` into a directory laid out as `.kiro/specs/<migration>/`.
9. THE Rules_Generator SHALL record in `traceability.yaml` the source cells or macro lines for every Rule.

### Requirement 4: Decisions

**User Story:** As a business owner, I want to decide which behaviour is correct when the spreadsheet contradicts itself, so that the new system does what I intend and the choice is documented.

#### Acceptance Criteria

1. WHEN a user answers a Finding or Mismatch, THE Core_Engine SHALL create a Decision with `decision_id`, `finding_id` or `rule_id`, chosen behaviour, reason, author and date.
2. THE Core_Engine SHALL store Decisions in `decisions.yaml` in the Migration_Spec.
3. WHEN Decisions change, THE Core_Engine SHALL summarise them in the Migration_Spec `design.md`.
4. WHILE no Decision exists for a Finding, THE Converter SHALL produce behaviour identical to the original Workbook for that Finding.
5. IF a Decision lacks any of its required fields, THEN THE Core_Engine SHALL reject the Decision with an error naming the missing fields.

### Requirement 5: Referee Process

**User Story:** As a verifier, I want the original workbook recalculated without Excel, so that I have a trustworthy oracle on any machine.

#### Acceptance Criteria

1. WHEN a job starts, THE Referee_Client SHALL install the Referee script into a temporary LibreOffice user profile at `user/Scripts/python/`.
2. WHEN a job starts, THE Referee_Client SHALL start `soffice --headless` with macro URL `vnd.sun.star.script:<file>$serve?language=Python&location=user`.
3. WHEN the Referee script starts, THE Referee SHALL connect back to the Referee_Client over 127.0.0.1 on an engine-chosen port and exchange line-delimited JSON.
4. THE Referee_Client SHALL locate `soffice` using, in order, the `GHOST_SOFFICE` environment variable, `~/Applications/LibreOffice.app`, `/Applications/LibreOffice.app` and standard Linux paths.
5. IF `soffice` cannot be located, THEN THE Referee_Client SHALL fail with an error that names the searched locations and the packages `libreoffice-calc-nogui` and `libreoffice-script-provider-python`.
6. THE Referee SHALL support the commands `open{path,run_macros}`, `eval{inputs,outputs}`, `read{cells}`, `macros`, `run_macro{name,inputs,outputs}`, `save_with_vba{out,modules}` and `quit`.
7. THE Referee SHALL return values as number, string, null or `{"error":"#DIV/0!"}` with the Excel error code.
8. WHEN the Referee evaluates or reads, THE Referee SHALL call calculateAll() first.
9. THE Referee_Client SHALL run one long-lived Referee per job and SHALL NOT modify the uploaded file.
10. THE Referee_Client SHALL write a LibreOffice profile `registrymodifications.xcu` that sets `/org.openoffice.Office.Calc/Filter/Import/VBA` properties Load, Executable and Save to true.
11. THE Referee SHALL open Workbooks with Macro_Mode NEVER_EXECUTE by default, so that a VBA function cell reads `#MACRO?`.
12. WHERE the Workbook is from a Trusted_Source and `run_macros` is true, THE Referee SHALL use Macro_Mode ALWAYS_EXECUTE_NO_WARN.
13. IF `run_macro` is requested while Macro_Mode is NEVER_EXECUTE, THEN THE Referee SHALL refuse the command with an error.
14. IF a Workbook originates from a Web_App upload, THEN THE Referee_Client SHALL NOT enable `run_macros`.
15. WHEN the Referee writes an `.xlsm` Sample, THE Referee SHALL set BasicLibraries.VBACompatibilityMode to True, ProjectName to "VBAProject", name the library VBAProject, give each module a ModuleInfo with ModuleType NORMAL, and save with filter "Calc MS Excel 2007 VBA XML".
16. IF the Referee process exits or stops responding, THEN THE Referee_Client SHALL fail the job with an error and release the process.

### Requirement 6: Referee Sanity Check

**User Story:** As a reviewer, I want to know whether the referee agrees with real Excel, so that I know how much to trust the proof.

#### Acceptance Criteria

1. WHEN a Workbook contains Excel-saved values for formula cells, THE Core_Engine SHALL compare the Referee recalculated value with the Excel-saved value for every formula cell.
2. WHEN the comparison completes, THE Core_Engine SHALL report matched count and total formula cell count (for example "referee matched Excel on 1,206/1,206 formula cells").
3. IF the Workbook was written by a script and has no Excel-saved values, THEN THE Core_Engine SHALL report "not cross-checked against Excel" and SHALL NOT report "pass".
4. WHEN any formula cell value differs, THE Core_Engine SHALL list each differing cell with both values.

### Requirement 7: Converter

**User Story:** As a developer, I want a deterministic transpiler to pure Python, so that I get readable, testable code without AI.

#### Acceptance Criteria

1. WHEN formulas in the P0 subset are provided, THE Converter SHALL generate a Python module exposing `compute(inputs: dict) -> dict`.
2. THE Converter SHALL support the operators `+ - * / ^ &`, unary minus, comparisons and percent.
3. THE Converter SHALL support IF, AND, OR, NOT, IFERROR, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, ABS, MIN, MAX, SUM, AVERAGE, CHOOSE, INDEX and exact-match MATCH.
4. THE Converter SHALL support named ranges, cross-sheet references and ranges inside aggregate functions.
5. THE Converter SHALL use Python Decimal arithmetic and SHALL convert floats with `Decimal(repr(x))`.
6. THE Converter SHALL apply Excel rounding semantics per the Excel_Semantics_Table.
7. IF a formula uses a construct outside the P0 subset, THEN THE Converter SHALL list the formula as "not converted" with its cell and reason, and SHALL NOT generate a guess.
8. WHERE Faithful_Mode is selected, THE Converter SHALL mirror original behaviour including quirks.
9. WHERE Intended_Mode is selected, THE Converter SHALL apply each recorded Decision to the generated logic.
10. THE Converter SHALL produce a `mapping.yaml` mapping every input and output name to a cell reference.
11. THE Converter SHALL produce identical output for identical input.

### Requirement 8: Verifier

**User Story:** As a business owner, I want the new code tested against the original workbook on many inputs, so that I can trust the migration.

#### Acceptance Criteria

1. WHEN verification runs, THE Verifier SHALL generate Cases with Hypothesis and compare `compute` outputs with Referee outputs for the same inputs.
2. THE Verifier SHALL weight generated inputs toward Threshold neighbours (t-1, t, t+1, and t±0.1 for decimals), zero, negatives where allowed, large values and decimals.
3. THE Verifier SHALL infer input type (integer or decimal) and range from sample values and data validation, and SHALL accept user overrides.
4. WHEN a Threshold applies to a calculated cell, THE Verifier SHALL run Boundary_Probing by binary search on one numeric input to locate the exact change point.
5. THE Verifier SHALL compare numbers with absolute tolerance 1e-6 by default, strings exactly and Excel errors by error type.
6. WHEN a Mismatch is found, THE Verifier SHALL shrink the Case to a minimal counterexample.
7. THE Verifier SHALL record the random seed so that a run is reproducible.
8. THE Verifier SHALL track rule coverage by observing each Rule condition as true and as false.
9. WHEN a Rule condition is not observed both ways, THE Verifier SHALL attempt targeted generation and, if still unobserved, SHALL report the Rule as uncovered.
10. WHEN a Mismatch is found, THE Verifier SHALL link it to a `rule_id` and cell and classify it as a Mismatch_Class.
11. WHEN a Mismatch matches a Finding, THE Verifier SHALL classify it as "original workbook inconsistency" and link the `finding_id`.
12. WHILE Intended_Mode is active, WHEN a Mismatch is explained by a Decision, THE Verifier SHALL classify it as "expected by decision D-xxx".
13. WHILE Faithful_Mode is active, THE Verifier SHALL treat any Mismatch as a failure.
14. WHILE Intended_Mode is active, THE Verifier SHALL treat only Mismatches not explained by a Decision as failures.
15. WHEN a verification run contains at least 300 Cases on a clean Sample, THE Verifier SHALL report zero Mismatches in Faithful_Mode.

### Requirement 9: Mutation Self-Check (P1)

**User Story:** As a skeptical reviewer, I want evidence that the verifier would catch real mistakes, so that a passing report means something.

#### Acceptance Criteria

1. WHEN mutation check runs, THE Mutation_Checker SHALL generate Mutants that flip `>=` and `>`, change a constant by ±1, swap rounding mode between half-up and half-even, and drop an IF branch.
2. WHEN a Mutant is generated, THE Mutation_Checker SHALL run the Verifier against the Referee for that Mutant.
3. THE Mutation_Checker SHALL report the score as killed Mutants over total Mutants.
4. WHEN a Mutant survives, THE Mutation_Checker SHALL report the Mutant and the reason it survived.

### Requirement 10: Proof Report

**User Story:** As a business owner, I want one report I can read and keep, so that I can show the migration was checked.

#### Acceptance Criteria

1. WHEN verification completes, THE Core_Engine SHALL generate a Proof_Report in HTML and JSON.
2. THE Proof_Report JSON SHALL conform to a versioned JSON schema stored in the repository.
3. THE Proof_Report SHALL include inputs tested, pass or fail result, minimal counterexamples, boundary cases with exact hits, rule coverage, mutation score, Sanity_Check result, Findings, Decisions, seed, and versions of LibreOffice, Python and Ghost.
4. IF a check was not performed, THEN THE Proof_Report SHALL state "not checked" for that item.
5. THE Proof_Report SHALL contain only values produced by the engine and SHALL NOT contain invented data.
6. WHEN `decisions.yaml` changes, THE Core_Engine SHALL regenerate the Proof_Report on request.

### Requirement 11: Command-Line Interface

**User Story:** As a developer, I want to run the whole flow from a terminal, so that I can script it and demo it.

#### Acceptance Criteria

1. THE CLI SHALL provide commands for autopsy, rules generation, conversion, verification, mutation check, report generation, decision recording and routing.
2. WHEN `--trust-macros` is passed with a local file, THE CLI SHALL allow `run_macros` for that file.
3. WHEN the demo script runs on Samples (a) and (b), THE CLI SHALL produce a Migration_Spec and a Proof_Report for each Sample.
4. IF a CLI command fails, THEN THE CLI SHALL exit with a non-zero status and a message naming the cause.

### Requirement 12: MCP Server and Kiro Power

**User Story:** As a Kiro user, I want Ghost available as a Power, so that my AI agent can analyse, implement and verify migrations with the same proof.

#### Acceptance Criteria

1. THE Kiro_Power SHALL use the Agent Plugins format with `plugin.json`, `skills/` and `mcp.json`, and SHALL be installable from a GitHub URL.
2. THE Kiro_Power SHALL declare the keywords excel, xlsx, xlsm, vba, macro, spreadsheet and workbook migration.
3. THE MCP_Server SHALL expose the tools analyze_workbook, list_rules, get_dependencies, find_inconsistencies, extract_vba, evaluate_original, boundary_cases, check_against_excel_cache, verify_implementation, mutation_check, record_decision, generate_proof_report and recommend_route.
4. THE MCP_Server SHALL implement extract_vba as read-only.
5. WHEN `evaluate_original` is called with inputs and outputs, THE MCP_Server SHALL return Referee values for those outputs.
6. WHEN `verify_implementation` is called with a module, mapping and cases, THE MCP_Server SHALL run the Verifier on the supplied module.
7. THE Kiro_Power SHALL include skills for autopsy of a workbook, writing a rules spec, implementing from the rules spec, verifying a migration, recording a human decision on a Mismatch, and guardrails.
8. WHEN the write-rules skill runs, THE Kiro_Power SHALL create `.kiro/specs/<migration>/` with rules, traceability and findings.
9. THE Kiro_Power guardrails SHALL require: no behaviour change without a recorded Decision; Decimal for money; Excel rounding per the Excel_Semantics_Table; no macro execution from untrusted files; no invented data in reports.
10. THE Kiro_Power SHALL operate alongside the official AWS Transform power without conflicting tool names.
11. IF an MCP tool receives invalid arguments, THEN THE MCP_Server SHALL return a structured error naming the invalid argument.

### Requirement 13: Web Application

**User Story:** As a small-business owner, I want to upload my spreadsheet in a browser and get a proof report, so that I do not need to install anything.

#### Acceptance Criteria

1. THE Web_App SHALL provide a single-page flow: upload or "Try a sample", autopsy summary with findings and rules, confirm inputs and outputs, answer findings, run verification with live progress, and view the Proof_Report.
2. WHEN a user answers a Finding, THE Web_App SHALL record a Decision.
3. WHEN verification completes, THE Web_App SHALL offer download of the Proof_Report as HTML and JSON and of the generated module.
4. WHEN a job is started, THE Job_Runner SHALL run it in the background and report progress through polling or server-sent events.
5. THE Job_Runner SHALL run one Referee per job and SHALL enforce a configurable concurrency limit.
6. IF the concurrency limit is reached, THEN THE Web_App SHALL queue the job and show its queue position.
7. THE Web_App SHALL meet WCAG 2.1 AA colour contrast, support keyboard navigation and render usably at 360 px width.
8. THE Web_App SHALL offer a haunted-lab/graveyard theme in dark and light modes.
9. THE Web_App SHALL require no login.
10. THE Web_App SHALL store uploads in a per-session Session_Folder and SHALL delete the Session_Folder at session end or timeout.
11. THE Web_App SHALL display a privacy note before upload.
12. THE Web_App SHALL NOT run macros from uploaded files.
13. THE Web_App SHALL perform no LLM calls and SHALL need no API keys.
14. IF an upload fails validation, THEN THE Web_App SHALL display the error from the Ingestor.

### Requirement 14: Deployment

**User Story:** As a judge, I want to open a public URL and try the demo, so that I can evaluate the project without setup.

#### Acceptance Criteria

1. THE Ghost repository SHALL provide a Dockerfile based on Debian slim with `libreoffice-calc-nogui`, `libreoffice-script-provider-python` and the application installed.
2. THE container SHALL run as a non-root user.
3. THE container SHALL run on any Docker host with at least 1 GB RAM.
4. THE Web_App SHALL be deployed to a public URL on a Docker host (Amazon ECS Express Mode, Fly.io or Render).
5. WHEN the container starts, THE Web_App SHALL expose a health endpoint that reports Referee availability.
6. THE repository SHALL contain no secrets.

### Requirement 15: Excel and VBA Semantics

**User Story:** As an accountant, I want the new code to round and calculate exactly like Excel, so that totals match to the cent.

#### Acceptance Criteria

1. THE Converter SHALL implement worksheet ROUND as half away from zero: ROUND(2.5,0)=3, ROUND(-2.5,0)=-3, ROUND(0.125,2)=0.13.
2. THE Converter SHALL evaluate ROUND using 15 significant digits so that ROUND(2.675,2)=2.68.
3. WHERE VBA conversion is enabled, THE Converter SHALL implement VBA Round as half-even: Round(2.5)=2, Round(3.5)=4, Round(0.125,2)=0.12.
4. WHERE VBA conversion is enabled, THE Converter SHALL implement VBA Int as floor and Fix as truncation: Int(-2.5)=-3 and Fix(-2.5)=-2.
5. THE Converter SHALL implement worksheet MOD with the sign of the divisor: MOD(-7,3)=2.
6. WHERE VBA conversion is enabled, THE Converter SHALL implement VBA Mod with the sign of the dividend: -7 Mod 3 = -1.
7. THE Converter SHALL treat an empty cell as 0 in arithmetic and as "" in text operations.
8. THE Converter SHALL treat TRUE as 1 and FALSE as 0 in arithmetic.
9. THE Converter SHALL compare text case-insensitively.
10. THE Verifier SHALL treat floating-point differences within the tolerance of requirement 8.5 as equal.
11. WHERE date support is enabled (P2), THE Converter SHALL implement the 1900 leap-year quirk so that serial 60 is 29 February 1900.
12. THE Core_Engine golden tests SHALL check each row of the Excel_Semantics_Table against both the Referee and the generated Python code.

### Requirement 16: Migration Routing (P1)

**User Story:** As a user with a bigger VBA estate, I want Ghost to tell me when AWS Transform is the better tool, so that I choose the right migration path.

#### Acceptance Criteria

1. WHEN `recommend_route` runs, THE Router SHALL return a Route computed deterministically from Autopsy metrics and Routing_Thresholds.
2. WHEN a Workbook is formula-heavy or has VBA below the configured line threshold (default about 2,000 lines) and has calculator shape, THE Router SHALL return "Ghost converts".
3. WHEN VBA exceeds the line threshold, or UserForm or Windows API Declare counts exceed their thresholds, or a batch contains at least 10 Workbooks, THE Router SHALL return "AWS Transform custom".
4. WHEN a Workbook mixes convertible formulas with large VBA, THE Router SHALL return "Split".
5. THE Router SHALL read thresholds from `routing-thresholds.md` so that they are configurable.
6. WHEN the Route involves AWS Transform custom, THE Router SHALL output an exact `atx custom def exec ...` command as a dry run and SHALL NOT execute it.
7. WHERE AWS credentials exist and the official AWS Transform Kiro power is installed, THE Kiro_Power SHALL hand off to that power.
8. WHEN a Route is produced, THE Core_Engine SHALL write a plain-English explanation into the Migration_Spec `design.md`.
9. WHEN a migration is performed by either path, THE Verifier SHALL be available to verify the result.

### Requirement 17: VBA Conversion (P2, STRETCH)

**User Story:** As a user with a simple macro, I want basic VBA converted and verified, so that my button-driven logic is preserved.

#### Acceptance Criteria

1. WHEN a Workbook contains a VBA function called from a cell (for example `=DeliveryFee(B2,B4)`), THE Core_Engine SHALL map the function to its call-site cells.
2. WHEN a VBA sub reads or writes `ws.Range("B11").Value`, THE Core_Engine SHALL map the variable to that cell.
3. WHEN a simple VBA function or sub is within the supported subset, THE Converter SHALL generate pure Python for it.
4. IF VBA code is outside the supported subset, THEN THE Converter SHALL list it as "not converted".
5. WHEN a VBA sub is verified, THE Referee SHALL run it only for a Trusted_Source with `run_macros` true.

### Requirement 18: TypeScript Export (P2, STRETCH)

**User Story:** As a web developer, I want the generated logic as TypeScript, so that I can use it in a frontend.

#### Acceptance Criteria

1. WHERE TypeScript export is enabled, THE Converter SHALL generate a TypeScript module with the same compute semantics as the Python module.
2. WHERE TypeScript export is enabled, THE Verifier SHALL verify the TypeScript module against the Referee.

### Requirement 19: Sample Workbooks

**User Story:** As a judge, I want ready-made sample workbooks, so that I can try Ghost without my own file.

#### Acceptance Criteria

1. THE repository SHALL contain committed scripts that generate every Sample and SHALL label each Sample "generated".
2. THE Sample (a) SHALL implement a discount calculator with inputs quantity, unit price and delivery distance; a 10% bulk discount at 50 or more; a delivery fee of 5.00 up to 10 km plus 0.40 per km beyond, free at 50 or more; 20% VAT; ROUND; and a Tests sheet of 200 fixed rows.
3. THE Sample (b) SHALL be the haunted variant where free delivery uses `>50` while the discount uses `>=50`.
4. THE Sample (c) SHALL implement a multi-scenario tax-style model with 4 inputs and 10 scenarios, selecting the best using MAX with INDEX/MATCH, using only the P0 subset.
5. WHERE VBA conversion is enabled, THE Sample (d) SHALL be an `.xlsm` pair with a VBA function `=DeliveryFee(B2,B4)` and a button macro AwardPoints (points equal whole tens of total, Gold from 500), plus a haunted twin where the macro rounds total/10.
6. THE Sample (e) SHALL be a "Traps" Workbook exercising every row of the Excel_Semantics_Table.
7. WHEN Autopsy runs on Sample (b), THE Autopsy SHALL create finding F-001 for the conflicting bulk thresholds.
8. WHEN Intended_Mode runs on Sample (b) with Decision D-001 "bulk means 50 or more", THE Verifier SHALL show an expected difference at exactly 50 units.

### Requirement 20: Testing Strategy

**User Story:** As the sole developer, I want a test suite that proves the tool itself is correct, so that I can trust my own demo.

#### Acceptance Criteria

1. THE repository SHALL contain unit tests for ingestion, classification, threshold extraction, rules, transpiler, comparison and report.
2. THE repository SHALL contain referee fidelity tests covering hand-calculated values, the VBA Round probe, macros-off default with `run_macro` refused, and the Sanity_Check against `tests/fixtures/excel-saved/`.
3. IF `tests/fixtures/excel-saved/` is missing, THEN the Excel-saved fidelity test SHALL be skipped with a message naming the missing directory and SHALL NOT fake results.
4. THE repository SHALL contain golden semantics tests that run against both the Referee and generated code.
5. THE repository SHALL contain product property-based tests: clean Samples show zero Mismatches over at least 300 Cases; haunted Sample (b) shows minimal counterexample quantity=50; haunted `.xlsm` shows minimal counterexample total 6.00 (1 point versus 0); Boundary_Probing lands exactly on 500.00 for Gold.
6. THE repository SHALL contain engine property-based tests: tolerance comparison is symmetric; shrinking preserves failure; `rule_id` values are stable; EARS text is deterministic; threshold extraction finds every literal comparison; formula fuzzing from a grammar of the supported subset compares Referee and transpiled code and shrinks failures to the smallest formula.
7. THE repository SHALL contain mutation tests: a Gold `>` versus `>=` Mutant is caught by Boundary_Probing; a half-even rounding Mutant is caught at 235 × 0.03.
8. THE repository SHALL contain end-to-end tests: a CLI demo script and API tests, with a Playwright smoke test (P1).
9. WHEN 500 Cases are verified, THE Verifier SHALL complete within 60 seconds.
10. THE repository SHALL provide a GitHub Actions workflow on Ubuntu that installs `libreoffice-calc-nogui` and `libreoffice-script-provider-python` and runs the test suite.

### Requirement 21: Repository Kiro Setup and Documentation

**User Story:** As a hackathon judge, I want to see deliberate use of Kiro in the repository, so that I can assess how the project was built.

#### Acceptance Criteria

1. THE repository SHALL contain steering files `product.md`, `tech.md`, `structure.md`, `ghost-guardrails.md`, `excel-semantics.md` and `routing-thresholds.md` under `.kiro/steering/`.
2. THE repository SHALL contain hooks that re-run verification when generated logic files or `mapping.yaml` are saved, run autopsy when a Workbook is added to `/graveyard`, run golden semantics tests when `converter/` changes, and regenerate the Proof_Report when `decisions.yaml` changes.
3. WHERE custom agents are provided, THE repository SHALL define Coroner, Medium, Skeptic and Clerk agents.
4. THE repository SHALL keep `docs/KIRO_USAGE.md` as a running log of Kiro usage.
5. THE repository SHALL commit `.kiro/` and SHALL NOT list `.kiro/` in `.gitignore`.
6. THE repository SHALL include a MIT licence.
7. THE README SHALL cover setup (LibreOffice, venv), local running, Docker, using the Power in Kiro, creating real-Excel fixtures with Excel for the web, safety, and a note that `reference/testbench/` was a feasibility spike before this spec.

### Requirement 22: Out of Scope

**User Story:** As the sole developer, I want explicit exclusions, so that scope stays achievable in ten days.

#### Acceptance Criteria

1. THE Ghost SHALL NOT automate real Excel.
2. THE Ghost SHALL NOT run macros from uploaded files.
3. THE Ghost SHALL NOT include payments, a mobile app, full UserForm recreation or LLM calls from the Web_App.
