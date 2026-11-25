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
    exact_hit_text,
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
    "describe_cases",
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


def describe_cases(d: dict[str, Any]) -> str:
    """"300 generated + 9 targeted, 176 distinct"; only the total when not counted."""
    gen, tgt, dist = d.get("cases_generated"), d.get("cases_targeted"), d.get("distinct_cases")
    if gen is None and tgt is None and dist is None:
        return str(d["cases_tested"])
    text = f"{gen if gen is not None else d['cases_tested']} generated" + (f" + {tgt} targeted" if tgt else "")
    return text + (f", {dist} distinct" if dist is not None else "")


def build_report(
    *,
    seed: int,
    mode: str,
    cases_tested: int,
    passed: bool,
    cases_generated: int | None = None,
    cases_targeted: int | None = None,
    distinct_cases: int | None = None,
    mismatches: Iterable[Mismatch] = (),
    boundaries: Iterable[BoundaryResult] = (),
    boundary_notes: Iterable[str] = (),
    tested_domains: Iterable[dict[str, Any]] = (),
    not_converted: Iterable[dict[str, str]] = (),
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
        cases_generated=cases_generated,
        cases_targeted=cases_targeted,
        distinct_cases=distinct_cases,
        passed=passed,
        mismatches=list(mismatches),
        boundaries=list(boundaries),
        boundary_notes=list(boundary_notes),
        tested_domains=list(tested_domains),
        not_converted=[{"cell": str(e["cell"]), "reason": str(e["reason"])} for e in not_converted],
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


def _value_text(v: Any) -> str:
    """One serialised engine value: text as-is (Excel errors are already their code
    text, e.g. "#REF!"), anything else in its JSON form."""
    return v if isinstance(v, str) else json.dumps(v, sort_keys=True, ensure_ascii=False)


def _case_text(case: Any) -> str:
    """A mutant's counterexample as plain text, from the serialised ``killed_by`` case.

    "inputs: amount=4; Referee: y=7; new code: y=#REF!". Empty for a survivor.
    """
    if not isinstance(case, dict):
        return ""
    parts = []
    for key, label in (("inputs", "inputs"), ("referee", "Referee"), ("actual", "new code")):
        values = case.get(key) or {}
        if isinstance(values, dict):
            shown = ", ".join(f"{k}={_value_text(values[k])}" for k in sorted(values))
        else:
            shown = _value_text(values)
        parts.append(f"{label}: {shown or '(none)'}")
    return "; ".join(parts)


def _plain(v: Any) -> str:
    """Readable text for a JSON value: no braces or brackets."""
    if isinstance(v, dict):
        return ", ".join(f"{k}: {_plain(x)}" for k, x in sorted(v.items()))
    if isinstance(v, list):
        return "; ".join(_plain(x) for x in v)
    return "" if v is None else str(v)


def _bracket_text(b: dict[str, Any]) -> str:
    """The change-point bracket as text: ``49 → 50`` (last unchanged → first changed)."""
    if b.get("kind") == "condition flip":
        if b.get("below") is not None and b.get("above") is not None:
            return f"{b['below']} → {b['above']}"
        return ""
    parts = []
    for h in b.get("exact_hits") or []:
        if isinstance(h, dict) and set(h) == {"last_unchanged", "first_changed"}:
            parts.append(f"{_plain(h['last_unchanged'])} → {_plain(h['first_changed'])}")
        else:
            parts.append(_plain(h))
    return "; ".join(parts)


def _threshold_text(b: dict[str, Any]) -> str:
    """The threshold constant; flip rows say "calculated" when there is none."""
    if b.get("kind") != "condition flip":
        return str(b["threshold"])
    if b.get("threshold_constant") is not None:
        return str(b["threshold_constant"])
    return "calculated" if b.get("threshold_calculated") else _NC


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
                ["Mode", "Seed", "Cases", "LibreOffice", "Python", "Ghost"],
                [[d["mode"], d["seed"], describe_cases(d), ver["libreoffice"], ver["python"], ver["ghost"]]],
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
                (m["decision_id"] or "")
                + (f" ({m['cases']} cases)" if m.get("cases") is not None else ""),
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

    notes_html = (
        "<ul>" + "".join(f"<li>{_e(n)}</li>" for n in d.get("boundary_notes", [])) + "</ul>"
        if d.get("boundary_notes") else ""
    )
    if d["boundaries"]:
        parts.append(
            _section(
                "Boundaries",
                notes_html + _table(
                    ["Cell", "Input", "Threshold", "Change point", "Owner of threshold",
                     "Change-point bracket", "Exact hits"],
                    [
                        [b.get("condition_id") or b["cell"], b["input_name"],
                         _threshold_text(b), b["change_point"] or _NC,
                         # Operator ownership only; a flip row has none.
                         (b["operator_includes"] or _NC) if b.get("kind") != "condition flip" else _NC,
                         _bracket_text(b),
                         # Real exact hits exist only where flip probing found the input value
                         # that makes the condition hold with equality.
                         exact_hit_text(b.get("exact"), b.get("exact_others"), b.get("exact_note"))
                         or _NC]
                        for b in d["boundaries"]
                    ],
                ),
            )
        )
    else:
        parts.append(_section("Boundaries", _para(_NC) + notes_html))

    if d.get("tested_domains"):
        parts.append(
            _section(
                "Tested domains",
                _para("Ranges of the verification cases. Mutation cases and their survivor "
                      "reasons stay inside the same ranges.")
                + _table(
                    ["Input", "Type", "Min", "Max", "Decimal places", "Distinct values"],
                    [
                        [t["input"], t["type"],
                         _NC if t.get("not_tested") else t.get("min", ""),
                         _NC if t.get("not_tested") else t.get("max", ""),
                         t.get("decimal_places", ""), t.get("distinct_values", "")]
                        for t in d["tested_domains"]
                    ],
                ) + "".join(
                    _para(f"Max of {t['input']} includes the workbook's own value "
                          f"{t['max_includes_sample']}.")
                    for t in d["tested_domains"] if t.get("max_includes_sample")
                ),
            )
        )
    else:
        parts.append(_section("Tested domains", _para(_NC)))

    if d.get("not_converted"):
        parts.append(
            _section(
                "Not converted",
                _para("These cells are not converted and are not compared with the Referee.")
                + _table(["Cell", "Reason"], [[e["cell"], e["reason"]] for e in d["not_converted"]]),
            )
        )

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
                + (_para(mut["survivor_explanation"]) if mut.get("survivor_explanation") else "")
                + _table(
                    ["Mutant", "Operator", "Location", "Killed", "Counterexample", "Survivor reason"],
                    [
                        [m["mutant_id"], m["operator"], m["location"], m["killed"],
                         _case_text(m.get("killed_by")), m["survivor_reason"] or ""]
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
