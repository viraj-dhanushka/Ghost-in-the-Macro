"""Safety limits and error types for workbook ingestion."""

from __future__ import annotations

import time
from dataclasses import dataclass

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FORMULAS = 20_000
# Cells (<c> elements, all sheets), counted while streaming the sheet XML
# before openpyxl loads anything. Bounds memory for large but legal files.
MAX_CELLS = 200_000
DEFAULT_TIMEOUT_S = 60.0
# Guard against zip bombs: total uncompressed size of all archive parts.
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

ACCEPTED_FORMATS = (".xlsx", ".xlsm")


class IngestError(Exception):
    """Base class for ingestion errors."""


class UnsupportedFormat(IngestError):
    pass


class TooLarge(IngestError):
    pass


class TooManyFormulas(IngestError):
    pass


class TooManyCells(IngestError):
    pass


class ProcessingTimeout(IngestError):
    pass


@dataclass(frozen=True)
class Limits:
    max_bytes: int = MAX_FILE_BYTES
    max_formulas: int = MAX_FORMULAS
    max_cells: int = MAX_CELLS
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES


class Deadline:
    """Cooperative wall-clock deadline. `clock` is injectable for tests."""

    def __init__(self, timeout_s: float, clock=time.monotonic) -> None:
        self._clock = clock
        self._timeout = timeout_s
        self._end = clock() + timeout_s

    def check(self) -> None:
        if self._clock() > self._end:
            raise ProcessingTimeout(
                f"Processing exceeded the {self._timeout:g} s timeout; aborted."
            )
