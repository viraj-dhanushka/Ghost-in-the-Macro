"""Progress_Module: maps CLI Event_Lines and a Job status to presentation data.

Pure parsing. No I/O, and no import from ``ghost`` or the Referee.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum


class Phase(IntEnum):
    QUEUED = 0
    VERIFICATION_STARTED = 1
    MUTATION_SELF_CHECK = 2
    CASES_COMPARED = 3
    PROOF_WRITTEN = 4


PHASE_LABELS: dict[Phase, str] = {
    Phase.QUEUED: "Queued",
    Phase.VERIFICATION_STARTED: "Verification started",
    Phase.MUTATION_SELF_CHECK: "Mutation self-check",
    Phase.CASES_COMPARED: "Cases compared",
    Phase.PROOF_WRITTEN: "Proof written",
}

_START = "Starting verification"
# ASCII digits only, at most four per number: the engine never prints more, and a longer run
# of digits would raise in int() or ask for billions of tombstones.
_MUTANT_RE = re.compile(r"mutation check: mutant ([0-9]{1,4})/([0-9]{1,4})")


def _marker_phase(line: str) -> Phase | None:
    if line == _START:
        return Phase.VERIFICATION_STARTED
    if _MUTANT_RE.fullmatch(line):
        return Phase.MUTATION_SELF_CHECK
    if line.startswith(("[faithful]", "[intended]")):
        return Phase.CASES_COMPARED
    if line.startswith("Proof report:"):
        return Phase.PROOF_WRITTEN
    return None


def phase_of(events: list[str], status: str) -> Phase:
    """Highest Phase whose Phase_Marker is present. Without a marker the floor
    is QUEUED for every status (a Phase is never shown as reached unseen)."""
    best = Phase.QUEUED
    for line in events:
        p = _marker_phase(line)
        if p is not None and p > best:
            best = p
    return best


@dataclass(frozen=True)
class MutantCounts:
    done: int | None
    total: int | None


def mutant_counts(events: list[str]) -> MutantCounts:
    """done = largest i, total = n of the latest line. Lines with i > n are ignored."""
    done: int | None = None
    total: int | None = None
    for line in events:
        m = _MUTANT_RE.fullmatch(line)
        if not m:
            continue
        i, n = int(m.group(1)), int(m.group(2))
        if i > n:
            continue
        done = i if done is None else max(done, i)
        total = n
    # Keep done <= total even when a later line lowers n.
    if done is not None and total is not None and done > total:
        done = total
    return MutantCounts(done=done, total=total)


def status_line_text(phase: Phase, status: str | None = None) -> str:
    """Pure function of the Phase and the Job status. A running job with no marker line yet is
    "Starting", never "Queued" (owner decision, task 17 follow-up); every other case is the Phase name."""
    if phase == Phase.QUEUED and status == "running":
        return "Starting"
    return PHASE_LABELS[phase]
@dataclass(frozen=True)
class Tombstone:
    mutant_id: str
    operator: str
    location: str
    state: str  # "neutral" | "killed" | "survived"
    reason: str = ""  # survivor_reason from the report; only for survivors


def has_mutation_total(mutation_block: dict | None) -> bool:
    return isinstance(mutation_block, dict) and "total" in mutation_block


def tombstones(status: str, counts: MutantCounts, mutation_block: dict | None) -> list[Tombstone]:
    if status == "done":
        if not has_mutation_total(mutation_block):
            return []
        out: list[Tombstone] = []
        for k, m in enumerate(mutation_block.get("mutants") or []):
            out.append(
                Tombstone(
                    mutant_id=str(m.get("mutant_id") or f"mutant-{k + 1}"),
                    operator=str(m.get("operator") or ""),
                    location=str(m.get("location") or ""),
                    state="killed" if m.get("killed") else "survived",
                    reason="" if m.get("killed") else str(m.get("survivor_reason") or ""),
                )
            )
        return out
    if counts.total is None:
        return []
    return [Tombstone(f"mutant-{k + 1}", "", "", "neutral") for k in range(counts.total)]


def rail_context(events: list[str], status: str, mutation_block: dict | None) -> dict:
    phase = phase_of(events, status)
    counts = mutant_counts(events)
    finished = status == "done"
    not_checked = finished and not has_mutation_total(mutation_block)
    tombs = [] if not_checked else tombstones(status, counts, mutation_block)
    survivors = [t for t in tombs if t.state == "survived"]
    return {
        "phase": phase,
        "status_line": status_line_text(phase, status),
        "not_started": phase == Phase.QUEUED and status in ("failed", "timeout"),
        "counts": counts,
        "show_bar": counts.total is not None,
        "tombstones": tombs,
        "survivors": survivors,
        "mutation_not_checked": not_checked
        or (status in ("failed", "timeout") and counts.total is None),
        "events": list(events),
    }
