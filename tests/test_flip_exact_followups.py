"""L-04 follow-ups (task 3.12): Skeptic findings on exact hits.

**Validates: Requirements 1.3, 2.3** (live-fixes-2026-11-24)
No LibreOffice needed: workbooks are built with openpyxl into ``tmp_path``; the other
modules are hand-written.
"""
from __future__ import annotations

from decimal import Decimal

from openpyxl import Workbook as XlWorkbook

from ghost import cli
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.models import BoundaryResult, IOSpec, Mapping, exact_hit_text
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_dict, validate_report_dict
from ghost.verifier.flip import (
    MAX_FLIP_CASES, Flip, FlipSummary, find_flips, flip_boundaries, flip_cases,
)
from ghost.verifier.run import load_compute


def _book(tmp_path, cells, sheet="Calc"):
    book = XlWorkbook()
    ws = book.active
    ws.title = sheet
    for k, v in cells.items():
        ws[k] = v
    path = tmp_path / "w.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    return wb, generate_mapping(wb)


_TIER = {"A2": "Quantity", "B2": 3, "A3": "Price", "B3": 25.5, "A4": "Total",
         "B4": "=B2*B3", "A5": "Tier", "B5": '=IF(B4>=500,"Gold","Standard")'}


# --- 1. decimal exact hits are confirmed through the compared-values trace -------------

def _decimal_mapping():
    return Mapping(
        inputs={"p": IOSpec(cell="S!B1", type="decimal", min=Decimal(0), max=Decimal(100))},
        outputs={"o": IOSpec(cell="S!B2", type="string")},
    )


def test_decimal_exact_hit_without_compared_values_is_not_inferred():
    def compute(inputs, trace=None):
        c = inputs["p"] >= Decimal("50.5")
        if trace is not None:
            trace("S!B2#1", c)
        return {"o": "y" if c else "n"}

    s = FlipSummary()
    flips = find_flips(compute, _decimal_mapping(), {"p": Decimal(30)}, seed=1, summary=s)
    assert flips and all(f.exact is None for f in flips), flips
    assert ("S!B2#1", "p") in s.exact_not_checked
    assert any(n.startswith("exact hit not checked (the module's trace did not report")
               for n in s.notes()), s.notes()


def test_transpiled_decimal_condition_keeps_its_confirmed_exact_hit(tmp_path):
    wb, _ = _book(tmp_path, {"B1": 30.5, "B2": '=IF(B1>=50.5,"y","n")'}, sheet="S")
    mapping = _decimal_mapping()
    s = FlipSummary()
    flips = find_flips(load_compute(emit_python(wb, mapping)), mapping, {"p": Decimal(30)},
                       seed=1, summary=s)
    assert {f.exact for f in flips} == {Decimal("50.500")}, flips
    assert not s.exact_not_checked, s.notes()


def test_tier_repro_keeps_its_exact_hits(tmp_path):
    wb, mapping = _book(tmp_path, _TIER)
    flips, s = cli._probe_flips_with_summary(wb, mapping)
    exact = {(f.input_name, f.exact) for f in flips if f.exact is not None}
    assert ("price", Decimal(500)) in exact and ("quantity", Decimal(500)) in exact, flips
    assert not s.exact_not_checked, s.notes()


# --- 2. the case cap never hides an exact hit that is reported -------------------------

def _int_mapping():
    return Mapping(
        inputs={"q": IOSpec(cell="S!B1", type="integer", min=Decimal(0), max=Decimal(10_000)),
                "r": IOSpec(cell="S!B3", type="integer", min=Decimal(0), max=Decimal(10_000))},
        outputs={"o": IOSpec(cell="S!B2", type="string")},
    )


def _flip(i, exact):
    return Flip(f"S!B{i}#1", "q", {"r": Decimal(i)}, Decimal(1000 + i), Decimal(2000 + i),
                Decimal(3000 + i) if exact else None)


def test_exact_cases_come_first_when_the_cap_truncates():
    flips = [_flip(i, exact=False) for i in range(120)] + [_flip(i, exact=True) for i in range(120, 140)]
    s = FlipSummary()
    cases = flip_cases(flips, _int_mapping(), summary=s)
    assert len(cases) == MAX_FLIP_CASES and s.cases_truncated == MAX_FLIP_CASES
    ran = {(c["q"], c["r"]) for c in cases}
    assert all((3000 + i, i) in ran for i in range(120, 140))
    assert not s.exact_not_run
    assert all(b.exact_note is None for b in flip_boundaries(flips, summary=s))


def test_dropped_exact_case_is_marked_on_its_row_and_counted_in_the_notes():
    flips = [_flip(i, exact=True) for i in range(250)]
    s = FlipSummary()
    cases = flip_cases(flips, _int_mapping(), summary=s)
    assert len(cases) == MAX_FLIP_CASES
    assert len(s.exact_not_run) == 50
    rows = flip_boundaries(flips, summary=s)
    ran = {(c["q"], c["r"]) for c in cases}
    for b in rows:
        i = int(b.condition_id.split("!B")[1].split("#")[0])
        if (3000 + i, i) in ran:
            assert b.exact_note is None
        else:
            assert b.exact_note == "found but not run: case limit", b
            assert b.exact is not None
    assert sum(b.exact_note is not None for b in rows) == 50
    assert any("50 exact hits found but not run" in n and str(MAX_FLIP_CASES) in n
               for n in s.notes()), s.notes()


def test_no_truncation_changes_nothing():
    flips = [_flip(i, exact=True) for i in range(10)]
    s = FlipSummary()
    cases = flip_cases(flips, _int_mapping(), summary=s)
    assert cases == [c for f in flips for c in _expected(f)]
    assert s.cases_truncated is None and not s.exact_not_run


def _expected(f):
    return [{**f.others, f.input_name: int(v)} for v in (f.below, f.above, f.exact)]


# --- 3. the exact hit says which other values it needs --------------------------------

def test_boundary_row_names_the_other_values_the_exact_hit_needs(tmp_path):
    wb, mapping = _book(tmp_path, _TIER)
    flips, _ = cli._probe_flips_with_summary(wb, mapping)
    rows = {b.input_name: b for b in flip_boundaries(flips)}
    assert rows["price"].exact == Decimal(500) and rows["price"].exact_others == {"quantity": "1"}
    assert exact_hit_text(rows["price"].exact, rows["price"].exact_others, None) == "500.000 (with quantity = 1)"
    assert rows["quantity"].exact_others == {"price": "1"}
    # schema-valid, in the JSON and in the HTML cell
    report = build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                          boundaries=list(rows.values()))
    data = report_to_dict(report)
    validate_report_dict(data)
    assert any(b.get("exact_others") == {"quantity": "1"} for b in data["boundaries"])
    assert "500.000 (with quantity = 1)" in render_html(report)


def test_older_boundary_json_without_the_new_fields_is_still_valid():
    b = BoundaryResult(cell="S!B1", input_name="q", threshold=Decimal(5))
    data = report_to_dict(build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                                       boundaries=[b]))
    for key in ("exact_others", "exact_note"):
        data["boundaries"][0].pop(key, None)
    validate_report_dict(data)


def test_exact_hit_text_variants():
    assert exact_hit_text(None, None, None) is None
    assert exact_hit_text(Decimal(50), {}, None) == "50"
    assert exact_hit_text(Decimal(50), {"b": "2", "a": "1"}, None) == "50 (with a = 1, b = 2)"
    assert exact_hit_text(Decimal(50), None, "found but not run: case limit") == \
        "50 (found but not run: case limit)"


# --- 4. the CLI line does not call an exact-hit row "off-threshold" --------------------

def test_cli_boundary_line_with_an_exact_hit_is_not_off_threshold():
    b = BoundaryResult(cell="Calc!B5", input_name="price", threshold=Decimal(500),
                       change_point=Decimal(500), kind="condition flip",
                       condition_id="Calc!B5#1", exact=Decimal(500),
                       exact_others={"quantity": "1"})
    line = cli._boundary_line(b)
    assert "off-threshold" not in line
    assert "exact hit 500 (with quantity = 1)" in line
    plain = BoundaryResult(cell="Calc!B5", input_name="price", threshold=Decimal(500),
                           change_point=Decimal(500), kind="condition flip")
    assert "off-threshold" in cli._boundary_line(plain)


# --- 6. the budget note is accurate ----------------------------------------------------

def test_budget_ran_out_before_any_condition_was_found_says_so():
    def compute(inputs, trace=None):
        c = inputs["p"] >= 50
        if trace is not None:
            trace("S!B2#1", c)
        return {"o": "y" if c else "n"}

    s = FlipSummary()
    find_flips(compute, _decimal_mapping(), {"p": Decimal(30)}, seed=1, max_evaluations=1, summary=s)
    assert s.cap_reached and not s.conditions
    notes = s.notes()
    assert not any("0 condition/input pairs not checked" in n for n in notes), notes
    assert any("before any condition was found" in n for n in notes), notes


def test_pairs_searched_at_some_base_points_are_not_counted_as_not_checked(tmp_path):
    wb, mapping = _book(tmp_path, _TIER)
    compute = load_compute(emit_python(wb, mapping))
    base = {"quantity": Decimal(3), "price": Decimal("25.5")}
    full = FlipSummary()
    find_flips(compute, mapping, base, seed=1, summary=full)
    # stop after the first base point finished for every input, before the later bases
    for limit in range(20, full.evaluations_used, 7):
        s = FlipSummary()
        find_flips(compute, mapping, base, seed=1, max_evaluations=limit, summary=s)
        if s.cap_reached and s.conditions and s.partly_checked:
            assert not set(s.partly_checked) & set(s.not_completed)
            notes = s.notes()
            assert any("not checked" in n for n in notes) or not s.not_completed
            assert any("only some of the base points" in n for n in notes), notes
            return
    raise AssertionError("no budget limit left a pair searched at only some base points")


def test_decimal_thresholds_finer_than_the_probe_step_are_noted(tmp_path):
    wb, mapping = _book(tmp_path, {"B1": 3.5, "B2": '=IF(B1>=500.0005,"y","n")'}, sheet="S")
    flips, s = cli._probe_flips_with_summary(wb, mapping)
    assert any("finer than the 0.001 probe step" in n for n in s.notes()), s.notes()


def test_hand_written_logic_gets_a_note_that_flips_come_from_the_transpiled_module():
    assert "transpiled module" in cli._HAND_WRITTEN_FLIP_NOTE
    assert "logic.py" in cli._HAND_WRITTEN_FLIP_NOTE
