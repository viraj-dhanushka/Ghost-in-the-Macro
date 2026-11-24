"""Property 7: Comparison normalisation (R-07).

**Validates: Requirements 2.21**

Numeric comparisons in ghost/runtime/excel.py agree with comparing both sides after
normalising each to 15 significant digits (round half up), as Excel does. The oracle
below is independent of the runtime: it uses only decimal.Context.plus.

Fixed in task 7.2 (R-07).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Context, Decimal

from hypothesis import given, seed, settings
from hypothesis import strategies as st

from ghost.runtime.excel import xl_eq, xl_ge, xl_gt, xl_le, xl_lt, xl_ne

_CTX15 = Context(prec=15, rounding=ROUND_HALF_UP)
_WIDE = Context(prec=60)



def _norm(x: Decimal) -> Decimal:
    return _CTX15.plus(x)


def _expected(a: Decimal, b: Decimal) -> dict:
    na, nb = _norm(a), _norm(b)
    return {
        xl_eq: na == nb,
        xl_ne: na != nb,
        xl_lt: na < nb,
        xl_le: na <= nb,
        xl_gt: na > nb,
        xl_ge: na >= nb,
    }


# Up to 30 significant digits, with exponents spanning small and large magnitudes.
_decimals = st.builds(
    lambda sign, digits, exp: Decimal(sign * digits).scaleb(exp),
    st.sampled_from([1, -1]),
    st.integers(min_value=0, max_value=10**30 - 1),
    st.integers(min_value=-30, max_value=15),
)

# A 15-digit mantissa plus a perturbation of at most 0.4 units of the 15th digit.
_near_pairs = st.builds(
    lambda m, d1, d2, exp: (
        _WIDE.add(Decimal(m), Decimal(d1) / 100).scaleb(exp),
        _WIDE.add(Decimal(m), Decimal(d2) / 100).scaleb(exp),
    ),
    st.integers(min_value=10**14 + 1, max_value=10**15 - 1),  # 10**14 - 0.06 would cross a decade and normalise to a different 15-digit value
    st.integers(min_value=-40, max_value=40),
    st.integers(min_value=-40, max_value=40),
    st.integers(min_value=-20, max_value=10),
)


@seed(20261124)
@settings(max_examples=300, deadline=None, derandomize=True)
@given(st.one_of(_decimals.flatmap(lambda a: st.tuples(st.just(a), _decimals)), _near_pairs))
def test_property_7_comparison_normalisation(pair):
    a, b = pair
    for fn, want in _expected(a, b).items():
        assert fn(a, b) is want, (fn.__name__, a, b)


@seed(20261124)
@settings(max_examples=200, deadline=None, derandomize=True)
@given(_near_pairs)
def test_property_7_beyond_15th_digit_is_equal(pair):
    a, b = pair
    assert xl_eq(a, b) is True, (a, b)
    assert xl_ge(a, b) is True and xl_le(a, b) is True, (a, b)
    assert xl_lt(a, b) is False and xl_gt(a, b) is False, (a, b)


def test_property_7_division_examples():
    third = Decimal(1) / Decimal(3)
    assert xl_eq(third * 3, Decimal(1)) is True
    ten_thirds = Context(prec=60).divide(Decimal(10), Decimal(3))
    assert xl_ge(Context(prec=60).multiply(ten_thirds, Decimal(3)), Decimal(10)) is True
