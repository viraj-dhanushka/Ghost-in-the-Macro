---
inclusion: always
---

# Repository structure

```
ghost/
  ingest/        workbook.py, vba.py, limits.py
  autopsy/       classify.py, thresholds.py, findings.py, metrics.py
  rules/         ears.py, ids.py, spec_writer.py
  referee/       client.py, script/ghost_referee.py, locate.py, profile.py, sanity.py
  converter/     parser.py, ast.py, emit_python.py, semantics.py, subset.py
  runtime/       excel.py   (vendored into generated module folders)
  verifier/      strategies.py, compare.py, boundary.py, coverage.py, classify.py, run.py
  mutation/      mutants.py, run.py
  report/        model.py, html.py, schema/proof-report-1.json
  decisions/     store.py
  router/        route.py, thresholds.py
  models.py
  cli.py
mcp_server/      server.py
web/             app.py, jobs.py, templates/, static/
samples/         make_discount.py, make_haunted.py, make_scenarios.py, make_xlsm.py, make_traps.py
graveyard/       workbooks to analyse (hook runs autopsy on new files)
plugin/          plugin.json, mcp.json, skills/
tests/           unit, property, golden, e2e; fixtures/excel-saved/ for real-Excel files
docs/            KIRO_USAGE.md
scripts/         demo.sh
.kiro/           steering/, hooks/, specs/, agents/  (committed, never gitignored)
Dockerfile
```

## Migration spec layout

Each migration lives in `.kiro/specs/<migration>/`:
`rules.md`, `traceability.yaml`, `findings.yaml`, `decisions.yaml`, `design.md`, `mapping.yaml`.

## Implementation contract

A migration produces `logic.py` exposing `compute(inputs: dict) -> dict` and `mapping.yaml` mapping input and output names to cell references (`Sheet!A1`). The verifier uses this contract for both the transpiler output and an AI-written module.

## Rules of placement

- Front ends (CLI, MCP server, web) contain no business logic. They call `ghost.*`.
- The Referee script file runs inside LibreOffice's Python and must not import from `ghost`.
- Samples are produced by committed scripts and labelled "generated". Do not commit hand-edited workbooks as samples.
