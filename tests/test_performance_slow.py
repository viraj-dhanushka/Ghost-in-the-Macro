"""Performance: a typical sample verifies in under 60 seconds (task 9.6, R-20).

**Validates: Requirements 1.31, 2.31**

Haunted sample, Faithful mode, 500 generated cases, condition-flip cases and the
mutation self-check at the web default (``GHOST_MUTATION_CASES``), against the
real Referee. The clock includes LibreOffice start-up. Skipped without soffice.
Deselect with ``-m "not slow"``.
"""

from __future__ import annotations

import json
import time

import pytest

from ghost import cli
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from samples import make_haunted
from web.jobs import mutation_cases_from_env

try:
    locate_soffice()
    _HAVE_SOFFICE = True
except RefereeUnavailable:
    _HAVE_SOFFICE = False

CASES = 500
LIMIT_SECONDS = 60.0


@pytest.mark.slow
@pytest.mark.skipif(not _HAVE_SOFFICE, reason="soffice not available (set GHOST_SOFFICE)")
def test_haunted_500_cases_with_mutation_check_under_60_seconds(tmp_path, capsys):
    workbook = make_haunted.build(tmp_path / "haunted.xlsx")
    mdir = tmp_path / "migration"
    mutation_cases = mutation_cases_from_env()
    assert mutation_cases > 0, "GHOST_MUTATION_CASES=0 would skip the mutation check"

    assert cli.main(["convert", str(workbook), "--migration", str(mdir)]) == 0

    start = time.perf_counter()
    rc = cli.main(
        [
            "verify", str(mdir), "--mode", "faithful", "--cases", str(CASES),
            "--mutation-cases", str(mutation_cases),
        ]
    )
    elapsed = time.perf_counter() - start

    out = capsys.readouterr().out
    with capsys.disabled():
        print(
            f"\n[performance] haunted faithful, {CASES} cases + flip cases + mutation check "
            f"({mutation_cases} cases/mutant), LibreOffice start-up included: "
            f"{elapsed:.1f} s (limit {LIMIT_SECONDS:.0f} s)"
        )
    assert rc == 0, out
    report = json.loads((mdir / "proof-report.json").read_text(encoding="utf-8"))
    assert report["cases_tested"] >= CASES
    assert elapsed < LIMIT_SECONDS, f"took {elapsed:.1f} s; output:\n{out}"
