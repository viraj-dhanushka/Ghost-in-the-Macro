"""Proof report: assembly, HTML rendering, writing and regeneration.

Everything shown comes from the report dict produced by ``report_to_dict``.
Absent checks are rendered as "not checked". All values are HTML-escaped.
The output is deterministic (no timestamps).
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Callable, Iterable

from ghost.decisions.store import load_decisions
from ghost.models import (
    BoundaryResult,
    Decision,
    Finding,
    Mismatch,
    MutationResult,
    NotChecked,
    Report,
    RuleCoverage,
    SanityResult,
    Versions,
)
from ghost.report.model import (
    ProofReport,
    ReportValidationError,
    make_versions,
    report_to_dict,
    report_to_json,
    validate_report_dict,
)

__all__ = [
    "build_report",
    "render_html",
    "write_report",
    "regenerate",
    "REPORT_JSON",
    "REPORT_HTML",
]

REPORT_JSON = "proof-report.json"
REPORT_HTML = "proof-report.html"
_NC = "not checked"


def build_report(
    *,
    seed: int,
    mode: str,
    cases_tested: int,
    passed: bool,
    mismatches: Iterable[Mismatch] = (),
    boundaries: Iterable[BoundaryResult] = (),
    rule_coverage: Iterable[RuleCoverage] = (),
    mutation: MutationResult | NotChecked | None = None,
    sanity: SanityResult | NotChecked | None = None,
    findings: Iterable[Finding] = (),
    decisions: Iterable[Decision] = (),
    libreoffice_version: str | None = None,
    versions: Versions | None = None,
) -> ProofReport:
    """Assemble a report from engine outputs. Absent checks become "not checked"."""
    from ghost import __version__

    v = versions or make_versions(libreoffice_version)
    return Report(
        ghost_version=__version__,
        seed=seed,
        versions=v,
        mode=mode,  # type: ignore[arg-type]
        cases_tested=cases_tested,
        passed=passed,
        mismatches=list(mismatches),
        boundaries=list(boundaries),
        rule_coverage=list(rule_coverage),
        mutation=mutation if mutation is not None else NotChecked(),
        sanity=sanity if sanity is not None else NotChecked(),
        findings=list(findings),
        decisions=list(decisions),
    )


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------


def _e(v: Any) -> str:
    if isinstance(v, (dict, list)):
        v = json.dumps(v, sort_keys=True, ensure_ascii=False)
    return escape("" if v is None else str(v), quote=True)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _section(title: str, inner: str) -> str:
    return f"<section><h2>{_e(title)}</h2>{inner}</section>"


def _para(text: str) -> str:
    return f"<p>{_e(text)}</p>"


def render_html(report: ProofReport | dict[str, Any]) -> str:
    """Render a self-contained HTML page for the report."""
    d = report if isinstance(report, dict) else report_to_dict(report)
    parts: list[str] = []

    verdict = "PASS" if d["passed"] else "FAIL"
    ver = d["versions"]
    parts.append(
        _section(
            "Summary",
            f'<p class="verdict {verdict.lower()}">{verdict}</p>'
            + _table(
                ["Mode", "Seed", "Cases tested", "LibreOffice", "Python", "Ghost"],
                [[d["mode"], d["seed"], d["cases_tested"], ver["libreoffice"], ver["python"], ver["ghost"]]],
            ),
        )
    )

    mm = d["mismatches"]
    if mm:
        rows = [
            [
                m["class"],
                m["output"],
                m["cell"],
                m["inputs"],
                m["expected"],
                m["actual"],
                m["rule_id"] or "",
                m["finding_id"] or "",
                m["decision_id"] or "",
                "yes" if m["minimal"] else "no",
            ]
            for m in mm
        ]
        parts.append(
            _section(
                "Mismatches",
                _table(
                    ["Class", "Output", "Cell", "Inputs", "Expected (Referee)", "Actual", "Rule", "Finding", "Decision", "Minimal"],
                    rows,
                ),
            )
        )
    else:
        parts.append(_section("Mismatches", _para("No mismatches.")))

    if d["boundaries"]:
        parts.append(
            _section(
                "Boundaries",
                _table(
                    ["Cell", "Input", "Threshold", "Change point", "Owner of threshold", "Exact hits"],
                    [
                        [b["cell"], b["input_name"], b["threshold"], b["change_point"] or _NC, b["operator_includes"] or _NC, b["exact_hits"]]
                        for b in d["boundaries"]
                    ],
                ),
            )
        )
    else:
        parts.append(_section("Boundaries", _para(_NC)))

    if d["rule_coverage"]:
        parts.append(
            _section(
                "Rule coverage",
                _table(
                    ["Rule", "Condition", "Seen true", "Seen false", "Status"],
                    [
                        [
                            r["rule_id"],
                            r["condition_id"],
                            r["seen_true"],
                            r["seen_false"],
                            "covered" if r["seen_true"] and r["seen_false"] else "uncovered",
                        ]
                        for r in d["rule_coverage"]
                    ],
                ),
            )
        )
    else:
        parts.append(_section("Rule coverage", _para(_NC)))

    mut = d["mutation"]
    if mut.get("status") == _NC:
        parts.append(_section("Mutation self-check", _para(_NC)))
    else:
        parts.append(
            _section(
                "Mutation self-check",
                _para(f"{mut['killed']} of {mut['total']} mutants killed.")
                + _table(
                    ["Mutant", "Operator", "Location", "Killed", "Survivor reason"],
                    [
                        [m["mutant_id"], m["operator"], m["location"], m["killed"], m["survivor_reason"] or ""]
                        for m in mut["mutants"]
                    ],
                ),
            )
        )

    san = d["sanity"]
    if san.get("status") == _NC:
        parts.append(_section("Excel cross-check", _para(_NC)))
    elif san["status"] == "not cross-checked against Excel":
        parts.append(_section("Excel cross-check", _para("not cross-checked against Excel")))
    else:
        inner = _para(f"{san['status']}: {san['matched']} of {san['total']} matched.")
        if san["differences"]:
            inner += _table(["Difference"], [[x] for x in san["differences"]])
        parts.append(_section("Excel cross-check", inner))

    if d["findings"]:
        parts.append(
            _section(
                "Findings",
                _table(
                    ["Finding", "Kind", "Cell", "Constant", "Locations"],
                    [[f["finding_id"], f["kind"], f["cell"], f["constant"], f["locations"]] for f in d["findings"]],
                ),
            )
        )
    else:
        parts.append(_section("Findings", _para("No findings.")))

    if d["decisions"]:
        parts.append(
            _section(
                "Decisions",
                _table(
                    ["Decision", "Finding", "Rule", "Behaviour", "Reason", "Author", "Date"],
                    [
                        [x["decision_id"], x["finding_id"] or "", x["rule_id"] or "", x["behaviour"], x["reason"], x["author"], x["date"]]
                        for x in d["decisions"]
                    ],
                ),
            )
        )
    else:
        parts.append(_section("Decisions", _para("No decisions recorded.")))

    css = (
        "body{font-family:sans-serif;max-width:1100px;margin:2em auto;padding:0 1em}"
        "table{border-collapse:collapse;width:100%;margin:.5em 0}"
        "th,td{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}"
        ".verdict{font-size:1.6em;font-weight:bold}.pass{color:#0a7d2c}.fail{color:#b00020}"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Ghost proof report</title>"
        f"<style>{css}</style></head><body>"
        "<h1>Ghost proof report</h1>"
        + "".join(parts)
        + "</body></html>\n"
    )


# --------------------------------------------------------------------------
# Writing and regeneration
# --------------------------------------------------------------------------


def write_report(report: ProofReport, out_dir: str | Path) -> tuple[Path, Path]:
    """Validate against the schema, then write JSON and HTML. Returns both paths.

    Nothing is written when validation fails.
    """
    data = report_to_dict(report)
    validate_report_dict(data)  # raises ReportValidationError before any write
    json_text = report_to_json(report)
    html_text = render_html(data)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp, hp = out / REPORT_JSON, out / REPORT_HTML
    jp.write_text(json_text, encoding="utf-8")
    hp.write_text(html_text, encoding="utf-8")
    return jp, hp


def regenerate(
    migration_dir: str | Path,
    rebuild: Callable[[list[Decision]], ProofReport],
) -> tuple[Path, Path]:
    """Rebuild the proof report after ``decisions.yaml`` changed.

    ``rebuild`` receives the current decisions and must return a report from
    engine output (typically by re-running classification or verification).
    The result is validated and written into the migration directory.
    """
    mdir = Path(migration_dir)
    return write_report(rebuild(load_decisions(mdir)), mdir)
