"""Excel worksheet semantics for generated Ghost modules.

Standalone on purpose: this file is vendored into each generated module
folder, so it imports only from the standard library.

Rules implemented (see .kiro/steering/excel-semantics.md):
  * floats convert with ``Decimal(repr(x))``, never ``Decimal(x)``
  * ROUND works on 15 significant digits, half away from zero
  * worksheet MOD takes the sign of the divisor, INT is floor
  * empty is 0 (arithmetic) or "" (text), booleans are 1/0 in arithmetic
  * text comparison is case-insensitive
  * Excel errors propagate and are never coerced to numbers
"""

from __future__ import annotations

from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
    InvalidOperation,
    localcontext,
)
from typing import Any

__all__ = [
    "ExcelError",
    "DIV0",
    "VALUE",
    "NA",
    "REF",
    "NAME",
    "NUM",
    "NULL",
    "is_error",
    "to_decimal",
    "xl_num",
    "xl_text",
    "xl_bool",
    "xl_add",
    "xl_sub",
    "xl_mul",
    "xl_div",
    "xl_pow",
    "xl_neg",
    "xl_percent",
    "xl_concat",
    "xl_round",
    "xl_roundup",
    "xl_rounddown",
    "xl_int",
    "xl_mod",
    "xl_compare",
    "xl_eq",
    "xl_ne",
    "xl_lt",
    "xl_le",
    "xl_gt",
    "xl_ge",
]

_PREC = 60  # working precision, well above Excel's 15 significant digits


# ---------------------------------------------------------------- errors


class ExcelError:
    """An Excel error value. Equality is by error type (the code string)."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        object.__setattr__(self, "code", code)

    def __setattr__(self, name: str, value: Any) -> None:  # immutable
        raise AttributeError("ExcelError is immutable")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExcelError) and other.code == self.code

    def __hash__(self) -> int:
        return hash(("ExcelError", self.code))

    def __repr__(self) -> str:
        return f"ExcelError({self.code!r})"

    def __str__(self) -> str:
        return self.code


DIV0 = ExcelError("#DIV/0!")
VALUE = ExcelError("#VALUE!")
NA = ExcelError("#N/A")
REF = ExcelError("#REF!")
NAME = ExcelError("#NAME?")
NUM = ExcelError("#NUM!")
NULL = ExcelError("#NULL!")


def is_error(x: Any) -> bool:
    return isinstance(x, ExcelError)


# ------------------------------------------------------------ conversion


def to_decimal(x: Any) -> Decimal:
    """Convert a Python number to Decimal. Floats go through ``repr``.

    Raises ``TypeError`` for non-numeric input; use ``xl_num`` for Excel
    coercion rules.
    """
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        return Decimal(int(x))
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        if x != x or x in (float("inf"), float("-inf")):
            raise ValueError("non-finite float has no Excel value")
        return Decimal(repr(x))
    raise TypeError(f"cannot convert {type(x).__name__} to Decimal")


def xl_num(x: Any) -> Decimal | ExcelError:
    """Coerce a value for arithmetic: empty 0, bool 1/0, numeric text parsed."""
    if isinstance(x, ExcelError):
        return x
    if x is None:
        return Decimal(0)
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return VALUE
        try:
            d = Decimal(s)
        except InvalidOperation:
            return VALUE
        return d if d.is_finite() else VALUE
    try:
        return to_decimal(x)
    except (TypeError, ValueError):
        return VALUE


def xl_text(x: Any) -> str | ExcelError:
    """Coerce a value for text operations: empty is "", bool TRUE/FALSE."""
    if isinstance(x, ExcelError):
        return x
    if x is None:
        return ""
    if isinstance(x, bool):
        return "TRUE" if x else "FALSE"
    if isinstance(x, str):
        return x
    try:
        d = to_decimal(x)
    except (TypeError, ValueError):
        return VALUE
    return _decimal_text(d)


def xl_bool(x: Any) -> bool | ExcelError:
    """Coerce a value for logical tests (IF conditions)."""
    if isinstance(x, ExcelError):
        return x
    if x is None:
        return False
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        u = x.strip().upper()
        if u == "TRUE":
            return True
        if u == "FALSE":
            return False
        return VALUE
    n = xl_num(x)
    if isinstance(n, ExcelError):
        return n
    return n != 0


def _decimal_text(d: Decimal) -> str:
    with localcontext(Context(prec=_PREC)):
        d = _sig15(d)
        if d == 0:
            return "0"
        d = d.normalize()
        exp = d.adjusted()
        # Scientific notation for very large and very small magnitudes, as in
        # the Excel General format: "1E+20", "1.23456789012346E+17", "1E-20".
        # The switch points (>= 1E16, < 1E-14) are the ones measured on the
        # Referee; they are not verified against Excel.
        if exp >= 16 or exp <= -15:
            sign, digits, _ = d.as_tuple()
            mant = "".join(str(x) for x in digits)
            mant = mant[0] + ("." + mant[1:] if len(mant) > 1 else "")
            return f"{'-' if sign else ''}{mant}E{'+' if exp >= 0 else '-'}{abs(exp):02d}"
        s = format(d, "f")
    return s


# -------------------------------------------------------------- arithmetic


def _binary(a: Any, b: Any):
    x, y = xl_num(a), xl_num(b)
    if isinstance(x, ExcelError):
        return x, None, x
    if isinstance(y, ExcelError):
        return None, y, y
    return x, y, None


def xl_add(a: Any, b: Any) -> Decimal | ExcelError:
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    with localcontext(Context(prec=_PREC)):
        return x + y


def xl_sub(a: Any, b: Any) -> Decimal | ExcelError:
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    with localcontext(Context(prec=_PREC)):
        return x - y


def xl_mul(a: Any, b: Any) -> Decimal | ExcelError:
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    with localcontext(Context(prec=_PREC)):
        return x * y


def xl_div(a: Any, b: Any) -> Decimal | ExcelError:
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    if y == 0:
        return DIV0
    with localcontext(Context(prec=_PREC)):
        return x / y


def xl_pow(a: Any, b: Any) -> Decimal | ExcelError:
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    with localcontext(Context(prec=_PREC)):
        try:
            if x == 0 and y == 0:
                return NUM
            if x == 0 and y < 0:
                return DIV0
            if x < 0 and y != y.to_integral_value():
                return NUM
            return x**y
        except InvalidOperation:
            return NUM


def xl_neg(a: Any) -> Decimal | ExcelError:
    x = xl_num(a)
    if isinstance(x, ExcelError):
        return x
    with localcontext(Context(prec=_PREC)):
        return -x if x != 0 else Decimal(0)


def xl_percent(a: Any) -> Decimal | ExcelError:
    x = xl_num(a)
    if isinstance(x, ExcelError):
        return x
    with localcontext(Context(prec=_PREC)):
        return x / Decimal(100)


def xl_concat(a: Any, b: Any) -> str | ExcelError:
    x, y = xl_text(a), xl_text(b)
    if isinstance(x, ExcelError):
        return x
    if isinstance(y, ExcelError):
        return y
    return x + y


# ---------------------------------------------------------------- rounding


def _sig15(d: Decimal) -> Decimal:
    """Normalise to 15 significant digits (half away from zero)."""
    return Context(prec=15, rounding=ROUND_HALF_UP).create_decimal(d)


def _digits(n: Any) -> int | ExcelError:
    d = xl_num(n)
    if isinstance(d, ExcelError):
        return d
    return int(d.to_integral_value(rounding=ROUND_DOWN))  # Excel truncates digits


def _round_with(x: Any, n: Any, mode: str) -> Decimal | ExcelError:
    v = xl_num(x)
    if isinstance(v, ExcelError):
        return v
    k = _digits(n)
    if isinstance(k, ExcelError):
        return k
    with localcontext(Context(prec=_PREC)):
        v = _sig15(v)
        if v == 0:
            return Decimal(0)
        quantum = Decimal(1).scaleb(-k)
        # quantize needs result digits <= prec; widen for large inputs
        try:
            r = v.quantize(quantum, rounding=mode)
        except InvalidOperation:
            return v
        return r if r != 0 else Decimal(0)


def xl_round(x: Any, n: Any = 0) -> Decimal | ExcelError:
    """Worksheet ROUND: 15 significant digits, half away from zero."""
    return _round_with(x, n, ROUND_HALF_UP)


def xl_roundup(x: Any, n: Any = 0) -> Decimal | ExcelError:
    """Worksheet ROUNDUP: away from zero."""
    return _round_with(x, n, ROUND_UP)


def xl_rounddown(x: Any, n: Any = 0) -> Decimal | ExcelError:
    """Worksheet ROUNDDOWN: toward zero."""
    return _round_with(x, n, ROUND_DOWN)


def xl_int(x: Any) -> Decimal | ExcelError:
    """Worksheet INT: floor."""
    v = xl_num(x)
    if isinstance(v, ExcelError):
        return v
    with localcontext(Context(prec=_PREC)):
        r = _sig15(v).to_integral_value(rounding=ROUND_FLOOR)
        return r if r != 0 else Decimal(0)


def xl_mod(a: Any, b: Any) -> Decimal | ExcelError:
    """Worksheet MOD: result takes the sign of the divisor."""
    x, y, err = _binary(a, b)
    if err is not None:
        return err
    if y == 0:
        return DIV0
    with localcontext(Context(prec=_PREC)):
        r = x % y  # exact; sign follows the dividend
        if r != 0 and (r < 0) != (y < 0):
            r += y
        return r if r != 0 else Decimal(0)


# -------------------------------------------------------------- comparison


def _rank(v: Any) -> int:
    if isinstance(v, bool):
        return 2
    if isinstance(v, str):
        return 1
    return 0


def xl_compare(a: Any, b: Any) -> int | ExcelError:
    """Three-way compare with Excel rules. Returns -1, 0, 1 or an error.

    Empty takes the type of the other operand. Otherwise numbers sort below
    text and text below booleans. Text compares case-insensitively.
    """
    if isinstance(a, ExcelError):
        return a
    if isinstance(b, ExcelError):
        return b
    if a is None and b is None:
        return 0
    if a is None:
        a = "" if isinstance(b, str) else (False if isinstance(b, bool) else Decimal(0))
    elif b is None:
        b = "" if isinstance(a, str) else (False if isinstance(a, bool) else Decimal(0))
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    if ra == 1:
        sa, sb = a.casefold(), b.casefold()
        return (sa > sb) - (sa < sb)
    if ra == 2:
        return (a > b) - (a < b)
    try:
        da, db = to_decimal(a), to_decimal(b)
    except (TypeError, ValueError):
        return VALUE
    # Excel compares numbers after normalising to 15 significant digits.
    da, db = _sig15(da), _sig15(db)
    return (da > db) - (da < db)


def _cmp(a: Any, b: Any, test) -> bool | ExcelError:
    c = xl_compare(a, b)
    if isinstance(c, ExcelError):
        return c
    return test(c)


def xl_eq(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c == 0)


def xl_ne(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c != 0)


def xl_lt(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c < 0)


def xl_le(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c <= 0)


def xl_gt(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c > 0)


def xl_ge(a: Any, b: Any) -> bool | ExcelError:
    return _cmp(a, b, lambda c: c >= 0)
