---
inclusion: always
---

# Technology

## Stack

- Python 3.11+ for everything (package `ghost`).
- Workbook reading: openpyxl (formulas, plus `data_only=True` for Excel-saved values). VBA extraction: oletools/olevba, static only. All XML parsing through defusedxml.
- Models and validation: dataclasses and pydantic. YAML via pyyaml. Report schema checked with jsonschema.
- Verification: Hypothesis with an explicit seed. Tests: pytest.
- Web: FastAPI, uvicorn, Jinja2, HTMX. No login, no LLM calls, no API keys.
- MCP server: the `mcp` Python SDK over stdio.
- Referee: headless LibreOffice (`soffice --headless`) running a Python script from the user profile (`user/Scripts/python/`), connecting back to the engine over 127.0.0.1 with line-delimited JSON.
- Deployment: Docker (Debian slim) on a public host with at least 1 GB RAM. Packages `libreoffice-calc-nogui` and `libreoffice-script-provider-python` are required.

## Conventions

- Money and spreadsheet arithmetic use `decimal.Decimal`. Convert floats with `Decimal(repr(x))`, never `Decimal(x)`.
- Deterministic output: identical input yields identical generated code, rule text and `rule_id` values. No timestamps or random values in generated artifacts.
- `rule_id = "R-" + sha1(sheet|cell|normalised_formula)[:8]`.
- Unsupported constructs are listed as "not converted" with cell and reason. Never guess.
- Verifier tolerance: absolute 1e-6 for numbers, exact strings, Excel errors compared by error type.
- One long-lived Referee per job. The uploaded file is copied and never modified.
- Macros are off (`NEVER_EXECUTE`) by default and only enabled for a trusted source (bundled sample, or local CLI with `--trust-macros`). Never for web uploads.
- Limits: 5 MB file size, 20,000 formulas, 200,000 cells (`MAX_CELLS`, counted while streaming the sheet XML in the defusedxml pre-scan, before openpyxl loads anything), a processing timeout.
- Environment variables: `GHOST_SOFFICE` (path to soffice), `GHOST_MAX_JOBS` (default 2).
- Tests co-located under `tests/`. Property tests use Hypothesis and cite the property number and requirements they validate.
- Everything in a proof report comes from engine output. Missing checks are written as "not checked".
