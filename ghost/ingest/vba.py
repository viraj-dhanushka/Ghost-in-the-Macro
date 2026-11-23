"""Static VBA extraction using oletools/olevba. Macros are never executed."""

from __future__ import annotations

import logging
from pathlib import Path

from ghost.models import VbaModule


def extract_vba(path: str | Path) -> list[VbaModule]:
    """Return the VBA modules in a workbook, or [] if it has none.

    Reads the vbaProject.bin container statically; nothing is run. Modules are
    returned sorted by name so output is deterministic.
    """
    from oletools.olevba import VBA_Parser  # lazy: keeps import cost off other paths

    logging.getLogger("olevba").setLevel(logging.CRITICAL)
    parser = VBA_Parser(str(path))
    modules: list[VbaModule] = []
    try:
        if not parser.detect_vba_macros():
            return []
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
