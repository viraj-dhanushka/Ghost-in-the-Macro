"""Migration spec writer (Requirements 3.8, 3.9).

``write_spec`` writes ``rules.md``, ``traceability.yaml`` and ``findings.yaml``
into a migration directory (``.kiro/specs/<migration>/``). Output is
deterministic: no timestamps, stable ordering, stable YAML formatting.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml

from ghost.models import Finding, Location, Rule

__all__ = ["write_spec", "render_rules_md", "traceability_data", "findings_data"]


def _loc(loc: Location) -> dict[str, object]:
    out: dict[str, object] = {}
    if loc.cell is not None:
        out["cell"] = loc.cell
    if loc.module is not None:
        out["module"] = loc.module
    if loc.line is not None:
        out["line"] = loc.line
    return out


def render_rules_md(rules: Sequence[Rule]) -> str:
    lines = ["# Business rules", ""]
    if not rules:
        lines += ["No rules were generated.", ""]
    for rule in rules:
        lines += [f"## {rule.rule_id}", "", rule.text, ""]
        sources = list(rule.cells) + [
            f"{m.module}:{m.line}" for m in rule.macro_lines if m.module is not None
        ]
        if sources:
            lines += [f"Source: {', '.join(sources)}", ""]
    return "\n".join(lines)


def traceability_data(rules: Sequence[Rule]) -> dict[str, object]:
    entries = []
    for rule in rules:
        entries.append(
            {
                "rule_id": rule.rule_id,
                "cells": list(rule.cells),
                "macro_lines": [_loc(m) for m in rule.macro_lines],
                "conditions": [
                    {"condition_id": c.condition_id, "text": c.text, "cell": c.cell}
                    for c in rule.conditions
                ],
            }
        )
    return {"version": 1, "rules": entries}


def findings_data(findings: Sequence[Finding]) -> dict[str, object]:
    entries = []
    for f in findings:
        entries.append(
            {
                "finding_id": f.finding_id,
                "kind": f.kind,
                "cell": f.cell,
                "constant": str(f.constant),
                "locations": [{**_loc(loc), "operator": op} for loc, op in f.locations],
            }
        )
    return {"version": 1, "findings": entries}


def _dump(data: object) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def write_spec(
    migration_dir: str | Path,
    rules: Sequence[Rule],
    findings: Sequence[Finding],
) -> dict[str, Path]:
    """Write the three spec files; return their paths keyed by file name."""
    root = Path(migration_dir)
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "rules.md": render_rules_md(rules),
        "traceability.yaml": _dump(traceability_data(rules)),
        "findings.yaml": _dump(findings_data(findings)),
    }
    paths: dict[str, Path] = {}
    for name, content in files.items():
        p = root / name
        p.write_text(content, encoding="utf-8", newline="\n")
        paths[name] = p
    return paths
