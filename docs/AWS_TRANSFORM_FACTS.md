# AWS Transform custom: facts checked for Ghost (Feature 7, Step 0)

Read on 2026-11-26 from the AWS documentation pages listed below. Nothing here was run: no `atx` and no AWS command was executed on this machine (`atx` is not installed). Where this file differs from the feature prompt, the documentation wins and the difference is marked **DIFFERS**. Where a claim could not be read from a page, it is marked **NOT VERIFIED**.

## Sources
- Command reference: https://docs.aws.amazon.com/transform/latest/userguide/custom-command-reference.html
- Workflows (modes, configuration files, trust settings): https://docs.aws.amazon.com/transform/latest/userguide/custom-workflows.html
- AWS-managed transformations: https://docs.aws.amazon.com/transform/latest/userguide/transform-aws-customs.html
- Getting started (prerequisites): https://docs.aws.amazon.com/transform/latest/userguide/custom-get-started.html
- Troubleshooting: https://docs.aws.amazon.com/transform/latest/userguide/custom-troubleshooting.html
- CLI version history: https://docs.aws.amazon.com/transform/latest/userguide/custom-cli-versions.html
- Pricing: https://aws.amazon.com/transform/pricing/
- Service improvement and opt-out: https://docs.aws.amazon.com/transform/latest/userguide/service-improvement.html
- Blog, "Modernizing Excel VBA to Python at Scale with AWS Transform custom": https://aws.amazon.com/blogs/devops/modernizing-excel-vba-to-python-at-scale-with-aws-transform-custom/

## Checked facts, one by one
| # | Claim in the feature prompt | Result | Source |
|---|---|---|---|
| 1 | Managed definition `AWS/vba-to-python-migration`, Early access, for `.bas`, `.cls`, `.frm` and VBA embedded in `.xlsm` | **Confirmed.** Status "Early access". The page says it migrates VBA macros, modules, UserForms and embedded logic to Python scripts and modules (openpyxl, pandas, tkinter or PyQt6), target Python 3.8 or later, "Use when converting .bas, .cls, .frm, or .xlsm-embedded VBA code". | transform-aws-customs |
| 2 | `atx custom def exec` flags `-n -p -c -x -t -g/--configuration` | **Confirmed**, with more flags the prompt did not list: `-d/--do-not-learn`, `--tv/--transformation-version`, `--limit` (an agent-minutes budget: the run exits when it is reached and can be resumed with a higher limit), `--share-learnings`, `-h`. `-g` takes a path to a JSON or YAML file, or key=value pairs. | command-reference, workflows |
| 3 | Configuration key `additionalPlanContext` carries extra instructions | **Confirmed.** The example file also shows `codeRepositoryPath`, `transformationName`, `buildCommand` and `validationCommands`. The file is passed as `--configuration file://config.yaml` in the workflows page; the command reference says "path to config file". | workflows |
| 4 | A managed definition run with `-x` fails without `additionalPlanContext` | **Confirmed in words, not as an observed failure.** The troubleshooting page says that for AWS-managed transformations (names starting `AWS/`) in non-interactive mode you need to provide `additionalPlanContext` in `--configuration`. | troubleshooting |
| 5 | `-p` must be a Git repository | **Confirmed.** "the working directory needs to be a valid Git repo to execute a transformation"; Troubleshooting: "requires repositories to be under git source control". The blog says "Git repository initialized in source directory". | get-started, troubleshooting, blog |
| 6 | Since CLI 3.22.1 a failed transformation still exits 0 | **Confirmed.** Version 3.22.1 (5 Nov 2026) "stops non-interactive runs (`atx custom def exec -x`) from exiting with code 3 when the agent reports that the transformation failed. They exit with code 0 again, as they did before 3.22.0." Latest listed version: 3.25.0 (19 Nov 2026). So a non-interactive run exits 0 on a failed transformation. | cli-versions |
| 7 | The log line `Execution was not successful` is the failure signal the official Kiro power checks | **NOT VERIFIED.** No AWS documentation page I read names that line. I could not open the official power's source. Treat it as unconfirmed: `RUN.md` tells the owner to read the conversation log and the output for the failure message and to rely on `ghost challenge`, not on the exit code. Logs are at `~/.aws/atx/custom/<conversation-id>/logs/` (troubleshooting and blog). | none |
| 8 | A definition on disk is a folder with `SKILL.md` and optional `references/` and `scripts/` | **Partly confirmed.** The workflows page mentions the skill format "SKILL.md + references/". `scripts/` is not mentioned on the pages I read. Not needed by Ghost, which does not write a definition. | workflows |
| 9 | Price $0.035 per agent minute | **Confirmed.** Billing unit agent minute, minimum increment 1 minute, price $0.035 per agent minute, idle time and CLI-side operations (reads, builds) not charged. (Another example on the same page, an AWS-managed .NET transformation, is priced at $0.00 within a quota; that does not apply to this definition.) | pricing |
| 10 | Node.js 22 or later | **Confirmed by the user guide** (get-started and troubleshooting). **DIFFERS** from the blog, which says "Node.js: Version 20 or higher". Ghost follows the user guide. | get-started, blog |
| 11 | The official Kiro power `aws-transform` runs Transform custom through the `atx` CLI with ordinary AWS credentials | **NOT VERIFIED here.** The documentation lists an "AWS Transform plugin" for Claude Code, Codex and Cursor, and an IDE plugin, and says the CLI needs AWS credentials with `transform-custom:*`. I did not find a page for a Kiro power. | get-started, troubleshooting |

## Facts the prompt did not state
- **The blog uses a different definition name.** Its examples run `--transformation-name "VBA-to-Python-Migration"`, a definition the author created and published to their own registry. That name is not the managed one. The managed name is `AWS/vba-to-python-migration`.
- **Non-interactive trust.** `-x` and `-t` together give a fully autonomous run. `-t` approves all tool calls and bypasses most guardrails; `alwaysPromptCommands` patterns are not enforced in non-interactive mode. Ghost prints `-x -t` only as part of a suggested command and warns about this.
- **Checkpoint commits.** AWS Transform creates checkpoint commits in the repository while it applies changes (author "ATX Bot" unless `ATX_GIT_COMMITTER_NAME` and `ATX_GIT_COMMITTER_EMAIL` are set). The kit's repository will therefore have extra commits after a run.
- **Service improvement.** AWS "may use certain content from AWS Transform for service improvement", including "the responses and code that AWS Transform generates", for example for model training. Opt out with an AI services opt-out policy in AWS Organizations. The kit's `RUN.md` must say this and link the page above.
- **Windows.** Native Windows is supported for the CLI, but the `atx ct` commands are not. Not relevant to `atx custom def exec`.
- **Network.** The CLI needs `transform-cli.awsstatic.com`, `transform-custom.<region>.api.aws` and `*.s3.amazonaws.com`.
- **Agent minutes in a session.** In an interactive `atx` session the command `/usage` shows the accumulated agent minutes (command reference).
- **Nothing about worksheets.** None of these pages says anything about worksheet formulas, cell counts or workbook size. The managed definition is described for VBA code only. Ghost must never say that AWS Transform converts formulas or handles workbook size.

## What this changes in Feature 7
- The command printed by Ghost uses the managed definition `AWS/vba-to-python-migration` by default, always has `-g <file>` with `additionalPlanContext`, and checks that the target is a Git repository. It is only printed, labelled "suggested command, not run".
- The failure signal in `RUN.md` cannot cite the `Execution was not successful` line as documented (fact 7). `RUN.md` says: the exit code is 0 even when the transformation failed (fact 6, documented), read the conversation log, and judge the result by `ghost challenge`.
- Node.js 22 or later is stated (fact 10), with the blog's lower number noted as a discrepancy.
