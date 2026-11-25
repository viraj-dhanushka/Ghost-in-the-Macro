# Live fixes summary, 2026-11-24

Spec: `.kiro/specs/live-fixes-2026-11-24/`. Details per finding are in the "Live-test resolution" table at the end of `docs/LIVE_TEST_REPORT_2026-11-24.md` and in `docs/KIRO_USAGE.md`.

**Nothing is committed or deployed.** The live site still shows the original findings.

## What changed per finding

- **L-02:** Excel errors in a report are written as text (`"#VALUE!"`), so the report no longer crashes. A failure while writing a report now shows as "The report could not be written (…)" (CLI exit code 4, MCP `report_not_written`). "Verification found mismatches." appears only for real mismatches.
- **L-03:** `INDEX(range,0)` now follows the measured Referee behaviour (implicit intersection on the formula's row or column). A negative index gives `#VALUE!`. An `INDEX` passed through `IF`, `IFERROR` or `CHOOSE` inside an aggregate is listed as "not converted". Excel 365 spills instead; not checked against Excel.
- **L-04:** Exact hits for `IF` thresholds are confirmed from the values the module compares, not from the operator. A flip is retried with other numeric inputs set to 1, 2, 4, 5 or 10. The `flip_comparison` mutant on the tier sample is now killed.
- **L-05:** Not-converted and not-verifiable cells are no longer offered or pre-checked as outputs. Choosing one explicitly is rejected (web 422, MCP `invalid_argument`, CLI `CliError`) with the cell and the reason. The report lists them under "Not converted".
- **L-06:** The boundary table shows a readable change-point bracket (`49 → 50`), the real threshold constant ("calculated" or "not checked" otherwise), and no raw JSON.
- **L-07:** One domain definition (`ghost/verifier/domain.py`) for targeted cases, flip probing, mutation cases and strategies. Cases below the declared minimum (such as -1) are dropped. The "Tested domains" table shows the same ranges.
- **L-08:** New `ghost/verifier/selection.py` searches for inputs where the row picked by `MAX`, `MIN` or `MATCH` changes. The mutation section explains remaining survivors without claiming equivalence. No mutant was removed and the score formula is unchanged.

## Tests added or updated

New files:
- `tests/test_live_findings.py`
- `tests/test_live_preservation.py`
- `tests/test_property_report_excel_errors.py`
- `tests/test_report_write_failure.py`
- `tests/test_property_index_zero.py`
- `tests/test_index_zero_measurement.py`
- `tests/test_index_zero_contexts.py`
- `tests/golden/test_index_zero_golden.py`
- `tests/test_property_exact_hits.py`
- `tests/test_flip_integer_exact.py`
- `tests/test_flip_exact_followups.py`
- `tests/test_not_converted_rejection.py`
- `tests/test_property_not_converted_outputs.py`
- `tests/test_report_boundary_table.py`
- `tests/test_property_targeted_domain.py`
- `tests/unit/test_effective_domain.py`
- `tests/test_selection_search.py`
- `tests/test_survivor_explanation.py`

Updated files:
- `tests/test_demo_invariants.py`
- `tests/test_report_details.py`
- `tests/test_review_semantics.py`
- `tests/test_web_samples.py`
- `tests/unit/test_mapping_text_outputs.py`
- `tests/unit/test_mcp_server.py`
- `tests/unit/test_report_html.py`
- `tests/unit/test_report_model.py`

Exploration tests that failed before the fix were marked as expected failures. The markers were removed once the fixes landed, and the assertions were left unchanged.

### Edits that changed an assertion

- `tests/unit/test_mapping_text_outputs.py`: the TEXT case was changed with the owner's approval. (Reason as agreed with the owner; see the entry in `docs/KIRO_USAGE.md`.)
- L-02 CLI/MCP test (`tests/test_live_findings.py`): accepts `#REF!` or `#VALUE!`, because the negative-index fix in L-03 changed which error the Referee case produces.
- `tests/test_report_details.py`: the `first_changed` assertion was replaced by the readable bracket (L-06 no longer shows the raw change point as the threshold).
- Task 5.3 test: docstring and helper updated for the owner's domain decision (L-07).
- `tests/test_review_semantics.py`: `index_out_of_range` is now version-aware, because `INDEX` past the end gives `#REF!` on LibreOffice 26.8.3 and `#VALUE!` on 7.4.7.2.

## Owner decisions

- **L-07 (task 5.4):** widen the domain to include the workbook's own sample value, then clamp. The scenarios sample value 60,000 is kept (domain 0..60,000), and -1 is dropped where the minimum is 0.
- **L-04 and L-08:** the changed haunted case counts were accepted (haunted 300 + 11 targeted, 200 distinct; discount 300 + 8, 197 distinct). Mutation scores did not change.
- **L-08:** the search size was agreed with the owner at task 5.7.
- **L-02:** the CLI/MCP test accepts `#REF!` or `#VALUE!`; the open question below is still unanswered.

## Deferred or open

- (a) An exit 1 with a `ghost: error:` line that is not about the report (for example "Referee unavailable") also shows "The report could not be written". Left unchanged; the other option is "Verification stopped: <message>". Needs an owner choice.
- (b) `INDEX` past the end of the range: `#REF!` on 26.8.3, `#VALUE!` on 7.4.7.2. Ghost gives `#REF!`, so such a workbook shows a mismatch on 7.4.7.2. The two versions disagree, so there is no single value to match.
- (c) `SUM(IF(TRUE,N5))` with text in N5: the Referee gives 0, Ghost gives `#VALUE!`. Predates these fixes and is outside L-03.
- (d) Decimal thresholds finer than the 0.001 probe step are not checked. The report says so.
- (e) A fully negative small-value retry shows "not checked".
- (f) For haunted, the exact hit lists other inputs (`delivery_distance_km` 12, `unit_price` 19.95) that the condition does not depend on.
- (g) Three scenarios survivors are killable in principle, but the search found no separating input.
- Excel and the live site: not checked.

## Final numbers

- Full suite: 932 passed, 2 skipped, 0 failed. Golden: 67 passed.
- Demo storyline unchanged: discount Faithful pass. Haunted raises F-001, Faithful has 0 mismatches, and Intended with D-001 passes with one expected difference at quantity=50 (Referee 6.0, new code 0).
- Mutation: haunted 33/35, discount 31/33. Scenarios 55/132 live, 70/132 now. Best reachable is 73/132.
- Docker on LibreOffice 7.4.7.2 matches the local run (haunted flow and the L-02 to L-05 repros, scenarios 70/132). The HTML boundary table was not inspected in the container.

## Changed files

Modified: `.kiro/steering/excel-semantics.md`, `README.md`, `docs/KIRO_USAGE.md`, `docs/LIVE_TEST_REPORT_2026-11-24.md`, `ghost/autopsy/classify.py`, `ghost/cli.py`, `ghost/converter/emit_python.py`, `ghost/converter/subset.py`, `ghost/models.py`, `ghost/mutation/run.py`, `ghost/report/{domains,html,model}.py`, `ghost/report/schema/proof-report-1.json`, `ghost/verifier/{coverage,flip,run}.py`, `mcp_server/server.py`, `web/flow.py`, `web/jobs.py`, and the updated tests listed above.

New: `ghost/verifier/domain.py`, `ghost/verifier/selection.py`, `.kiro/specs/live-fixes-2026-11-24/`, the new tests listed above, `tests/index_zero_probe.py`, `tests/index_zero_contexts_probe.py`, and the docs `KIRO_FEATURE_PROMPT_2026-11-25.md`, `KIRO_FIX_PROMPT_LIVE_2026-11-24.md`.

## Next steps for the owner

1. Review and commit.
2. Dry run: `scripts/deploy_ecs_express.sh --dry-run`.
3. Deploy: `scripts/deploy_ecs_express.sh`, with `GHOST_SESSION_SECRET` not set.
4. Re-run the live test. No separate live-test prompt is in `docs/`; the earlier run is recorded in `docs/LIVE_TEST_REPORT_2026-11-24.md`, so use its checks as the list.
