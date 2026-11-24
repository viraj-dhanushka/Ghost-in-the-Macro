"""Workbook loader: formulas, Excel-saved values, named ranges, dependency graph.

Nothing here executes macros. All XML is parsed with defusedxml (pre-scan of
every archive part here, and openpyxl itself uses defusedxml when installed).
"""

from __future__ import annotations

import os
import re
import zipfile
from collections.abc import Callable

import defusedxml.ElementTree as DET
from defusedxml import DefusedXmlException
from openpyxl import load_workbook as _opx_load
from openpyxl.utils import get_column_letter, range_boundaries
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from ghost.ingest.limits import (
    ACCEPTED_FORMATS,
    Deadline,
    Limits,
    ProcessingTimeout,
    TooLarge,
    TooManyCells,
    TooManyFormulas,
    UnsupportedFormat,
)
from ghost.models import Cell, CellRef, Workbook

__all__ = ["load_workbook", "extract_references"]

_EXPAND_LIMIT = 10_000  # max cells enumerated for one range reference

_STRING_RE = re.compile(r'"(?:[^"]|"")*"')
_REF_RE = re.compile(
    r"""(?:(?P<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?
        (?P<a>\$?[A-Za-z]{1,3}\$?\d+)
        (?::(?P<b>\$?[A-Za-z]{1,3}\$?\d+))?
        (?![A-Za-z0-9_(])""",
    re.VERBOSE,
)
_IDENT_RE = re.compile(r"(?<![A-Za-z0-9_.!'$])[A-Za-z_][A-Za-z0-9_.]*(?![A-Za-z0-9_.(!])")
_EXTERNAL_RE = re.compile(r"\[[^\]]*\]")


def _unquote_sheet(name: str) -> str:
    if name.startswith("'") and name.endswith("'"):
        return name[1:-1].replace("''", "'")
    return name


def _norm(a1: str) -> str:
    return a1.replace("$", "").upper()


def _expand(sheet: str, a: str, b: str | None, existing: set[CellRef]) -> list[CellRef]:
    a, b_ = _norm(a), (_norm(b) if b else None)
    if b_ is None:
        return [f"{sheet}!{a}"]
    try:
        c1, r1, c2, r2 = range_boundaries(f"{a}:{b_}")
    except ValueError:
        return []
    if (c2 - c1 + 1) * (r2 - r1 + 1) <= _EXPAND_LIMIT:
        return [
            f"{sheet}!{get_column_letter(c)}{r}"
            for r in range(r1, r2 + 1)
            for c in range(c1, c2 + 1)
        ]
    # Very large range: only cells that actually exist.
    out = []
    for ref in existing:
        sh, _, addr = ref.rpartition("!")
        if sh != sheet:
            continue
        col, row = _split(addr)
        if c1 <= col <= c2 and r1 <= row <= r2:
            out.append(ref)
    return sorted(out)


def _split(addr: str) -> tuple[int, int]:
    from openpyxl.utils import column_index_from_string

    m = re.fullmatch(r"([A-Z]+)(\d+)", addr)
    assert m
    return column_index_from_string(m.group(1)), int(m.group(2))


def extract_references(
    formula: str,
    current_sheet: str,
    named_ranges: dict[str, str] | None = None,
    existing: set[CellRef] | None = None,
) -> set[CellRef]:
    """Cell references (ranges expanded, names resolved) read by `formula`."""
    existing = existing or set()
    named_ranges = named_ranges or {}
    text = _EXTERNAL_RE.sub("", _STRING_RE.sub('""', formula))
    refs: set[CellRef] = set()
    consumed: list[tuple[int, int]] = []
    for m in _REF_RE.finditer(text):
        sheet = _unquote_sheet(m.group("sheet")) if m.group("sheet") else current_sheet
        refs.update(_expand(sheet, m.group("a"), m.group("b"), existing))
        consumed.append(m.span())
    if named_ranges:
        upper = {k.upper(): v for k, v in named_ranges.items()}
        for m in _IDENT_RE.finditer(text):
            if any(s <= m.start() < e for s, e in consumed):
                continue
            target = upper.get(m.group(0).upper())
            if target:
                refs.update(extract_references(target, current_sheet, None, existing))
    return refs


_NAME_TARGET_RE = re.compile(
    r"^(?:'((?:[^']|'')+)'|([^'!:()\s,\[\]]+))!"
    r"\$?([A-Za-z]{1,3})\$?(\d+)(?::\$?([A-Za-z]{1,3})\$?(\d+))?$"
)


def classify_name_target(text: str, sheets: list[str]) -> tuple[str | None, str | None]:
    """(target, None) for a name that is one cell or one rectangle on an existing
    sheet, else (None, reason). Target looks like ``Sheet!A1`` or ``Sheet!A1:B3``."""
    t = text.strip()
    if "[" in t:
        return None, "external reference"
    if "(" in t:
        return None, "dynamic name (formula such as OFFSET or INDIRECT)"
    if "," in t:
        return None, "multi-area name"
    m = _NAME_TARGET_RE.match(t)
    if not m:
        return None, "not a single cell or rectangular range on one sheet"
    sheet = (m.group(1).replace("''", "'") if m.group(1) is not None else m.group(2))
    if sheet not in sheets:
        return None, f"unknown sheet {sheet!r}"
    first = f"{m.group(3).upper()}{m.group(4)}"
    if m.group(5) is None:
        return f"{sheet}!{first}", None
    return f"{sheet}!{first}:{m.group(5).upper()}{m.group(6)}", None


def _check_archive(path: str, limits: Limits, deadline: Deadline) -> None:
    """Reject non-zip, zip bombs and XML with entities (billion laughs, XXE)."""
    if not zipfile.is_zipfile(path):
        raise UnsupportedFormat(
            "Not a valid workbook archive. Accepted formats: .xlsx and .xlsm."
        )
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if sum(i.file_size for i in infos) > limits.max_uncompressed_bytes:
                raise TooLarge("Workbook expands to too much data; rejected.")
            names = {i.filename for i in infos}
            if "xl/workbook.xml" not in names:
                raise UnsupportedFormat(
                    "Not an Excel workbook. Accepted formats: .xlsx and .xlsm."
                )
            cells = 0
            for info in infos:
                deadline.check()
                if not info.filename.lower().endswith((".xml", ".rels", ".vml")):
                    continue
                is_sheet = info.filename.startswith("xl/worksheets/") and info.filename.endswith(".xml")
                with zf.open(info) as fh:
                    if not is_sheet:
                        for _ in DET.iterparse(fh):
                            pass
                        continue
                    # Stream the sheet: count <c> elements and free each one as it
                    # closes, so memory stays flat whatever the sheet size.
                    for _, elem in DET.iterparse(fh, events=("end",)):
                        tag = elem.tag
                        if tag == "c" or tag.endswith("}c"):
                            cells += 1
                            if cells > limits.max_cells:
                                raise TooManyCells(
                                    f"Workbook has more than {limits.max_cells:,} cells; "
                                    f"the limit is {limits.max_cells:,} cells."
                                )
                            if cells % 5000 == 0:
                                deadline.check()
                        if tag == "c" or tag.endswith(("}c", "}row")) or tag == "row":
                            elem.clear()
    except DefusedXmlException as exc:
        raise UnsupportedFormat(f"Workbook XML rejected as unsafe: {exc}") from exc
    except (zipfile.BadZipFile, DET.ParseError) as exc:
        raise UnsupportedFormat(
            f"Corrupt workbook archive ({exc}). Accepted formats: .xlsx and .xlsm."
        ) from exc


def _formula_text(value: object) -> str | None:
    if isinstance(value, ArrayFormula):
        return value.text if value.text.startswith("=") else "=" + value.text
    if isinstance(value, DataTableFormula):
        # Marker only; the feature scanner flags it as a data table.
        return f"=TABLE({value.ref})"
    if isinstance(value, str) and value.startswith("=") and len(value) > 1:
        return value
    return None


def _fill(cell) -> str | None:
    fill = cell.fill
    if fill is None or fill.patternType != "solid":
        return None
    rgb = fill.fgColor.rgb if fill.fgColor.type == "rgb" else None
    if isinstance(rgb, str) and rgb not in ("00000000",):
        return rgb
    if fill.fgColor.type == "theme":
        return f"theme:{fill.fgColor.theme}"
    if fill.fgColor.type == "indexed":
        return f"indexed:{fill.fgColor.indexed}"
    return None


def load_workbook(
    path: str,
    limits: Limits | None = None,
    clock: Callable[[], float] | None = None,
) -> Workbook:
    """Load a .xlsx/.xlsm file into a `Workbook`. Never modifies or executes it."""
    limits = limits or Limits()
    path = str(path)
    if not path.lower().endswith(ACCEPTED_FORMATS):
        raise UnsupportedFormat(
            f"Unsupported file type. Accepted formats: .xlsx and .xlsm."
        )
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise UnsupportedFormat(f"Cannot read file: {exc}") from exc
    if size > limits.max_bytes:
        raise TooLarge(
            f"File is {size} bytes; the limit is {limits.max_bytes // (1024 * 1024)} MB."
        )

    deadline = Deadline(limits.timeout_s, clock) if clock else Deadline(limits.timeout_s)
    _check_archive(path, limits, deadline)

    keep_vba = path.lower().endswith(".xlsm")
    try:
        wb_f = _opx_load(path, data_only=False, keep_vba=keep_vba)
        deadline.check()
        wb_v = _opx_load(path, data_only=True, keep_vba=keep_vba)
    except (ProcessingTimeout, TooLarge):
        raise
    except DefusedXmlException as exc:
        raise UnsupportedFormat(f"Workbook XML rejected as unsafe: {exc}") from exc
    except Exception as exc:  # openpyxl raises many types on malformed input
        raise UnsupportedFormat(
            f"Could not read workbook ({type(exc).__name__}). "
            "Accepted formats: .xlsx and .xlsm."
        ) from exc

    # Formula limit first, cheaply, before building anything.
    formula_count = 0
    for ws in wb_f.worksheets:
        for row in ws.iter_rows():
            deadline.check()
            for c in row:
                if _formula_text(c.value) is not None:
                    formula_count += 1
                    if formula_count > limits.max_formulas:
                        raise TooManyFormulas(
                            f"Workbook has more than {limits.max_formulas:,} formulas; "
                            f"the limit is {limits.max_formulas:,}."
                        )

    result = Workbook(path=path, sheets=[ws.title for ws in wb_f.worksheets])

    # Named ranges (workbook-level and sheet-level).
    for name, dn in wb_f.defined_names.items():
        if dn.attr_text:
            result.named_ranges[name] = dn.attr_text.replace("$", "")
    for name, dn in wb_f.defined_names.items():
        if not dn.attr_text:
            continue
        target, reason = classify_name_target(dn.attr_text, result.sheets)
        if target:
            result.name_targets[name] = target
        else:
            result.name_issues[name] = reason or "not supported"
    scoped = set()
    for ws in wb_f.worksheets:
        for name, dn in ws.defined_names.items():
            if dn.attr_text:
                result.named_ranges.setdefault(name, dn.attr_text.replace("$", ""))
                scoped.add(name)
    for name in sorted(scoped):
        # A sheet-scoped name is never resolved (which sheet's value wins depends
        # on the formula's sheet); a workbook name it shadows is unsafe too.
        result.name_targets.pop(name, None)
        result.name_issues[name] = "sheet-scoped name is not resolved"

    n = 0
    for ws in wb_f.worksheets:
        ws_v = wb_v[ws.title]
        validations: dict[str, str] = {}
        for dv in ws.data_validations.dataValidation:
            desc = dv.type or "validation"
            if dv.formula1:
                desc += f":{dv.formula1}"
            for rng in str(dv.sqref).split():
                try:
                    c1, r1, c2, r2 = range_boundaries(rng)
                except ValueError:
                    continue
                if (c2 - c1 + 1) * (r2 - r1 + 1) > _EXPAND_LIMIT:
                    continue
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        validations[f"{get_column_letter(c)}{r}"] = desc
        for row in ws.iter_rows():
            for c in row:
                n += 1
                if n % 500 == 0:
                    deadline.check()
                formula = _formula_text(c.value)
                fill = _fill(c)
                validation = validations.get(c.coordinate)
                if c.value is None and fill is None and validation is None:
                    continue
                ref = f"{ws.title}!{c.coordinate}"
                if formula is not None:
                    saved = ws_v[c.coordinate].value
                    result.cells[ref] = Cell(
                        ref=ref, value=None, formula=formula, saved_value=saved,
                        fill=fill, validation=validation,
                    )
                    if saved is not None:
                        result.excel_saved = True
                elif c.value is not None:
                    result.cells[ref] = Cell(
                        ref=ref, value=c.value, fill=fill, validation=validation
                    )
                # Styled-but-empty cells carry no logic and are not stored.

    existing = set(result.cells)
    for ref, cell in result.cells.items():
        if cell.formula is None:
            continue
        n += 1
        if n % 200 == 0:
            deadline.check()
        sheet = ref.rpartition("!")[0]
        result.deps[ref] = extract_references(
            cell.formula, sheet, result.named_ranges, existing
        )
    # VBA is detected by content (xl/vbaProject.bin), never by extension, and read
    # statically. Every front end gets the same result from here.
    from ghost.ingest.vba import extract_vba, has_vba_project

    result.vba_present = has_vba_project(path)
    try:
        result.vba_modules = extract_vba(path)
    except Exception as exc:  # unreadable container: keep the upload, say so, never invent modules
        result.vba_modules = []
        result.vba_error = f"{type(exc).__name__}: {exc}".strip()[:200] or "unknown error"
    return result
