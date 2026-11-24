"""Generate ``mapping.yaml`` (Requirements 7.10, 8.3).

Maps every INPUT and OUTPUT cell to a stable name, a cell reference, an
inferred type and an inferred range. Output is a pure function of the
workbook: sorted iteration, no timestamps.

Inference rules (all deterministic):
- name: slug of the left-adjacent text label, else ``<sheet>_<address>``;
  duplicates get ``_2``, ``_3`` ... in cell order.
- type: shared with the verifier (ghost/converter/typeinfer.py): ``decimal``
  validation -> decimal, ``whole`` -> integer, else the sample value (int ->
  integer, float -> decimal, str -> string, bool -> boolean). Outputs use the Excel-saved
  value when present; else ``string`` when the formula AST decides the result is text
  (R-26: string literals in every IF branch, ``&``, text functions, INDEX into a text
  range); else decimal (undecided, default kept).
- min: 0 when the sample value is a non-negative number (inputs only).
  No max is inferred. Validation operators are not retained by ingestion,
  so validation bounds are not used.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import yaml
from openpyxl.utils import column_index_from_string

from ghost.autopsy.classify import classify
from ghost.converter.typeinfer import infer_formula_kind, infer_input_type
from ghost.models import Cell, CellRef, IOSpec, Mapping, Workbook

__all__ = ["generate_mapping", "mapping_to_yaml", "write_mapping", "read_mapping"]

_ADDR_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text.strip().lower()).strip("_")
    if not s:
        return ""
    return "n_" + s if s[0].isdigit() else s


def _label(wb: Workbook, ref: CellRef) -> str | None:
    sheet, _, addr = ref.rpartition("!")
    m = _ADDR_RE.match(addr)
    if not m:
        return None
    col = column_index_from_string(m.group(1))
    if col <= 1:
        return None
    from openpyxl.utils import get_column_letter

    left = wb.cells.get(f"{sheet}!{get_column_letter(col - 1)}{m.group(2)}")
    if left is None or left.formula is not None:
        return None
    if isinstance(left.value, str) and left.value.strip():
        return left.value.strip()
    return None


def _type_of(value: object, validation: str | None = None) -> str:
    """Shared with the verifier: validation first, then the sample value."""
    return infer_input_type([value], validation)


def _non_negative(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
    )


def _name(wb: Workbook, ref: CellRef, used: set[str]) -> str:
    base = _slug(_label(wb, ref) or "") or _slug(ref.replace("!", "_"))
    name, n = base, 2
    while name in used:
        name = f"{base}_{n}"
        n += 1
    used.add(name)
    return name


def _static_kind(wb: Workbook, cell: Cell, seen: frozenset[str] = frozenset()) -> str | None:
    """Result kind of ``cell`` from its formula AST (shared typeinfer rules)."""
    if cell.formula is None:
        v = cell.value
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, str):
            return "text" if v != "" else None
        return "number" if isinstance(v, (int, float)) else None
    if cell.ref in seen:
        return None  # circular reference: undecided
    seen = seen | {cell.ref}

    def cell_kind(sheet: str, addr: str) -> str | None:
        other = wb.cells.get(f"{sheet}!{addr}")
        return None if other is None else _static_kind(wb, other, seen)

    sheet = cell.ref.rpartition("!")[0]
    return infer_formula_kind(cell.formula, cell_kind, sheet)


def _output_type(wb: Workbook, cell: Cell) -> str:
    """Excel-saved value first; else the formula AST decides text; else decimal.

    When neither decides (mixed branches, unknown functions, no saved value) the
    historical default ``decimal`` is kept.
    """
    if cell.saved_value is not None:
        return _type_of(cell.saved_value)
    if _static_kind(wb, cell) == "text":
        return "string"
    return "decimal"  # undecided: keep the default


def generate_mapping(
    workbook: Workbook,
    roles: dict[CellRef, str] | None = None,
    user_outputs: list[CellRef] | tuple[CellRef, ...] = (),
) -> Mapping:
    """Build the Mapping for INPUT and OUTPUT cells of ``workbook``."""
    if roles is None:
        roles = classify(workbook, user_outputs)
    inputs: dict[str, IOSpec] = {}
    outputs: dict[str, IOSpec] = {}
    used_in: set[str] = set()
    used_out: set[str] = set()
    for ref in sorted(roles):
        cell: Cell | None = workbook.cells.get(ref)
        if cell is None:
            continue
        if roles[ref] == "INPUT":
            kind = _type_of(cell.value, cell.validation)
            lo = Decimal(0) if kind in ("integer", "decimal") and _non_negative(cell.value) else None
            inputs[_name(workbook, ref, used_in)] = IOSpec(cell=ref, type=kind, min=lo)
        elif roles[ref] == "OUTPUT":
            kind = _output_type(workbook, cell)
            outputs[_name(workbook, ref, used_out)] = IOSpec(cell=ref, type=kind)
    return Mapping(inputs=inputs, outputs=outputs)


def _spec_dict(spec: IOSpec) -> dict:
    d: dict = {"cell": spec.cell, "type": spec.type}
    for key in ("min", "max"):
        v = getattr(spec, key)
        if v is not None:
            d[key] = int(v) if v == v.to_integral_value() else float(v)
    return d


def mapping_to_yaml(mapping: Mapping) -> str:
    data = {
        "version": mapping.version,
        "inputs": {k: _spec_dict(v) for k, v in sorted(mapping.inputs.items())},
        "outputs": {k: _spec_dict(v) for k, v in sorted(mapping.outputs.items())},
    }
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def write_mapping(mapping: Mapping, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(mapping_to_yaml(mapping), encoding="utf-8")


def read_mapping(path: str | Path) -> Mapping:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    def spec(d: dict) -> IOSpec:
        d = dict(d)
        for key in ("min", "max"):
            if d.get(key) is not None:
                d[key] = Decimal(repr(d[key]))
        return IOSpec(**d)

    return Mapping(
        version=data.get("version", 1),
        inputs={k: spec(v) for k, v in (data.get("inputs") or {}).items()},
        outputs={k: spec(v) for k, v in (data.get("outputs") or {}).items()},
    )
