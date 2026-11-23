"""Proof report model and JSON serialisation.

The report is a thin wrapper over ``ghost.models.Report``. It holds only values
produced by the engine. A check with no result is serialised as
``{"status": "not checked"}``. The JSON form is validated against the versioned
schema ``schema/proof-report-1.json``.
"""

from __future__ import annotations

import json
import platform
from datetime import date
from decimal import Decimal
from enum import Enum
from importlib import resources
from typing import Any

import jsonschema

from ghost import __version__
from ghost.models import (
    Mismatch,
    MutationResult,
    NotChecked,
    Report,
    SanityResult,
    Versions,
)

SCHEMA_VERSION = "1"
SCHEMA_FILE = "proof-report-1.json"
NOT_CHECKED: dict[str, str] = {"status": "not checked"}

ProofReport = Report


class ReportValidationError(ValueError):
    """The report JSON does not conform to the proof-report schema."""


def load_schema() -> dict[str, Any]:
    text = (resources.files("ghost.report") / "schema" / SCHEMA_FILE).read_text(
        encoding="utf-8"
    )
    return json.loads(text)


def make_versions(libreoffice: str | None) -> Versions:
    """Versions block. A missing LibreOffice version is reported as 'not checked'."""
    return Versions(
        libreoffice=libreoffice or "not checked",
        python=platform.python_version(),
        ghost=__version__,
    )


def _jsonable(value: Any) -> Any:
    """Convert engine values to JSON types without losing precision."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return [_jsonable(v) for v in items]
    if isinstance(value, float) and value != value:
        return "NaN"
    return value


def _mismatch_json(m: Mismatch) -> dict[str, Any]:
    return {
        "inputs": _jsonable(m.case.inputs),
        "expected": _jsonable(m.case.referee),
        "actual": _jsonable(m.case.actual),
        "output": m.output,
        "cell": m.cell,
        "rule_id": m.rule_id,
        "finding_id": m.finding_id,
        "decision_id": m.decision_id,
        "minimal": m.minimal,
        "class": m.mismatch_class,
    }


def _mutation_json(m: MutationResult | NotChecked) -> dict[str, Any]:
    if isinstance(m, NotChecked):
        return dict(NOT_CHECKED)
    return _jsonable(m.model_dump(mode="python"))


def _sanity_json(s: SanityResult | NotChecked) -> dict[str, Any]:
    if isinstance(s, NotChecked):
        return dict(NOT_CHECKED)
    return _jsonable(s.model_dump(mode="python"))


def report_to_dict(report: ProofReport) -> dict[str, Any]:
    """Serialise a report to the JSON shape defined by proof-report-1.json."""
    return {
        "schema_version": report.schema_version,
        "ghost_version": report.ghost_version,
        "seed": report.seed,
        "versions": report.versions.model_dump(),
        "mode": report.mode,
        "cases_tested": report.cases_tested,
        "passed": report.passed,
        "mismatches": [_mismatch_json(m) for m in report.mismatches],
        "boundaries": [_jsonable(b.model_dump(mode="python")) for b in report.boundaries],
        "rule_coverage": [r.model_dump() for r in report.rule_coverage],
        "mutation": _mutation_json(report.mutation),
        "sanity": _sanity_json(report.sanity),
        "findings": [_jsonable(f.model_dump(mode="python")) for f in report.findings],
        "decisions": [_jsonable(d.model_dump(mode="python")) for d in report.decisions],
    }


def validate_report_dict(data: dict[str, Any]) -> None:
    """Raise ReportValidationError when data does not match the schema."""
    validator = jsonschema.Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise ReportValidationError(f"{path}: {first.message}")


def report_to_json(report: ProofReport) -> str:
    """Validated, deterministic JSON text (sorted keys, no timestamps)."""
    data = report_to_dict(report)
    validate_report_dict(data)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
