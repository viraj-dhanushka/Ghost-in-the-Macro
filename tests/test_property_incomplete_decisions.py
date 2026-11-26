"""Property 12 of the main spec: incomplete decisions are rejected and decisions.yaml is left unchanged.
Validates Requirement 4.5. No LibreOffice."""
from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings, strategies as st

from ghost.decisions.store import InvalidDecision, load_decisions, record

REQUIRED = ("behaviour", "reason", "author", "date")
FULL = {"behaviour": "keep the original", "reason": "bulk means 50 or more", "author": "A. Owner",
        "date": date(2026, 11, 26), "finding_id": "F-001"}


@settings(max_examples=60, deadline=None)
@given(st.sets(st.sampled_from(REQUIRED), min_size=1), st.sampled_from(["absent", "blank", "none"]))
def test_property_12_a_decision_missing_required_fields_is_rejected_naming_them(tmp_path_factory, drop, how):
    mdir = tmp_path_factory.mktemp("d")
    record(mdir, {**FULL, "finding_id": "F-900"})  # one valid Decision already on file
    before = (mdir / "decisions.yaml").read_bytes()
    bad = dict(FULL)
    for key in drop:
        if how == "absent":
            del bad[key]
        elif how == "blank":
            bad[key] = "   " if key != "date" else None
        else:
            bad[key] = None
    with pytest.raises(InvalidDecision) as err:
        record(mdir, bad)
    assert set(err.value.missing) == drop
    for key in drop:
        assert key in str(err.value)
    assert (mdir / "decisions.yaml").read_bytes() == before
    assert len(load_decisions(mdir)) == 1


def test_property_12_nothing_is_written_when_the_first_decision_is_incomplete(tmp_path):
    with pytest.raises(InvalidDecision):
        record(tmp_path, {k: v for k, v in FULL.items() if k != "reason"})
    assert not (tmp_path / "decisions.yaml").exists()
