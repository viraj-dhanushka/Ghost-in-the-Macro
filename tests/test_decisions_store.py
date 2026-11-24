from datetime import date

import pytest

from ghost.decisions import InvalidDecision, load_decisions, record
from ghost.decisions.store import SUMMARY_BEGIN

GOOD = {
    "finding_id": "F-001",
    "behaviour": "bulk means 50 or more",
    "reason": "Policy",
    "author": "ana",
    "date": "2026-11-20",
    "patch": {"op": "set_operator", "cell": "B7", "to": ">="},
}


def test_record_assigns_ids_and_roundtrips(tmp_path):
    d1 = record(tmp_path, GOOD)
    d2 = record(tmp_path, {**GOOD, "finding_id": "F-002", "decision_id": "D-099"})
    assert (d1.decision_id, d2.decision_id) == ("D-001", "D-002")
    loaded = load_decisions(tmp_path)
    assert loaded == [d1, d2]
    assert loaded[0].date == date(2026, 11, 20)
    assert loaded[0].patch["to"] == ">="
    design = (tmp_path / "design.md").read_text()
    assert design.count(SUMMARY_BEGIN) == 1 and "D-002" in design


def test_summary_preserves_surrounding_design_text(tmp_path):
    (tmp_path / "design.md").write_text("# Design\n\nIntro\n")
    record(tmp_path, GOOD)
    record(tmp_path, {**GOOD, "finding_id": "F-002"})
    text = (tmp_path / "design.md").read_text()
    assert text.startswith("# Design\n\nIntro") and text.count(SUMMARY_BEGIN) == 1


def test_missing_fields_rejected_and_file_unchanged(tmp_path):
    record(tmp_path, GOOD)
    before = (tmp_path / "decisions.yaml").read_text()
    bad = {k: v for k, v in GOOD.items() if k not in ("reason", "author", "finding_id")}
    with pytest.raises(InvalidDecision) as ei:
        record(tmp_path, bad)
    assert {"reason", "author", "finding_id or rule_id"} <= set(ei.value.missing)
    assert (tmp_path / "decisions.yaml").read_text() == before
