"""Tests for ghost.verifier.run (Requirements 8.1, 8.6, 8.7).

**Validates: Requirements 8.1, 8.6, 8.7** (Properties 25 and 26 by example).
The last test runs the real LibreOffice Referee and is skipped without soffice.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ghost.models import IOSpec, Mapping, Threshold, Location
from ghost.verifier.run import VerifyConfig, verify

MAPPING = Mapping(
    inputs={"quantity": IOSpec(cell="S!B2", type="integer", min=Decimal(0))},
    outputs={"ship": IOSpec(cell="S!B9", type="decimal")},
)
THRESHOLDS = [
    Threshold(cell="S!B2", operator=">", constant=Decimal(50), source=Location(cell="S!B9"))
]


class FakeReferee:
    """Original workbook: free delivery only above 50."""

    def __init__(self) -> None:
        self.calls = 0

    def eval(self, inputs, outputs):
        self.calls += 1
        return {"S!B9": 0 if inputs["S!B2"] > 50 else 5}


def _good(inputs):
    return {"ship": Decimal(0) if inputs["quantity"] > 50 else Decimal(5)}


def _bad(inputs):  # planted bug: >= instead of >
    return {"ship": Decimal(0) if inputs["quantity"] >= 50 else Decimal(5)}


def test_clean_module_passes_with_requested_case_count():
    r = verify(_good, MAPPING, FakeReferee(), VerifyConfig(thresholds=THRESHOLDS))
    assert r.passed and not r.mismatches
    assert r.cases_tested == 300


def test_mismatch_shrinks_to_minimal_counterexample_and_fails_faithful():
    r = verify(_bad, MAPPING, FakeReferee(), VerifyConfig(thresholds=THRESHOLDS))
    assert not r.passed
    (m,) = r.mismatches
    assert m.minimal and m.cell == "S!B9" and m.output == "ship"
    assert m.case.inputs == {"quantity": 50}
    assert m.case.referee == {"ship": 5} and m.case.actual == {"ship": Decimal(0)}


def test_same_seed_gives_same_case_sequence():
    a = verify(_good, MAPPING, FakeReferee(), VerifyConfig(seed=7, max_examples=50))
    b = verify(_good, MAPPING, FakeReferee(), VerifyConfig(seed=7, max_examples=50))
    c = verify(_good, MAPPING, FakeReferee(), VerifyConfig(seed=8, max_examples=50))
    assert a.cases == b.cases
    assert a.cases != c.cases


def test_progress_callback_and_eval_cache():
    ref = FakeReferee()
    seen: list[int] = []
    r = verify(_good, MAPPING, ref, VerifyConfig(progress=lambda d, t: seen.append(d)))
    assert seen == sorted(seen) and seen[-1] == ref.calls
    assert ref.calls <= r.cases_tested  # duplicates are served from the cache


def test_intended_mode_passes_only_when_explained():
    explained = lambda m: m.model_copy(update={"mismatch_class": "expected by decision"})  # noqa: E731
    cfg = dict(thresholds=THRESHOLDS, mode="intended")
    assert not verify(_bad, MAPPING, FakeReferee(), VerifyConfig(**cfg)).passed
    r = verify(_bad, MAPPING, FakeReferee(), VerifyConfig(classifier=explained, **cfg))
    assert r.passed and len(r.mismatches) == 1


def test_crashing_compute_is_a_mismatch():
    def boom(inputs):
        raise RuntimeError("x")

    r = verify(boom, MAPPING, FakeReferee(), VerifyConfig(max_examples=5))
    assert not r.passed and r.mismatches[0].case.actual["ship"].startswith("<compute raised")


def test_real_referee_on_samples(tmp_path):
    from ghost.converter.emit_python import emit_python
    from ghost.converter.mapping import generate_mapping
    from ghost.ingest.workbook import load_workbook
    from ghost.referee.client import RefereeClient
    from ghost.referee.locate import RefereeUnavailable, locate_soffice
    from samples import make_discount, make_haunted

    try:
        locate_soffice()
    except RefereeUnavailable:
        pytest.skip("soffice not available")
    for mod in (make_discount, make_haunted):
        path = mod.build(tmp_path / f"{mod.__name__.rsplit('.', 1)[-1]}.xlsx")
        wb = load_workbook(str(path))
        mapping = generate_mapping(wb)
        with RefereeClient(None, path) as ref:
            r = verify(emit_python(wb, mapping), mapping, ref)
        assert r.cases_tested == 300 and r.passed, r.mismatches
