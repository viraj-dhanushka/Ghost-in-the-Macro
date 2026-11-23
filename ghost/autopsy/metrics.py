"""Workbook metrics (requirement 2.9). Every number is counted from ingest output."""

from __future__ import annotations

import re

from ghost.models import Metrics, VbaModule, Workbook

_DECLARE = re.compile(
    r"^\s*(?:(?:Public|Private|Global)\s+)?Declare\s+(?:PtrSafe\s+)?(?:Sub|Function)\b",
    re.IGNORECASE | re.MULTILINE,
)
# Exported UserForm modules start with a form header and a "Begin {GUID} Name" block.
_USERFORM = re.compile(r"^\s*Begin\s+\{[0-9A-Fa-f-]+\}\s+\w+", re.MULTILINE)
_NOT_CONVERTED_KINDS = {"unsupported_function", "data_table", "array_formula", "dynamic_array"}


def _is_userform(module: VbaModule) -> bool:
    return bool(_USERFORM.search(module.source))


def metrics(workbook: Workbook, vba: list[VbaModule] | None = None) -> Metrics:
    """Counts for routing and the autopsy report.

    ``calculator_shape`` is True for a workbook of plain formulas: at least one
    formula and no UserForms, Declare calls, external links, volatile functions
    or unsupported constructs. VBA modules alone do not clear the flag.
    """
    modules = workbook.vba_modules if vba is None else vba
    formula_count = sum(1 for c in workbook.cells.values() if c.formula)
    userforms = sum(1 for m in modules if _is_userform(m))
    declares = sum(len(_DECLARE.findall(m.source)) for m in modules)
    external = sum(1 for f in workbook.features if f.kind == "external_link")
    volatile = sum(1 for f in workbook.features if f.kind == "volatile")
    unsupported = sum(1 for f in workbook.features if f.kind in _NOT_CONVERTED_KINDS)
    shape = (
        formula_count > 0
        and userforms == 0
        and declares == 0
        and external == 0
        and volatile == 0
        and unsupported == 0
    )
    return Metrics(
        formula_count=formula_count,
        vba_line_count=sum(m.line_count for m in modules),
        module_count=len(modules),
        userform_count=userforms,
        declare_count=declares,
        external_link_count=external,
        volatile_count=volatile,
        unsupported_count=unsupported,
        calculator_shape=shape,
    )
