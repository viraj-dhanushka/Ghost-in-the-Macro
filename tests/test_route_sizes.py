"""The router with sizes (large-workbook-lane, Requirement 2, Properties 2 and 5). No LibreOffice."""
from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ghost.ingest.limits import MAX_CELLS, MAX_FILE_BYTES, MAX_FORMULAS
from ghost.ingest.triage import SizeProfile
from ghost.models import Metrics
from ghost.router import DEFAULT_THRESHOLDS, RoutingThresholds, parse_thresholds, recommend_route
from ghost.router.route import route_for_sizes

ROOT = Path(__file__).resolve().parent.parent
FOUR_KEYS = """```yaml
routing_thresholds:
  version: 1
  vba_line_threshold: 2000
  userform_threshold: 3
  declare_threshold: 5
  batch_size_threshold: 10
```"""


def profile(**o):
    d = dict(file_bytes=1000, cells=100, formulas=10, counted=True, not_counted_reason=None, vba_present=False,
             vba_lines=0, vba_modules=0, userforms=0, declares=0, vba_error=None)
    d.update(o)
    return SizeProfile(**d)


# -- thresholds (Property 5) -------------------------------------------------------------------
def test_a_file_with_only_the_four_original_keys_loads_with_the_defaults():
    t = parse_thresholds(FOUR_KEYS)
    assert t == DEFAULT_THRESHOLDS
    assert (t.max_file_bytes, t.max_cells, t.max_formulas) == (MAX_FILE_BYTES, MAX_CELLS, MAX_FORMULAS)
    assert t.transform_definition == "AWS/vba-to-python-migration"


def test_the_shipped_steering_file_loads_and_equals_the_defaults():
    from ghost.router import load_thresholds
    assert load_thresholds() == DEFAULT_THRESHOLDS


def test_the_optional_keys_are_read_and_checked():
    text = FOUR_KEYS.replace("batch_size_threshold: 10", "batch_size_threshold: 10\n  max_cells: 1000\n  transform_definition: Team/vba")
    t = parse_thresholds(text)
    assert t.max_cells == 1000 and t.transform_definition == "Team/vba"
    from ghost.router import ThresholdError
    for bad in ("max_cells: -1", "max_cells: abc", "transform_definition: 5", "transform_definition: ''"):
        with pytest.raises(ThresholdError):
            parse_thresholds(FOUR_KEYS.replace("batch_size_threshold: 10", "batch_size_threshold: 10\n  " + bad))


def test_a_size_threshold_above_the_ingest_limit_does_not_raise_the_limit():
    t = RoutingThresholds(max_cells=10 * MAX_CELLS)
    r = route_for_sizes(profile(cells=MAX_CELLS + 1), t)
    assert any("cells" in x for x in r.reasons)


# -- routes ------------------------------------------------------------------------------------
def test_an_over_limit_workbook_without_big_vba_gets_its_own_route_and_says_formulas_are_not_sent():
    r = route_for_sizes(profile(cells=MAX_CELLS + 5, formulas=30_000), DEFAULT_THRESHOLDS)
    assert r.route == "Over Ghost's limits"
    text = "\n".join(r.reasons)
    assert f"{MAX_CELLS + 5:,} cells" in text and "30,000 formulas" in text
    assert "Formulas: 30,000, not sent, not converted by Ghost (over the limit)" in r.parts
    assert "VBA: none" in r.parts
    assert r.atx_command is None


def test_an_over_limit_workbook_with_big_vba_routes_the_vba_to_aws_and_not_the_formulas():
    r = route_for_sizes(profile(cells=MAX_CELLS + 1, vba_present=True, vba_lines=5000, vba_modules=4), DEFAULT_THRESHOLDS)
    assert r.route == "AWS Transform custom"
    assert "VBA: 5000 lines, goes to AWS Transform custom (suggested command, not run)" in r.parts
    assert any(p.startswith("Formulas: 10, not sent, not converted by Ghost") for p in r.parts)
    assert "5000 VBA lines exceed" in " ".join(r.reasons) and "cells" in " ".join(r.reasons)


def test_a_file_over_the_byte_limit_is_named():
    r = route_for_sizes(profile(file_bytes=MAX_FILE_BYTES + 1), DEFAULT_THRESHOLDS)
    assert any("file is" in x and "bytes" in x for x in r.reasons)


def test_uncounted_formulas_are_said_to_be_uncounted_never_guessed():
    r = route_for_sizes(profile(file_bytes=MAX_FILE_BYTES + 1, cells=None, formulas=None, counted=False,
                                not_counted_reason="not counted: the archive expands to more than 200 MB"),
                        DEFAULT_THRESHOLDS)
    assert "Formulas: not counted" in r.parts
    assert any("not counted" in x for x in r.reasons)


def test_unreadable_vba_is_said_so_and_does_not_crash():
    r = route_for_sizes(profile(cells=MAX_CELLS + 1, vba_present=True, vba_error="ValueError: x"), DEFAULT_THRESHOLDS)
    assert "VBA: not readable" in r.parts


def test_not_checked_metrics_are_named():
    r = route_for_sizes(profile(cells=MAX_CELLS + 1), DEFAULT_THRESHOLDS)
    assert any(p.startswith("Not checked") and "external links" in p for p in r.parts)


def test_the_old_path_is_unchanged_and_now_carries_part_sentences():
    r = recommend_route(Metrics(formula_count=3, vba_line_count=10, calculator_shape=True))
    assert r.route == "Ghost converts"
    assert r.reasons == [
        "10 VBA lines are within the threshold of 2000",
        "UserForm and Declare counts are within their thresholds",
        "batch size 1 is below 10",
    ]
    assert "VBA: 10 lines, read statically, not converted by Ghost" in r.parts
    assert any(p.startswith("Formulas: 3, not sent, converted by Ghost") for p in r.parts)
    big = recommend_route(Metrics(formula_count=5, vba_line_count=3000))
    assert big.route == "Split"
    assert "VBA: 3000 lines, goes to AWS Transform custom (suggested command, not run)" in big.parts


# -- Property 2 --------------------------------------------------------------------------------
sizes = st.builds(
    SizeProfile,
    file_bytes=st.integers(0, 3 * MAX_FILE_BYTES),
    cells=st.one_of(st.none(), st.integers(0, 3 * MAX_CELLS)),
    formulas=st.one_of(st.none(), st.integers(0, 3 * MAX_FORMULAS)),
    counted=st.booleans(),
    not_counted_reason=st.one_of(st.none(), st.just("not counted: reason")),
    vba_present=st.booleans(),
    vba_lines=st.integers(0, 10_000),
    vba_modules=st.integers(0, 20),
    userforms=st.integers(0, 10),
    declares=st.integers(0, 20),
    vba_error=st.one_of(st.none(), st.just("ValueError: x")),
)
thresholds = st.builds(
    RoutingThresholds,
    vba_line_threshold=st.integers(0, 5000), userform_threshold=st.integers(0, 6), declare_threshold=st.integers(0, 10),
    batch_size_threshold=st.integers(1, 20), max_file_bytes=st.integers(1, 2 * MAX_FILE_BYTES),
    max_cells=st.integers(1, 2 * MAX_CELLS), max_formulas=st.integers(1, 2 * MAX_FORMULAS),
)


@settings(max_examples=300, deadline=None)
@given(sizes, thresholds, st.integers(1, 15))
def test_property_2_exactly_one_route_and_every_limit_exceeded_is_in_the_reasons(s, t, batch):
    """Property 2 (large-workbook-lane design). Validates Requirements 2.3 and 2.1."""
    r = route_for_sizes(s, t, batch_size=batch)
    assert r.route in ("Ghost converts", "AWS Transform custom", "Split", "Over Ghost's limits")
    text = " ".join(r.reasons)
    mb = min(t.max_file_bytes, MAX_FILE_BYTES)
    mc = min(t.max_cells, MAX_CELLS)
    mf = min(t.max_formulas, MAX_FORMULAS)
    if s.file_bytes > mb:
        assert f"{s.file_bytes:,} bytes" in text
    if s.cells is not None and s.cells > mc:
        assert f"{s.cells:,} cells" in text
    if s.formulas is not None and s.formulas > mf:
        assert f"{s.formulas:,} formulas" in text
    if s.formulas is None or not s.counted:
        assert any(p.startswith("Formulas: not counted") for p in r.parts)
    assert r.parts, "every route says what happens to each part"
    # a route that is "Ghost converts" or "Split" is only possible when nothing is over a limit
    over = s.file_bytes > mb or (s.cells or 0) > mc or (s.formulas or 0) > mf
    if over:
        assert r.route in ("AWS Transform custom", "Over Ghost's limits")
