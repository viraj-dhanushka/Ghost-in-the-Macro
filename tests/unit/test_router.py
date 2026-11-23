"""Unit tests for the Router (requirements 16.1 to 16.5)."""

import pytest

from ghost.models import Metrics
from ghost.router import ThresholdError, load_thresholds, parse_thresholds, recommend_route

T = load_thresholds()


def test_thresholds_parsed_from_steering_file():
    assert (T.vba_line_threshold, T.userform_threshold, T.declare_threshold, T.batch_size_threshold) == (
        2000,
        3,
        5,
        10,
    )


def test_parse_errors():
    with pytest.raises(ThresholdError):
        parse_thresholds("no block here")
    with pytest.raises(ThresholdError):
        parse_thresholds("```yaml\nrouting_thresholds:\n  version: 1\n```")


def test_ghost_converts():
    m = Metrics(formula_count=10, vba_line_count=2000, calculator_shape=True)
    assert recommend_route(m, 9, T).route == "Ghost converts"


def test_aws_on_batch_userforms_declares():
    assert recommend_route(Metrics(), 10, T).route == "AWS Transform custom"
    assert recommend_route(Metrics(userform_count=4), 1, T).route == "AWS Transform custom"
    assert recommend_route(Metrics(declare_count=6), 1, T).route == "AWS Transform custom"
    assert recommend_route(Metrics(userform_count=3, declare_count=5), 1, T).route == "Ghost converts"


def test_split_and_large_vba_without_formulas():
    assert recommend_route(Metrics(formula_count=5, vba_line_count=2001), 1, T).route == "Split"
    assert recommend_route(Metrics(vba_line_count=2001), 1, T).route == "AWS Transform custom"
