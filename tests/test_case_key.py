"""R-28: distinct-case keys treat equal numbers as one case."""
from __future__ import annotations

from decimal import Decimal

from ghost.mutation.run import _case_key
from ghost.verifier.compare import case_key


def test_equal_numbers_share_one_key():
    keys = {case_key({"q": v}) for v in (Decimal("1.0"), Decimal("1.00"), 1, 1.0, Decimal("1"))}
    assert len(keys) == 1
    assert case_key({"q": Decimal("100")}) == case_key({"q": 100}) == case_key({"q": Decimal("1E+2")})


def test_different_values_and_types_stay_distinct():
    assert case_key({"q": Decimal("1.5")}) != case_key({"q": 1})
    assert case_key({"q": "1"}) != case_key({"q": 1})
    assert case_key({"q": True}) != case_key({"q": 1})
    assert case_key({"a": 1, "b": 2}) != case_key({"a": 2, "b": 1})


def test_mutation_case_key_normalises_too():
    assert _case_key({"q": Decimal("1.0")}) == _case_key({"q": 1})
