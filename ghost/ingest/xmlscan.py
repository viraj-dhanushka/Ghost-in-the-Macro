"""Stream an XML part through defusedxml without building a tree.

``ElementTree.iterparse`` builds elements as it goes, and even a cleared element stays attached to its parent, so
a sheet with millions of rows grows memory with the row count. A parser *target* receives the events and builds
nothing; the defusedxml parser still refuses entities, DTDs and external references.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import BinaryIO

import defusedxml.ElementTree as DET

__all__ = ["scan_xml", "local_name"]

_CHUNK = 1 << 16


def local_name(tag: str) -> str:
    """``{namespace}c`` -> ``c``."""
    return tag.rsplit("}", 1)[-1]


class _Target:
    def __init__(self, on_start: Callable[[str], None] | None) -> None:
        self._on_start = on_start

    def start(self, tag: str, attrib: dict) -> None:
        if self._on_start is not None:
            self._on_start(tag)

    def end(self, tag: str) -> None:
        pass

    def data(self, data: str) -> None:
        pass

    def close(self) -> None:
        return None


def scan_xml(fh: BinaryIO, on_start: Callable[[str], None] | None = None) -> None:
    """Parse ``fh`` completely (so a malformed or unsafe part is rejected) and call ``on_start(tag)`` for every
    start tag. Raises the defusedxml exceptions and ``ParseError`` as the tree-building parser did; an exception
    raised by ``on_start`` propagates."""
    parser = DET.XMLParser(target=_Target(on_start))
    while True:
        data = fh.read(_CHUNK)
        if not data:
            break
        parser.feed(data)
    parser.close()
