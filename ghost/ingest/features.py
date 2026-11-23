"""Feature scanner: constructs that cannot be verified or converted as-is.

Static only. Reports each occurrence with its cell reference (Requirements 1.6, 1.7).
"""

from __future__ import annotations

import re

from openpyxl import load_workbook as _opx_load
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from ghost.converter.subset import SUPPORTED_FUNCTIONS
from ghost.models import CellRef, FeatureFlag, Workbook

__all__ = ["scan_features", "VOLATILE_FUNCTIONS", "SUPPORTED_FUNCTIONS", "DYNAMIC_ARRAY_FUNCTIONS"]

VOLATILE_FUNCTIONS = frozenset(
    {"NOW", "TODAY", "RAND", "RANDBETWEEN", "OFFSET", "INDIRECT"}
)


DYNAMIC_ARRAY_FUNCTIONS = frozenset(
    {
        "FILTER", "SORT", "SORTBY", "UNIQUE", "SEQUENCE", "RANDARRAY",
        "TEXTSPLIT", "TOCOL", "TOROW", "VSTACK", "HSTACK", "WRAPCOLS",
        "WRAPROWS", "TAKE", "DROP", "EXPAND", "CHOOSECOLS", "CHOOSEROWS",
    }
)

_STRING_RE = re.compile(r'"(?:[^"]|"")*"')
_FUNC_RE = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_.]*)\s*\(")
_PREFIX_RE = re.compile(r"^(?:_xlfn\.)?(?:_xlws\.)?", re.IGNORECASE)
# [1]Sheet!A1, '[1]Sheet'!A1, 'C:\path\[Book.xlsx]Sheet'!A1
_EXTERNAL_RE = re.compile(r"\[[^\]]+\]")
_SPILL_RE = re.compile(r"[A-Za-z0-9_\)]#")


def _function_names(formula: str) -> list[str]:
    """Distinct function names in order of first appearance, upper-cased."""
    text = _STRING_RE.sub('""', formula)
    seen: dict[str, None] = {}
    for m in _FUNC_RE.finditer(text):
        seen.setdefault(_PREFIX_RE.sub("", m.group(1)).upper(), None)
    return list(seen)


def _array_cells(path: str) -> set[CellRef]:
    """Cells stored as legacy array (CSE) formulas. Empty set if file unreadable."""
    out: set[CellRef] = set()
    try:
        wb = _opx_load(path, data_only=False)
    except Exception:
        return out
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, ArrayFormula):
                    out.add(f"{ws.title}!{c.coordinate}")
                elif isinstance(c.value, DataTableFormula):
                    out.add(f"{ws.title}!{c.coordinate}")
    return out


def scan_features(workbook: Workbook) -> list[FeatureFlag]:
    """Flag volatile, external, data-table, array, dynamic-array and unsupported
    constructs, one flag per occurrence, each with its cell reference.

    The result is also stored on `workbook.features`.
    """
    array_cells = _array_cells(workbook.path)
    flags: list[FeatureFlag] = []

    for ref, cell in workbook.cells.items():
        formula = cell.formula
        if not formula:
            continue
        names = _function_names(formula)
        no_strings = _STRING_RE.sub('""', formula)

        if formula.startswith("=TABLE("):
            flags.append(FeatureFlag(kind="data_table", cell=ref, detail=formula))
            continue
        if ref in array_cells:
            flags.append(FeatureFlag(kind="array_formula", cell=ref, detail=formula))
        dyn = [n for n in names if n in DYNAMIC_ARRAY_FUNCTIONS]
        if dyn or _SPILL_RE.search(no_strings):
            flags.append(
                FeatureFlag(
                    kind="dynamic_array",
                    cell=ref,
                    detail=", ".join(dyn) if dyn else "spill reference (#)",
                )
            )
        if _EXTERNAL_RE.search(no_strings):
            flags.append(
                FeatureFlag(
                    kind="external_link",
                    cell=ref,
                    detail="external workbook reference",
                    not_verifiable=True,
                )
            )
        for name in names:
            if name in VOLATILE_FUNCTIONS:
                flags.append(
                    FeatureFlag(
                        kind="volatile", cell=ref, detail=name, not_verifiable=True
                    )
                )
            elif name in SUPPORTED_FUNCTIONS or name in DYNAMIC_ARRAY_FUNCTIONS:
                continue
            else:
                flags.append(
                    FeatureFlag(kind="unsupported_function", cell=ref, detail=name)
                )

    workbook.features = flags
    return flags
