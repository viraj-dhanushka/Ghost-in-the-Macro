# Design: large-workbook-lane
## Where things go
| Piece | File | Notes |
|---|---|---|
| Triage | `ghost/ingest/triage.py` (new) | `scan_sizes(path, limits=None, clock=None) -> SizeProfile`; its own streaming loop over the sheet XML with defusedxml, counting `c` and `f` end events and clearing elements; never calls openpyxl. VBA facts from `ghost.ingest.vba.extract_vba` (static) and the `ghost.autopsy.metrics` regexes. |
| Thresholds | `ghost/router/thresholds.py` | Optional keys `max_file_bytes`, `max_cells`, `max_formulas`, `transform_definition`. Effective size limit is `min(threshold, ingest limit)`. |
| Route | `ghost/router/route.py`, `ghost/models.py` | `recommend_route(metrics, batch, thresholds, sizes=None)`; the `sizes=None` path is the old code. New `RouteName` "Over Ghost's limits". `Route` gains optional `parts` (the per-part sentences) and `sizes` (a dict) which are `None` or `[]` for the old path. |
| Command | `ghost/router/explain.py` | Rewritten builder (Part B). |
| Front ends | `ghost/cli.py` (`route`, `handoff`, `receipt`), `mcp_server/server.py` (`recommend_route`, `prepare_handoff`), `web/flow.py` and `web/app.py` (route card, message) | Front ends call `ghost.*` only. |
| Kit | `ghost/handoff.py` (new) | Pure text builders plus one `write_kit`. |
| Brief | `ghost/repair_brief.py` (new), `scripts/repair_brief.py` | The brief logic moves into `ghost/`; the script imports it and keeps its own file reading, so Feature 5 tests still pass. |
| Challenge | `ghost/challenge.py` | Writes `repair-brief.json` into `--out`. No `--trust-macros`. |
| Receipt | `ghost/receipt.py` (new) | Subprocess runner and receipt writer. |
| Docker | `.dockerignore` | `!.kiro/steering/routing-thresholds.md` needs `.kiro/*` and `.kiro/steering/*` forms, see below. |
## Decisions
- **Triage reads, it does not enforce.** `load_workbook` and its limits are unchanged. Triage runs before it in `ghost route` and `recommend_route`, and in the web upload path only after the ingest limit error.
- **No guessed numbers.** The formula count is `<f>` elements, exact when counting finishes. A shared formula's dependent cells carry `<f t="shared" si="0"/>`, so they are counted, like openpyxl counts them (checked by a test against openpyxl on a generated file).
- **Over-limit without big VBA gets its own route name,** not "Ghost converts" (which would be untrue) and not "AWS Transform custom" (which would suggest AWS handles cells).
- **D2 (foreign module on a VBA-fed output):** decided, not asked. `run_verification` already refuses any output that is not converted or not verifiable (L-05), for generated and foreign code alike. That stays. Rationale: the macro spike (below) shows the Referee cannot calculate a VBA-called cell even with macros trusted, so there is no value to referee against.
- **Macro spike result (observed 2026-11-26, LibreOffice 26.8):** with `run_macros=True`, a trusted source, `MacroSecurityLevel` 0 and `ALWAYS_EXECUTE_NO_WARN`, the Referee lists `DeliveryFee` and `AwardPoints` (the VBA project loaded) but `Calculator!B13` (`=DeliveryFee(B2,B4)`) still evaluates to `#MACRO?`, as it does with macros off. I did not find out why. So VBA-fed outputs are "not verifiable by the Referee".
- **Receipt runner is a subprocess** of `ghost challenge` (a separate process), so that a candidate that calls `os._exit` cannot take down the runner and a timeout can kill it. It reads `proof-report.json` and the exit code only.
- **`.dockerignore`:** `.kiro` is excluded as a directory today. Docker cannot re-include a file under an excluded directory, so the rule becomes `.kiro/*`, `!.kiro/steering`, `.kiro/steering/*`, `!.kiro/steering/routing-thresholds.md`. A test builds the file list with the same matching rules the Docker documentation describes and checks that only that one file under `.kiro` is let in. The Docker build itself is not run (not checked).
## Correctness properties
1. Triage never loads the workbook, and the route for a workbook within the limits is identical to today's.
2. For any size profile and thresholds, exactly one route is returned, and every limit exceeded appears in the reasons.
3. The kit is byte-identical across two runs, contains no absolute path, and every VBA module appears exactly once.
4. The printed command always carries `-g`, and never appears without the "not run" label.
5. A thresholds file with only the four original keys loads with the defaults.
6. The receipt records a pass only when all five conditions hold (a Hypothesis test over exit codes, report states, case counts and seeds).
## Tests
`tests/test_triage.py`, `tests/test_route_sizes.py`, `tests/test_atx_command.py`, `tests/test_handoff.py`, `tests/test_receipt.py`, `tests/test_docker_ignore.py`, `tests/test_web_large_workbook.py`, `tests/test_macro_spike.py` (LibreOffice), Properties 1 to 6. No test creates AWS output; the stand-in module in the tests is labelled as one.
