"""R-04 follow-up: flip probing reports what it did not check (no LibreOffice needed).
**Validates: Requirements 2.8** (review-fixes-2026-11-24, task 4.9; guardrail 5).
"""
from __future__ import annotations
import tempfile
from decimal import Decimal
from pathlib import Path
import pytest
from openpyxl import Workbook as XlWorkbook
from ghost import cli
from ghost.converter.emit_python import emit_python
from ghost.ingest.workbook import load_workbook
from ghost.models import IOSpec, Mapping
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_dict, validate_report_dict
from ghost.verifier.flip import FlipSummary, find_flips, flip_cases, literals_from_workbook
from ghost.verifier.run import load_compute


def _wb(cells: dict[str, object]):
    book = XlWorkbook()
    ws = book.active
    ws.title = "S"
    for ref, v in cells.items():
        ws[ref] = v
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "w.xlsx"
        book.save(path)
        return load_workbook(str(path))


def _map(inputs: dict[str, str], outputs: dict[str, str], types=None) -> Mapping:
    types = types or {}
    return Mapping(
        inputs={n: IOSpec(cell=c, type=types.get(n, "integer"), min=Decimal(0), max=Decimal(1000))
                if types.get(n, "integer") in ("integer", "decimal") else IOSpec(cell=c, type=types[n])
                for n, c in inputs.items()},
        outputs={n: IOSpec(cell=c, type="decimal") for n, c in outputs.items()},
    )


def _base(wb, m):
    return {n: wb.cells[s.cell].value for n, s in m.inputs.items()}


@pytest.fixture
def window():
    wb = _wb({"B1": 7, "B3": 5, "D1": "=IF(AND(B1>10,B1<20),1,0)", "D3": "=IF(B3=777,1,0)"})
    m = _map({"a": "S!B1", "c": "S!B3"}, {"d1": "S!D1", "d3": "S!D3"})
    return wb, m


def test_cap_reached_is_reported(window):
    wb, m = window
    s = FlipSummary()
    find_flips(load_compute(emit_python(wb, m)), m, _base(wb, m), max_evaluations=12, summary=s)
    assert s.cap_reached and s.evaluations_used == 12 and s.not_completed
    line = s.notes()[0]
    assert line == f"flip probing stopped at 12 evaluations; {len(s.not_completed)} condition/input pairs not checked"


def test_blind_spots_caught_with_formula_literals(window):
    wb, m = window
    compute = load_compute(emit_python(wb, m))
    assert {Decimal(10), Decimal(20), Decimal(777)} <= set(literals_from_workbook(wb))
    plain = find_flips(compute, m, _base(wb, m))
    assert not any(f.condition_id.startswith("S!D1") or f.condition_id.startswith("S!D3") for f in plain)
    s = FlipSummary()
    flips = find_flips(compute, m, _base(wb, m), literals=literals_from_workbook(wb), summary=s)
    by = {(f.condition_id.split("#")[0], f.input_name) for f in flips}
    assert ("S!D1", "a") in by and ("S!D3", "c") in by
    d3 = [f for f in flips if f.condition_id.startswith("S!D3")]
    assert any(777 in (f.below, f.above) for f in d3)


def test_unflipped_pair_and_text_input_are_reported():
    wb = _wb({"B1": 7, "B2": 3, "B4": "y", "D1": '=IF(AND(B1>5,B4="y"),1,0)'})
    m = _map({"a": "S!B1", "b": "S!B2", "t": "S!B4"}, {"d": "S!D1"}, {"t": "string"})
    s = FlipSummary()
    find_flips(load_compute(emit_python(wb, m)), m, _base(wb, m), summary=s)
    notes = s.notes()
    assert any(n.startswith("no flip found for S!D1#1 on b [0, 1000]") for n in notes)
    assert "not probed: text input t" in notes
    assert not any("on a " in n or n.endswith("on a") for n in notes if n.startswith("no flip"))


def test_flips_per_search_and_case_truncation_are_reported():
    wb = _wb({"B1": 1, "D1": "=IF(MOD(B1,2)=0,1,0)"})
    m = _map({"a": "S!B1"}, {"d": "S!D1"})
    s = FlipSummary()
    flips = find_flips(load_compute(emit_python(wb, m)), m, _base(wb, m), summary=s)
    assert s.flips_truncated == [("S!D1#1", "a")]
    assert any("kept only the first 3 change points" in n for n in s.notes())
    flip_cases(flips, m, limit=2, summary=s)
    assert s.cases_truncated == 2
    assert any("limit of 2" in n for n in s.notes())


def test_not_convertible_is_reported_not_swallowed(window, monkeypatch, caplog):
    wb, m = window

    def boom(*a, **k):
        raise ValueError("cannot convert")

    monkeypatch.setattr(cli, "_emit_logic", boom)
    flips, s = cli._probe_flips_with_summary(wb, m)
    assert flips == []
    assert s.notes() == ["flip probing not checked: ValueError: cannot convert"]
    assert any("flip probing failed" in r.message for r in caplog.records)


def test_cli_probe_catches_window_and_equality(window):
    wb, m = window
    flips, s = cli._probe_flips_with_summary(wb, m)
    assert {f.condition_id.split("#")[0] for f in flips} == {"S!D1", "S!D3"}
    assert not s.cap_reached


def test_report_carries_notes_and_stays_schema_valid():
    r = build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                     boundary_notes=["flip probing stopped at 5 evaluations; 2 condition/input pairs not checked"])
    data = report_to_dict(r)
    validate_report_dict(data)
    assert data["boundary_notes"]
    assert "stopped at 5 evaluations" in render_html(r)
    plain = report_to_dict(build_report(seed=1, mode="faithful", cases_tested=1, passed=True))
    assert "boundary_notes" not in plain
    validate_report_dict(plain)
