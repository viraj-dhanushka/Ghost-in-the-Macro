"""Property 31 of the main spec: routing is deterministic and total.
Validates Requirements 16.1 to 16.5. No LibreOffice."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost.models import Metrics
from ghost.router import RoutingThresholds, recommend_route

thresholds = st.builds(
    RoutingThresholds, vba_line_threshold=st.integers(0, 4000), userform_threshold=st.integers(0, 8),
    declare_threshold=st.integers(0, 10), batch_size_threshold=st.integers(1, 20),
)
metrics = st.builds(
    Metrics, formula_count=st.integers(0, 5000), vba_line_count=st.integers(0, 8000), module_count=st.integers(0, 30),
    userform_count=st.integers(0, 12), declare_count=st.integers(0, 15),
)


# Feature: ghost-in-the-macro, Property 31: Routing is deterministic and total
@settings(max_examples=500, deadline=None)
@given(metrics, st.integers(1, 30), thresholds)
def test_property_31_exactly_one_route_the_same_every_time_following_the_rules(m, batch, t):
    r = recommend_route(m, batch, t)
    assert r == recommend_route(m, batch, t)
    assert r.route in ("Ghost converts", "AWS Transform custom", "Split")
    assert r.reasons and all(isinstance(x, str) and x for x in r.reasons)
    aws = batch >= t.batch_size_threshold or m.userform_count > t.userform_threshold or m.declare_count > t.declare_threshold
    large = m.vba_line_count > t.vba_line_threshold
    if aws:
        assert r.route == "AWS Transform custom"      # 16.2: batch, UserForms or Declares over their thresholds
    elif large and m.formula_count > 0:
        assert r.route == "Split"                      # 16.4: large VBA beside convertible formulas
    elif large:
        assert r.route == "AWS Transform custom"       # 16.3: large VBA and nothing for Ghost to convert
    else:
        assert r.route == "Ghost converts"
    if large:
        assert any(f"{m.vba_line_count} VBA lines exceed" in x for x in r.reasons) or aws
    assert r.metrics == m


@settings(max_examples=100, deadline=None)
@given(metrics, thresholds)
def test_property_31_a_larger_batch_never_moves_a_workbook_back_to_ghost(m, t):
    routes = [recommend_route(m, b, t).route for b in range(1, 25)]
    seen_aws = False
    for route in routes:
        if seen_aws:
            assert route == "AWS Transform custom"
        seen_aws = seen_aws or route == "AWS Transform custom"
