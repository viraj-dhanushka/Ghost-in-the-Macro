"""Mismatch classification and verdict.

Property 28: Mismatch classification and verdict.
**Validates: Requirements 8.10, 8.11, 8.12, 8.13, 8.14**
"""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from ghost.models import Case, Decision, Finding, Location, Mismatch, Rule
from ghost.verifier.classify import make_classifier, verdict

DEPS = {"S!C1": {"S!B1"}, "S!D1": {"S!C1"}}
FINDING = Finding(
    finding_id="F-001", cell="S!B1", constant=50,
    locations=[(Location(cell="S!C1"), ">"), (Location(cell="S!D1"), ">=")],
)
DECISION = Decision(
    decision_id="D-001", finding_id="F-001", behaviour="b", reason="r",
    author="a", date=date(2026, 1, 1),
)
RULE = Rule(rule_id="R-00000001", text="t", cells=["S!D1"])


def _m(cell="S!D1"):
    return Mismatch(case=Case(inputs={"q": 50}), output="o", cell=cell,
                    mismatch_class="translation bug", minimal=True)


def test_translation_bug_without_findings():
    out = make_classifier("faithful", deps=DEPS)(_m())
    assert out.mismatch_class == "translation bug" and out.finding_id is None


def test_finding_match_links_ids():
    out = make_classifier("faithful", [FINDING], [DECISION], [RULE], DEPS)(_m())
    assert out.mismatch_class == "original workbook inconsistency"
    assert out.finding_id == "F-001" and out.rule_id == "R-00000001"
    assert out.decision_id is None


def test_decision_explains_only_in_intended():
    out = make_classifier("intended", [FINDING], [DECISION], [RULE], DEPS)(_m())
    assert out.mismatch_class == "expected by decision"
    assert out.decision_id == "D-001" and out.finding_id == "F-001"


def test_unrelated_cell_is_translation_bug():
    out = make_classifier("intended", [FINDING], [DECISION], [], DEPS)(_m("S!Z9"))
    assert out.mismatch_class == "translation bug"


@given(
    mode=st.sampled_from(["faithful", "intended"]),
    classes=st.lists(
        st.sampled_from(["translation bug", "original workbook inconsistency", "expected by decision"]),
        max_size=5,
    ),
)
def test_verdict_property(mode, classes):
    ms = [_m().model_copy(update={"mismatch_class": c}) for c in classes]
    if mode == "faithful":
        assert verdict(mode, ms) == (not ms)
    else:
        assert verdict(mode, ms) == all(c == "expected by decision" for c in classes)


def test_explaining_decision_needs_all_three_conditions():
    """R-01 (clause 2.5): Faithful matches Referee, candidate differs, patched hook differs."""
    from ghost.verifier.classify import explaining_decision

    d = DECISION.model_copy(update={"patch": {"op": "set_operator", "cell": "S!C1", "from": ">", "to": ">="}})
    ref, faith = {"o": 5}, {"o": 5}
    ft, ct = {"S!C1#1": False}, {"S!C1#1": True}
    assert explaining_decision([d], ["o"], ref, {"o": 0}, ct, faith, ft) == "D-001"
    # (a) fails: the Faithful module disagrees with the Referee
    assert explaining_decision([d], ["o"], {"o": 6}, {"o": 0}, ct, faith, ft) is None
    # (b) fails: candidate equals Faithful
    assert explaining_decision([d], ["o"], ref, {"o": 5}, ct, faith, ft) is None
    # (c) fails: the patched comparison evaluates the same in both modules
    assert explaining_decision([d], ["o"], ref, {"o": 0}, ft, faith, ft) is None
    # a record-only Decision (no patch) never explains a difference
    assert explaining_decision([DECISION], ["o"], ref, {"o": 0}, ct, faith, ft) is None


def test_faithful_inconsistency_needs_disagreeing_comparisons():
    """R-02 (clause 2.6): blame the workbook only when the Finding's comparisons disagree."""
    clf = make_classifier("faithful", [FINDING], [], [RULE], DEPS)
    agree = {"S!C1#1": True, "S!D1#1": True}
    differ = {"S!C1#1": False, "S!D1#1": True}
    assert clf(_m(), trace=agree).mismatch_class == "translation bug"
    assert clf(_m(), trace={}).mismatch_class == "translation bug"
    out = clf(_m(), trace=differ)
    assert out.mismatch_class == "original workbook inconsistency" and out.finding_id == "F-001"
