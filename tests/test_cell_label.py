"""The one public label function (readable-proof, Requirement 8.5).

`cell_label` has the exact body of the old private `_left_label`, which now delegates to it. The
two engine helpers were found equivalent on 2026-11-26; this test is the guard for that claim.
`ghost/converter/mapping._label` and the rules namer are not changed by this feature.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

from ghost.autopsy import classify
from ghost.converter.mapping import _label
from ghost.ingest.workbook import load_workbook

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def _workbook(name):
    spec = importlib.util.spec_from_file_location(name, SAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return load_workbook(mod.build(Path(tempfile.mkdtemp()) / f"{name}.xlsx"))


def test_cell_label_is_public_and_exported():
    assert callable(classify.cell_label) and "cell_label" in classify.__all__
    assert classify.cell_label.__doc__ and "left-adjacent" in classify.cell_label.__doc__


@pytest.mark.parametrize("name", ["make_discount", "make_haunted", "make_scenarios"])
def test_cell_label_agrees_with_the_private_helpers_on_every_sample_cell(name):
    wb = _workbook(name)
    assert wb.cells
    for ref in wb.cells:
        got = classify.cell_label(wb, ref)
        assert got == classify._left_label(wb, ref) == _label(wb, ref), ref


def test_known_labels_in_the_haunted_sample():
    wb = _workbook("make_haunted")
    assert classify.cell_label(wb, "Calculator!B2") == "Quantity"
    assert classify.cell_label(wb, "Calculator!B11") is None or classify.cell_label(wb, "Calculator!B11") == "Total"
    assert classify.cell_label(wb, "Calculator!A2") is None  # column A has no left neighbour


def test_left_label_delegates_to_cell_label(monkeypatch):
    monkeypatch.setattr(classify, "cell_label", lambda wb, ref: "delegated")
    assert classify._left_label(None, "S!B2") == "delegated"
