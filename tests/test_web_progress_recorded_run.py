"""Recorded-run regression: the Progress_Module against a real haunted run.

Feature: front-door, Requirement 15. The fixture holds the Event_Lines the
Job_Runner captured from a real haunted run (scrubbed, unedited) and the mutant
total from that run's Proof_Report.
"""
from __future__ import annotations

import json
from pathlib import Path

from web.progress import Phase, mutant_counts, phase_of

FIXTURE = Path(__file__).parent / "fixtures" / "front_door" / "haunted_run_events.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_has_start_line_and_no_server_paths():  # 15.1, 15.4
    events = _load()["events"]
    assert events[0] == "Starting verification"
    for line in events:
        assert "/Users/" not in line and "/var/" not in line and "/tmp/" not in line


def test_phases_appear_in_order_line_by_line():  # 15.2
    events = _load()["events"]
    seen: list[Phase] = []
    for i in range(1, len(events) + 1):
        p = phase_of(events[:i], "running")
        if not seen or seen[-1] != p:
            seen.append(p)
    assert seen == [
        Phase.VERIFICATION_STARTED,
        Phase.MUTATION_SELF_CHECK,
        Phase.CASES_COMPARED,
        Phase.PROOF_WRITTEN,
    ]


def test_finished_mutant_counts_equal_report_total():  # 15.3
    data = _load()
    total = data["_meta"]["proof_report_mutation"]["total"]
    counts = mutant_counts(data["events"])
    assert counts.total == total
    assert counts.done == total
