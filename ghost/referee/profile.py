"""Build a temporary LibreOffice user profile for the Referee."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

SCRIPT_NAME = "ghost_referee.py"
DEFAULT_SCRIPT = Path(__file__).parent / "script" / SCRIPT_NAME

_XCU_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
)


def _item(path: str, name: str, value: str) -> str:
    return (
        f'<item oor:path="{path}"><prop oor:name="{name}" oor:op="fuse">'
        f"<value>{value}</value></prop></item>\n"
    )


def registry_xcu(run_macros: bool = False) -> str:
    """Return registrymodifications.xcu content (deterministic).

    VBA import Load/Executable/Save true, UpdateDocMode NO_UPDATE (0).
    Macro execution defaults to NEVER_EXECUTE; the referee script also passes
    the per-document MacroExecutionMode, so this is the profile-level default.
    """
    vba = "/org.openoffice.Office.Calc/Filter/Import/VBA"
    parts = [_XCU_HEADER]
    for name in ("Load", "Executable", "Save"):
        parts.append(_item(vba, name, "true"))
    parts.append(_item("/org.openoffice.Office.Common/Load", "UpdateDocMode", "0"))
    # MacroSecurityLevel: 3 = very high (signed/trusted only), 0 = low.
    parts.append(
        _item(
            "/org.openoffice.Office.Common/Security/Scripting",
            "MacroSecurityLevel",

            "0" if run_macros else "3",
        )
    )
    parts.append("</oor:items>\n")
    return "".join(parts)


def build_profile(
    parent: str | Path | None = None,
    script_src: str | Path | None = None,
    run_macros: bool = False,
) -> Path:
    """Create a temp profile dir and return its path.

    Layout: ``<profile>/user/registrymodifications.xcu`` and
    ``<profile>/user/Scripts/python/ghost_referee.py``.
    The caller removes the directory (shutil.rmtree) when the job ends.
    """
    src = Path(script_src) if script_src else DEFAULT_SCRIPT
    if not src.is_file():
        raise FileNotFoundError(f"Referee script not found: {src}")
    profile = Path(tempfile.mkdtemp(prefix="ghost-lo-", dir=str(parent) if parent else None))
    user = profile / "user"
    scripts = user / "Scripts" / "python"
    scripts.mkdir(parents=True)
    shutil.copyfile(src, scripts / SCRIPT_NAME)
    (user / "registrymodifications.xcu").write_text(registry_xcu(run_macros), encoding="utf-8")
    return profile


def profile_url(profile: str | Path) -> str:
    """``-env:UserInstallation`` value for the profile directory."""
    return "-env:UserInstallation=" + Path(profile).resolve().as_uri()
