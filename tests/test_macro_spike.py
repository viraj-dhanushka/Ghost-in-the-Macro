"""Macro spike (large-workbook-lane, Requirement 6.3 and 9): what the Referee really does with a cell that
calls a VBA function, with macros off and (opt in, GHOST_MACRO_SPIKE=1) with macros trusted. LibreOffice needed;
LOCAL ONLY. The macros-on test is skipped unless you opt in.

The workbook is the bundled generated sample (samples/make_xlsm.py), a trusted source. The OBSERVED result on
2026-11-26 (LibreOffice 26.8.3.1) is pinned here: if a LibreOffice upgrade changes it, this test fails and the
wording in the kit, the README and the web text must be revisited.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ghost import cli
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice

ROOT = Path(__file__).resolve().parent.parent


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


pytestmark = pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")


@pytest.fixture(scope="module")
def macro_sample(tmp_path_factory) -> Path:
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_xlsm
    finally:
        sys.path.remove(str(ROOT / "samples"))
    return make_xlsm.build(tmp_path_factory.mktemp("spike") / "discount_vba.xlsm")


def _eval(path: Path, tmp: Path, macros: bool, quantity=10):
    with RefereeClient(None, path, run_macros=macros, trusted_source=macros, job_dir=tmp) as ref:
        listed = ref.macros() if macros else None
        got = ref.eval({"Calculator!B2": quantity, "Calculator!B4": 25}, ["Calculator!B13", "Calculator!B11"])
    return got, listed


def test_with_macros_off_the_vba_cell_is_not_calculated(macro_sample, tmp_path):
    got, _ = _eval(macro_sample, tmp_path, macros=False)
    assert got["Calculator!B13"] == {"error": "#MACRO?"}
    assert isinstance(got["Calculator!B11"], float)  # the formula cell beside it still calculates


def test_listing_the_procedures_works_with_macros_off_too(macro_sample, tmp_path):
    """So a listing of the macros is no sign that macros are enabled or that the VBA runs."""
    with RefereeClient(None, macro_sample, run_macros=False, job_dir=tmp_path) as ref:
        assert {m["name"] for m in ref.macros()} == {"DeliveryFee", "AwardPoints"}


@pytest.mark.skipif(os.environ.get("GHOST_MACRO_SPIKE") != "1",
                    reason="opt in with GHOST_MACRO_SPIKE=1: this opens the Referee with macros trusted (the bundled sample only)")
def test_with_macros_trusted_the_cell_still_reads_macro_error(macro_sample, tmp_path):
    """Observed 2026-11-26: with macros trusted the cell still reads #MACRO?. The cause was not found."""
    got, listed = _eval(macro_sample, tmp_path, macros=True)
    assert {m["name"] for m in listed} == {"DeliveryFee", "AwardPoints"}
    assert got["Calculator!B13"] == {"error": "#MACRO?"}
    assert isinstance(got["Calculator!B11"], float)


def test_ghost_challenge_refuses_an_output_fed_by_a_vba_function(macro_sample, tmp_path, capsys):
    mapping = tmp_path / "m.yaml"
    mapping.write_text("version: 1\ninputs:\n  quantity:\n    cell: Calculator!B2\n    type: integer\n    min: 0\n"
                       "outputs:\n  fee:\n    cell: Calculator!B13\n    type: decimal\n", encoding="utf-8")
    code_file = tmp_path / "c.py"
    code_file.write_text("def compute(inputs):\n    return {'fee': 0}\n", encoding="utf-8")
    rc = cli.main(["challenge", str(macro_sample), "--code", str(code_file), "--mapping", str(mapping)])
    err = capsys.readouterr().err
    assert rc == 2
    assert err.count("\n") == 1 and "Calculator!B13" in err and "cannot be an output" in err
