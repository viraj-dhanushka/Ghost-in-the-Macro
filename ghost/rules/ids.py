"""Stable rule identifiers (Requirement 3.6).

``rule_id = "R-" + sha1(sheet|cell|normalised_formula)[:8]``. Normalisation
strips whitespace and ``$`` and upper-cases function names. String literals
are left untouched.
"""

from __future__ import annotations

import hashlib
import re

from ghost.models import CellRef

__all__ = ["normalise_formula", "rule_id"]

_FUNC_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?=\()")


def _normalise_code(code: str) -> str:
    code = re.sub(r"\s+", "", code).replace("$", "")
    return _FUNC_RE.sub(lambda m: m.group(0).upper(), code)


def normalise_formula(formula: str) -> str:
    """Strip whitespace and ``$`` and upper-case function names, outside strings."""
    text = formula.strip()
    if text.startswith("="):
        text = text[1:]
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append(_normalise_code("".join(buf)))
            buf = []
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    break
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
        else:
            buf.append(ch)
            i += 1
    out.append(_normalise_code("".join(buf)))
    return "".join(out)


def rule_id(ref: CellRef, formula: str) -> str:
    """Return ``R-xxxxxxxx`` for a formula cell ``Sheet!A1``."""
    sheet, _, addr = ref.rpartition("!")
    key = f"{sheet}|{addr}|{normalise_formula(formula)}"
    return "R-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
