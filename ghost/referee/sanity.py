"""Excel sanity check: does the Referee agree with values Excel saved?

Requirements 6.1 to 6.4. A workbook with no Excel-saved values is reported as
"not cross-checked against Excel", never as a pass.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any, Protocol

from ghost.models import SanityResult, Workbook

__all__ = ["compare_pairs", "run_sanity", "sanity_equal", "NOT_CROSS_CHECKED"]

NOT_CROSS_CHECKED = "not cross-checked against Excel"
TOLERANCE = Decimal("1e-6")
_ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}
_CHUNK = 500


class _Reader(Protocol):
    def read(self, cells: list[str]) -> dict[str, Any]: ...


def _error_type(v: Any) -> str | None:
    if isinstance(v, dict) and isinstance(v.get("error"), str):
        return v["error"].upper()
    if isinstance(v, str) and v.upper() in _ERRORS:
        return v.upper()
    return None


def sanity_equal(referee_value: Any, excel_value: Any) -> bool:
    """Numbers by absolute 1e-6, strings exact, Excel errors by error type."""
    ea, eb = _error_type(referee_value), _error_type(excel_value)
    if ea is not None or eb is not None:
        return ea == eb
    # An empty-string result and an empty cell are the same thing in a saved file.
    if referee_value in (None, "") and excel_value in (None, ""):
        return True
    if isinstance(referee_value, bool) or isinstance(excel_value, bool):
        return (
            isinstance(referee_value, bool)
            and isinstance(excel_value, bool)
            and referee_value == excel_value
        )
    a_num = isinstance(referee_value, (int, float, Decimal))
    b_num = isinstance(excel_value, (int, float, Decimal))
    if a_num and b_num:
        da = Decimal(repr(referee_value)) if isinstance(referee_value, float) else Decimal(referee_value)
        db = Decimal(repr(excel_value)) if isinstance(excel_value, float) else Decimal(excel_value)
        if (isinstance(referee_value, float) and not math.isfinite(referee_value)) or (
            isinstance(excel_value, float) and not math.isfinite(excel_value)
        ):
            return referee_value == excel_value
        return abs(da - db) <= TOLERANCE
    if a_num or b_num:
        return False
    return referee_value == excel_value


def compare_pairs(
    pairs: Iterable[tuple[str, Any, Any]],
) -> tuple[int, int, list[dict[str, object]]]:
    """Compare (cell, referee_value, excel_value) triples.

    Returns (matched, total, differences). Each difference lists both values.
    """
    matched = total = 0
    differences: list[dict[str, object]] = []
    for ref, referee_value, excel_value in pairs:
        total += 1
        if sanity_equal(referee_value, excel_value):
            matched += 1
        else:
            differences.append(
                {"cell": ref, "referee": referee_value, "excel": excel_value}
            )
    return matched, total, differences


def run_sanity(workbook: Workbook, referee: _Reader) -> SanityResult:
    """Compare Referee values with Excel-saved values for every formula cell."""
    formula_cells: Sequence[str] = sorted(
        ref for ref, c in workbook.cells.items() if c.formula is not None
    )
    saved = {
        ref: workbook.cells[ref].saved_value
        for ref in formula_cells
        if workbook.cells[ref].saved_value is not None
    }
    if not workbook.excel_saved or not saved:
        return SanityResult(status=NOT_CROSS_CHECKED)  # type: ignore[arg-type]

    # Only formula cells that carry an Excel-saved value can be compared.
    refs = [r for r in formula_cells if r in saved]
    values: dict[str, Any] = {}
    for i in range(0, len(refs), _CHUNK):
        values.update(referee.read(refs[i : i + _CHUNK]))
    matched, total, diffs = compare_pairs(
        (r, values.get(r), saved[r]) for r in refs
    )
    return SanityResult(
        status="matched" if not diffs else "differences",
        matched=matched,
        total=total,
        differences=diffs,
    )
