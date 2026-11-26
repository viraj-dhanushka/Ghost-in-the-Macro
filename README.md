# Ghost-in-the-Macro

Ghost takes the business logic trapped in one Excel workbook (formulas first, VBA read statically) and produces three things:

1. Plain-English business rules (EARS style), each traced to a source cell.
2. A pure-function Python module (`logic.py` with `compute(inputs) -> outputs`) and a web UI around it.
3. A proof report. The new module is run against the original workbook recalculated by headless LibreOffice (the "Referee"), using property-based tests with a fixed seed.

When the new code and the workbook disagree, the workbook may be the one that is wrong. A human records a Decision (`decisions.yaml`) and Ghost checks the migration in two modes: Faithful (reproduce the workbook, quirks included) and Intended (apply the Decisions).

## Live demo

https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws

The hosted copy will be taken down after judging.

The web app has no login, makes no LLM calls and needs no API keys. Pick a bundled sample, review the autopsy, confirm the inputs, and run the verification.

## Quick start

You need Python 3.11 or newer and LibreOffice Calc. LibreOffice is the Referee; without it the verifier cannot run.

### 1. Install LibreOffice

- **macOS:** install LibreOffice and put `LibreOffice.app` in `/Applications` or `~/Applications`. Ghost finds `Contents/MacOS/soffice` in either place. If it lives elsewhere, set `GHOST_SOFFICE=/path/to/soffice`.
- **Debian or Ubuntu:**
  ```
  sudo apt-get update
  sudo apt-get install -y libreoffice-calc-nogui libreoffice-script-provider-python
  ```
  Ghost looks in `/usr/bin/soffice`, `/usr/lib/libreoffice/program/soffice` and `/opt/libreoffice*/program/soffice`. Otherwise set `GHOST_SOFFICE`.

If the Referee cannot be found, the error names every path that was searched.

### 2. Create the virtual environment

From the repository root:

```
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m ghost.cli --help
```

The last command should list the subcommands `autopsy`, `rules`, `convert`, `verify`, `report`, `decide`, `mutate`, `route` and `demo`.

### 3. Run the CLI demo

```
scripts/demo.sh            # writes to demo-out/
scripts/demo.sh /tmp/out   # or pick a folder
```

This generates the sample workbooks with the committed scripts in `samples/`, then runs the whole flow on sample (a), the discount calculator, and sample (b), the "haunted" discount calculator. It prints, for the haunted sample:

- Finding F-001: free delivery compares the quantity with `>` 50 while the discount uses `>=` 50.
- Faithful mode passes (300 generated + 11 targeted cases, 200 distinct, 0 mismatches).
- After Decision D-001 ("bulk means 50 or more") Intended mode passes on the same cases, with one difference expected by the Decision and the minimal example at quantity = 50.

Proof reports are written to `demo-out/<sample>/reports/<mode>/proof-report.html`. Open them in a browser.

Each step is also available on its own, for example:

```
.venv/bin/python -m ghost.cli autopsy path/to/workbook.xlsx
.venv/bin/python -m ghost.cli rules   path/to/workbook.xlsx --migration .kiro/specs/my-migration
.venv/bin/python -m ghost.cli convert path/to/workbook.xlsx --migration .kiro/specs/my-migration
.venv/bin/python -m ghost.cli verify  .kiro/specs/my-migration --mode both
.venv/bin/python -m ghost.cli decide  .kiro/specs/my-migration --finding F-001 \
    --behaviour "bulk means 50 or more" --reason "..." --author you \
    --set-operator Calculator!B9 '>' '>='
```

Run `.venv/bin/python -m ghost.cli <command> --help` for every option. Macros are never run unless you pass `--trust-macros` to `verify` for a local file you trust.

### 4. Run the tests

```
.venv/bin/python -m pytest -q
```

Most tests need LibreOffice (they start the Referee). Tests that need something missing skip with a message.

```
.venv/bin/python -m pytest -q -m golden        # golden semantics tests (tests/golden/), one per in-scope row of the Excel semantics table
.venv/bin/python -m pytest -q -m "not slow"    # everything except the 500-case performance test (about a minute)
.venv/bin/python -m pytest -q tests/test_excel_saved_fixtures.py   # skips with a message while tests/fixtures/excel-saved/ is empty
```

The formula-fuzzing property test (Hypothesis, fixed seed) and the CLI end-to-end test (runs `scripts/demo.sh` into a temp folder) are part of the normal run.

### Kiro hooks

The four hooks in `.kiro/hooks/` (autopsy on a new file in `graveyard/`, golden tests on a converter save, re-verify on a `logic.py` save, regenerate the report on a decision) run `scripts/ghost-py scripts/ghost_hook.py <name>`. `scripts/ghost-py` runs `.venv/bin/python` from the repository root whatever the caller's working directory or `PATH`, so create the venv first (step 2). Run one by hand to check it, for example `scripts/ghost-py scripts/ghost_hook.py golden`.

## Run the web app locally

```
.venv/bin/python -m uvicorn web.app:app --port 8080
```

Open http://127.0.0.1:8080. `GET /healthz` returns `{"status":"ok","referee":{"available":true}}` when LibreOffice was found. The bundled samples are generated by the scripts in `samples/` and are served from `/sample/{id}` (the Docker build writes them to `samples/`).

### What the proof report shows

Everything in the report comes from engine output. A check that did not run is written as "not checked".

- **Cases:** generated cases, targeted cases (boundary and flip probes) and distinct cases, for example "300 generated + 11 targeted, 200 distinct". Many generated cases can repeat, so the distinct count is the honest one.
- **Tested domains:** for each input, its type, minimum, maximum and decimal places. A pass only covers those domains. The domain includes the workbook's own sample value when that is above the default cap, and targeted cases stay inside it.
- **Boundaries:** for each threshold, a change-point bracket shown as "below → above" (the two input values on either side of the flip, found by probing every `IF` condition), the threshold constant or "calculated", and the exact hits, where an input value equals the threshold. An exact hit is listed only when the compared values confirm it, together with the other input values needed to reach it. Notes say when only a bracket was found.
- **Mutation self-check:** the share of injected bugs the verifier caught. A surviving mutant is worded "no difference found on N distinct cases" with the tested domain. That does not mean the mutant is equivalent to the original. Ghost aims cases at changing which row `MAX`, `MIN` or `MATCH` picks, and when survivors remain on rows that never win on any tested input, the report says so.
- **Not converted:** cells Ghost could not convert are listed with the cell and the reason.
- **Excel errors** appear in reports as their text (`#VALUE!`). If a job fails while writing the report, the page says "The report could not be written".
- **Excel cross-check:** "not cross-checked against Excel" unless the workbook has Excel-saved values.
- **Both modes:** when Faithful and Intended both ran, the job page links the Faithful report as well (`/run/<job id>/report.html?mode=faithful`).

**One verification at a time per session.** A session can have at most one queued or running verification job. If you press "Verify" again while one is active, the server answers `429 Too Many Requests` with the message "This session already has a verification queued or running. Wait for it to finish, then start a new run." The page shows that message above the job that is still in progress. The second request is refused, not queued, and the running job is untouched. Once the job has finished (passed, failed or timed out) you can start a new run. `GHOST_MAX_JOBS` still limits how many jobs from different sessions run at once.

## Run with Docker

The image is based on `debian:bookworm-slim` and installs `libreoffice-calc-nogui` and `libreoffice-script-provider-python`. Give the container at least 1 GB of RAM.

```
docker build -t ghost-in-the-macro .
docker run --rm -p 8080:8080 ghost-in-the-macro
```

Open http://127.0.0.1:8080.

Environment variables (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `GHOST_SOFFICE` | found automatically; `/usr/bin/soffice` in the image | Path to the `soffice` executable |
| `GHOST_MAX_JOBS` | `2` | Verification jobs that run at once; extra jobs wait in a queue |
| `GHOST_MUTATION_CASES` | `100` | Cases per mutant for the web mutation self-check; `0` turns the check off (reported as "not checked") |
| `GHOST_SESSION_SECRET` | random per process | Secret that signs the session cookie. Set it if you run more than one process or want sessions to survive a restart |
| `GHOST_COOKIE_SECURE` | off | Set to `1` to mark the session cookie `Secure` (use behind HTTPS) |
| `GHOST_SESSION_IDLE_S` | `1800` | Seconds of inactivity before a session and its files are deleted |
| `PORT` | `8080` in the image | Port the container listens on |

Example:

```
docker run --rm -p 8080:8080 -e GHOST_MAX_JOBS=1 -e GHOST_COOKIE_SECURE=1 \
  -e GHOST_SESSION_SECRET="$(openssl rand -hex 32)" ghost-in-the-macro
```

### Deploy

`scripts/deploy_ecs_express.sh` and `docs/DEPLOY_ECS_EXPRESS.md` deploy the image to Amazon ECS Express Mode. Read the guide first: it lists the IAM permissions and roles and what each command creates. Use `scripts/deploy_ecs_express.sh --dry-run` to print every command without running anything.

## Check someone else's rewrite: `ghost challenge`

```
.venv/bin/python -m ghost.cli challenge workbook.xlsx --code candidate.py [--mapping mapping.yaml] [--out DIR]
```

The workbook, recalculated by LibreOffice, referees a `compute(inputs) -> dict` that someone else wrote (a person, or an AI agent). The command runs in Faithful mode and prints the cases tried, the seed, the LibreOffice version and either "no difference found on N cases" or one counterexample with the rule it belongs to. Exit 0: no difference found. Exit 1: a difference found. Exit 2: anything else (unreadable candidate, a candidate that raises or calls `exit`, missing file, Referee unavailable), with one line saying why. There is no sandbox: the command defends against a careless candidate, not a hostile one.

- `ghost challenge` runs the candidate's code on this machine, with your permissions. A candidate that loops will hang it. Do not challenge code you do not trust.
- Without `--mapping` the input and output names are derived from the workbook, and the command says they were not confirmed by a person.
- Without `--out` the migration folder is temporary. With `--out DIR` (new or empty) the folder and the proof report are kept.
- It is a command-line tool only: the web app and the MCP server do not offer it. Macros stay off. Generated Ghost code is refused, because the verifier would regenerate it.

## Use the Kiro Power

The `plugin/` folder is a Kiro Power: `plugin.json`, `mcp.json` (an MCP server over stdio, started with `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`) and eight skills in `plugin/skills/`: `getting-started` (onboarding), `autopsy`, `write-rules-spec`, `implement-from-rules`, `verify-migration`, `record-decision`, `route-migration` and `guardrails` (which carries copies of the two steering files in its `references/` folder). There is no `POWER.md` and no `plugin/steering/`; the Power follows the documented `plugin.json` format.

Status in Kiro: four of the five hooks in `.kiro/hooks/` were seen to fire in the Kiro IDE (shown by side effects, 2026-11-25). The workspace MCP server `ghost` (`.kiro/settings/mcp.json`) was observed Connected with 13 tools in the Kiro MCP panel by the Owner on 2026-11-25 (checklist row). Installing the Power, the four agents and the `review-findings-on-create` hook are not checked in Kiro; `docs/KIRO_OWNER_CHECKLIST.md` lists the steps and its rows stay empty until the Owner records an observed result.

In this path an AI agent in Kiro writes `logic.py` from the rules spec, and the same verifier that checks the web app's transpiler output checks it against the Referee.

Prerequisites on the machine that runs Kiro:

- LibreOffice Calc (the Referee). On macOS install it to `/Applications/LibreOffice.app`; set `GHOST_SOFFICE` if `soffice` is somewhere else. On Debian use `libreoffice-calc-nogui` and `libreoffice-script-provider-python`.
- [`uv`](https://docs.astral.sh/uv/) (provides `uvx`). The Power starts the server with `uvx --from git+https://github.com/viraj-dhanushka/Ghost-in-the-Macro ghost-mcp`. `uvx` downloads Python 3.11+ and Ghost's dependencies by itself, so no `python` command, virtual environment or working directory is needed. The first start takes a minute.

1. Install `uv` and LibreOffice (above).
2. Install the Power in Kiro from the GitHub URL (`docs/KIRO_OWNER_CHECKLIST.md` lists what to check). To run from a local checkout instead, change `args` in `plugin/mcp.json` to `["--from", "/path/to/Ghost-in-the-Macro", "ghost-mcp"]`.
3. Ask the agent to migrate a workbook. The skills guide it: autopsy, write the rules, implement `compute(inputs)`, verify, and record a Decision when the workbook contradicts itself.

The agent must not change behaviour without a recorded Decision (see the `guardrails` skill).

The `.kiro/` folder (steering, hooks, specs, agents) is committed to this repository on purpose and is not ignored by `.gitignore`. `docs/KIRO_USAGE.md` logs how Kiro was used.

## Excel-saved test files

Ghost can only say "checked against Excel" when a workbook carries values that Excel itself calculated and saved. Files written by openpyxl or LibreOffice have no such values, and the report then says "not cross-checked against Excel" instead of "pass".

To make a fixture without desktop Excel:

1. Generate a sample, for example `.venv/bin/python -m samples.make_haunted`.
2. Upload it to Excel for the web (office.com), make a tiny edit and undo it so Excel recalculates and saves, then File > Create a Copy > Download a Copy.
3. Put the `.xlsx` in `tests/fixtures/excel-saved/` (see the README there). The `.gitignore` already lets files in `tests/fixtures/` through.
4. Run `.venv/bin/python -m pytest -q tests/test_excel_saved_fixtures.py`. The folder is empty until someone adds files, and the test skips with a message naming it.

The cross-check reads the saved values with openpyxl (`data_only=True`) and compares them with the Referee.

## Safety

- **Macros never run from uploads.** The web app opens every upload with macros off (`NEVER_EXECUTE`) and reads VBA statically with oletools. Macros are only enabled for a bundled sample, or for a local file when you pass `--trust-macros` on the command line.
- The uploaded file is copied. The original is never modified.
- XML is parsed with defusedxml, and a zip-bomb guard limits the total uncompressed size (200 MB).
- The Referee listens on 127.0.0.1 only, one process per job.
- Each browser session gets its own folder, deleted after the idle timeout. There are no accounts.
- No API keys, tokens or credentials belong in this repository or in generated reports.

## Limits and known differences

- Upload limits: 5 MB per file, 20,000 formulas, 200,000 cells (`MAX_CELLS`, counted while streaming the sheet XML, before the workbook is loaded; larger files are rejected with a message naming the limit), and a processing timeout (60 s by default). Only `.xlsx` and `.xlsm` are accepted. The uncompressed size is capped at 200 MB. A session may have one queued or running verification at a time (a second gets 429), and `GHOST_MAX_JOBS` caps jobs across sessions.
- Named ranges that point at one cell or one rectangular range are converted, and rule text uses the name. Names defined by `OFFSET`, `INDIRECT` or other dynamic formulas are listed as "not converted" with the cell and reason.
- Volatile or external constructs (`NOW`, `TODAY`, `RAND`, `RANDBETWEEN`, `OFFSET`, `INDIRECT`, external links) are reported as "not verifiable as-is" and left out of the comparison.
- Anything Ghost cannot convert is listed as "not converted" with the cell and the reason. It does not guess.
- Comparison tolerance: absolute 1e-6 for numbers, exact for strings, Excel errors compared by error type.
- **LibreOffice is not Excel.** The Referee is LibreOffice, so a pass means "matches LibreOffice", and matches Excel only where the two agree. They differ on seven known cases (R-24): `0^0`, `(-8)^(1/3)`, `MATCH("2",numbers,0)`, `MATCH(TRUE,numbers,0)`, `TRUE>1`, `SUM("5",1)` and `TRUE&""`. Ghost's generated code follows Excel in these, so a workbook that relies on one shows a false mismatch. The table in `.kiro/steering/excel-semantics.md` lists each result; the Excel column there is documented behaviour, not measured. Those cases are left out of golden tests and formula fuzzing, and `tests/test_referee_libreoffice_differences.py` pins today's LibreOffice results so an upgrade is noticed.
- Very large or small numbers converted to text (`&""`) use scientific notation as Excel does ("1E+20"). LibreOffice writes "1E+020"; the verifier treats scientific strings of the same value as equal (R-08).
- `INDEX` with a 0 row or column uses implicit intersection the way the Referee does: in a single-cell formula it returns the element on the formula's own row or column, or `#VALUE!` outside the range's span. Excel 365 spills the whole row or column instead, and Excel's result was not checked. An `INDEX` that can select a whole row or column and is passed through `IF`, `IFERROR` or `CHOOSE` into an aggregate is "not converted". The rules and measurements are in `.kiro/steering/excel-semantics.md` ("INDEX with a 0 row or column"). The live site runs LibreOffice 7.4.7; a current macOS install is newer, so edge cases can differ between the two Referees.
- Two differences were found and not fixed (details in the same steering file): an `INDEX` past the end of its range gives `#REF!` on LibreOffice 26.8.3 but `#VALUE!` on 7.4.7.2 (the live version), and Ghost gives `#REF!`; and `SUM(IF(TRUE,N5))` with text in N5 gives 0 on the Referee but `#VALUE!` in Ghost. Excel was not checked for either.
- Outputs that are "not converted" or "not verifiable" are not offered as outputs in the web app. If you choose one explicitly, the request is rejected with the cell and the reason.
- Worksheet `ROUND` is half away from zero on 15 significant digits. Its behaviour on numbers with more than 15 significant digits has not been checked against Excel. Unverified example: `=ROUND(123456789012345.67,1)` gives `123456789012345.7` in the Referee (LibreOffice 26.8.3.1 and 7.4.7.2) and `123456789012346.0` in Ghost's generated code. The owner will confirm Excel's result in Excel for the web; until then, treat a match or mismatch on such values as unverified (see `.kiro/steering/excel-semantics.md`).
- The mutation self-check, which injects bugs to see whether the verifier notices, runs on request with `ghost mutate` or `ghost verify --mutation-cases N`, and in the web app with `GHOST_MUTATION_CASES` cases per mutant. When it did not run, the report says "not checked".
- VBA is read statically. Conversion of VBA to Python is a stretch goal; portfolios with a lot of VBA are routed to AWS Transform custom with `ghost route` (dry run only, nothing is executed).
- A known-issues list from the latest review is in `docs/TEST_REPORT_2026-11-24.md`.

## About the feasibility test bench

Before the spec was written, the feasibility of the approach (LibreOffice as a recalculation oracle, formula fuzzing against it) was tested with a separate test bench. That test bench was built outside this repository and is not included here. Nothing in the repository depends on it. The tests that ship in `tests/` are the ones this repository runs.

## Repository layout

- `ghost/`: the engine (ingest, autopsy, rules, referee, converter, verifier, mutation, report, decisions, router) and the `ghost` CLI.
- `web/`: the FastAPI app (templates, static files, jobs, sessions).
- `mcp_server/`: the MCP server used by the Power.
- `plugin/`: the Kiro Power (manifest, MCP config, skills).
- `samples/`: scripts that generate the sample workbooks (they are not committed as files).
- `scripts/`: `demo.sh`, `ghost-py` (runs the venv's Python for hooks), `ghost_hook.py` and the ECS deploy script.
- `.kiro/`: steering, hooks, specs and agents.
- `docs/`: deploy guide, Kiro usage log, test report.

## License

MIT, see `LICENSE`.
