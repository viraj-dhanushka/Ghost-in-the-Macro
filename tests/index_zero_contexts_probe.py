"""Measurement probe for L-03, task 3.7: ``INDEX`` contexts beyond the task 3.5 table.

Task 3.5 (``tests/index_zero_probe.py``) measured 69 placements. While fixing L-03,
task 3.7 measured the contexts that table lists as "not checked" and that the fix
touches: ``INDEX`` with 0 inside ``MIN``, ``MAX``, ``AND``, ``OR``, ``IF``, ``ROUND``,
``IFERROR`` and ``CHOOSE``; a computed 0 inside an aggregate; a defined-name range;
a grid with the column omitted; error order (negative and too-large indexes); text,
boolean, fraction and empty-cell indexes; and ``INDEX`` passed through ``IF``,
``IFERROR`` or ``CHOOSE`` inside ``SUM``.

Like the task 3.5 probe it depends only on ``ghost.referee`` and openpyxl, so it also
runs inside the Docker image::

    PYTHONPATH=. .venv/bin/python tests/index_zero_contexts_probe.py
    docker run --rm --platform linux/amd64 \\
        -v "$PWD/tests/index_zero_contexts_probe.py:/probe/p.py:ro" \\
        ghost-local:l03 /opt/venv/bin/python /probe/p.py

``tests/test_index_zero_contexts.py`` imports ``CASES``, ``DATA``, ``NAMES`` and
``build_workbook`` from here.

Layout (sheet ``Calc``): ``M5:M7`` = 7, 8, 9 (``M8`` empty); ``N5:N7`` = "x", 4, empty;
``P5:P7`` = TRUE, FALSE, TRUE; grid ``Q5:R7`` (Q = 31, 32, 33; R = 41, 42, 43);
``E20:G20`` = 21, 22, 23; ``Z1`` = 0; ``Y1`` empty; name ``Col`` = ``Calc!$M$5:$M$7``.
Row 6 is inside the rows 5 to 7, rows 9 to 12 are outside.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

M, N, P, G = "$M$5:$M$7", "$N$5:$N$7", "$P$5:$P$7", "$Q$5:$R$7"

# (formula cell, formula). Results are pinned in tests/test_index_zero_contexts.py.
CASES: tuple[tuple[str, str], ...] = (
    # --- row 6, inside the rows of M5:M7, N5:N7, P5:P7 and Q5:R7
    ("Calc!B6", f"=SUM(INDEX({M},$Z$1))"),
    ("Calc!C6", f"=MIN(INDEX({M},0))"),
    ("Calc!D6", f"=MAX(INDEX({M},0))"),
    ("Calc!E6", f"=AND(INDEX({P},0))"),
    ("Calc!F6", f"=OR(INDEX({P},0))"),
    ("Calc!G6", f"=IF(INDEX({M},0)>7,1,2)"),
    ("Calc!H6", f"=ROUND(INDEX({M},0),0)"),
    ("Calc!I6", f"=SUM(INDEX({M},0),1)"),
    ("Calc!J6", f"=SUM(INDEX({N},0))"),
    ("Calc!K6", f"=SUM(INDEX({M},2))"),
    ("Calc!L6", "=INDEX(Col,0)"),
    ("Calc!O6", "=SUM(INDEX(Col,0))"),
    ("Calc!S6", f"=IFERROR(INDEX({M},0),-1)"),
    ("Calc!T6", f"=CHOOSE(1,INDEX({M},0))"),
    ("Calc!U6", f"=SUM(INDEX({G},$Z$1,$Z$1))"),
    ("Calc!V6", f"=AVERAGE(INDEX({N},1))"),
    ("Calc!W6", f"=SUM(INDEX({G},0))"),
    ("Calc!X6", f"=SUM(-INDEX({M},0))"),
    ("Calc!Y6", f"=INDEX({M},0.5)"),
    ("Calc!AA6", f"=SUM(INDEX({M},0.5))"),
    ("Calc!AB6", f'=INDEX({M},"0")'),
    ("Calc!AC6", f"=INDEX({M},TRUE)"),
    ("Calc!AD6", f"=INDEX({M},FALSE)"),
    ("Calc!AE6", f"=INDEX({M},$Y$1)"),
    ("Calc!AF6", f"=INDEX({M},0,2)"),
    ("Calc!AG6", f"=INDEX({M},5,-1)"),
    ("Calc!AH6", f"=INDEX({G},0,-1)"),
    ("Calc!AI6", f"=INDEX({G},0,3)"),
    ("Calc!AN6", f"=INDEX({M},-1)"),
    # --- rows 9 to 12, outside those rows
    ("Calc!B9", f"=SUM(INDEX({M},$Z$1))"),
    ("Calc!C9", f"=MIN(INDEX({M},0))"),
    ("Calc!D9", f"=MAX(INDEX({M},0))"),
    ("Calc!E9", f"=AND(INDEX({P},0))"),
    ("Calc!F9", f"=OR(INDEX({P},0))"),
    ("Calc!G9", f"=IF(INDEX({M},0)>7,1,2)"),
    ("Calc!H9", f"=ROUND(INDEX({M},0),0)"),
    ("Calc!I9", f"=SUM(INDEX({M},0)+1)"),
    ("Calc!J9", f"=AVERAGE(INDEX({N},0))"),
    ("Calc!K9", f"=SUM(INDEX({N},2))"),
    ("Calc!L9", "=INDEX(Col,0)"),
    ("Calc!O9", f"=SUM(INDEX({M},$Z$1,1))"),
    ("Calc!S9", f"=IFERROR(INDEX({M},0),-1)"),
    ("Calc!T9", f"=SUM(INDEX({M},0,$Z$1))"),
    ("Calc!U9", f"=SUM(INDEX({N},1))"),
    ("Calc!V9", f"=SUM(INDEX({M},1,1))"),
    ("Calc!W9", f"=SUM(INDEX({G},2))"),
    ("Calc!X9", f"=INDEX({G},2)"),
    ("Calc!Q9", f"=INDEX({G},2)"),
    ("Calc!R9", f"=INDEX({G},2)"),
    ("Calc!Y9", f"=SUM(INDEX({G},$Z$1))"),
    ("Calc!AA9", f"=SUM(INDEX({M},0,0))"),
    ("Calc!AB9", "=SUM(INDEX($E$20:$G$20,0,0))"),
    ("Calc!AC9", f"=SUM(INDEX({M},4))"),
    ("Calc!AD9", f"=SUM(INDEX({M},0,2))"),
    ("Calc!AE9", f"=MAX(INDEX({M},0),INDEX({G},0,2))"),
    ("Calc!AF9", "=SUM(INDEX($M5:$M7,0))"),
    ("Calc!AG9", "=SUM(INDEX(M5,0))"),
    ("Calc!AH9", "=SUM(INDEX($M$5:$M$8,0))"),
    ("Calc!AI9", "=AVERAGE(INDEX($M$5:$M$8,0))"),
    ("Calc!AJ9", f"=INDEX({M},0,2)"),
    ("Calc!AK9", f"=INDEX({G},0,3)"),
    ("Calc!AL9", f"=INDEX({G},4,0)"),
    ("Calc!Q10", f"=INDEX({G},4,0)"),
    ("Calc!AM9", "=INDEX($E$20:$G$20,2,0)"),
    ("Calc!F30", "=INDEX($E$20:$G$20,2,0)"),
    ("Calc!AN9", f"=INDEX({M},-1)"),
    ("Calc!AO9", f"=INDEX({M},0.5)"),
    ("Calc!AP9", f"=SUM(INDEX({M},-1))"),
    ("Calc!AQ9", f"=SUM(INDEX({M},2)*2)"),
    ("Calc!AR9", f"=INDEX({M},-1,2)"),
    ("Calc!AS9", f"=INDEX({G},-1,0)"),
    ("Calc!AT9", f"=INDEX({M},1,-1)"),
    ("Calc!AU9", f"=SUM(INDEX({G},0,5))"),
    ("Calc!AV9", f"=INDEX({G},0,0.5)"),
    ("Calc!Q12", f"=INDEX({G},1.9,0)"),
    # --- INDEX passed through IF / IFERROR / CHOOSE inside SUM
    ("Calc!AW6", f"=SUM(IF(TRUE,INDEX({M},0)))"),
    ("Calc!AX6", f"=SUM(IFERROR(INDEX({M},0),0))"),
    ("Calc!AY6", f"=SUM(CHOOSE(1,INDEX({M},0)))"),
    ("Calc!AW9", f"=SUM(IF(TRUE,INDEX({M},0)))"),
    ("Calc!AX9", f"=SUM(IFERROR(INDEX({M},0),0))"),
    ("Calc!AY9", f"=SUM(CHOOSE(1,INDEX({M},0)))"),
    ("Calc!AZ9", f"=SUM(IF(TRUE,INDEX({M},2)))"),
)

DATA: dict[str, object] = {
    "M5": 7, "M6": 8, "M7": 9,
    "N5": "x", "N6": 4,
    "P5": True, "P6": False, "P7": True,
    "Q5": 31, "Q6": 32, "Q7": 33, "R5": 41, "R6": 42, "R7": 43,
    "E20": 21, "F20": 22, "G20": 23,
    "Z1": 0,
}
NAMES = (("Col", "Calc!$M$5:$M$7"),)
_EMPTY = {"M8", "N7", "Y1"}  # must stay empty


def build_workbook(path: Path) -> Path:
    """Write the probe workbook; refuse overlapping or reserved cells."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    used = set(DATA) | _EMPTY
    for addr, value in DATA.items():
        ws[addr] = value
    for ref, formula in CASES:
        addr = ref.split("!")[1]
        if addr in used:
            raise ValueError(f"probe layout collision at {ref}")
        used.add(addr)
        ws[addr] = formula
    for name, target in NAMES:
        wb.defined_names[name] = DefinedName(name, attr_text=target)
    wb.save(path)
    return path


def _plain(v: object) -> object:
    return v["error"] if isinstance(v, dict) and "error" in v else v


def soffice_version(soffice: str) -> str:
    out = subprocess.run([soffice, "--version"], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r"LibreOffice\s+([\d.]+)", out)
    return m.group(1) if m else out.strip()


def measure_referee(workdir: Path) -> dict:
    """Referee value for every probe cell, plus the LibreOffice version."""
    from ghost.referee.client import RefereeClient
    from ghost.referee.locate import locate_soffice

    path = build_workbook(Path(workdir) / "index_zero_contexts.xlsx")
    refs = [ref for ref, _ in CASES]
    with RefereeClient(None, path) as ref:
        values = ref.read(refs)
    return {"libreoffice": soffice_version(locate_soffice()),
            "referee": {r: _plain(values[r]) for r in refs}}


def main(argv: list[str]) -> int:
    with tempfile.TemporaryDirectory(prefix="ghost-l03-ctx-") as tmp:
        result = measure_referee(Path(tmp))
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
