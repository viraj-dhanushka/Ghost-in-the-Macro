"""Tests for ghost.verifier.strategies (task 7.2)."""

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, seed, settings, strategies as st

from ghost.models import IOSpec, Location, Mapping, Threshold
from ghost.verifier.strategies import (
    infer_spec,
    infer_type,
    input_strategy,
    inputs_strategy,
    threshold_neighbours,
)


def _thr(cell: str, c: str) -> Threshold:
    return Threshold(cell=cell, operator=">=", constant=Decimal(c), source=Location(cell=cell))


def _draw_many(strategy, n=1000) -> list:
    out: list = []

    @seed(1)
    @settings(max_examples=n, database=None, derandomize=False,
              suppress_health_check=list(HealthCheck))
    @given(strategy)
    def collect(v):
        out.append(v)

    collect()
    return out


def test_infer_type():
    assert infer_type([1, 2.0, "3"]) == "integer"
    assert infer_type([1, 2.5]) == "decimal"
    assert infer_type([]) == "decimal"
    assert infer_type([True]) == "boolean"
    assert infer_type(["abc"]) == "string"


def test_infer_spec_validation_and_override():
    assert infer_spec("S!A1", [1.5], "whole:1").type == "integer"
    ov = IOSpec(cell="S!A1", type="decimal", min=Decimal(5))
    assert infer_spec("S!A1", [1], None, ov) is ov
    spec = infer_spec("S!A1", [3, 4])
    assert spec.type == "integer" and spec.min == 0


def test_neighbours_decimal_vs_integer():
    assert Decimal("49.9") in threshold_neighbours([Decimal(50)], "decimal")
    assert Decimal("49.9") not in threshold_neighbours([Decimal(50)], "integer")


# Feature: ghost-in-the-macro, Property 23: Input generation reaches thresholds
# **Validates: Requirements 8.2, 8.3**
@pytest.mark.parametrize("t", [2, 50, 500, 9_999])
@pytest.mark.parametrize("decimal", [False, True])
def test_property_23_reaches_thresholds(t, decimal):
    spec = IOSpec(cell="S!B2", type="decimal" if decimal else "integer", min=Decimal(0))
    draws = set(_draw_many(input_strategy(spec, [_thr("S!B2", str(t))])))
    expected = {Decimal(t - 1), Decimal(t), Decimal(t + 1)}
    if decimal:
        expected |= {Decimal(t) - Decimal("0.1"), Decimal(t) + Decimal("0.1")}
    assert expected <= {Decimal(d) for d in draws}


# Feature: ghost-in-the-macro, Property 23 (type inference half)
# **Validates: Requirements 8.3**
@settings(max_examples=50, database=None)
@given(st.lists(st.one_of(st.integers(-1000, 1000),
                          st.decimals(-1000, 1000, places=2, allow_nan=False)),
                min_size=1, max_size=10))
def test_property_23_integer_iff_all_integers(samples):
    all_int = all(Decimal(s) == Decimal(s).to_integral_value() for s in samples)
    assert (infer_type(samples) == "integer") == all_int


def test_inputs_strategy_respects_range_and_types():
    m = Mapping(inputs={
        "qty": IOSpec(cell="S!B2", type="integer", min=Decimal(0)),
        "flag": IOSpec(cell="S!B3", type="boolean"),
    })
    draws = _draw_many(inputs_strategy(m, [_thr("S!B2", "50")]), 200)
    assert all(isinstance(d["qty"], int) and d["qty"] >= 0 for d in draws)
    assert all(isinstance(d["flag"], bool) for d in draws)
