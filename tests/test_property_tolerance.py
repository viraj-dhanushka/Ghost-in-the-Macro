"""Property 22 of the main spec: tolerance comparison.
Validates Requirements 8.5 and 15.10. No LibreOffice."""
from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings, strategies as st

from ghost.runtime.excel import ExcelError
from ghost.verifier.compare import DEFAULT_TOL, values_equal

numbers = st.one_of(st.integers(-10**9, 10**9), st.decimals(min_value=-10**6, max_value=10**6, places=6),
                    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
texts = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=12).filter(
    lambda s: not s.startswith("#") and "E" not in s.upper())
codes = st.sampled_from(["#DIV/0!", "#VALUE!", "#N/A", "#REF!", "#NAME?", "#NUM!", "#NULL!"])


# Feature: ghost-in-the-macro, Property 22: Tolerance comparison
@settings(max_examples=300, deadline=None)
@given(numbers, numbers)
def test_property_22_numbers_are_symmetric_and_reflexive(a, b):
    assert values_equal(a, b) == values_equal(b, a)
    assert values_equal(a, a)


@settings(max_examples=300, deadline=None)
@given(st.decimals(min_value=-10**6, max_value=10**6, places=6), st.decimals(min_value=0, max_value=Decimal("0.0000009"), places=7))
def test_property_22_numbers_within_1e_6_are_equal(a, d):
    assert values_equal(a, a + d) and values_equal(a + d, a)


@settings(max_examples=300, deadline=None)
@given(st.decimals(min_value=-10**6, max_value=10**6, places=6), st.decimals(min_value=Decimal("0.000002"), max_value=Decimal("1000"), places=6))
def test_property_22_numbers_further_apart_are_not_equal(a, d):
    assert not values_equal(a, a + d) and not values_equal(a + d, a)
    assert DEFAULT_TOL == 1e-6


@settings(max_examples=200, deadline=None)
@given(texts, texts)
def test_property_22_strings_compare_exactly(a, b):
    assert values_equal(a, b) == (a == b)


@settings(max_examples=100, deadline=None)
@given(codes, codes, st.one_of(numbers, texts))
def test_property_22_excel_errors_compare_by_error_type(c1, c2, other):
    assert values_equal(c1, c2) == (c1 == c2)
    assert values_equal(ExcelError(c1), c1)  # an error object and its code are the same error type
    assert not values_equal(c1, other)
