"""L-06: the boundary table puts each value in its own column, as readable text.

Live finding L-06 (docs/LIVE_TEST_REPORT_2026-11-24.md): flip text sat under "Owner of
threshold", threshold rows showed raw JSON in "Change-point bracket", a flip row showed
its change point as the Threshold, and exact hits that exist were not shown.

The assertions read the visible text of the rendered HTML table, cell by cell, not the
markup. The synthetic report has both kinds of boundary row. A second test renders the real
haunted report.

**Validates: Requirements 1.5, 2.5**
"""

from __future__ import annotations

import json
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest

from ghost import cli
from ghost.models import BoundaryResult
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.report.html import build_report, render_html


class _Tables(HTMLParser):
    """Collect each table as a list of rows of visible cell text."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None


def _boundary_table(html: str) -> list[dict[str, str]]:
    """The boundary table as rows keyed by header text."""
    parser = _Tables()
    parser.feed(html)
    for table in parser.tables:
        if table and "Change-point bracket" in table[0]:
            head = table[0]
            return [dict(zip(head, row)) for row in table[1:]]
    raise AssertionError("no boundary table in the report")


def _synthetic_rows() -> dict[str, dict[str, str]]:
    boundaries = [
        # Threshold row (operator ownership, bracket as change-point dict).
        BoundaryResult(
            cell="S!B1", input_name="quantity", threshold=Decimal(50), change_point=Decimal(50),
            operator_includes="at",
            exact_hits=[{"last_unchanged": 49, "first_changed": 50}],
        ),
        # Flip row, exact hit that needs another input.
        BoundaryResult(
            cell="S!B2", input_name="price", threshold=Decimal(10), change_point=Decimal(10),
            kind="condition flip", condition_id="S!B2#1",
            below=Decimal(9), above=Decimal(11), exact=Decimal(10),
            exact_others={"quantity": "1"},
        ),
        # Flip row, exact hit found but its case was dropped by the case limit.
        BoundaryResult(
            cell="S!B3", input_name="price", threshold=Decimal(500), change_point=Decimal(500),
            kind="condition flip", condition_id="S!B3#1",
            below=Decimal("499.999"), above=Decimal("500"), exact=Decimal(500),
            exact_note="found but not run: case limit",
        ),
        # Flip row with no exact hit; threshold equals the change point (51), as B9 had.
        BoundaryResult(
            cell="S!B4", input_name="quantity", threshold=Decimal(51), change_point=Decimal(51),
            kind="condition flip", condition_id="S!B4#1",
            below=Decimal(50), above=Decimal(51),
        ),
    ]
    html = render_html(build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                                    boundaries=boundaries))
    rows = _boundary_table(html)
    assert len(rows) == 4
    return {r["Condition"] if "Condition" in r else r["Cell"]: r for r in rows}


def test_l06_bracket_column_is_readable_text_for_both_row_kinds():
    rows = _synthetic_rows()
    assert rows["S!B1"]["Change-point bracket"] == "49 → 50"
    assert rows["S!B2#1"]["Change-point bracket"] == "9 → 11"
    assert rows["S!B3#1"]["Change-point bracket"] == "499.999 → 500"
    assert rows["S!B4#1"]["Change-point bracket"] == "50 → 51"


def test_l06_no_raw_json_and_no_flip_text_outside_the_bracket_column():
    for row in _synthetic_rows().values():
        for header, text in row.items():
            assert "first_changed" not in text and "last_unchanged" not in text, header
            assert "{" not in text and "[" not in text, header
            if header != "Change-point bracket":
                assert "condition flip" not in text and "one side" not in text, header


def test_l06_owner_column_only_says_which_side_owns_the_threshold():
    rows = _synthetic_rows()
    owner = "Owner of threshold"
    assert rows["S!B1"][owner] == "at"
    # A flip row has no operator ownership: not-checked text, never the flip bracket.
    for key in ("S!B2#1", "S!B3#1", "S!B4#1"):
        assert rows[key][owner] == "not checked"


def test_l06_threshold_column_is_the_constant_or_calculated_never_the_change_point():
    rows = _synthetic_rows()
    assert rows["S!B1"]["Threshold"] == "50"
    # B4's threshold field holds its change point (51), like B9 did. The column must not show it.
    assert rows["S!B4#1"]["Threshold"] != "51"


# Not xfail: task 3.12 already fills this column, so this test passes today and guards it.
def test_l06_exact_hits_column_shows_the_value_with_other_inputs_or_the_reason():
    rows = _synthetic_rows()
    hits = "Exact hits"
    assert rows["S!B1"][hits] == "not checked"
    assert rows["S!B2#1"][hits] == "10 (with quantity = 1)"
    assert rows["S!B3#1"][hits] == "500 (found but not run: case limit)"
    assert rows["S!B4#1"][hits] == "not checked"
    # The bracket never leaks into the exact hits column.
    assert "→" not in "".join(r[hits] for r in rows.values())


# --- the real haunted report ------------------------------------------------

try:
    locate_soffice()
    _HAVE_SOFFICE = True
except RefereeUnavailable:
    _HAVE_SOFFICE = False


@pytest.fixture(scope="module")
def haunted_html(tmp_path_factory) -> str:
    out: Path = tmp_path_factory.mktemp("demo_l06")
    assert cli.main(["demo", "--out", str(out)]) == 0
    return (out / "haunted" / "reports" / "faithful" / "proof-report.html").read_text(encoding="utf-8")


@pytest.mark.skipif(not _HAVE_SOFFICE, reason="soffice not available")
def test_l06_haunted_report_shows_quantity_50_as_an_exact_hit(haunted_html):
    rows = _boundary_table(haunted_html)
    flips = {r["Cell"]: r for r in rows if r["Input"] == "quantity"}
    assert set(flips) == {"Calculator!B7#1", "Calculator!B9#1"} or {
        "Calculator!B7", "Calculator!B9"} <= set(flips)
    for cell, bracket in (("B7", "49 → 50"), ("B9", "50 → 51")):
        row = next(r for k, r in flips.items() if k.startswith(f"Calculator!{cell}"))
        assert row["Exact hits"].startswith("50"), row
        assert row["Change-point bracket"] == bracket
        assert row["Threshold"] == "50"  # the constant in the formula, not 51
    # The threshold rows (input is the cell reference) show brackets as text too.
    for row in rows:
        assert "first_changed" not in json.dumps(row)


# --- L-06: flip probing says whether a condition has a constant threshold ----


def _flip_boundaries_for(tmp_path, cells):
    from openpyxl import Workbook as XlWorkbook

    from ghost.converter.mapping import generate_mapping
    from ghost.ingest.workbook import load_workbook

    book = XlWorkbook()
    ws = book.active
    ws.title = "S"
    for k, v in cells.items():
        ws[k] = v
    path = tmp_path / "w.xlsx"
    book.save(path)
    wb = load_workbook(str(path))
    flips, _summary = cli._probe_flips_with_summary(wb, generate_mapping(wb))
    from ghost.verifier.flip import flip_boundaries

    return {(b.condition_id, b.input_name): b for b in flip_boundaries(flips)}


def test_l06_flip_probing_reports_constant_and_calculated_thresholds(tmp_path):
    rows = _flip_boundaries_for(tmp_path, {
        "A1": "Qty", "B1": 20, "A2": "Limit", "B2": 40,
        "B3": '=IF(B1>=50,"bulk","small")',        # literal constant
        "B5": "=B1*2",
        "B4": '=IF(B1*3>=B5+30,"bulk","small")',   # both sides move with the input: calculated
    })
    const = rows[("S!B3#1", "Qty")] if ("S!B3#1", "Qty") in rows else next(
        b for (c, _), b in rows.items() if c == "S!B3#1")
    calc = [b for (c, _), b in rows.items() if c == "S!B4#1"]
    assert const.threshold_constant == Decimal(50) and not const.threshold_calculated
    assert calc and all(b.threshold_calculated and b.threshold_constant is None for b in calc), calc
    # The report shows them as the constant and as "calculated".
    html = render_html(build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                                    boundaries=list(rows.values())))
    texts = {r["Cell"]: r["Threshold"] for r in _boundary_table(html)}
    assert texts["S!B3#1"] == "50" and texts["S!B4#1"] == "calculated"
