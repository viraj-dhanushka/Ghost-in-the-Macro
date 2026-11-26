"""Size triage: how big is this workbook, without loading it (large-workbook-lane, Part A).

Reads the archive as a stream (defusedxml, one element at a time, freed as it closes). It never calls
openpyxl and never runs a macro; VBA is read statically. Nothing here enforces a limit: ``load_workbook``
keeps its own limits. A number that could not be counted is ``None`` or a lower bound, and says so.
"""
from __future__ import annotations

import os
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

import defusedxml.ElementTree as DET
from defusedxml import DefusedXmlException

from ghost.ingest.limits import DEADLINE_EVERY_TAGS, Deadline, Limits, ProcessingTimeout, UnsupportedFormat
from ghost.ingest.xmlscan import local_name, scan_xml

__all__ = ["SizeProfile", "scan_sizes"]

_DECLARE = re.compile(
    r"^\s*(?:(?:Public|Private|Global)\s+)?Declare\s+(?:PtrSafe\s+)?(?:Sub|Function)\b",
    re.IGNORECASE | re.MULTILINE,
)
_USERFORM = re.compile(r"^\s*Begin\s+\{[0-9A-Fa-f-]+\}\s+\w+", re.MULTILINE)


@dataclass(frozen=True)
class SizeProfile:
    """What was measured. ``cells`` and ``formulas`` are exact when ``counted`` is True; otherwise they are a
    lower bound (counting stopped) or None (nothing was counted), and ``not_counted_reason`` says which."""

    file_bytes: int
    cells: int | None
    formulas: int | None
    counted: bool
    not_counted_reason: str | None
    vba_present: bool
    vba_lines: int
    vba_modules: int
    userforms: int
    declares: int
    vba_error: str | None

    def exceeded(self, limits: Limits) -> tuple[str, ...]:
        """The ingest limits this workbook is over (a lower bound already over counts), in a fixed order."""
        out = []
        if self.file_bytes > limits.max_bytes:
            out.append("file size")
        if self.cells is not None and self.cells > limits.max_cells:
            out.append("cells")
        if self.formulas is not None and self.formulas > limits.max_formulas:
            out.append("formulas")
        return tuple(out)


def _vba_facts(path: str) -> tuple[bool, int, int, int, int, str | None]:
    from ghost.ingest.vba import extract_vba, has_vba_project

    present = has_vba_project(path)
    if not present:
        return False, 0, 0, 0, 0, None
    try:
        modules = extract_vba(path)
    except Exception as exc:  # noqa: BLE001 - an unreadable project is a fact about the file, not a crash
        return True, 0, 0, 0, 0, f"{type(exc).__name__}: {exc}".strip()[:200]
    return (
        True,
        sum(m.line_count for m in modules),
        len(modules),
        sum(1 for m in modules if _USERFORM.search(m.source)),
        sum(len(_DECLARE.findall(m.source)) for m in modules),
        None,
    )


def scan_sizes(
    path: str | os.PathLike[str],
    limits: Limits | None = None,
    clock: Callable[[], float] | None = None,
) -> SizeProfile:
    """Measure ``path`` (.xlsx or .xlsm) by streaming. Raises ``UnsupportedFormat`` for a file that is not a
    workbook archive: no route can be made for it."""
    limits = limits or Limits()
    path = str(path)
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise UnsupportedFormat(f"Cannot read file: {exc}") from exc
    if not zipfile.is_zipfile(path):
        raise UnsupportedFormat("Not a valid workbook archive. Accepted formats: .xlsx and .xlsm.")
    deadline = Deadline(limits.timeout_s, clock) if clock else Deadline(limits.timeout_s)
    cells = formulas = 0
    counted = True
    reason: str | None = None
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if "xl/workbook.xml" not in {i.filename for i in infos}:
                raise UnsupportedFormat("Not an Excel workbook. Accepted formats: .xlsx and .xlsm.")
            if sum(i.file_size for i in infos) > limits.max_uncompressed_bytes:
                cells = formulas = None  # type: ignore[assignment]
                counted = False
                reason = (
                    f"not counted: the archive expands to more than "
                    f"{limits.max_uncompressed_bytes // (1024 * 1024)} MB"
                )
            else:
                tags = 0

                def on_start(tag: str) -> None:
                    nonlocal cells, formulas, tags
                    tags += 1
                    if tags % DEADLINE_EVERY_TAGS == 0:
                        deadline.check()  # every start tag counts, not only cells
                    name = local_name(tag)
                    if name == "c":
                        cells += 1
                    elif name == "f":
                        formulas += 1

                try:
                    for info in infos:
                        deadline.check()
                        name = info.filename
                        if not (name.startswith("xl/worksheets/") and name.endswith(".xml")):
                            continue
                        with zf.open(info) as fh:
                            scan_xml(fh, on_start)
                except ProcessingTimeout:
                    counted = False
                    reason = (
                        f"counting stopped at the {limits.timeout_s:g} s limit; "
                        f"at least {cells} cells and {formulas} formulas were counted"
                    )
    except DefusedXmlException as exc:
        raise UnsupportedFormat(f"Workbook XML rejected as unsafe: {exc}") from exc
    except (zipfile.BadZipFile, DET.ParseError) as exc:
        raise UnsupportedFormat(f"Corrupt workbook archive ({exc}). Accepted formats: .xlsx and .xlsm.") from exc
    present, lines, modules, userforms, declares, vba_error = _vba_facts(path)
    return SizeProfile(
        file_bytes=size, cells=cells, formulas=formulas, counted=counted, not_counted_reason=reason,
        vba_present=present, vba_lines=lines, vba_modules=modules, userforms=userforms, declares=declares,
        vba_error=vba_error,
    )
