"""Thresholds read from VBA conditions: a single-line `If <cond> Then <stmt>` is read only before Then.

Owner-approved engine change (2026-11-26): `If extraKm < 0 Then extraKm = 0` has an assignment after Then,
which the extractor used to read as the comparison `extraKm = 0` and raise a false operator conflict.
Block-form conditions, loops and IIf are unchanged. Known limit, pinned here: on a single-line
`If ... Then ... Else If ...` the second condition is not read.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.thresholds import thresholds_from_vba
from ghost.models import VbaModule


def read(*lines):
    src = "\n".join(lines)
    return thresholds_from_vba([VbaModule(name="Module1.bas", source=src, line_count=len(lines))])


def triples(ts):
    return [(t.cell, t.operator, t.constant, t.source.line) for t in ts]


def test_the_single_line_if_of_the_macro_sample_yields_exactly_one_threshold_and_no_finding():
    ts = read("Function F(extraKm As Double)", "    If extraKm < 0 Then extraKm = 0", "End Function")
    assert triples(ts) == [("extraKm", "<", Decimal("0"), 2)]
    assert detect_inconsistencies(ts) == []


def test_block_form_if_is_unchanged():
    ts = read("If quantity >= 50 Then", "    x = 1", "End If")
    assert triples(ts) == [("quantity", ">=", Decimal("50"), 1)]


def test_the_block_form_of_the_same_logic_gives_the_same_threshold():
    one_line = read("If extraKm < 0 Then extraKm = 0")
    block = read("If extraKm < 0 Then", "    extraKm = 0", "End If")
    assert [(t.cell, t.operator, t.constant) for t in one_line] == [(t.cell, t.operator, t.constant) for t in block]


def test_elseif_with_then_at_the_end_is_unchanged():
    ts = read("If a > 1 Then", "x = 1", "ElseIf total >= 500 Then", "x = 2", "End If")
    assert triples(ts) == [("a", ">", Decimal("1"), 1), ("total", ">=", Decimal("500"), 3)]


def test_every_comparison_before_then_is_still_read():
    ts = read("If a < 1 And b >= 2 Then c = 3")
    assert [(t.cell, t.operator, t.constant) for t in ts] == [("a", "<", Decimal("1")), ("b", ">=", Decimal("2"))]


def test_a_comparison_after_then_is_not_read():
    assert [t.cell for t in read("If a > 1 Then b = 2")] == ["a"]
    assert [t.cell for t in read("If a > 1 Then b > 7")] == ["a"]


def test_a_range_condition_is_read_and_the_statement_after_then_is_not():
    ts = read('If Range("B2").Value > 5 Then x = 0')
    assert len(ts) == 1 and ts[0].operator == ">" and ts[0].constant == Decimal("5")
    assert ts[0].cell.endswith("!B2")


def test_then_is_case_insensitive():
    assert [t.cell for t in read("if a > 1 then b = 2")] == ["a"]
    assert [t.cell for t in read("IF a > 1 THEN b = 2")] == ["a"]


def test_a_variable_that_merely_contains_then_is_not_a_cut_point():
    ts = read("If thenCount > 3 Then x = 1")
    assert [(t.cell, t.operator) for t in ts] == [("thenCount", ">")]


def test_loops_and_iif_are_unchanged():
    assert [t.cell for t in read("While n < 10")] == ["n"]
    assert [t.cell for t in read("x = IIf(a < 5, 1, 2)")] == ["a"]
    assert [t.cell for t in read("Do Until done = 1")] == ["done"]


def test_a_comment_after_then_is_still_stripped_first():
    assert [t.cell for t in read("If a > 1 Then b = 2 ' c < 3")] == ["a"]


def test_known_limit_the_second_condition_of_a_single_line_if_then_else_if_is_not_read():
    ts = read("If a > 1 Then b = 2 Else If c < 3 Then d = 4")
    assert [t.cell for t in ts] == ["a"]  # `c < 3` is not read: recorded as a known limit in the spec


@pytest.mark.parametrize("line", ["If x > 0 Then", "If x > 0 Then ' comment", "ElseIf x > 0 Then"])
def test_a_line_that_ends_at_then_is_read_whole(line):
    assert [t.cell for t in read(line)] == ["x"]
