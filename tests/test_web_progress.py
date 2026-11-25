"""Unit tests for web/progress.py (front-door task 1.1).

Event lines are hand-built from what the engine really prints:
- ``Starting verification`` is emitted by web/jobs.py before the CLI spawns.
- ``mutation check: mutant i/n`` and ``mutation check: not checked (...)``,
  ``[faithful] PASS: ...`` / ``[intended] FAIL: ...`` and ``Proof report: ...``
  are printed by ghost/cli.py.

Written before web/progress.py exists (test-first).
"""

from __future__ import annotations

from web.progress import (
    PHASE_LABELS,
    MutantCounts,
    Phase,
    mutant_counts,
    phase_of,
    status_line_text,
)

START = "Starting verification"
MUT_1 = "mutation check: mutant 1/33"
MUT_LAST = "mutation check: mutant 33/33"
FAITHFUL = "[faithful] PASS: 200 distinct cases, 0 mismatch(es), seed 20261204"
INTENDED = "[intended] FAIL: 26 distinct cases, 1 mismatch(es), seed 20261204"
PROOF = "Proof report: report.html"
NOT_CHECKED = "mutation check: not checked (the unmutated module has 1 Mismatch(es))"


# --- phase_of: Req 6.1, 6.3-6.5 ---------------------------------------------

def test_queued_status_without_events_is_queued():
    assert phase_of([], "queued") == Phase.QUEUED


def test_empty_events_running_status_is_queued_floor():
    # Req 6.14: Phase derived from the empty list and the supplied status.
    assert phase_of([], "running") == Phase.QUEUED


def test_phase_order_values():
    assert (
        Phase.QUEUED
        < Phase.VERIFICATION_STARTED
        < Phase.MUTATION_SELF_CHECK
        < Phase.CASES_COMPARED
        < Phase.PROOF_WRITTEN
    )


# --- each Phase_Marker: Req 6.5-6.8 -----------------------------------------

def test_starting_verification_marker():
    assert phase_of([START], "running") == Phase.VERIFICATION_STARTED


def test_mutant_line_marker():
    assert phase_of([START, MUT_1], "running") == Phase.MUTATION_SELF_CHECK


def test_faithful_line_marker():
    assert phase_of([START, FAITHFUL], "running") == Phase.CASES_COMPARED


def test_intended_line_marker():
    assert phase_of([START, INTENDED], "running") == Phase.CASES_COMPARED


def test_proof_report_marker():
    events = [START, MUT_1, MUT_LAST, FAITHFUL, PROOF]
    assert phase_of(events, "done") == Phase.PROOF_WRITTEN


# --- highest marker wins: Req 6.9 -------------------------------------------

def test_highest_marker_wins_regardless_of_line_order():
    events = [PROOF, START, FAITHFUL, MUT_1]
    assert phase_of(events, "running") == Phase.PROOF_WRITTEN


# --- unrecognised lines: Req 6.10-6.12 --------------------------------------

def test_unrecognised_lines_leave_phase_unchanged():
    base = [START, MUT_1]
    noisy = base + ["  boundary: quantity near 50", "something else", ""]
    assert phase_of(noisy, "running") == phase_of(base, "running")


def test_unrecognised_lines_alone_do_not_reach_a_phase():
    assert phase_of(["hello", "  note"], "running") == Phase.QUEUED


def test_no_mutation_lines_skips_mutation_phase_without_reaching_it():
    # Req 6.11, 6.12: the run goes from Verification started to Cases compared.
    assert phase_of([START], "running") == Phase.VERIFICATION_STARTED
    assert phase_of([START, FAITHFUL], "running") == Phase.CASES_COMPARED


def test_marker_must_start_the_line():
    # A path or a note containing the words is not a marker.
    assert phase_of(["see [faithful] above"], "running") == Phase.QUEUED
    assert phase_of(["  Proof report: x"], "running") == Phase.QUEUED


# --- not checked line: Req 6.13 ---------------------------------------------

def test_not_checked_line_is_not_a_phase_marker():
    assert phase_of([START, NOT_CHECKED], "running") == Phase.VERIFICATION_STARTED
    assert phase_of([NOT_CHECKED], "running") == Phase.QUEUED


# --- terminal statuses: Req 6.14 / 10.11 ------------------------------------

def test_timeout_keeps_phase_reached_and_no_later_phase():
    events = [START, MUT_1]
    assert phase_of(events, "timeout") == Phase.MUTATION_SELF_CHECK
    assert phase_of(events, "failed") == Phase.MUTATION_SELF_CHECK


def test_timeout_before_any_marker_is_not_started():
    assert phase_of([], "timeout") == Phase.QUEUED


# --- determinism: Req 6.15 --------------------------------------------------

def test_phase_of_is_deterministic():
    events = [START, MUT_1, FAITHFUL]
    assert phase_of(events, "running") == phase_of(list(events), "running")


# --- mutant_counts: Req 7.1, 7.2, 7.6 ---------------------------------------

def test_mutant_counts_without_lines_is_none_none():
    assert mutant_counts([START, FAITHFUL]) == MutantCounts(done=None, total=None)


def test_mutant_counts_single_line():
    assert mutant_counts([MUT_1]) == MutantCounts(done=1, total=33)


def test_mutant_counts_largest_i_and_latest_n():
    events = [
        "mutation check: mutant 1/10",
        "mutation check: mutant 5/10",
        "mutation check: mutant 3/12",
    ]
    assert mutant_counts(events) == MutantCounts(done=5, total=12)


def test_mutant_counts_ignores_i_greater_than_n():
    events = ["mutation check: mutant 2/10", "mutation check: mutant 11/10"]
    counts = mutant_counts(events)
    assert counts == MutantCounts(done=2, total=10)


def test_only_out_of_order_line_gives_no_counts():
    assert mutant_counts(["mutation check: mutant 7/3"]) == MutantCounts(None, None)


def test_out_of_order_line_is_not_a_phase_marker_for_counts_only():
    # An i>n line is ignored for counts; counts never exceed the total.
    counts = mutant_counts(["mutation check: mutant 9/4"])
    assert counts.done is None or counts.done <= counts.total


def test_mutant_counts_ignores_not_checked_and_malformed_lines():
    events = [NOT_CHECKED, "mutation check: mutant x/y", "mutation check: mutant 1/"]
    assert mutant_counts(events) == MutantCounts(None, None)


def test_mutant_done_never_exceeds_total():
    events = [f"mutation check: mutant {i}/33" for i in range(1, 34)]
    counts = mutant_counts(events)
    assert counts == MutantCounts(done=33, total=33)
    assert counts.done <= counts.total


# --- task 17 review: lines the engine never prints are not markers ------------
def test_non_ascii_digits_are_not_markers():
    # int() accepts Arabic-Indic and fullwidth digits; the engine prints ASCII only.
    for line in ("mutation check: mutant \u0663/\u0661\u0660", "mutation check: mutant \uff13/\uff11\uff10"):
        assert mutant_counts([line]) == MutantCounts(None, None)
        assert phase_of([line], "running") == Phase.QUEUED
def test_huge_numbers_are_not_markers_and_do_not_raise():
    # 5000 digits made int() raise ValueError; 9999999999 asked for ten billion tombstones.
    for line in ("mutation check: mutant 1/" + "9" * 5000, "mutation check: mutant 1/9999999999"):
        assert mutant_counts([line]) == MutantCounts(None, None)
        assert phase_of([line], "running") == Phase.QUEUED
def test_four_digit_limit_is_exact():
    # Documented limit (task 17): numbers up to 9999 are markers, five digits are not.
    assert mutant_counts(["mutation check: mutant 1/9999"]) == MutantCounts(done=1, total=9999)
    assert phase_of(["mutation check: mutant 1/9999"], "running") == Phase.MUTATION_SELF_CHECK
    assert mutant_counts(["mutation check: mutant 1/10000"]) == MutantCounts(None, None)
    assert phase_of(["mutation check: mutant 1/10000"], "running") == Phase.QUEUED
# --- status_line_text: Req 9.4, 9.5 -----------------------------------------

def test_status_line_text_is_the_phase_label():
    for phase in Phase:
        assert status_line_text(phase) == PHASE_LABELS[phase]


def test_running_job_with_no_marker_says_starting_not_queued():
    # Owner decision (task 17 follow-up): "Queued" is for a queued job only.
    assert phase_of([], "running") == Phase.QUEUED  # the Phase floor is unchanged
    assert status_line_text(Phase.QUEUED, "running") == "Starting"
    assert status_line_text(Phase.QUEUED, "queued") == "Queued"
    for status in ("done", "failed", "timeout"):
        assert status_line_text(Phase.QUEUED, status) == "Queued"
def test_a_marker_line_replaces_starting_with_the_phase_name():
    for phase in Phase:
        if phase != Phase.QUEUED:
            assert status_line_text(phase, "running") == PHASE_LABELS[phase]
def test_rail_status_line_for_a_running_job_with_no_marker_is_starting():
    from web.progress import rail_context
    assert rail_context([], "running", None)["status_line"] == "Starting"
    assert rail_context([], "queued", None)["status_line"] == "Queued"
    assert rail_context(["Starting verification"], "running", None)["status_line"] == "Verification started"
def test_phase_labels_match_the_spec_names():
    assert [PHASE_LABELS[p] for p in Phase] == [
        "Queued",
        "Verification started",
        "Mutation self-check",
        "Cases compared",
        "Proof written",
    ]


def test_status_line_text_is_stable_per_phase():
    for phase in Phase:
        assert status_line_text(phase) == status_line_text(phase)
