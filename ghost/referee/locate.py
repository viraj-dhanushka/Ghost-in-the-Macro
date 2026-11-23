"""Locate the LibreOffice ``soffice`` executable."""

from __future__ import annotations

import glob
import os
from pathlib import Path

REQUIRED_PACKAGES = ("libreoffice-calc-nogui", "libreoffice-script-provider-python")

_MAC_REL = "Contents/MacOS/soffice"


class RefereeUnavailable(Exception):
    """soffice could not be located."""


def candidate_paths() -> list[str]:
    """Ordered search locations. ``/opt/libreoffice*`` is expanded with glob."""
    paths: list[str] = []
    env = os.environ.get("GHOST_SOFFICE")
    if env:
        paths.append(env)
    home = Path(os.path.expanduser("~"))
    paths.append(str(home / "Applications" / "LibreOffice.app" / _MAC_REL))
    paths.append("/Applications/LibreOffice.app/" + _MAC_REL)
    paths.append("/usr/bin/soffice")
    paths.append("/usr/lib/libreoffice/program/soffice")
    paths.extend(sorted(glob.glob("/opt/libreoffice*/program/soffice")))
    return paths


def _is_executable(p: str) -> bool:
    return os.path.isfile(p) and os.access(p, os.X_OK)


def locate_soffice() -> str:
    """Return the path to soffice or raise RefereeUnavailable naming searched paths."""
    searched = candidate_paths()
    for p in searched:
        if _is_executable(p):
            return p
    shown = list(searched)
    if not glob.glob("/opt/libreoffice*/program/soffice"):
        shown.append("/opt/libreoffice*/program/soffice")
    if not os.environ.get("GHOST_SOFFICE"):
        shown.insert(0, "$GHOST_SOFFICE (not set)")
    raise RefereeUnavailable(
        "soffice not found. Searched: "
        + ", ".join(shown)
        + ". Install LibreOffice, or on Debian/Ubuntu the packages "
        + " and ".join(REQUIRED_PACKAGES)
        + ", or set GHOST_SOFFICE to the soffice path."
    )
