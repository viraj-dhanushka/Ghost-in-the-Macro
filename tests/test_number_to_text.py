"""R-08: number-to-text like Excel, and the scientific-string rule in the verifier."""
from __future__ import annotations

from decimal import Decimal

import pytest

from ghost.runtime.excel import xl_concat
from ghost.verifier.compare import values_equal


@pytest.mark.parametrize(
    "value, text",
    [
        (Decimal("1E+20"), "1E+20"),
        (Decimal("1E-20"), "1E-20"),
        (Decimal("-1E+20"), "-1E+20"),
        (Decimal("1.5E+25"), "1.5E+25"),
        (Decimal("123456789012345678"), "1.23456789012346E+17"),
        (Decimal("0.1") + Decimal("0.2"), "0.3"),
        (Decimal(1) / Decimal(3), "0.333333333333333"),
        (Decimal("1E+14"), "100000000000000"),
        (Decimal("0.00001"), "0.00001"),
        (Decimal("1234.5"), "1234.5"),
        (Decimal(0), "0"),
    ],
)
def test_number_to_text(value, text):
    assert xl_concat(value, "") == text


def test_scientific_strings_with_same_value_are_equal():
    assert values_equal("1E+20", "1E+020")
    assert values_equal("1.5E-20", "1.5E-020")
    assert not values_equal("1E+20", "1E+21")


def test_ordinary_numeric_looking_strings_stay_exact():
    assert not values_equal("1.0", "1")
    assert not values_equal("100", "1E+02")
    assert not values_equal("1E+20", "100000000000000000000")
    assert not values_equal("0.30", "0.3")
