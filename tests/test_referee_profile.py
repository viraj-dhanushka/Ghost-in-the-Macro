import shutil

import pytest

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.referee.profile import build_profile, registry_xcu


def test_locate_env_var(tmp_path, monkeypatch):
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("GHOST_SOFFICE", str(fake))
    assert locate_soffice() == str(fake)


def test_locate_error_names_paths_and_packages(monkeypatch):
    monkeypatch.setenv("GHOST_SOFFICE", "/nonexistent/soffice")
    monkeypatch.setattr("ghost.referee.locate._is_executable", lambda p: False)
    with pytest.raises(RefereeUnavailable) as e:
        locate_soffice()
    msg = str(e.value)
    for needle in (
        "/nonexistent/soffice",
        "/Applications/LibreOffice.app",
        "/usr/bin/soffice",
        "libreoffice-calc-nogui",
        "libreoffice-script-provider-python",
    ):
        assert needle in msg


def test_xcu_vba_and_update_mode():
    x = registry_xcu()
    for name in ("Load", "Executable", "Save"):
        assert f'oor:name="{name}"' in x
    assert "/org.openoffice.Office.Calc/Filter/Import/VBA" in x
    assert "UpdateDocMode" in x
    assert registry_xcu() == x


def test_build_profile_layout(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("def serve(): pass\n")
    p = build_profile(parent=tmp_path, script_src=script)
    try:
        assert (p / "user" / "registrymodifications.xcu").is_file()
        assert (p / "user" / "Scripts" / "python" / "ghost_referee.py").read_text() == script.read_text()
    finally:
        shutil.rmtree(p)
