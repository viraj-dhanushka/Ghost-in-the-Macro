"""Sanity check against workbooks saved by real Excel (Requirements 6.1 to 6.4).

For each .xlsx/.xlsm in tests/fixtures/excel-saved/, the Referee recalculates
every formula cell and the result is compared with the value Excel saved.
With no fixtures the test skips; it never reports a pass it did not earn.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.referee.sanity import run_sanity

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "excel-saved"
FIXTURES = sorted(
    p for p in FIXTURE_DIR.glob("*") if p.suffix.lower() in (".xlsx", ".xlsm")
)

NO_FIXTURES = (
    f"No Excel-saved workbooks in {FIXTURE_DIR}. Make them with Excel for the web "
    "(upload a generated sample, make a tiny edit, File > Create a Copy > "
    "Download a Copy) and save them there, e.g. haunted-excel.xlsx. "
    "See the README in that folder. Workbooks without Excel-saved values are "
    "reported as 'not cross-checked against Excel'."
)


def test_fixture_folder_exists():
    assert FIXTURE_DIR.is_dir(), f"missing fixture folder {FIXTURE_DIR}"
    assert (FIXTURE_DIR / "README.md").is_file()


@pytest.mark.skipif(bool(FIXTURES), reason="fixtures present")
def test_no_excel_saved_fixtures_yet():
    pytest.skip(NO_FIXTURES)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_referee_matches_excel_saved_values(path: Path):
    try:
        soffice = locate_soffice()
    except RefereeUnavailable as exc:
        pytest.skip(f"soffice not available, cannot run the Referee: {exc}")

    wb = load_workbook(str(path))
    with RefereeClient(soffice, path, run_macros=False) as referee:
        result = run_sanity(wb, referee)

    assert result.status != "not cross-checked against Excel", (
        f"{path.name} holds no Excel-saved formula values, so it is not a valid "
        "fixture. Re-create it with Excel for the web (see the folder README)."
    )
    assert result.status == "matched", (
        f"{path.name}: Referee matched Excel on {result.matched} of {result.total} "
        f"formula cells. Differences: {result.differences}"
    )
    assert result.total > 0
