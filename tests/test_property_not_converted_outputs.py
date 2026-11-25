"""Property 6: not-converted and not-verifiable cells are never offered as outputs (PBT).

Task 3.13 of ``.kiro/specs/live-fixes-2026-11-24`` (finding L-05).

**Validates: Requirements 2.4, 3.11**

Workbooks are generated with openpyxl. Each one mixes convertible formulas
(``C1``, ``C2``, always terminal, so they are OUTPUT candidates) with a random
selection of cells the test itself made not-converted (a dynamic OFFSET or
INDIRECT defined name, an unsupported function, the INDEX_PASSED_THROUGH case)
or not-verifiable (NOW, TODAY, RAND, RANDBETWEEN, an external link), and
optionally a dependant of each. The oracle is that list, built by the test, not
the engine's own list. Every place that proposes outputs is checked:

- ``generate_mapping`` defaults (``ghost.converter.mapping``)
- the web autopsy page (``GET /autopsy``, built by ``web.flow._describe``):
  offered and pre-checked output boxes
- the CLI defaults (``ghost.cli._analyse`` and the ``ghost autopsy`` text)
- the MCP defaults (``analyze_workbook``)

Explicit selection of such a cell is task 3.15 and is not covered here.
"""
from __future__ import annotations

import html as htmlmod
import re
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from ghost import cli
from ghost.converter.mapping import generate_mapping
from ghost.converter.subset import find_not_converted
from ghost.ingest.features import scan_features
from ghost.ingest.workbook import load_workbook
from mcp_server.server import _MappedWorkbookArgs, analyze_workbook
from web.app import create_app

SEED = 20261124

# kind -> (formula template for the bad cell, marks it not-verifiable?)
BAD_KINDS: dict[str, tuple[str, bool]] = {
    "offset_name": ("=DynO*2", False),
    "indirect_name": ("=DynI*2", False),
    "unsupported_function": ("=GAMMALN(B1)", False),
    "index_passed_through": ("=SUM(IFERROR(INDEX(M1:M3,0),0))", False),
    "now": ("=NOW()", True),
    "today": ("=TODAY()", True),
    "rand": ("=RAND()", True),
    "randbetween": ("=RANDBETWEEN(1,10)", True),
    "external_link": ("='[ext.xlsx]Sheet1'!A1+B1", True),
}

_BOX = re.compile(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>')


@st.composite
def bad_selections(draw):
    kinds = draw(st.lists(st.sampled_from(sorted(BAD_KINDS)), min_size=1, max_size=5, unique=True))
    with_dependant = [draw(st.booleans()) for _ in kinds]
    return list(zip(kinds, with_dependant))


def build(path: Path, selection) -> set[str]:
    """Write the workbook; return the cells the test made not-converted or not-verifiable."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"], ws["B1"] = "Amount", 4
    ws["A2"], ws["B2"] = "Rate", 3
    for i, v in enumerate((7, 8, 9), start=1):
        ws[f"M{i}"] = v
    wb.defined_names["DynO"] = DefinedName("DynO", attr_text="OFFSET(Calc!$B$1,0,0)")
    wb.defined_names["DynI"] = DefinedName("DynI", attr_text='INDIRECT("Calc!$B$1")')
    ws["C1"] = "=B1*2"          # convertible, terminal
    ws["C2"] = "=B1+B2"         # convertible, terminal
    bad: set[str] = set()
    for row, (kind, dependant) in enumerate(selection, start=4):
        ws[f"D{row}"] = BAD_KINDS[kind][0]
        bad.add(f"Calc!D{row}")
        if dependant:
            ws[f"E{row}"] = f"=D{row}+1"
            bad.add(f"Calc!E{row}")
    wb.save(path)
    return bad


def _boxes(page: str) -> tuple[list[str], list[str]]:
    """Offered and pre-checked output boxes on the autopsy page."""
    offered, checked = [], []
    for kind, value, rest in _BOX.findall(page):
        if kind != "outputs":
            continue
        value = htmlmod.unescape(value)
        offered.append(value)
        if "checked" in rest:
            checked.append(value)
    return offered, checked






@seed(SEED)
@settings(
    max_examples=15, deadline=None, derandomize=True, database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(selection=bad_selections())
def test_property6_bad_cells_never_offered_as_outputs(tmp_path, selection, capsys):
    work = Path(tempfile.mkdtemp(dir=tmp_path))
    try:
        path = work / "mix.xlsx"
        bad = build(path, selection)
        good = {"Calc!C1", "Calc!C2"}

        # Generator sanity: the engine really does flag what the test built.
        wb = load_workbook(str(path))
        flagged = {e.cell for e in find_not_converted(wb)} | {
            f.cell for f in scan_features(wb) if f.not_verifiable
        }
        assert {c for c in bad if c.startswith("Calc!D")} <= flagged, (selection, flagged)

        offenders: dict[str, set[str]] = {}

        def record(place: str, cells) -> None:
            hit = set(cells) & bad
            if hit:
                offenders[place] = hit

        # 1. generate_mapping defaults
        mapping = generate_mapping(wb)
        map_out = {s.cell for s in mapping.outputs.values()}
        record("generate_mapping", map_out)
        assert good <= map_out, ("convertible outputs missing from mapping", map_out)

        # 2. web autopsy
        app = create_app(session_root=work / "sessions")
        client = TestClient(app)
        r = client.post("/upload", files={"file": (path.name, path.read_bytes(),
                                                   "application/octet-stream")})
        assert r.status_code == 200, r.text
        page = client.get("/autopsy")
        assert page.status_code == 200, page.text
        offered, checked = _boxes(page.text)
        record("web offered", offered)
        record("web pre-checked", checked)
        assert good <= set(checked), ("convertible outputs not pre-checked", checked)

        # 3. CLI defaults
        an = cli._analyse(path)
        cli_out = {r_ for r_, v in an.roles.items() if v == "OUTPUT"}
        record("cli defaults", cli_out)
        record("cli generate_mapping", {s.cell for s in generate_mapping(an.wb, an.roles).outputs.values()})
        capsys.readouterr()
        assert cli.cmd_autopsy(
            type("A", (), {"workbook": str(path), "inputs": None, "outputs": None})()
        ) in (0, None)
        text = capsys.readouterr().out
        line = next(ln for ln in text.splitlines() if ln.strip().startswith("outputs ("))
        record("cli autopsy text", {c.strip() for c in line.split(":", 1)[1].split(",")})

        # 4. MCP defaults
        mcp = analyze_workbook(_MappedWorkbookArgs(workbook=str(path)))
        record("mcp analyze_workbook", mcp["outputs"])
        assert good <= set(mcp["outputs"]), ("convertible outputs missing in MCP", mcp["outputs"])

        assert not offenders, f"offered as outputs: {offenders}"
    finally:
        shutil.rmtree(work, ignore_errors=True)
