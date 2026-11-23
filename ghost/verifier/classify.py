"""Mismatch classification and verdict (Requirements 8.10 to 8.14).

``make_classifier`` returns a ``Mismatch -> Mismatch`` callable for
``VerifyConfig.classifier``. It

* links the Mismatch to a ``rule_id`` (Rules whose cells include the output
  cell, else Rules touching a cell the output depends on),
* matches it to a Finding when the Finding's cell, or any cell listed in its
  locations, is the output cell or one of its transitive precedents,
* classifies it as
  "expected by decision" (Intended mode only, a Decision names the matched
  Finding or the linked ``rule_id``; ``decision_id`` is set),
  "original workbook inconsistency" (matches a Finding; ``finding_id`` set),
  or otherwise "translation bug".

``verdict`` applies Requirements 8.13 and 8.14.
"""

from __future__ import annotations

from typing import Callable, Iterable

from ghost.models import CellRef, Decision, Finding, Mismatch, Mode, Rule

__all__ = ["make_classifier", "verdict"]


def _precedents(cell: CellRef, deps: dict[CellRef, set[CellRef]]) -> set[CellRef]:
    seen: set[CellRef] = set()
    stack = [cell]
    while stack:
        for p in deps.get(stack.pop(), ()):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def make_classifier(
    mode: Mode = "faithful",
    findings: Iterable[Finding] = (),
    decisions: Iterable[Decision] = (),
    rules: Iterable[Rule] = (),
    deps: dict[CellRef, set[CellRef]] | None = None,
) -> Callable[[Mismatch], Mismatch]:
    findings = sorted(findings, key=lambda f: f.finding_id)
    decisions = sorted(decisions, key=lambda d: d.decision_id)
    rules = sorted(rules, key=lambda r: r.rule_id)
    deps = deps or {}

    def classify(m: Mismatch) -> Mismatch:
        upstream = _precedents(m.cell, deps)
        reach = upstream | {m.cell}

        direct = [r for r in rules if m.cell in r.cells]
        linked = direct or [r for r in rules if reach.intersection(r.cells)]
        rule_id = m.rule_id or (linked[0].rule_id if linked else None)
        rule_ids = {r.rule_id for r in linked}
        if rule_id:
            rule_ids.add(rule_id)

        matched = [
            f for f in findings
            if f.cell in reach or any(loc.cell in reach for loc, _ in f.locations if loc.cell)
        ]
        matched_ids = {f.finding_id for f in matched}

        if mode == "intended":
            for d in decisions:
                if (d.finding_id and d.finding_id in matched_ids) or (
                    d.rule_id and d.rule_id in rule_ids
                ):
                    fid = d.finding_id if d.finding_id in matched_ids else (
                        matched[0].finding_id if matched else None
                    )
                    return m.model_copy(update={
                        "rule_id": rule_id,
                        "mismatch_class": "expected by decision",
                        "decision_id": d.decision_id,
                        "finding_id": fid,
                    })
        if matched:
            return m.model_copy(update={
                "rule_id": rule_id,
                "mismatch_class": "original workbook inconsistency",
                "finding_id": matched[0].finding_id,
            })
        return m.model_copy(update={"rule_id": rule_id, "mismatch_class": "translation bug"})

    return classify


def verdict(mode: Mode, mismatches: Iterable[Mismatch]) -> bool:
    """Faithful: pass only with zero Mismatches. Intended: every one explained."""
    ms = list(mismatches)
    if mode == "faithful":
        return not ms
    return all(m.mismatch_class == "expected by decision" for m in ms)
