"""Value comparison between Referee output and generated code output.

Numbers compare by absolute tolerance (default 1e-6), strings compare exactly,
and Excel errors compare by error type. Errors are never coerced to numbers.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from ghost.runtime.excel import ExcelError

DEFAULT_TOL = 1e-6

_ERROR_CODES = frozenset(
    {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}
)


def error_code(value: Any) -> str | None:
    """Return the Excel error type of ``value``, or None if it is not an error."""
    if isinstance(value, ExcelError):
        return value.code
    if isinstance(value, str) and value in _ERROR_CODES:
        return value
    return None


def _is_number(value: Any) -> bool:
    # Booleans behave as 1/0 (Excel semantics table row 8).
    return isinstance(value, (int, float, Decimal))


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(value)


def _numbers_equal(a: Any, b: Any, tol: float) -> bool:
    a_nan = (isinstance(a, float) and math.isnan(a)) or (isinstance(a, Decimal) and a.is_nan())
    b_nan = (isinstance(b, float) and math.isnan(b)) or (isinstance(b, Decimal) and b.is_nan())
    if a_nan or b_nan:
        return a_nan and b_nan
    da, db = _to_decimal(a), _to_decimal(b)
    if da.is_infinite() or db.is_infinite():
        return da == db
    return abs(da - db) <= Decimal(repr(float(tol)))


# Number-to-text in scientific notation: Excel writes "1E+20", LibreOffice "1E+020".
# Only strings of exactly this shape, on both sides, compare by value (R-08).
_SCI = re.compile(r"-?[0-9](?:\.[0-9]+)?E[+-][0-9]{2,3}")


def _same_scientific(a: str, b: str) -> bool:
    if not (_SCI.fullmatch(a) and _SCI.fullmatch(b)):
        return False
    return Decimal(a) == Decimal(b)


def values_equal(a: Any, b: Any, tol: float = DEFAULT_TOL) -> bool:
    """True when ``a`` and ``b`` are equal under the Ghost verifier rules."""
    ea, eb = error_code(a), error_code(b)
    if ea is not None or eb is not None:
        return ea == eb
    if _is_number(a) and _is_number(b):
        return _numbers_equal(a, b, tol)
    if isinstance(a, str) and isinstance(b, str):
        return a == b or _same_scientific(a, b)
    if _is_number(a) or _is_number(b) or isinstance(a, str) or isinstance(b, str):
        return False
    return a == b


def _norm_value(value: Any) -> tuple[str, str]:
    """Key part for one input value: equal numbers share a key (R-28)."""
    if isinstance(value, bool):
        return ("bool", str(value))
    if isinstance(value, (int, float, Decimal)):
        try:
            d = value if isinstance(value, Decimal) else Decimal(repr(value))
            if d.is_finite():
                return ("num", format(d.normalize(), "f"))
        except Exception:  # noqa: BLE001
            pass
        return ("num", str(value))
    return (type(value).__name__, str(value))


def case_key(case: dict[str, Any]) -> tuple:
    """Hashable key of one input case. Decimal('1.0'), Decimal('1.00') and 1 are one case."""
    return tuple((n, *_norm_value(case[n])) for n in sorted(case))
