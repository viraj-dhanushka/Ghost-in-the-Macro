"""Review 2026-11-24: transpiler output vs the LibreOffice Referee on edge-case formulas.

Passing cases are regression tests. xfail(strict=True) cases are transpiler bugs where
Excel and LibreOffice agree and Ghost differs. Cases where LibreOffice itself differs
from Excel (0^0, MATCH("2",...), TRUE>1, SUM("5",1)) are listed in
docs/TEST_REPORT_2026-11-24.md and deliberately not tested here.
"""
from __future__ import annotations

import pytest
from openpyxl import Workbook

from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.verifier.compare import values_equal
from ghost.verifier.run import load_compute

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

PASSING = {
    "round_neg_digits": "=ROUND(1234.5,-2)",
    "round_half_neg_digits": "=ROUND(-1250,-2)",
    "round_1005": "=ROUND(1.005,2)",
    "mod_decimals": "=MOD(-5.5,2)",
    "mod_div0": "=MOD(10,0)",
    "text_vs_number": '="10"=10',
    "number_lt_text": '=10<"5"',
    "text_plus_number": '="5"+1',
    "text_cell_times_2": "=T1*2",
    "sum_with_empty": "=SUM(G1:G3)",
    "average_with_empty": "=AVERAGE(G1:G3)",
    "average_all_empty": "=AVERAGE(Z1:Z3)",
    "sum_text_in_range": "=SUM(T1:T2)",
    "iferror_div0": '=IFERROR(1/0,"x")',
    "iferror_na": "=IFERROR(MATCH(99,M1:M3,0),-1)",
    "match_miss": "=MATCH(99,M1:M3,0)",
    "index_out_of_range": "=INDEX(M1:M3,5)",
    "match_text_case_insensitive": '=MATCH("b",K1:K3,0)',
    "choose_out_of_range": '=CHOOSE(4,"a","b","c")',
    "choose_fraction": '=CHOOSE(2.9,"a","b","c")',
    "quoted_sheet_space": "='My Data'!A1*2",
    "quoted_sheet_apostrophe": "='Bob''s'!A1+1",
    "percent": "=50%*10",
    "double_percent": "=5%%",
    "neg_power": "=-2^2",
    "power_left_assoc": "=2^3^2",
    "neg_sqrt": "=-2^0.5",
    "concat_third": '=1/3&""',
    "concat_noise": '=(0.1+0.2)&""',
    "concat_rounded": '=ROUND(1234.5,-2)&" units"',
    "or_all_empty": "=OR(Z1:Z3)",
    # R-08 number-to-text: the Referee writes "1E+020"; values_equal treats
    # scientific strings of the same value as equal.
    "text_1e20": '=1E+20&""',
    "text_1em20": '=1E-20&""',
    "text_neg_1e20": '=-1E+20&""',
    "text_17_digits": '=123456789012345678&""',
    "text_1e14": '=1E+14&""',
    "text_small_plain": '=0.00001&""',
    "text_sum_noise": '=(0.1+0.2)&""',
    # R-30: a 0 on a dimension of length 1 selects that row or column (Referee,
    # LibreOffice 26.8.3.1; Excel not verified). A 0 on a longer dimension is #VALUE!.
    "index_1x1_row0": "=INDEX(M1:M1,0)",
    "index_1x1_col0": "=INDEX(M1:M1,1,0)",
    "index_1x1_both0": "=INDEX(M1:M1,0,0)",
    "index_1x1_row0_col1": "=INDEX(M1:M1,0,1)",
    "index_single_ref_0": "=INDEX(M1,0)",
    "index_column_vector_col0": "=INDEX(M1:M3,2,0)",
    "index_row_vector_row0": "=INDEX(M1:O1,0,2)",
    "index_multi_both0": "=INDEX(M1:M3,0,0)",
    "index_multi_row0_col1": "=INDEX(M1:M3,0,1)",
    "index_row_vector_col0": "=INDEX(M1:O1,1,0)",
    "index_row_vector_single_arg0": "=INDEX(M1:O1,0)",
}

BUGS = {
    "compare_after_division": (
        '=IF(10/3*3>=10,"ok","low")',
        "R-07: Decimal division (28 digits) then exact comparison; Excel and LibreOffice give 'ok'",
    ),
    "equality_after_division": (
        "=1/3*3=1",
        "R-07: Excel and LibreOffice give TRUE, Ghost gives FALSE",
    ),
    "index_row_zero": (
        "=INDEX(M1:M3,0)",
        "R-08: row 0 means the whole column; LibreOffice and legacy Excel give #VALUE!, Ghost gives #REF!",
    ),
}


# Cases from BUGS whose fix has landed: the xfail marker is gone, the test must pass.
FIXED = {"compare_after_division", "equality_after_division", "index_row_zero"}  # R-07 (7.2), R-08 (7.3)


def _build(path, formulas: dict[str, str]) -> list[str]:
    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    for i, v in enumerate((1, 2, 3), start=1):
        ws[f"M{i}"] = v
    for i, v in enumerate(("a", "B", "c"), start=1):
        ws[f"K{i}"] = v
    ws["G1"], ws["G3"] = 1, 3
    ws["T1"], ws["T2"] = "5", 1
    wb.create_sheet("My Data")["A1"] = 21
    wb.create_sheet("Bob's")["A1"] = 4
    cells = []
    for r, (cid, formula) in enumerate(formulas.items(), start=1):
        ws[f"A{r}"] = cid
        ws[f"B{r}"] = formula
        cells.append(f"S!B{r}")
    wb.save(path)
    return cells


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    formulas = dict(PASSING) | {k: v[0] for k, v in BUGS.items()}
    path = tmp_path_factory.mktemp("sem") / "semantics.xlsx"
    cells = _build(path, formulas)
    wb = load_workbook(str(path))
    roles = {ref: ("OUTPUT" if c.formula else "PARAMETER") for ref, c in wb.cells.items()}
    mapping = generate_mapping(wb, roles)
    res = emit_module(wb, mapping)
    got = load_compute(res.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    with RefereeClient(None, path) as ref:
        refv = ref.read(cells)
    out = {}
    for cid, cell in zip(formulas, cells):
        r = refv[cell]
        out[cid] = (r["error"] if isinstance(r, dict) else r, got.get(name_of.get(cell)))
    return out


@pytest.mark.parametrize("cid", sorted(PASSING))
def test_transpiler_matches_referee(results, cid):
    referee, ghost = results[cid]
    assert values_equal(referee, ghost, 1e-6), (PASSING[cid], referee, ghost)


@pytest.mark.parametrize("cid", sorted(BUGS))
def test_transpiler_bug(results, cid, request):
    if cid not in FIXED:
        request.applymarker(pytest.mark.xfail(strict=True, reason=BUGS[cid][1]))
    referee, ghost = results[cid]
    assert values_equal(referee, ghost, 1e-6), (BUGS[cid][0], referee, ghost)
