"""Property tests for the front-door Progress_Module (``web/progress.py``).

Pure module, no LibreOffice. Hypothesis with explicit seed 20261204.
Properties 3-6 are added by later tasks (1.4 to 1.7) below the marked line.
"""
from __future__ import annotations

import re

import pytest
from hypothesis import given, seed, settings, strategies as st

from web.progress import phase_of

SEED = 20261204
STATUSES = ("queued", "running", "done", "failed", "timeout")

# Real marker line shapes (web/jobs.py, ghost/cli.py).
_marker_lines = st.one_of(
    st.just("Starting verification"),
    st.builds(
        lambda n, i: f"mutation check: mutant {i % n + 1}/{n}",
        st.integers(1, 60),
        st.integers(0, 1000),
    ),
    st.builds(
        lambda mode, verdict, n, m: f"[{mode}] {verdict}: {n} distinct cases, {m} mismatch(es), seed {SEED}",
        st.sampled_from(["faithful", "intended"]),
        st.sampled_from(["PASS", "FAIL"]),
        st.integers(0, 500),
        st.integers(0, 20),
    ),
    st.builds(lambda p: f"Proof report: {p}", st.text(max_size=30)),
    st.builds(lambda r: f"mutation check: not checked ({r})", st.text(max_size=30)),
)
_event_lines = st.one_of(_marker_lines, st.text(max_size=60))
_events = st.lists(_event_lines, max_size=25)
_status = st.sampled_from(STATUSES)


# Feature: front-door, Property 1: Phase index is monotone under append
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(events=_events, line=_event_lines, status=_status)
def test_property_1_phase_index_monotone_under_append(events, line, status):
    """**Validates: Requirements 6.9, 16.1**"""
    before = phase_of(list(events), status)
    after = phase_of(list(events) + [line], status)
    assert after >= before


# Exact oracle written from the Phase_Marker glossary (requirements.md), not from web/progress.py:
# the start line whole, the mutant line whole with ASCII numbers of 1 to 4 digits, and the three
# prefixes at column 0. Task 17 (Skeptic): the earlier oracle was looser than the code ("\\s*",
# lstrip, substring search), so it filtered every near-duplicate out and could not test them.
_MUTANT_RE = re.compile(r"mutation check: mutant [0-9]{1,4}/[0-9]{1,4}")
def _matches_no_marker(line: str) -> bool:
    return not (
        line == "Starting verification"
        or _MUTANT_RE.fullmatch(line)
        or line.startswith(("[faithful]", "[intended]", "Proof report:"))
    )
# Near-duplicates of real marker lines: none is a marker.
_NEAR_DUPLICATES = [" Starting verification", "Starting verification ", "Starting verification now",
        "STARTING VERIFICATION", "Starting  verification",
        "mutation check: mutant  3/10", "mutation check: mutant 3 /10", "mutation check: mutant 3/ 10",
        "mutation check: mutant 3/10 ", " mutation check: mutant 3/10", "x mutation check: mutant 3/10",
        "Mutation check: mutant 3/10", "mutation check: mutant 3/10000", "mutation check: mutant 10000/10000",
        "mutation check: mutant \u0663/\u0661\u0660", "mutation check: mutant \uff13/\uff11\uff10",
        " [faithful] PASS", "[Faithful] PASS", " [intended] FAIL", " Proof report: x", "proof report: x",
        "see [faithful] PASS above", "log: Starting verification",
]
# Near misses that must not match any marker, plus arbitrary text.
_near_misses = st.one_of(
    st.builds(lambda r: f"mutation check: not checked ({r})", st.text(max_size=30)),
    st.just("mutation check: mutant x/y"),
    st.just("mutation check: mutant 3"),
    st.builds(lambda t: f"[other] {t}", st.text(max_size=20)),
    st.builds(lambda t: f"Proof report {t}", st.text(max_size=20)),
    st.sampled_from(["Starting", "verification", "Referee ready", "", "faithful", "intended"]),
    st.sampled_from(_NEAR_DUPLICATES),
)
_unrecognised_lines = st.one_of(_near_misses, st.text(max_size=60)).filter(_matches_no_marker)


@pytest.mark.parametrize("line", _NEAR_DUPLICATES)
@pytest.mark.parametrize("status", STATUSES)
def test_property_2_each_near_duplicate_is_not_a_marker(line, status):
    """**Validates: Requirements 6.10, 16.2.** Every listed near-duplicate, checked one by one,
    because the random generator above may not draw each of them."""
    assert _matches_no_marker(line)
    assert phase_of([line], status) == phase_of([], status)
# Feature: front-door, Property 2: Unrecognised lines never change the phase
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(events=_events, line=_unrecognised_lines, status=_status)
def test_property_2_unrecognised_lines_never_change_the_phase(events, line, status):
    """**Validates: Requirements 6.10, 16.2**"""
    assert phase_of(list(events) + [line], status) == phase_of(list(events), status)


# --- Properties 3-6 are added below by tasks 1.4 to 1.7 ---

from web.progress import MutantCounts, mutant_counts, tombstones  # noqa: E402

# Mutant lines with any i, n >= 1, including i > n and n changing between lines.
_any_mutant_lines = st.builds(
    lambda i, n: f"mutation check: mutant {i}/{n}",
    st.integers(1, 80),
    st.integers(1, 80),
)
_mutant_event_lines = st.one_of(_any_mutant_lines, _marker_lines, st.text(max_size=40))
_mutant_events = st.lists(_mutant_event_lines, max_size=40)


@st.composite
def _finished_mutation_blocks(draw):
    total = draw(st.integers(0, 40))
    killed_flags = draw(st.lists(st.booleans(), min_size=total, max_size=total))
    mutants = [
        {
            "mutant_id": f"M-{k:08x}",
            "operator": "rounding_mode",
            "location": f"Calculator!B{k + 1}",
            "killed": flag,
        }
        for k, flag in enumerate(killed_flags)
    ]
    return {"total": total, "killed": sum(killed_flags), "mutants": mutants}


# Feature: front-door, Property 3: Mutant counts stay within bounds and tombstone count matches the total
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(events=_mutant_events, block=_finished_mutation_blocks())
def test_property_3_mutant_counts_within_bounds_and_tombstones_match_total(events, block):
    """**Validates: Requirements 7.6, 7.7, 8.1, 8.9, 16.3**"""
    counts = mutant_counts(list(events))
    assert isinstance(counts, MutantCounts)
    if counts.total is not None:
        assert counts.done is not None
        assert counts.done <= counts.total
    # Finished job with a total: one tombstone per mutant in the total.
    done_tombs = tombstones("done", counts, block)
    assert len(done_tombs) == block["total"]


from web.progress import PHASE_LABELS, Phase, status_line_text  # noqa: E402


# Feature: front-door, Property 4: Status_Line text is a pure function of Phase and Job status
def _expected_status_text(phase, status):
    return "Starting" if phase == Phase.QUEUED and status == "running" else PHASE_LABELS[phase]
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(
    events_a=_events,
    events_b=_events,
    status_a=_status,
    status_b=_status,
    extra=_unrecognised_lines,
)
def test_property_4_status_line_text_is_a_pure_function_of_phase_and_status(
    events_a, events_b, status_a, status_b, extra
):
    """**Validates: Requirements 9.4, 9.5, 16.5, 16.6**"""
    phase_a = phase_of(list(events_a), status_a)
    phase_b = phase_of(list(events_b), status_b)
    text_a = status_line_text(phase_a, status_a)
    text_b = status_line_text(phase_b, status_b)
    assert text_a == _expected_status_text(phase_a, status_a)
    assert text_a == status_line_text(phase_a, status_a)
    # The same (Phase, status) from any two inputs gives identical text.
    if (phase_a, status_a) == (phase_b, status_b):
        assert text_a == text_b
    # Appending a line that does not change the phase does not change the text.
    phase_c = phase_of(list(events_a) + [extra], status_a)
    assert phase_c == phase_a
    assert status_line_text(phase_c, status_a) == text_a
    # A marker line is the only way off "Starting": once the phase moves, the text is its label.
    if phase_a != Phase.QUEUED:
        assert text_a == PHASE_LABELS[phase_a]
@st.composite
def _report_mutation_blocks(draw):
    """Finished block shaped like proof-report-1 `mutation`: reuses the Property 3
    generator and adds the optional per-mutant fields the engine may write."""
    block = draw(_finished_mutation_blocks())
    for m in block["mutants"]:
        if m["killed"]:
            m["killed_by"] = {"inputs": {"quantity": draw(st.integers(0, 200))}}
        else:
            m["survivor_reason"] = draw(st.text(max_size=20))
            if draw(st.booleans()):
                m["survivor_kind"] = "no_output_change"
    return block
# Feature: front-door, Property 5: Killed and survived tombstone counts match the finished report
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(
    events=_mutant_events,
    block=_report_mutation_blocks(),
    unfinished=st.sampled_from(("queued", "running", "failed", "timeout")),
)
def test_property_5_killed_and_survived_tombstones_match_finished_report(events, block, unfinished):
    """**Validates: Requirements 8.3, 8.4, 16.4**"""
    counts = mutant_counts(list(events))
    tombs = tombstones("done", counts, block)
    assert sum(t.state == "killed" for t in tombs) == block["killed"]
    assert sum(t.state == "survived" for t in tombs) == block["total"] - block["killed"]
    # Unfinished jobs never show a killed or survived tombstone.
    for t in tombstones(unfinished, counts, None):
        assert t.state == "neutral"


# Feature: front-door, Property 6: Determinism of phase_of
@seed(SEED)
@settings(max_examples=200, deadline=None, derandomize=False)
@given(events=_events, status=_status)
def test_property_6_determinism_of_phase_of(events, status):
    """**Validates: Requirements 6.15**"""
    snapshot = list(events)
    first = phase_of(events, status)
    second = phase_of(events, status)
    on_copy = phase_of(list(snapshot), status)
    assert first == second == on_copy
    # phase_of must not mutate its input list.
    assert events == snapshot
