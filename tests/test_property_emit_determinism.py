"""Property 18 of the main spec: Decimal conversion and emit determinism.
Validates Requirements 7.5 and 7.11. No LibreOffice."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ghost import cli
from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.runtime.excel import to_decimal

ROOT = Path(__file__).resolve().parent.parent


@settings(max_examples=500, deadline=None)
@given(st.floats(allow_nan=False, allow_infinity=False))
def test_property_18_a_float_converts_through_repr(x):
    assert to_decimal(x) == Decimal(repr(x))


@settings(max_examples=100, deadline=None)
@given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False))
def test_property_18_the_conversion_is_not_the_binary_expansion(x):
    # Decimal(x) keeps the binary noise (0.1 -> 0.1000000000000000055...); the runtime must not.
    if Decimal(x) != Decimal(repr(x)):
        assert to_decimal(x) != Decimal(x)


@pytest.mark.parametrize("sample", ["make_discount", "make_haunted"])
@pytest.mark.parametrize("mode", ["faithful", "intended"])
def test_property_18_emitting_twice_gives_byte_identical_output(tmp_path, sample, mode):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        mod = __import__(sample)
    finally:
        sys.path.remove(str(ROOT / "samples"))
    book = mod.build(tmp_path / "w.xlsx")
    a = cli._analyse(book)
    mapping = generate_mapping(a.wb, a.roles)
    first = emit_module(a.wb, mapping, mode, [])
    second = emit_module(cli._analyse(book).wb, mapping, mode, [])
    assert first.code == second.code
    assert first.code.encode("utf-8") == second.code.encode("utf-8")
    assert [(e.cell, e.reason) for e in first.not_converted] == [(e.cell, e.reason) for e in second.not_converted]
