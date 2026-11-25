"""L-03 measurement (task 3.5): ``INDEX`` with a 0 row or column, by formula position.

Runs ``tests/index_zero_probe.py`` against the installed Referee and pins what
LibreOffice returns for every placement, so an upgrade that changes one is noticed.
The table and its reading are in
``.kiro/specs/live-fixes-2026-11-24/measurements-l03.md``.

Measured 2026-11-24: LibreOffice 26.8.3.1 (local) and 7.4.7.2 (Docker image
``ghost-local:l03``, Debian bookworm) gave identical results for all 69 cases, so
both major versions share one expectation.

``test_ghost_keeps_agreeing_with_referee`` asserts the 36 cases the unfixed code
already got right (clause 3.10 preservation). ``GHOST_WRONG_BEFORE_FIX`` lists the
33 cases the unfixed code got wrong; since task 3.7 (L-03 fix)
``test_ghost_agrees_with_referee_after_l03_fix`` asserts Ghost matches them too, so
Ghost now matches all 69 and none is "not converted".

**Validates: Requirements 2.2, 3.10**
"""
from __future__ import annotations

import re

import pytest

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.compare import values_equal
from tests.index_zero_probe import CASES, measure

try:
    locate_soffice()
except RefereeUnavailable as exc:  # pragma: no cover
    pytest.skip(f"LibreOffice (soffice) not installed: the Referee is unavailable ({exc})",
                allow_module_level=True)

V = "#VALUE!"

# Case id -> Referee result. Identical on LibreOffice 7.4.7.2 and 26.8.3.1.
_SAME = {
    "col_r0_above_far": V, "col_r0_above_adj": V,
    "col_r0_top_edge": 7, "col_r0_inside": 8, "col_r0_bottom_edge": 9,
    "col_r0_below_adj": V, "col_r0_below_far": V,
    "col_r0_inside_right": 8,
    "col_r0c1_inside": 8, "col_r0c1_outside": V,
    "col_r0c0_inside": 8, "col_r0c0_outside": V,
    "col_r2c0_outside": 8,
    "col_rZ_inside": 8, "col_rZ_outside": V,
    "col_r0_plus0_inside": 8, "col_r0_plus0_outside": V,
    "col_r0_sum_inside": 24, "col_r0_sum_outside": 24,
    "col_r0_avg_inside": 8, "col_r0_avg_outside": 8,
    "row_c0_left_far": V, "row_c0_left_adj": V,
    "row_c0_left_edge": 21, "row_c0_inside": 22, "row_c0_right_edge": 23,
    "row_c0_right_adj": V, "row_c0_right_far": V,
    "row_c0_inside_above": 22,
    "row_r1c0_inside": 22, "row_r1c0_outside": V,
    "row_r0c0_inside": 22, "row_r0c0_outside": V,
    "row_r0c2_outside": 22,
    "row_c0_sum_inside": 66, "row_c0_sum_outside": 66,
    "grid_r0c2_above": V,
    "grid_r0c2_top_edge": 41, "grid_r0c2_inside": 42, "grid_r0c2_bottom_edge": 43,
    "grid_r0c2_below": V,
    "grid_r0c1_inside": 32, "grid_r0c1_outside": V,
    "grid_r2c0_left_adj": V, "grid_r2c0_left_edge": 32, "grid_r2c0_right_edge": 42,
    "grid_r2c0_right_adj": V,
    "grid_r0c0_row_inside": V, "grid_r0c0_col_inside": V, "grid_r0c0_neither": V,
    "grid_r0_row_inside": V, "grid_r0_col_inside": V, "grid_r0_neither": V,
    "grid_r0c2_sum_inside": 126, "grid_r0c2_sum_outside": 126,
    "grid_r2c0_sum_outside": 74, "grid_r0c0_sum": 222,
    "xsheet_col_r0_inside": 108, "xsheet_col_r0_outside": V,
    "xsheet_row_c0_inside": 122, "xsheet_row_c0_outside": V,
    "xsheet_back_inside": 8, "xsheet_back_outside": V,
    "cell_rng_r0_same_row": 55, "cell_rng_r0_other_row": 55,
    "cell_ref_r0_same_row": 55, "cell_ref_r0_other_row": 55,
    "cell_rng_r0c0_same_row": 55, "cell_rng_r0c0_other_row": 55,
}
EXPECTED: dict[int, dict] = {7: _SAME, 26: _SAME}

# Cases where the unfixed code (R-08 rule: a 0 on a longer dimension is #VALUE!)
# disagrees with the Referee. Measured 2026-11-24 on both LibreOffice versions.
GHOST_WRONG_BEFORE_FIX = frozenset({
    "col_r0_top_edge", "col_r0_inside", "col_r0_bottom_edge", "col_r0_inside_right",
    "col_r0c1_inside", "col_r0c0_inside", "col_rZ_inside", "col_r0_plus0_inside",
    "col_r0_sum_inside", "col_r0_sum_outside", "col_r0_avg_inside", "col_r0_avg_outside",
    "row_c0_left_edge", "row_c0_inside", "row_c0_right_edge", "row_c0_inside_above",
    "row_r1c0_inside", "row_r0c0_inside", "row_c0_sum_inside", "row_c0_sum_outside",
    "grid_r0c2_top_edge", "grid_r0c2_inside", "grid_r0c2_bottom_edge", "grid_r0c1_inside",
    "grid_r2c0_left_edge", "grid_r2c0_right_edge", "grid_r0c2_sum_inside",
    "grid_r0c2_sum_outside", "grid_r2c0_sum_outside", "grid_r0c0_sum",
    "xsheet_col_r0_inside", "xsheet_row_c0_inside", "xsheet_back_inside",
})

IDS = [cid for cid, _, _, _ in CASES]


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    result = measure(tmp_path_factory.mktemp("l03"))
    m = re.match(r"(\d+)\.", result["libreoffice"])
    if not m:  # pragma: no cover
        pytest.skip(f"cannot read the LibreOffice version from {result['libreoffice']!r}")
    return int(m.group(1)), {row["id"]: row for row in result["cases"]}


def test_every_case_has_an_expectation():
    assert set(IDS) == set(_SAME)
    assert GHOST_WRONG_BEFORE_FIX <= set(IDS)


@pytest.mark.parametrize("cid", IDS)
def test_referee_result_is_pinned(measured, cid):
    major, rows = measured
    if major not in EXPECTED:
        pytest.skip(f"LibreOffice {major} has no pinned expectations; run tests/index_zero_probe.py")
    row = rows[cid]
    assert values_equal(row["referee"], EXPECTED[major][cid], 1e-6), (
        f"LibreOffice {major} changed {row['formula']} at {row['cell']}: {row['referee']!r}; "
        "update EXPECTED and .kiro/specs/live-fixes-2026-11-24/measurements-l03.md"
    )


@pytest.mark.parametrize("cid", [c for c in IDS if c not in GHOST_WRONG_BEFORE_FIX])
def test_ghost_keeps_agreeing_with_referee(measured, cid):
    """Clause 3.10: cases Ghost already gets right stay right."""
    _, rows = measured
    row = rows[cid]
    assert row["agree"], (row["cell"], row["formula"], "referee", row["referee"], "ghost", row["ghost"])


@pytest.mark.parametrize("cid", sorted(GHOST_WRONG_BEFORE_FIX))
def test_ghost_agrees_with_referee_after_l03_fix(measured, cid):
    """Task 3.7 (L-03): the 33 cases the unfixed code got wrong now match the Referee.

    None is "not converted": the 23 scalar cases follow implicit intersection
    (rules 1, 2, 3, 7, 8) and the 10 SUM/AVERAGE cases aggregate the selection (rule 9).
    """
    _, rows = measured
    row = rows[cid]
    assert not str(row["ghost"]).startswith("not converted"), (row["cell"], row["ghost"])
    assert row["agree"], (row["cell"], row["formula"], "referee", row["referee"], "ghost", row["ghost"])
