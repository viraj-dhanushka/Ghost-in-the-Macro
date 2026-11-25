"""Measurement probe for L-03: ``INDEX`` with a 0 row or column, by formula position.

Task 3.5 of ``.kiro/specs/live-fixes-2026-11-24``. Builds one workbook with openpyxl,
reads every probe cell from the Referee (headless LibreOffice) and from Ghost's
generated code, and prints one JSON document. Nothing is assumed: every result in
the table in ``.kiro/specs/live-fixes-2026-11-24/measurements-l03.md`` comes from
running this script.

It depends only on ``ghost`` and openpyxl, so it also runs inside the Docker image
(which has no ``tests`` folder)::

    .venv/bin/python tests/index_zero_probe.py                 # local LibreOffice
    docker run --rm --platform linux/amd64 \\
        -v "$PWD/tests/index_zero_probe.py:/probe/index_zero_probe.py:ro" \\
        ghost-local:l03 /opt/venv/bin/python /probe/index_zero_probe.py

``tests/test_index_zero_measurement.py`` imports ``CASES`` and ``measure`` from here.

Layout (sheet ``Calc`` unless stated):

* single column ``M5:M7`` = 7, 8, 9
* single row ``E20:G20`` = 21, 22, 23
* two-dimensional ``Q5:R7``: column Q = 31, 32, 33; column R = 41, 42, 43
* single cell ``T5`` = 55
* ``Z1`` = 0 (a computed zero)
* sheet ``Data``: ``M5:M7`` = 107, 108, 109 and ``E20:G20`` = 121, 122, 123

A formula placed inside the range it reads would be a circular reference, so the
"inside" placements share only the row (or only the column) with the range.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

# (case id, formula cell, formula, placement note)
CASES: tuple[tuple[str, str, str, str], ...] = (
    # --- single column M5:M7, row 0 (formula in column B unless stated)
    ("col_r0_above_far", "Calc!B3", "=INDEX($M$5:$M$7,0)", "row 3, above rows 5-7"),
    ("col_r0_above_adj", "Calc!B4", "=INDEX($M$5:$M$7,0)", "row 4, just above"),
    ("col_r0_top_edge", "Calc!B5", "=INDEX($M$5:$M$7,0)", "row 5 = top edge"),
    ("col_r0_inside", "Calc!B6", "=INDEX($M$5:$M$7,0)", "row 6, middle"),
    ("col_r0_bottom_edge", "Calc!B7", "=INDEX($M$5:$M$7,0)", "row 7 = bottom edge"),
    ("col_r0_below_adj", "Calc!B8", "=INDEX($M$5:$M$7,0)", "row 8, just below"),
    ("col_r0_below_far", "Calc!B12", "=INDEX($M$5:$M$7,0)", "row 12, below"),
    ("col_r0_inside_right", "Calc!X6", "=INDEX($M$5:$M$7,0)", "row 6, column X right of the range"),
    ("col_r0c1_inside", "Calc!C6", "=INDEX($M$5:$M$7,0,1)", "row 6 inside"),
    ("col_r0c1_outside", "Calc!C9", "=INDEX($M$5:$M$7,0,1)", "row 9 outside"),
    ("col_r0c0_inside", "Calc!D6", "=INDEX($M$5:$M$7,0,0)", "row 6 inside"),
    ("col_r0c0_outside", "Calc!D9", "=INDEX($M$5:$M$7,0,0)", "row 9 outside"),
    ("col_r2c0_outside", "Calc!H9", "=INDEX($M$5:$M$7,2,0)", "row 9 outside (col 0 on width 1)"),
    ("col_rZ_inside", "Calc!I6", "=INDEX($M$5:$M$7,$Z$1)", "row 6 inside, row index from Z1 = 0"),
    ("col_rZ_outside", "Calc!I9", "=INDEX($M$5:$M$7,$Z$1)", "row 9 outside, row index from Z1 = 0"),
    ("col_r0_plus0_inside", "Calc!J6", "=INDEX($M$5:$M$7,0)+0", "row 6 inside, in arithmetic"),
    ("col_r0_plus0_outside", "Calc!J9", "=INDEX($M$5:$M$7,0)+0", "row 9 outside, in arithmetic"),
    ("col_r0_sum_inside", "Calc!K6", "=SUM(INDEX($M$5:$M$7,0))", "row 6 inside, inside SUM"),
    ("col_r0_sum_outside", "Calc!K9", "=SUM(INDEX($M$5:$M$7,0))", "row 9 outside, inside SUM"),
    ("col_r0_avg_inside", "Calc!L6", "=AVERAGE(INDEX($M$5:$M$7,0))", "row 6 inside, inside AVERAGE"),
    ("col_r0_avg_outside", "Calc!L9", "=AVERAGE(INDEX($M$5:$M$7,0))", "row 9 outside, inside AVERAGE"),
    # --- single row E20:G20, column 0 (formula on row 30 unless stated)
    ("row_c0_left_far", "Calc!C30", "=INDEX($E$20:$G$20,0)", "column C, left of E-G"),
    ("row_c0_left_adj", "Calc!D30", "=INDEX($E$20:$G$20,0)", "column D, just left"),
    ("row_c0_left_edge", "Calc!E30", "=INDEX($E$20:$G$20,0)", "column E = left edge"),
    ("row_c0_inside", "Calc!F30", "=INDEX($E$20:$G$20,0)", "column F, middle"),
    ("row_c0_right_edge", "Calc!G30", "=INDEX($E$20:$G$20,0)", "column G = right edge"),
    ("row_c0_right_adj", "Calc!H30", "=INDEX($E$20:$G$20,0)", "column H, just right"),
    ("row_c0_right_far", "Calc!K30", "=INDEX($E$20:$G$20,0)", "column K, right"),
    ("row_c0_inside_above", "Calc!F15", "=INDEX($E$20:$G$20,0)", "column F, row 15 above the range"),
    ("row_r1c0_inside", "Calc!F31", "=INDEX($E$20:$G$20,1,0)", "column F inside"),
    ("row_r1c0_outside", "Calc!C31", "=INDEX($E$20:$G$20,1,0)", "column C outside"),
    ("row_r0c0_inside", "Calc!F32", "=INDEX($E$20:$G$20,0,0)", "column F inside"),
    ("row_r0c0_outside", "Calc!C32", "=INDEX($E$20:$G$20,0,0)", "column C outside"),
    ("row_r0c2_outside", "Calc!C33", "=INDEX($E$20:$G$20,0,2)", "column C outside (row 0 on height 1)"),
    ("row_c0_sum_inside", "Calc!F34", "=SUM(INDEX($E$20:$G$20,0))", "column F inside, inside SUM"),
    ("row_c0_sum_outside", "Calc!C34", "=SUM(INDEX($E$20:$G$20,0))", "column C outside, inside SUM"),
    # --- two-dimensional Q5:R7
    ("grid_r0c2_above", "Calc!N4", "=INDEX($Q$5:$R$7,0,2)", "row 4, above rows 5-7"),
    ("grid_r0c2_top_edge", "Calc!N5", "=INDEX($Q$5:$R$7,0,2)", "row 5 = top edge"),
    ("grid_r0c2_inside", "Calc!N6", "=INDEX($Q$5:$R$7,0,2)", "row 6, middle"),
    ("grid_r0c2_bottom_edge", "Calc!N7", "=INDEX($Q$5:$R$7,0,2)", "row 7 = bottom edge"),
    ("grid_r0c2_below", "Calc!N8", "=INDEX($Q$5:$R$7,0,2)", "row 8, below"),
    ("grid_r0c1_inside", "Calc!O6", "=INDEX($Q$5:$R$7,0,1)", "row 6 inside"),
    ("grid_r0c1_outside", "Calc!O9", "=INDEX($Q$5:$R$7,0,1)", "row 9 outside"),
    ("grid_r2c0_left_adj", "Calc!P30", "=INDEX($Q$5:$R$7,2,0)", "column P, just left of Q-R"),
    ("grid_r2c0_left_edge", "Calc!Q30", "=INDEX($Q$5:$R$7,2,0)", "column Q = left edge"),
    ("grid_r2c0_right_edge", "Calc!R30", "=INDEX($Q$5:$R$7,2,0)", "column R = right edge"),
    ("grid_r2c0_right_adj", "Calc!S30", "=INDEX($Q$5:$R$7,2,0)", "column S, just right"),
    ("grid_r0c0_row_inside", "Calc!U6", "=INDEX($Q$5:$R$7,0,0)", "row 6 inside, column U outside"),
    ("grid_r0c0_col_inside", "Calc!Q31", "=INDEX($Q$5:$R$7,0,0)", "column Q inside, row 31 outside"),
    ("grid_r0c0_neither", "Calc!U31", "=INDEX($Q$5:$R$7,0,0)", "row and column outside"),
    ("grid_r0_row_inside", "Calc!U7", "=INDEX($Q$5:$R$7,0)", "one argument; row 7 inside"),
    ("grid_r0_col_inside", "Calc!Q32", "=INDEX($Q$5:$R$7,0)", "one argument; column Q inside"),
    ("grid_r0_neither", "Calc!U32", "=INDEX($Q$5:$R$7,0)", "one argument; outside"),
    ("grid_r0c2_sum_inside", "Calc!V6", "=SUM(INDEX($Q$5:$R$7,0,2))", "row 6 inside, inside SUM"),
    ("grid_r0c2_sum_outside", "Calc!V9", "=SUM(INDEX($Q$5:$R$7,0,2))", "row 9 outside, inside SUM"),
    ("grid_r2c0_sum_outside", "Calc!S33", "=SUM(INDEX($Q$5:$R$7,2,0))", "column S outside, inside SUM"),
    ("grid_r0c0_sum", "Calc!W6", "=SUM(INDEX($Q$5:$R$7,0,0))", "inside SUM"),
    # --- range on another sheet
    ("xsheet_col_r0_inside", "Calc!Y6", "=INDEX(Data!$M$5:$M$7,0)", "Calc row 6, range Data rows 5-7"),
    ("xsheet_col_r0_outside", "Calc!Y9", "=INDEX(Data!$M$5:$M$7,0)", "Calc row 9, range Data rows 5-7"),
    ("xsheet_row_c0_inside", "Calc!F35", "=INDEX(Data!$E$20:$G$20,0)", "Calc column F, range Data E-G"),
    ("xsheet_row_c0_outside", "Calc!C35", "=INDEX(Data!$E$20:$G$20,0)", "Calc column C, range Data E-G"),
    ("xsheet_back_inside", "Data!B6", "=INDEX(Calc!$M$5:$M$7,0)", "Data row 6, range Calc rows 5-7"),
    ("xsheet_back_outside", "Data!B9", "=INDEX(Calc!$M$5:$M$7,0)", "Data row 9, range Calc rows 5-7"),
    # --- single cell T5 (R-30)
    ("cell_rng_r0_same_row", "Calc!AA5", "=INDEX($T$5:$T$5,0)", "row 5 = the cell's row"),
    ("cell_rng_r0_other_row", "Calc!AA9", "=INDEX($T$5:$T$5,0)", "row 9"),
    ("cell_ref_r0_same_row", "Calc!AB5", "=INDEX($T$5,0)", "row 5"),
    ("cell_ref_r0_other_row", "Calc!AB9", "=INDEX($T$5,0)", "row 9"),
    ("cell_rng_r0c0_same_row", "Calc!AC5", "=INDEX($T$5:$T$5,0,0)", "row 5"),
    ("cell_rng_r0c0_other_row", "Calc!AC9", "=INDEX($T$5:$T$5,0,0)", "row 9"),
)

_DATA: dict[str, dict[str, object]] = {
    "Calc": {
        "M5": 7, "M6": 8, "M7": 9,
        "E20": 21, "F20": 22, "G20": 23,
        "Q5": 31, "Q6": 32, "Q7": 33, "R5": 41, "R6": 42, "R7": 43,
        "T5": 55,
        "Z1": 0,
    },
    "Data": {
        "M5": 107, "M6": 108, "M7": 109,
        "E20": 121, "F20": 122, "G20": 123,
    },
}


def build_workbook(path: Path) -> Path:
    """Write the measurement workbook; refuse overlapping cells."""
    wb = Workbook()
    sheets = {"Calc": wb.active}
    sheets["Calc"].title = "Calc"
    sheets["Data"] = wb.create_sheet("Data")
    used: set[str] = set()
    for sheet, cells in _DATA.items():
        for addr, value in cells.items():
            used.add(f"{sheet}!{addr}")
            sheets[sheet][addr] = value
    ids: set[str] = set()
    for cid, ref, formula, _ in CASES:
        if ref in used or cid in ids:
            raise ValueError(f"probe layout collision at {ref} ({cid})")
        used.add(ref)
        ids.add(cid)
        sheet, addr = ref.split("!")
        sheets[sheet][addr] = formula
    wb.save(path)
    return path


def _plain(v: object) -> object:
    """JSON form: Excel errors as their text, numbers as float, else unchanged."""
    from ghost.runtime.excel import ExcelError

    if isinstance(v, dict) and "error" in v:
        return v["error"]
    if isinstance(v, ExcelError):
        return v.code
    if isinstance(v, Decimal):
        return float(v)
    return v


def soffice_version(soffice: str) -> str:
    out = subprocess.run([soffice, "--version"], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r"LibreOffice\s+([\d.]+)", out)
    return m.group(1) if m else out.strip()


def measure(workdir: Path) -> dict:
    """Build the workbook in ``workdir`` and return Referee and Ghost results per case."""
    from ghost.converter.emit_python import emit_module
    from ghost.converter.mapping import generate_mapping
    from ghost.ingest.workbook import load_workbook
    from ghost.referee.client import RefereeClient
    from ghost.referee.locate import locate_soffice
    from ghost.verifier.compare import values_equal
    from ghost.verifier.run import load_compute

    path = build_workbook(Path(workdir) / "index_zero_probe.xlsx")
    refs = [ref for _, ref, _, _ in CASES]

    book = load_workbook(str(path))
    mapping = generate_mapping(book, {ref: "OUTPUT" for ref in refs})
    emitted = emit_module(book, mapping)
    ghost_out = load_compute(emitted.code)({})
    name_of = {spec.cell: name for name, spec in mapping.outputs.items()}
    not_converted = {nc.cell: nc.reason for nc in emitted.not_converted}

    soffice = locate_soffice()
    with RefereeClient(None, path) as ref:
        referee = ref.read(refs)

    rows = []
    for cid, cell, formula, note in CASES:
        r = _plain(referee[cell])
        if cell in not_converted:
            g: object = f"not converted: {not_converted[cell]}"
            agree = False
        else:
            g = _plain(ghost_out.get(name_of[cell]))
            agree = values_equal(r, g, 1e-6)
        rows.append({"id": cid, "cell": cell, "formula": formula, "placement": note,
                     "referee": r, "ghost": g, "agree": bool(agree)})
    return {"libreoffice": soffice_version(soffice), "cases": rows}


def main(argv: list[str]) -> int:
    with tempfile.TemporaryDirectory(prefix="ghost-l03-") as tmp:
        result = measure(Path(tmp))
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
