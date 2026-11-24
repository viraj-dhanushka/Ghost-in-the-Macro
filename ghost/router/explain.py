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
TRANSFORMATION_NAME = "excel-vba-to-python"
# AWS Transform custom CLI reference (checked 2026-11-24):
# https://docs.aws.amazon.com/transform/latest/userguide/custom-command-reference.html
# `atx custom def exec` takes -n, -p, -c, -x (--non-interactive) and -t
# (--trust-all-tools); the full-automation usage is `-x -t`:
# https://docs.aws.amazon.com/transform/latest/userguide/custom-workflows.html
#
# Build command: `python3 -m compileall -q .` instead of `py_compile **/*.py`.
# The command is run by a shell that may not enable `**` (without globstar, `**`
# behaves like `*` and only reaches one directory level), and the glob is not
# expanded at all if the CLI runs the string without a shell. compileall walks the
# tree itself, is in the standard library, and exits non-zero on a syntax error,
# which is what a build check needs. It is a syntax check only, not a test run.
BUILD_COMMAND = "python3 -m compileall -q ."
DESIGN_FILE = "design.md"

_AWS_ROUTES = ("AWS Transform custom", "Split")


def atx_dry_run_command(workbook: str | Path | None = None) -> str:
    """An ``atx custom def exec`` command to review, as a string only (never run).

    The transformation definition ``excel-vba-to-python`` must already exist in the
    user's AWS Transform registry (check with ``atx custom def list``).
    """
    path = str(workbook) if workbook else "<workbook-directory>"
    if workbook:
        path = str(Path(workbook).parent) or "."
    return " ".join(
        [
            "atx custom def exec",
            "-n", shlex.quote(TRANSFORMATION_NAME),
            "-p", shlex.quote(path),
            "-c", shlex.quote(BUILD_COMMAND),
            "-x",
            "-t",
        ]
    )


def with_atx_command(route: Route, workbook: str | Path | None = None) -> Route:
    """Return ``route`` with ``atx_command`` set for AWS and Split routes."""
    if route.route in _AWS_ROUTES:
        return route.model_copy(update={"atx_command": atx_dry_run_command(workbook)})
    return route.model_copy(update={"atx_command": None})


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
            "This workbook is better suited to AWS Transform custom. Ghost can still "
            "verify the migrated result against the original workbook."
        )
    else:
        lines.append(
            "Ghost converts the formulas. The VBA goes to AWS Transform custom. Ghost "
            "verifies the result of either path against the original workbook."
        )
    lines += ["", "Why:", ""]
    lines += [f"- {r}" for r in route.reasons]
    lines += [
        "",
        "Measured: "
        f"{m.formula_count} formulas, {m.vba_line_count} VBA lines, "
        f"{m.module_count} modules, {m.userform_count} UserForms, "
        f"{m.declare_count} API Declares.",
    ]
    if route.atx_command:
        lines += [
            "",
            "Dry-run command (shown only, never executed by Ghost):",
            "",
            "```",
            route.atx_command,
            "```",
            "",
            f"The transformation definition `{TRANSFORMATION_NAME}` must exist in your "
            "AWS Transform registry before this works. Check with "
            "`atx custom def list`. `-t` is required with `-x` (non-interactive).",
            "",
            "If AWS credentials exist and the official AWS Transform Kiro power is "
            "installed, hand this command to that power. Run Ghost verification "
            "afterwards.",
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
