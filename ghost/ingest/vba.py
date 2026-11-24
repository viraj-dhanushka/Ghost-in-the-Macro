"""Static VBA extraction using oletools/olevba. Macros are never executed."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from ghost.models import VbaModule

VBA_PROJECT_PART = "xl/vbaProject.bin"


def has_vba_project(path: str | Path) -> bool:
    """True if the zip holds ``xl/vbaProject.bin``, whatever the file extension."""
    try:
        with zipfile.ZipFile(str(path)) as z:
            return VBA_PROJECT_PART in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def extract_vba(path: str | Path) -> list[VbaModule]:
    """Return the VBA modules in a workbook, or [] if it has no vbaProject.bin.

    Raises ValueError (or an olevba error) when vbaProject.bin exists but cannot be read;
    ``load_workbook`` records that as ``vba_error`` instead of reporting "no VBA".

    Detection is by content (``xl/vbaProject.bin`` in the zip), not by extension.
    Reads the vbaProject.bin container statically; nothing is run. Modules are
    returned sorted by name so output is deterministic.
    """
    if not has_vba_project(path):
        return []
    from oletools.olevba import VBA_Parser  # lazy: keeps import cost off other paths

    logging.getLogger("olevba").setLevel(logging.CRITICAL)
    parser = VBA_Parser(str(path))
    modules: list[VbaModule] = []
    try:
        if not parser.detect_vba_macros():
            # xl/vbaProject.bin exists, so "no modules" would be invented data.
            raise ValueError("xl/vbaProject.bin is present but holds no readable VBA modules")
        for _file, _stream, name, code in parser.extract_macros():
            source = (code or "").replace("\r\n", "\n").replace("\r", "\n")
            source = source.rstrip("\n")
            line_count = len(source.split("\n")) if source else 0
            modules.append(
                VbaModule(name=str(name), source=source, line_count=line_count)
            )
    finally:
        parser.close()
    modules.sort(key=lambda m: m.name)
    return modules
