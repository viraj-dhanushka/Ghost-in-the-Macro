"""Property 8: Decision uniqueness (review-fixes-2026-11-24, task 5.5).

**Validates: Requirements 2.14**

For any sequence of `record` calls into one migration directory, at most one
Decision per `finding_id` and per `rule_id` is stored. A repeat raises
`InvalidDecision` naming the existing `decision_id` and leaves `decisions.yaml`
byte-identical (R-14).

The model below is the oracle: it tracks which finding_ids and rule_ids are
already taken and which decision_id holds each.
"""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from ghost.decisions.store import DECISIONS_FILE, InvalidDecision, load_decisions, record

PBT_SEED = 20261204

FINDINGS = ["F-001", "F-002", "F-003"]
RULES = ["R-aaaaaaaa", "R-bbbbbbbb", "R-cccccccc"]

# Each call targets a finding, a rule, or both. At least one is always present.
targets = st.one_of(
    st.tuples(st.sampled_from(FINDINGS), st.none()),
    st.tuples(st.none(), st.sampled_from(RULES)),
    st.tuples(st.sampled_from(FINDINGS), st.sampled_from(RULES)),
)


def _decision(finding_id, rule_id, n):
    return {
        "finding_id": finding_id,
        "rule_id": rule_id,
        "behaviour": f"behaviour {n}",
        "reason": f"reason {n}",
        "author": "tester",
        "date": date(2026, 11, 24),
        "patch": {},
    }


@seed(PBT_SEED)
@settings(max_examples=100, derandomize=False, database=None, deadline=None,
          suppress_health_check=list(HealthCheck))
@given(calls=st.lists(targets, min_size=1, max_size=12))
def test_property_8_decision_uniqueness(calls):
    with tempfile.TemporaryDirectory() as tmp:
        mdir = Path(tmp)
        path = mdir / DECISIONS_FILE
        owner_by_finding: dict[str, str] = {}
        owner_by_rule: dict[str, str] = {}

        for n, (fid, rid) in enumerate(calls):
            clash = [owner_by_finding[fid]] if fid in owner_by_finding else []
            clash += [owner_by_rule[rid]] if rid in owner_by_rule else []
            before = path.read_bytes() if path.exists() else None

            if clash:
                with pytest.raises(InvalidDecision) as exc:
                    record(mdir, _decision(fid, rid, n))
                assert any(existing in str(exc.value) for existing in clash), (str(exc.value), clash)
                after = path.read_bytes() if path.exists() else None
                assert after == before
            else:
                stored = record(mdir, _decision(fid, rid, n))
                if fid:
                    owner_by_finding[fid] = stored.decision_id
                if rid:
                    owner_by_rule[rid] = stored.decision_id

        decisions = load_decisions(mdir)
        finding_ids = [d.finding_id for d in decisions if d.finding_id]
        rule_ids = [d.rule_id for d in decisions if d.rule_id]
        assert len(finding_ids) == len(set(finding_ids))
        assert len(rule_ids) == len(set(rule_ids))
