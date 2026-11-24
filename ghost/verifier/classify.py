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

from typing import Any, Callable, Iterable

from ghost.models import CellRef, Decision, Finding, Mismatch, Mode, Rule
from ghost.verifier.compare import DEFAULT_TOL, values_equal

__all__ = ["explaining_decision", "finding_active", "make_classifier", "verdict"]

_UNSET: Any = object()


def _patch_cell(decision: Decision) -> str | None:
    p = decision.patch or {}
    if p.get("op") != "set_operator" or not p.get("cell"):
        return None
    return str(p["cell"]).replace("$", "")


def _hook_cell(hook: str) -> str:
    return hook.rsplit("#", 1)[0]


def explaining_decision(
    decisions: Iterable[Decision],
    outputs: Iterable[str],
    referee: dict[str, Any],
    candidate: dict[str, Any],
    candidate_trace: dict[str, bool],
    faithful: dict[str, Any],
    faithful_trace: dict[str, bool],
    tol: float = DEFAULT_TOL,
    intended: dict[str, Any] | None = None,
    intended_trace: dict[str, bool] | None = None,
) -> str | None:
    """Return the id of the Decision that explains a mismatch on one case, else None.

    A mismatch is explained only when (a) the Faithful module matches the Referee,
    (b) the module under test differs from the Faithful module, and (c) for a
    Decision's patched cell the candidate's hook is PRESENT and carries the truth
    value of the transpiled Intended module, which differs from the Faithful one.
    A missing hook never explains anything. When the Intended module's outputs are
    given, the candidate's outputs must also equal them (Requirement 8.10, clause 2.5).
    """
    outs = list(outputs)
    if not all(values_equal(referee.get(n), faithful.get(n), tol) for n in outs):
        return None
    if all(values_equal(candidate.get(n), faithful.get(n), tol) for n in outs):
        return None
    if intended is not None and not all(
        n in candidate and values_equal(candidate.get(n), intended.get(n), tol) for n in outs
    ):
        return None
    reference = intended_trace
    for d in sorted(decisions, key=lambda d: d.decision_id):
        target = _patch_cell(d)
        if target is None:
            continue
        for h in sorted(faithful_trace):
            c = _hook_cell(h)
            if not (c == target or c.endswith("!" + target)):
                continue
            if h not in candidate_trace:
                continue  # missing hook: cannot explain
            if reference is not None:
                if h in reference and reference[h] != faithful_trace[h] and candidate_trace[h] == reference[h]:
                    return d.decision_id
            elif candidate_trace[h] != faithful_trace[h]:
                return d.decision_id
    return None


def _hook_index(hook: str) -> int:
    try:
        return int(hook.rsplit("#", 1)[1])
    except (IndexError, ValueError):
        return 0


def finding_active(finding: Finding, trace: dict[str, bool]) -> bool:
    """True when the comparisons at the Finding's locations disagree on this case.

    Each cell location contributes the truth value of its first traced IF condition
    (the comparison that carries the Finding's operator). The Finding is active only
    if two locations evaluate to different truth values (Requirement 8.10, clause 2.6).
    A location with no traced condition contributes nothing, so a case without
    evidence is never blamed on the workbook.
    """
    values: list[bool] = []
    for loc, _op in finding.locations:
        if not loc.cell:
            continue
        cell = loc.cell.replace("$", "")
        hooks = sorted((h for h in trace if _hook_cell(h) == cell), key=_hook_index)
        if hooks:
            values.append(bool(trace[hooks[0]]))
    return len(set(values)) > 1


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

    def classify(
        m: Mismatch,
        explained_by: str | None = _UNSET,
        trace: dict[str, bool] | None = None,
    ) -> Mismatch:
        if explained_by is not _UNSET and mode == "intended":
            # The verifier ran the three-condition test on this case.
            upstream = _precedents(m.cell, deps)
            reach = upstream | {m.cell}
            direct = [r for r in rules if m.cell in r.cells]
            linked = direct or [r for r in rules if reach.intersection(r.cells)]
            rule_id = m.rule_id or (linked[0].rule_id if linked else None)
            if explained_by is None:
                return m.model_copy(update={"rule_id": rule_id, "mismatch_class": "translation bug"})
            d = next(d for d in decisions if d.decision_id == explained_by)
            matched = [
                f for f in findings
                if f.cell in reach or any(loc.cell in reach for loc, _ in f.locations if loc.cell)
            ]
            fid = d.finding_id or (matched[0].finding_id if matched else None)
            return m.model_copy(update={
                "rule_id": rule_id,
                "mismatch_class": "expected by decision",
                "decision_id": d.decision_id,
                "finding_id": fid,
            })
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
        if trace is not None:
            # The verifier supplied the case's comparison trace: blame the workbook
            # only for Findings whose locations disagree on this case.
            matched = [f for f in matched if finding_active(f, trace)]
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

    classify.decisions = decisions  # type: ignore[attr-defined]
    classify.mode = mode  # type: ignore[attr-defined]
    classify.findings = findings  # type: ignore[attr-defined]
    return classify


def verdict(mode: Mode, mismatches: Iterable[Mismatch]) -> bool:
    """Faithful: pass only with zero Mismatches. Intended: every one explained."""
    ms = list(mismatches)
    if mode == "faithful":
        return not ms
    return all(m.mismatch_class == "expected by decision" for m in ms)
