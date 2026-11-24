"""Decisions store: record human Decisions in a migration spec.

``record`` validates required fields, assigns the next ``D-NNN``, appends to
``decisions.yaml`` and refreshes the decision summary in ``design.md``.
On any validation failure nothing is written (Requirement 4.5).
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from ghost.models import Decision

__all__ = [
    "InvalidDecision",
    "SUMMARY_BEGIN",
    "SUMMARY_END",
    "load_decisions",
    "record",
    "write_summary",
]

DECISIONS_FILE = "decisions.yaml"
DESIGN_FILE = "design.md"
SUMMARY_BEGIN = "<!-- ghost:decisions:begin -->"
SUMMARY_END = "<!-- ghost:decisions:end -->"

_REQUIRED = ("behaviour", "reason", "author", "date")
_ID_RE = re.compile(r"^D-(\d+)$")


class InvalidDecision(ValueError):
    """A Decision lacks required fields or has invalid values."""

    def __init__(self, missing: list[str], message: str | None = None):
        self.missing = list(missing)
        super().__init__(
            message or "Decision is missing required field(s): " + ", ".join(self.missing)
        )


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _as_dict(decision: Decision | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(decision, Decision):
        return decision.model_dump()
    return dict(decision)


def _parse_date(v: Any) -> date:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError as exc:
        raise InvalidDecision([], f"Decision field 'date' is not an ISO date: {v!r}") from exc


def _validate(raw: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in _REQUIRED if _blank(raw.get(k))]
    if _blank(raw.get("finding_id")) and _blank(raw.get("rule_id")):
        missing.append("finding_id or rule_id")
    if missing:
        raise InvalidDecision(missing)
    patch = raw.get("patch") or {}
    if not isinstance(patch, dict):
        raise InvalidDecision([], "Decision field 'patch' must be a mapping")
    return {
        "finding_id": None if _blank(raw.get("finding_id")) else str(raw["finding_id"]),
        "rule_id": None if _blank(raw.get("rule_id")) else str(raw["rule_id"]),
        "behaviour": str(raw["behaviour"]),
        "reason": str(raw["reason"]),
        "author": str(raw["author"]),
        "date": _parse_date(raw["date"]),
        "patch": dict(patch),
    }


def _to_yaml_dict(d: Decision) -> dict[str, Any]:
    out = d.model_dump()
    out["date"] = d.date.isoformat()
    return out


def load_decisions(migration_dir: str | Path) -> list[Decision]:
    """Read ``decisions.yaml``; a missing or empty file yields ``[]``."""
    path = Path(migration_dir) / DECISIONS_FILE
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("decisions", []) if isinstance(data, dict) else data
    return [Decision(**item) for item in items or []]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _dump(decisions: list[Decision]) -> str:
    return yaml.safe_dump(
        {"decisions": [_to_yaml_dict(d) for d in decisions]},
        sort_keys=False,
        allow_unicode=True,
    )


def _summary_block(decisions: list[Decision]) -> str:
    lines = [SUMMARY_BEGIN, "## Decisions", ""]
    if not decisions:
        lines.append("No decisions recorded.")
    else:
        lines += ["| Decision | Applies to | Behaviour | Reason | Author | Date |", "|---|---|---|---|---|---|"]
        for d in decisions:
            target = d.finding_id or d.rule_id or ""
            cells = [d.decision_id, target, d.behaviour, d.reason, d.author, d.date.isoformat()]
            cells = [c.replace("|", "\\|").replace("\n", " ") for c in cells]
            lines.append("| " + " | ".join(cells) + " |")
    lines.append(SUMMARY_END)
    return "\n".join(lines)


def write_summary(migration_dir: str | Path, decisions: list[Decision] | None = None) -> None:
    """Create or replace the decision summary block in ``design.md``."""
    mdir = Path(migration_dir)
    if decisions is None:
        decisions = load_decisions(mdir)
    block = _summary_block(decisions)
    path = mdir / DESIGN_FILE
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(re.escape(SUMMARY_BEGIN) + r".*?" + re.escape(SUMMARY_END), re.S)
    if pattern.search(text):
        new = pattern.sub(lambda _m: block, text)
    else:
        new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"
    _atomic_write(path, new)


def _next_id(existing: list[Decision]) -> str:
    nums = [int(m.group(1)) for d in existing if (m := _ID_RE.match(d.decision_id))]
    return f"D-{(max(nums) + 1 if nums else 1):03d}"


def _reject_duplicate(existing: list[Decision], fields: dict[str, Any]) -> None:
    for key, label in (("finding_id", "Finding"), ("rule_id", "rule")):
        value = fields.get(key)
        if not value:
            continue
        for d in existing:
            if getattr(d, key) == value:
                raise InvalidDecision(
                    [],
                    f"{label} {value} already has Decision {d.decision_id}; "
                    "a second Decision for the same target is not accepted",
                )


def record(
    migration_dir: str | Path,
    decision: Decision | Mapping[str, Any],
    *,
    validate: Callable[[list[Decision]], None] | None = None,
) -> Decision:
    """Validate, assign ``D-NNN``, append to ``decisions.yaml``, update ``design.md``.

    Raises ``InvalidDecision`` (naming missing fields, or the existing
    ``decision_id`` when the finding or rule already has a Decision) and leaves
    files unchanged. Any ``decision_id`` supplied by the caller is ignored.
    ``validate`` receives the full Decision list including the new one and may
    raise ``InvalidDecision`` (used to check the patch against the workbook).
    """
    fields = _validate(_as_dict(decision))
    mdir = Path(migration_dir)
    existing = load_decisions(mdir)
    _reject_duplicate(existing, fields)
    new = Decision(decision_id=_next_id(existing), **fields)
    allowed = existing + [new]
    if validate is not None:
        validate(allowed)
    _atomic_write(mdir / DECISIONS_FILE, _dump(allowed))
    write_summary(mdir, allowed)
    return new
