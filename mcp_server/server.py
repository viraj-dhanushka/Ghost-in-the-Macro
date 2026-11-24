"""Ghost MCP server (stdio).

Exposes the Core_Engine to an AI agent (Kiro) as MCP tools. This module holds
no business logic: each tool validates its arguments with a pydantic model and
calls ``ghost.*`` (plus the shared helpers in ``ghost.cli``), then returns
JSON-serialisable engine output.

Rules enforced here:
* Macros are never executed (the Referee is always opened with macros off) and
  ``extract_vba`` reads VBA statically and never writes (Requirement 12.4).
* Invalid arguments return a structured error naming the argument
  (Requirement 12.11): ``{"error": {"type": "invalid_argument",
  "argument": "<name>", "message": "..."}}``.
* ``mutation_check`` runs the mutation self-check (task 15) and returns the score.

Run: ``python -m mcp_server.server``.

Requirements: 12.3, 12.4, 12.5, 12.6, 12.11.
"""
from __future__ import annotations

import contextlib
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Literal

import anyio
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.metrics import metrics as compute_metrics
from ghost.autopsy.thresholds import extract_thresholds
from ghost.cli import (
    CliError,
    patch_validator,
    _accepts_trace,
    _analyse,
    _load,
    _probe_boundaries,
    _probe_flips_with_summary,
    _roles_from_mapping,
    _soffice_version,
    run_verification,
)
from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.converter.subset import find_not_converted
from ghost.decisions.store import InvalidDecision, load_decisions, record
from ghost.ingest.limits import IngestError
from ghost.ingest.vba import extract_vba as ingest_extract_vba
from ghost.models import Mapping
from ghost.mutation.run import DEFAULT_MUTANT_CASES
from ghost.referee.client import RefereeClient, RefereeError
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.referee.sanity import run_sanity
from ghost.rules.ears import generate_rules
from ghost.verifier.classify import make_classifier
from ghost.verifier.coverage import CoverageTracker, candidate_inputs, close_gaps
from ghost.verifier.flip import flip_cases
from ghost.verifier.run import DEFAULT_CASES, DEFAULT_SEED, VerifyConfig, load_compute, verify

SERVER_NAME = "ghost-in-the-macro"
NOT_IMPLEMENTED = "not implemented yet"


# --------------------------------------------------------------------------
# Errors and serialisation
# --------------------------------------------------------------------------
class ToolFailure(Exception):
    """A tool-level failure returned to the caller as a structured error."""

    def __init__(self, kind: str, message: str, argument: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.argument = argument

    def payload(self) -> dict[str, Any]:
        err: dict[str, Any] = {"type": self.kind, "message": self.message}
        if self.argument is not None:
            err["argument"] = self.argument
        return {"error": err}


def _bad(argument: str, message: str) -> ToolFailure:
    return ToolFailure("invalid_argument", message, argument)


def jsonable(value: Any) -> Any:
    """Convert engine values to JSON types without losing Decimal precision."""
    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        return [jsonable(v) for v in items]
    if isinstance(value, Path):
        return str(value)
    return value


def _validation_failure(exc: ValidationError) -> ToolFailure:
    first = exc.errors()[0]
    loc = [str(p) for p in first["loc"]]
    argument = ".".join(loc) if loc else "arguments"
    if first["type"] == "missing":
        message = f"required argument '{argument}' is missing"
    elif first["type"] == "extra_forbidden":
        message = f"unknown argument '{argument}'"
    else:
        message = f"invalid argument '{argument}': {first['msg']}"
    return ToolFailure("invalid_argument", message, argument)


# --------------------------------------------------------------------------
# Argument models
# --------------------------------------------------------------------------
class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _WorkbookArgs(_Args):
    workbook: str = Field(description="Path to the .xlsx/.xlsm workbook. It is never modified.")


class _MappedWorkbookArgs(_WorkbookArgs):
    inputs: list[str] | None = Field(
        default=None, description="Input cells (Sheet!A1) overriding the proposed inputs."
    )
    outputs: list[str] | None = Field(
        default=None, description="Output cells (Sheet!A1) overriding the proposed outputs."
    )


class GetDependenciesArgs(_WorkbookArgs):
    cell: str = Field(description="Cell reference, Sheet!A1.")


class EvaluateOriginalArgs(_WorkbookArgs):
    inputs: dict[str, Any] = Field(description="Input values keyed by cell (Sheet!A1).")
    outputs: list[str] = Field(min_length=1, description="Cells (Sheet!A1) to return.")


class VerifyImplementationArgs(_WorkbookArgs):
    module: str = Field(
        description="Python source defining compute(inputs) -> dict, or a path to such a file."
    )
    mapping: dict[str, Any] | str = Field(
        description="Mapping as an object {inputs: {...}, outputs: {...}} or a path to mapping.yaml."
    )
    cases: int = Field(default=DEFAULT_CASES, ge=1, le=100_000, description="Number of cases.")
    seed: int = Field(default=DEFAULT_SEED, description="Hypothesis seed.")
    mode: Literal["faithful", "intended"] = "faithful"
    migration_dir: str | None = Field(
        default=None, description="Migration directory; its decisions.yaml is used to classify."
    )


class MutationCheckArgs(_Args):
    migration_dir: str = Field(description=".kiro/specs/<migration> directory with logic.py and mapping.yaml.")
    mode: Literal["auto", "faithful", "intended", "both"] = "auto"
    workbook: str | None = Field(default=None, description="Default: from source.yaml.")
    seed: int = DEFAULT_SEED
    cases: int = Field(default=DEFAULT_CASES, ge=1, le=100_000, description="Cases for the baseline verification.")
    mutant_cases: int = Field(default=DEFAULT_MUTANT_CASES, ge=1, le=10_000, description="Cases per Mutant.")


class RecordDecisionArgs(_Args):
    migration_dir: str = Field(description=".kiro/specs/<migration> directory.")
    behaviour: str
    reason: str
    author: str
    finding_id: str | None = None
    rule_id: str | None = None
    date: str | None = Field(default=None, description="ISO date; default today.")
    patch: dict[str, Any] = Field(default_factory=dict, description="Intended-mode patch.")


class GenerateProofReportArgs(_Args):
    migration_dir: str
    mode: Literal["auto", "faithful", "intended", "both"] = "auto"
    workbook: str | None = Field(default=None, description="Default: from source.yaml.")
    seed: int = DEFAULT_SEED
    cases: int = Field(default=DEFAULT_CASES, ge=1, le=100_000)


class RecommendRouteArgs(_Args):
    workbook: str | None = None
    batch_size: int = Field(default=1, ge=1, description="Workbooks in the batch.")
    migration_dir: str | None = Field(
        default=None, description="Write the explanation into this directory's design.md."
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _load_workbook(path: str, argument: str = "workbook"):
    try:
        return _load(path)
    except CliError as exc:
        raise _bad(argument, str(exc)) from exc


def _analyse_args(a: _MappedWorkbookArgs):
    try:
        return _analyse(
            a.workbook,
            ",".join(a.inputs) if a.inputs else None,
            ",".join(a.outputs) if a.outputs else None,
        )
    except CliError as exc:
        text = str(exc)
        arg = "workbook"
        if text.startswith("--inputs"):
            arg = "inputs"
        elif text.startswith("--outputs"):
            arg = "outputs"
        raise _bad(arg, text.replace("--inputs: ", "").replace("--outputs: ", "")) from exc


def _require_cells(wb, cells: list[str], argument: str) -> None:
    for ref in cells:
        if ref not in wb.cells:
            raise _bad(argument, f"cell {ref} is not in the workbook")


def _wire(v: Any) -> Any:
    return int(v) if isinstance(v, Decimal) and v == v.to_integral_value() else (
        float(v) if isinstance(v, Decimal) else v
    )


def _quiet(fn: Callable[[], Any]) -> Any:
    """Run ``fn`` with stdout redirected: stdout carries the MCP protocol."""
    with contextlib.redirect_stdout(sys.stderr):
        return fn()


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
def analyze_workbook(a: _MappedWorkbookArgs) -> dict[str, Any]:
    an = _analyse_args(a)
    wb = an.wb
    return {
        "workbook": a.workbook,
        "sheets": wb.sheets,
        "metrics": compute_metrics(wb),
        "excel_saved_values": (
            "present" if wb.excel_saved else "none (not cross-checked against Excel)"
        ),
        "inputs": sorted(r for r, v in an.roles.items() if v == "INPUT"),
        "outputs": sorted(r for r, v in an.roles.items() if v == "OUTPUT"),
        "thresholds": an.thresholds,
        "findings": an.findings,
        "rule_count": len(an.rules),
        "not_converted": [{"cell": e.cell, "reason": e.reason} for e in find_not_converted(wb)],
        "not_verifiable_as_is": [f for f in wb.features if f.not_verifiable],
    }


def list_rules(a: _MappedWorkbookArgs) -> dict[str, Any]:
    an = _analyse_args(a)
    return {"rules": an.rules, "findings": an.findings}


def get_dependencies(a: GetDependenciesArgs) -> dict[str, Any]:
    wb = _load_workbook(a.workbook)
    _require_cells(wb, [a.cell], "cell")
    precedents = sorted(wb.deps.get(a.cell, set()))
    dependents = sorted(c for c, deps in wb.deps.items() if a.cell in deps)
    return {"cell": a.cell, "precedents": precedents, "dependents": dependents}


def find_inconsistencies(a: _WorkbookArgs) -> dict[str, Any]:
    wb = _load_workbook(a.workbook)
    thresholds = extract_thresholds(wb)
    return {"thresholds": thresholds, "findings": detect_inconsistencies(thresholds)}


def extract_vba(a: _WorkbookArgs) -> dict[str, Any]:
    """Read-only: VBA is parsed statically from the file and nothing is executed or written."""
    p = Path(a.workbook)
    if not p.is_file():
        raise _bad("workbook", f"workbook not found: {p}")
    try:
        modules = ingest_extract_vba(p)
    except IngestError as exc:
        raise _bad("workbook", f"{type(exc).__name__}: {exc}") from exc
    return {"read_only": True, "modules": modules}


def evaluate_original(a: EvaluateOriginalArgs) -> dict[str, Any]:
    wb = _load_workbook(a.workbook)
    _require_cells(wb, list(a.inputs), "inputs")
    _require_cells(wb, a.outputs, "outputs")
    for cell, value in a.inputs.items():
        if value is not None and not isinstance(value, (str, int, float, bool, Decimal)):
            raise _bad(
                f"inputs.{cell}",
                f"invalid inputs.{cell}: expected a number, text, boolean or null, "
                f"got {type(value).__name__}",
            )
    inputs = {k: _wire(v) for k, v in a.inputs.items()}
    with RefereeClient(locate_soffice(), Path(a.workbook), run_macros=False) as ref:
        values = ref.eval(inputs, list(a.outputs))
    return {"values": values}


def boundary_cases(a: _MappedWorkbookArgs) -> dict[str, Any]:
    an = _analyse_args(a)
    mapping = generate_mapping(an.wb, an.roles)  # type: ignore[arg-type]
    with RefereeClient(locate_soffice(), Path(a.workbook), run_macros=False) as ref:
        results = _probe_boundaries(ref, an.wb, mapping, an.thresholds)
    return {"boundaries": results}


def check_against_excel_cache(a: _WorkbookArgs) -> dict[str, Any]:
    wb = _load_workbook(a.workbook)
    if not wb.excel_saved:
        return {"sanity": {"status": "not cross-checked against Excel"}}
    with RefereeClient(locate_soffice(), Path(a.workbook), run_macros=False) as ref:
        res = run_sanity(wb, ref)
    return {"sanity": res}


def _read_mapping_arg(value: dict[str, Any] | str) -> Mapping:
    from ghost.converter.mapping import read_mapping

    if isinstance(value, str):
        p = Path(value)
        if not p.is_file():
            raise _bad("mapping", f"mapping file not found: {p}")
        try:
            return read_mapping(p)
        except (ValueError, yaml.YAMLError, KeyError, TypeError) as exc:
            raise _bad("mapping", f"mapping file is not valid: {exc}") from exc
    try:
        return Mapping.model_validate(value)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(["mapping", *[str(p) for p in first["loc"]]])
        raise ToolFailure("invalid_argument", f"invalid {loc}: {first['msg']}", loc) from exc


def _read_module_arg(value: str) -> str:
    if "\n" not in value and len(value) < 4096 and Path(value).is_file():
        return Path(value).read_text(encoding="utf-8")
    return value


def verify_implementation(a: VerifyImplementationArgs) -> dict[str, Any]:
    wb = _load_workbook(a.workbook)
    mapping = _read_mapping_arg(a.mapping)
    if not mapping.outputs:
        raise _bad("mapping", "mapping has no outputs to verify")
    _require_cells(wb, [s.cell for s in mapping.inputs.values()], "mapping")
    _require_cells(wb, [s.cell for s in mapping.outputs.values()], "mapping")
    try:
        compute = load_compute(_read_module_arg(a.module))
    except Exception as exc:  # the supplied module is untrusted code: report, do not crash
        raise _bad("module", f"module cannot be loaded: {type(exc).__name__}: {exc}") from exc
    if a.migration_dir and not Path(a.migration_dir).is_dir():
        raise _bad("migration_dir", f"migration directory not found: {a.migration_dir}")
    decisions = load_decisions(a.migration_dir) if a.migration_dir else []
    thresholds = extract_thresholds(wb, roles=_roles_from_mapping(mapping))
    findings = detect_inconsistencies(thresholds)
    rules = generate_rules(wb, _roles_from_mapping(mapping), thresholds)  # type: ignore[arg-type]
    soffice = locate_soffice()
    tracker = CoverageTracker(rules)
    traced = _accepts_trace(compute)
    # Intended mode: the same three-condition test as the CLI. The comparison module is the
    # transpiled Faithful module; if the workbook is not fully convertible there is none, and
    # every mismatch is then classified as a translation bug (never excused by a Decision).
    faithful = None
    if a.mode == "intended" and decisions:
        try:
            built = emit_module(wb, mapping)
            faithful = None if built.not_converted else load_compute(built.code)
        except Exception:  # noqa: BLE001 - unconvertible means "cannot explain"
            faithful = None
    flips, flip_summary = _probe_flips_with_summary(wb, mapping, a.seed)
    flip_extra = flip_cases(flips, mapping, summary=flip_summary)  # R-04, as the CLI
    cfg = VerifyConfig(
        seed=a.seed,
        max_examples=a.cases,
        mode=a.mode,
        thresholds=thresholds,
        trace=tracker.trace if traced else None,
        faithful=faithful,
        classifier=make_classifier(a.mode, findings, decisions, rules, wb.deps),  # type: ignore[arg-type]
        extra_cases=flip_extra,
    )
    with RefereeClient(soffice, Path(a.workbook), run_macros=False) as ref:
        res = verify(compute, mapping, ref, cfg)
    uncovered: list[Any] = []
    if traced:
        base = {
            n: wb.cells[s.cell].value if s.cell in wb.cells else None
            for n, s in mapping.inputs.items()
        }
        close_gaps(tracker, compute, candidate_inputs(base, [t.constant for t in thresholds]))
        uncovered = [c for c in tracker.report() if c.uncovered]
    return {
        "mode": res.mode,
        "seed": res.seed,
        "cases_tested": res.cases_tested,
        "cases_generated": res.cases_generated,
        "cases_targeted": res.cases_targeted,
        "distinct_cases": res.distinct_cases,
        "passed": res.passed,
        "mismatches": res.mismatches,
        "decisions_cannot_explain": res.explain_unavailable,
        "boundary_notes": flip_summary.notes(),
        "uncovered_conditions": uncovered if traced else "not checked",
        "libreoffice": _soffice_version(soffice) or "not checked",
    }


def mutation_check(a: MutationCheckArgs) -> dict[str, Any]:
    """Verify, mutate, and report. The result comes from the proof report written to disk."""
    import json

    mdir = Path(a.migration_dir)
    if not mdir.is_dir():
        raise _bad("migration_dir", f"migration directory not found: {mdir}")
    try:
        ok = _quiet(
            lambda: run_verification(
                mdir, mode=a.mode, workbook=a.workbook, trust_macros=False,
                seed=a.seed, cases=a.cases, mutation_cases=a.mutant_cases,
            )
        )
    except CliError as exc:
        raise ToolFailure("invalid_argument", str(exc), "migration_dir") from exc
    jp = mdir / "proof-report.json"
    mutation: Any = {"status": "not checked"}
    if jp.is_file():
        mutation = json.loads(jp.read_text(encoding="utf-8")).get("mutation", mutation)
    return {"verification_passed": ok, "mutation": mutation, "report_json": str(jp)}


def record_decision(a: RecordDecisionArgs) -> dict[str, Any]:
    mdir = Path(a.migration_dir)
    if not mdir.is_dir():
        raise _bad("migration_dir", f"migration directory not found: {mdir}")
    raw = a.model_dump(exclude={"migration_dir"})
    if not raw.get("date"):
        from datetime import date as _date

        raw["date"] = _date.today().isoformat()
    try:
        d = record(mdir, raw, validate=patch_validator(mdir))
    except InvalidDecision as exc:
        missing = list(getattr(exc, "missing", []) or [])
        arg = missing[0] if missing else "decision"
        raise ToolFailure("invalid_argument", f"invalid Decision: {exc}", arg) from exc
    return {"decision": d, "file": str(mdir / "decisions.yaml")}


def generate_proof_report(a: GenerateProofReportArgs) -> dict[str, Any]:
    mdir = Path(a.migration_dir)
    if not mdir.is_dir():
        raise _bad("migration_dir", f"migration directory not found: {mdir}")
    try:
        ok = _quiet(
            lambda: run_verification(
                mdir, mode=a.mode, workbook=a.workbook, trust_macros=False,
                seed=a.seed, cases=a.cases,
            )
        )
    except CliError as exc:
        raise ToolFailure("invalid_argument", str(exc), "migration_dir") from exc
    out: dict[str, Any] = {
        "passed": ok,
        "report_html": str(mdir / "proof-report.html"),
        "report_json": str(mdir / "proof-report.json"),
    }
    jp = mdir / "proof-report.json"
    if jp.is_file():
        import json

        out["report"] = json.loads(jp.read_text(encoding="utf-8"))
    return out


def recommend_route(a: RecommendRouteArgs) -> dict[str, Any]:
    from ghost.router import (
        ThresholdError,
        explain_route,
        recommend_route as route_for,
        with_atx_command,
        write_route_explanation,
    )

    if not a.workbook:
        raise _bad("workbook", "required argument 'workbook' is missing")
    wb = _load_workbook(a.workbook)
    try:
        route = with_atx_command(route_for(compute_metrics(wb), a.batch_size), a.workbook)
    except ThresholdError as exc:
        raise ToolFailure("invalid_thresholds", str(exc)) from exc
    out: dict[str, Any] = {
        "route": route.route,
        "reasons": route.reasons,
        "metrics": route.metrics,
        "atx_command": route.atx_command,
        "atx_command_executed": False,
        "explanation": explain_route(route),
    }
    if a.migration_dir:
        out["design_md"] = str(write_route_explanation(a.migration_dir, route))
    return out


# --------------------------------------------------------------------------
# Registry and dispatch
# --------------------------------------------------------------------------
TOOLS: dict[str, tuple[type[_Args], Callable[[Any], dict[str, Any]], str]] = {
    "analyze_workbook": (
        _MappedWorkbookArgs, analyze_workbook,
        "Autopsy of a workbook: metrics, proposed inputs/outputs, thresholds, findings, "
        "constructs not converted. Read-only.",
    ),
    "list_rules": (
        _MappedWorkbookArgs, list_rules,
        "Derive EARS business rules, each traced to its source cell, plus findings.",
    ),
    "get_dependencies": (
        GetDependenciesArgs, get_dependencies,
        "Precedents and dependents of a cell.",
    ),
    "find_inconsistencies": (
        _WorkbookArgs, find_inconsistencies,
        "Findings where the workbook compares the same value to the same constant with different operators.",
    ),
    "extract_vba": (
        _WorkbookArgs, extract_vba,
        "Read VBA modules from an .xlsm statically. Read-only; nothing is executed.",
    ),
    "evaluate_original": (
        EvaluateOriginalArgs, evaluate_original,
        "Set inputs in the original workbook, recalculate in LibreOffice (the Referee) "
        "and return the requested output cells. Macros are never run.",
    ),
    "boundary_cases": (
        _MappedWorkbookArgs, boundary_cases,
        "Probe each threshold with the Referee and report where outputs change and which side owns the threshold.",
    ),
    "check_against_excel_cache": (
        _WorkbookArgs, check_against_excel_cache,
        "Compare Referee values with the values Excel saved. Reports 'not cross-checked "
        "against Excel' when the file has none.",
    ),
    "verify_implementation": (
        VerifyImplementationArgs, verify_implementation,
        "Run the property-based verifier on a supplied compute(inputs) module and mapping "
        "against the original workbook.",
    ),
    "mutation_check": (
        MutationCheckArgs, mutation_check,
        "Mutation self-check: mutate the implementation and verify each Mutant against the "
        "Referee. Returns killed/total and a reason for every survivor; also writes the proof report.",
    ),
    "record_decision": (
        RecordDecisionArgs, record_decision,
        "Record a human Decision in decisions.yaml (required: behaviour, reason, author, and a finding_id or rule_id).",
    ),
    "generate_proof_report": (
        GenerateProofReportArgs, generate_proof_report,
        "Verify a migration directory against the Referee and write the proof report (HTML and JSON).",
    ),
    "recommend_route": (
        RecommendRouteArgs, recommend_route,
        "Recommend a migration route (Ghost converts, AWS Transform custom, Split) with a "
        "dry-run atx command that is never executed.",
    ),
}


def call_tool_sync(name: str, arguments: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """Validate and run a tool. Returns ``(json_payload, is_error)``."""
    entry = TOOLS.get(name)
    if entry is None:
        return ToolFailure("unknown_tool", f"unknown tool '{name}'").payload(), True
    model, handler, _ = entry
    try:
        args = model.model_validate(arguments or {})
        return jsonable(handler(args)), False
    except ValidationError as exc:
        return _validation_failure(exc).payload(), True
    except ToolFailure as exc:
        return exc.payload(), True
    except IngestError as exc:
        return ToolFailure("ingest_error", f"{type(exc).__name__}: {exc}", "workbook").payload(), True
    except RefereeUnavailable as exc:
        return ToolFailure("referee_unavailable", str(exc)).payload(), True
    except RefereeError as exc:
        return ToolFailure("referee_error", str(exc)).payload(), True
    except CliError as exc:
        return ToolFailure("engine_error", str(exc)).payload(), True
    except OSError as exc:
        return ToolFailure("io_error", str(exc)).payload(), True


# --------------------------------------------------------------------------
# MCP wiring
# --------------------------------------------------------------------------
def build_server():
    """Create the MCP server. Tool listing and calls go through ``TOOLS``."""
    import json

    from mcp.server.mcpserver import MCPServer
    from mcp.types import CallToolResult, TextContent, Tool

    class GhostServer(MCPServer):
        async def list_tools(self):  # type: ignore[override]
            return [
                Tool(name=n, description=desc, input_schema=model.model_json_schema())
                for n, (model, _h, desc) in TOOLS.items()
            ]

        async def call_tool(self, name, arguments, context=None):  # type: ignore[override]
            payload, is_error = await anyio.to_thread.run_sync(
                lambda: _quiet(lambda: call_tool_sync(name, arguments))
            )
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload, sort_keys=True))],
                structured_content=payload,
                is_error=is_error,
            )

    return GhostServer(
        SERVER_NAME,
        instructions="Ghost in the Macro: migrate Excel business logic with proof against the original workbook.",
    )


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
