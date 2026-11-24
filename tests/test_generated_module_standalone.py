"""Downloaded module folder: logic.py imports with and without the ghost package.
The header tries ``.excel`` (package), then ``excel`` (run from the folder), then
``ghost.runtime.excel``. R-30 follow-up (task 7.3).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ghost import cli
from ghost.referee.locate import RefereeUnavailable, locate_soffice

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

ROOT = Path(__file__).resolve().parent.parent
INPUTS = {"quantity": 50, "unit_price": "10", "delivery_distance_km": "5"}
_STANDALONE = (
    "import json, logic; "
    "print(json.dumps({k: str(v) for k, v in logic.compute(%s).items()}, sort_keys=True))" % repr(INPUTS)
)


@pytest.fixture(scope="module")
def haunted_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("standalone")
    assert cli.main(["demo", "--out", str(out)]) == 0
    return out / "haunted"


def _run(code: str, cwd: Path, env: dict) -> dict:
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=cwd, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_logic_imports_from_its_folder_without_ghost(haunted_dir, tmp_path):
    work = tmp_path / "unzipped"
    work.mkdir()
    for name in ("logic.py", "excel.py"):
        shutil.copy(haunted_dir / name, work / name)
    # Clean environment: no PYTHONPATH, no venv, ghost is not importable.
    env = {"PATH": "/usr/bin:/bin"}
    probe = subprocess.run(
        [sys.executable, "-c", "import ghost"], capture_output=True, text=True, cwd=work, env=env
    )
    assert probe.returncode != 0, "ghost must not be importable in the standalone check"
    standalone = _run(_STANDALONE, work, env)

    # Same module through the package path (ghost importable, run from the repo).
    pkg_code = (
        "import json; from ghost.verifier.run import load_compute; "
        "f = load_compute(open(%r, encoding='utf-8').read()); "
        "print(json.dumps({k: str(v) for k, v in f(%r).items()}, sort_keys=True))"
    ) % (str(haunted_dir / "logic.py"), INPUTS)
    pkg = _run(pkg_code, ROOT, {**os.environ, "PYTHONPATH": str(ROOT)})
    assert standalone == pkg
    assert standalone["total"] != "None"


def test_logic_still_imports_as_a_package(haunted_dir, tmp_path):
    pkg_parent = tmp_path / "pkgs"
    shutil.copytree(haunted_dir, pkg_parent / "mig", ignore=shutil.ignore_patterns("reports"))
    (pkg_parent / "mig" / "__init__.py").write_text("", encoding="utf-8")
    code = (
        "import json; from mig import logic; "
        "print(json.dumps({k: str(v) for k, v in logic.compute(%r).items()}, sort_keys=True))" % INPUTS
    )
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": ""}
    got = _run(code, pkg_parent, env)
    work = tmp_path / "flat"
    work.mkdir()
    for name in ("logic.py", "excel.py"):
        shutil.copy(haunted_dir / name, work / name)
    assert got == _run(_STANDALONE, work, env)
