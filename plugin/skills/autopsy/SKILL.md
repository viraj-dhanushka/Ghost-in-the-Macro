---
name: autopsy
description: Examine an Excel workbook (.xlsx/.xlsm) before migration. Reports metrics, proposed inputs and outputs, thresholds, findings, VBA and constructs that cannot be converted. Use first when the user asks to migrate or understand a spreadsheet.
---

# Autopsy a workbook

Follow the `guardrails` skill throughout. Every tool here is read-only; none modifies the workbook.

## Steps

1. Call `analyze_workbook` with the workbook path. Record the metrics, proposed inputs and outputs, thresholds, findings and "not converted" constructs exactly as returned.
2. Call `find_inconsistencies`. It reports places where the same value is compared with the same constant using different operators (for example `>50` in one cell and `>=50` in another). Each one is a Finding.
3. If the file is `.xlsm`, call `extract_vba`. It reads VBA statically and runs nothing. Never run macros.
4. Call `boundary_cases` to probe each threshold with the Referee. It shows where outputs change and which side owns the threshold.
5. Call `check_against_excel_cache`. If the workbook has no Excel-saved values, say "not cross-checked against Excel". Do not say "pass".
6. For any cell the user asks about, call `get_dependencies` with `Sheet!A1`.

## Report to the user

- Counts and proposed inputs/outputs (the user confirms or overrides them; pass overrides as `inputs` and `outputs` in later calls).
- Each Finding with its ID, cells and the conflicting behaviour.
- Constructs "not converted" and volatile or external constructs "not verifiable as-is", each with cell and reason.
- Anything you did not check, labelled "not checked".

Next step: `write-rules-spec`.
