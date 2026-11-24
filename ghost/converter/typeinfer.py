"""One shared type-inference function (review R-03, Requirement 2.7).

Used by ``ghost/converter/mapping.py`` and ``ghost/verifier/strategies.py:infer_spec``
so the mapping and the verifier always agree on an input's type.

Order of decision:
1. Data validation: ``decimal`` -> decimal, ``whole`` -> integer.
2. Sample values: bool -> boolean; str -> string; otherwise numeric.

Whole-valued float (for example ``1.0``) with no validation: decimal.
Excel writes whole numbers to the file as ``12``, which openpyxl reads as ``int``;
a ``float`` only appears when the workbook author or generator deliberately stored
a decimal-typed value. Reading it as integer would hide fractional inputs, so a
truncating bug (``int(distance)``) would pass, which is the R-03 failure. Decimal
is the wider type: it still generates whole values, and every int-sample workbook
(samples (a) and (b)) keeps its integer type because their values are ``int``.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

__all__ = ["to_decimal", "is_integral", "infer_type", "validation_type", "infer_input_type", "infer_formula_kind"]


def to_decimal(x: object) -> Decimal | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        return Decimal(repr(x))
    if isinstance(x, str):
        try:
            return Decimal(x.strip())
        except Exception:
            return None
    return None


def is_integral(d: Decimal) -> bool:
    return d.is_finite() and d == d.to_integral_value()


def infer_type(samples: Iterable[object]) -> str:
    """Return "integer" iff all sample values are integers, else "decimal".

    Booleans give "boolean" and non-numeric strings give "string". With no
    usable samples the type defaults to "decimal".
    """
    vals = [s for s in samples if s is not None]
    if not vals:
        return "decimal"
    if all(isinstance(v, bool) for v in vals):
        return "boolean"
    nums = [to_decimal(v) for v in vals]
    if any(n is None for n in nums):
        return "string"
    return "integer" if all(is_integral(n) for n in nums if n is not None) else "decimal"


def validation_type(validation: str | None) -> str | None:
    if not validation:
        return None
    kind = validation.split(":", 1)[0]
    return {"whole": "integer", "decimal": "decimal"}.get(kind)


_TEXT_FUNCS = frozenset({
    "TEXT", "CONCATENATE", "CONCAT", "LEFT", "RIGHT", "MID", "UPPER", "LOWER",
    "PROPER", "TRIM", "SUBSTITUTE", "REPT", "CLEAN", "T",
})
_NUMBER_FUNCS = frozenset({
    "SUM", "ROUND", "ROUNDUP", "ROUNDDOWN", "INT", "ABS", "MAX", "MIN", "MOD",
    "LEN", "AVERAGE", "COUNT", "PRODUCT", "POWER", "SQRT", "MATCH", "SIGN",
})
_BOOL_FUNCS = frozenset({"AND", "OR", "NOT", "TRUE", "FALSE", "ISNUMBER", "ISTEXT", "ISBLANK", "ISERROR"})
_MAX_DEPTH = 20


def _merge(kinds: list[str | None]) -> str | None:
    """One kind if every branch agrees, else None (undecided)."""
    if not kinds or any(k is None for k in kinds) or len(set(kinds)) != 1:
        return None
    return kinds[0]


def infer_formula_kind(formula: str, cell_kind, sheet: str = "", _depth: int = 0) -> str | None:
    """Statically classify a formula's result as ``"text"``, ``"number"``,
    ``"boolean"`` or None (undecided).

    ``cell_kind(sheet, address)`` returns the same kinds for a referenced cell,
    or None. Nothing is guessed: an undecided branch makes the whole result
    undecided (review R-26).
    """
    from ghost.converter import ast as A
    from ghost.converter.parser import parse_formula

    if _depth > _MAX_DEPTH:
        return None
    try:
        tree = parse_formula(formula)
    except Exception:
        return None

    def ref_kind(r) -> str | None:
        return cell_kind(r.sheet or sheet, r.address)

    def range_kind(r) -> str | None:
        from openpyxl.utils import column_index_from_string, get_column_letter

        c1, c2 = sorted((column_index_from_string(r.start.col), column_index_from_string(r.end.col)))
        r1, r2 = sorted((r.start.row, r.end.row))
        if (c2 - c1 + 1) * (r2 - r1 + 1) > 10_000:
            return None
        sh = r.start.sheet or sheet
        kinds = [
            cell_kind(sh, f"{get_column_letter(c)}{row}")
            for c in range(c1, c2 + 1)
            for row in range(r1, r2 + 1)
        ]
        return _merge(kinds)

    def kind(n) -> str | None:
        if isinstance(n, A.String):
            return "text"
        if isinstance(n, (A.Number, A.Percent)):
            return "number"
        if isinstance(n, A.Boolean):
            return "boolean"
        if isinstance(n, A.CellRef):
            return ref_kind(n)
        if isinstance(n, A.RangeRef):
            return range_kind(n)
        if isinstance(n, A.UnaryOp):
            return "number"
        if isinstance(n, A.BinaryOp):
            if n.op == "&":
                return "text"
            if n.op in ("=", "<>", "<", "<=", ">", ">="):
                return "boolean"
            return "number"
        if isinstance(n, A.FuncCall):
            name = n.name
            if name in _TEXT_FUNCS:
                return "text"
            if name in _NUMBER_FUNCS:
                return "number"
            if name in _BOOL_FUNCS:
                return "boolean"
            if name == "IF" and len(n.args) >= 2:
                branches = [kind(n.args[1])]
                branches.append(kind(n.args[2]) if len(n.args) > 2 else "boolean")
                return _merge(branches)
            if name == "IFERROR" and len(n.args) == 2:
                return _merge([kind(n.args[0]), kind(n.args[1])])
            if name == "INDEX" and n.args:
                return kind(n.args[0])
        return None

    return kind(tree)


def infer_input_type(samples: Iterable[object], validation: str | None = None) -> str:
    """Validation decides first, then the sample values (see module docstring)."""
    vtype = validation_type(validation)
    if vtype:
        return vtype
    vals = [s for s in samples if s is not None]
    if any(isinstance(v, str) for v in vals):
        return "string"  # a text cell is text, even when it looks numeric
    if any(isinstance(v, float) for v in vals):
        return "decimal"  # whole-valued floats included, see module docstring
    return infer_type(vals)
