"""Dry-run AWS Transform command and plain-English route explanation.

Requirements 16.6 (dry-run command, never executed), 16.8 (explanation in the
migration ``design.md``). The command is only ever a string.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from ghost.models import Route

__all__ = [
    "ROUTE_BEGIN",
    "ROUTE_END",
    "atx_dry_run_command",
    "explain_route",
    "with_atx_command",
    "write_route_explanation",
]

ROUTE_BEGIN = "<!-- ghost:route:begin -->"
ROUTE_END = "<!-- ghost:route:end -->"
# Facts for the command come from docs/AWS_TRANSFORM_FACTS.md (read 2026-11-26), not from memory:
# * the AWS-managed definition is `AWS/vba-to-python-migration` (Early access);
# * `-g` takes a JSON or YAML file, and a managed definition run non-interactively needs
#   `additionalPlanContext` in it;
# * the target of `-p` must be under Git; Node.js 22 or later; a non-interactive run exits 0 even when
#   the transformation failed (CLI 3.22.1 or later).
# The command is only ever a string. It is not run, and nothing here has been run against AWS.
DEFAULT_DEFINITION = "AWS/vba-to-python-migration"
POWER = "documented by AWS; not installed or tested with Ghost"
CONFIG_FILE = "atx-config.yaml"
# Build command: `python3 -m compileall -q .` instead of `py_compile **/*.py`. The glob may not be expanded
# by the shell that runs it. compileall walks the tree itself and exits non-zero on a syntax error. It is a
# syntax check only, not a test run, and it is not the Referee (the build also runs before any logic.py exists).
BUILD_COMMAND = "python3 -m compileall -q ."
KIT_PLACEHOLDER = "<kit-folder>"
LABEL = "Suggested command, not run"
DESIGN_FILE = "design.md"
_AWS_ROUTES = ("AWS Transform custom", "Split")
def atx_dry_run_command(
    workbook: str | Path | None = None,
    definition: str | None = None,
    config: str = CONFIG_FILE,
    folder: str | None = None,
) -> str:
    """An ``atx custom def exec`` command to review, as a string only (never run). ``-p`` is always the kit
    folder that ``ghost handoff`` writes (the Git repository); ``workbook`` is accepted for compatibility and not
    used: the folder a workbook happens to sit in is never the one to hand to the agent."""
    path = folder or KIT_PLACEHOLDER
    return " ".join(
        [
            "atx custom def exec",
            "-n", shlex.quote(definition or DEFAULT_DEFINITION),
            "-p", shlex.quote(path),
            "-c", shlex.quote(BUILD_COMMAND),
            "-g", shlex.quote(config),
            "-x",
            "-t",
        ]
    )
def with_atx_command(route: Route, workbook: str | Path | None = None, definition: str | None = None) -> Route:
    """Return ``route`` with ``atx_command`` set for AWS and Split routes."""
    if route.route in _AWS_ROUTES:
        return route.model_copy(update={"atx_command": atx_dry_run_command(workbook, definition)})
    return route.model_copy(update={"atx_command": None})
def _definition_of(command: str | None) -> str | None:
    if not command:
        return None
    try:
        parts = shlex.split(command)
        return parts[parts.index("-n") + 1]
    except (ValueError, IndexError):
        return None


def explain_route(route: Route) -> str:
    """Deterministic plain-English explanation (markdown, no timestamps)."""
    m = route.metrics
    lines = ["## Migration route", "", f"**Recommended route: {route.route}.**", ""]
    if route.route == "Ghost converts":
        lines.append(
            "Ghost converts this workbook itself and checks the result against the "
            "original workbook."
        )
    elif route.route == "AWS Transform custom":
        lines.append(
            "The VBA of this workbook is better suited to AWS Transform custom. Its documentation "
            "describes migrating VBA code and says nothing about worksheet formulas, cell counts or workbook "
            "size, so Ghost asks it to migrate the VBA only; the worksheet formulas are restated in English in "
            "rules.md so that the agent can meet the contract, and rules.md is uploaded with the kit. Ghost can "
            "referee the returned code only while the workbook is within Ghost's limits, and only for outputs "
            "calculated by worksheet formulas, not for values the VBA produces itself."
        )
    elif route.route == "Split":
        lines.append(
            "Ghost converts the formulas. The VBA goes to AWS Transform custom. Ghost "
            "verifies what it converted, and can referee the returned code only for outputs that are not fed by "
            "a VBA function."
        )
    else:
        lines.append(
            "This workbook is over Ghost's limits, so Ghost does not convert or verify it here. "
            "AWS Transform custom's documentation describes migrating VBA code and says nothing about worksheet "
            "formulas, cell counts or workbook size. A kit for a workbook that was not loaded has no rules.md, so "
            "the formulas are not in it."
        )
    lines += ["", "Why:", ""]
    lines += [f"- {r}" for r in route.reasons]
    if route.parts:
        lines += ["", "What happens to each part:", ""]
        lines += [f"- {p}" for p in route.parts]
    if not any(p.startswith("Not checked") for p in route.parts):
        lines += [
            "",
            "Measured: "
            f"{m.formula_count} formulas, {m.vba_line_count} VBA lines, "
            f"{m.module_count} modules, {m.userform_count} UserForms, "
            f"{m.declare_count} API Declares.",
        ]
    if route.atx_command:
        definition = _definition_of(route.atx_command)
        if definition in (None, DEFAULT_DEFINITION):
            definition_note = (
                f"- The definition `{DEFAULT_DEFINITION}` is an AWS-managed definition in Early access; "
                "check what your registry offers with `atx custom def list`."
            )
        else:
            definition_note = (
                f"- `{definition}` is the definition you named; Ghost has not checked it exists. "
                "`atx custom def list` shows what your registry offers."
            )
        lines += [
            "",
            f"{LABEL} (shown only, never executed by Ghost):",
            "",
            "```",
            route.atx_command,
            "```",
            "",
            definition_note,
            f"- `-g {CONFIG_FILE}` is the configuration file that `ghost handoff` writes (it carries "
            "`additionalPlanContext`, which a managed definition needs for a non-interactive run).",
            "- `-p` is the folder to transform: use the kit folder that `ghost handoff` writes (it must be a Git "
            "repository), not the folder the workbook happens to be in. `-t` approves all tool calls and bypasses most guardrails; "
            "use it only on a copy you can discard.",
            "- A non-interactive run exits 0 even when the transformation failed (CLI 3.22.1 or later): "
            "do not read the exit code as a result. Judge the returned code with `ghost challenge`.",
            "- Node.js 22 or later is required. Nothing here has been run against AWS.",
        ]
        lines += [
            "",
            "If AWS credentials exist and the AWS Transform Kiro Power is installed (it is "
            f"{POWER}; see docs/AWS_TRANSFORM_FACTS.md), the owner may hand the kit to it. Run `ghost "
            "challenge` on the returned code afterwards.",
        ]
    return "\n".join(lines)
def write_route_explanation(migration_dir: str | Path, route: Route) -> Path:
    """Create or replace the route block in the migration ``design.md``."""
    mdir = Path(migration_dir)
    mdir.mkdir(parents=True, exist_ok=True)
    path = mdir / DESIGN_FILE
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"{ROUTE_BEGIN}\n{explain_route(route)}\n{ROUTE_END}"
    pattern = re.compile(re.escape(ROUTE_BEGIN) + r".*?" + re.escape(ROUTE_END), re.S)
    if pattern.search(text):
        new = pattern.sub(lambda _m: block, text)
    else:
        new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"
    path.write_text(new, encoding="utf-8")
    return path
