"""The XML element cap of the loader's pre-scan (large-workbook-lane correction 2), and the deadline there.
No LibreOffice."""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import pytest

from ghost.ingest.limits import Deadline, Limits, MAX_CELLS, ProcessingTimeout, TooLarge
from ghost.ingest.workbook import _check_archive, load_workbook
from tests.test_triage import _sheet_of_non_cell_tags, make_book

ROOT = Path(__file__).resolve().parent.parent


def test_the_default_cap_is_two_million_and_separate_from_the_cell_cap():
    lim = Limits()
    assert lim.max_xml_elements == 2_000_000
    assert lim.max_cells == MAX_CELLS == 200_000


def test_a_small_file_of_non_cell_tags_is_refused_by_load_workbook_quickly(tmp_path):
    p = _sheet_of_non_cell_tags(tmp_path / "tags.xlsx", 2_100_000)
    assert p.stat().st_size < 1024 * 1024  # a small file
    t0 = time.monotonic()
    with pytest.raises(TooLarge) as err:
        load_workbook(str(p))
    assert str(err.value) == "Workbook has too many XML elements; rejected."
    assert time.monotonic() - t0 < 20  # refused in the pre-scan; openpyxl never saw it


def test_the_cap_counts_every_part_not_only_sheets(tmp_path):
    p = make_book(tmp_path / "a.xlsx")
    with pytest.raises(TooLarge, match="too many XML elements"):
        _check_archive(str(p), Limits(max_xml_elements=20), Deadline(60))
    _check_archive(str(p), Limits(max_xml_elements=100_000), Deadline(60))  # a normal file is well inside


def test_the_cap_is_applied_before_the_cell_cap_can_matter(tmp_path):
    p = _sheet_of_non_cell_tags(tmp_path / "tags.xlsx", 5_000)
    with pytest.raises(TooLarge):
        _check_archive(str(p), Limits(max_xml_elements=1_000), Deadline(60))


def test_the_precheck_deadline_counts_every_start_tag(tmp_path):
    p = _sheet_of_non_cell_tags(tmp_path / "tags.xlsx", 1_000_000)
    calls = []

    def clock():
        calls.append(1)
        return len(calls) * 100.0

    with pytest.raises(ProcessingTimeout):
        _check_archive(str(p), Limits(max_xml_elements=50_000_000), Deadline(250, clock))
    assert len(calls) <= 8, len(calls)


def test_every_sample_workbook_loads_with_the_counts_it_had_before_the_change():
    """/tmp/counts_before.json is not available to a fresh checkout, so the counts are pinned here (measured with the
    code before the change on 2026-11-26)."""
    import sys
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_discount, make_haunted, make_scenarios, make_traps, make_xlsm
    finally:
        sys.path.remove(str(ROOT / "samples"))
    pinned = json.loads((ROOT / "tests" / "fixtures" / "sample_counts_2026-11-26.json").read_text(encoding="utf-8"))
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        make_discount.build(t / "discount.xlsx")
        make_haunted.build(t / "haunted.xlsx")
        make_scenarios.build(t / "scenarios.xlsx")
        make_traps.build().save(t / "traps.xlsx")
        got = {}
        for f in sorted(t.glob("*.xlsx")):
            wb = load_workbook(str(f))
            got[f.name] = {"cells": len(wb.cells), "formulas": sum(1 for c in wb.cells.values() if c.formula),
                           "sheets": wb.sheets, "deps": len(wb.deps)}
    assert got == pinned
