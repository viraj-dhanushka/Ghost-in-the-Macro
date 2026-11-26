"""`ghost handoff`: the kit for AWS Transform custom (large-workbook-lane, Requirement 5, Property 3).
Nothing is executed and no AWS service is called. LibreOffice is needed only for the macro-sample tests."""
from __future__ import annotations

import filecmp
import os
import re
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest
import yaml
from hypothesis import given, settings, strategies as st

from ghost import cli, handoff
from ghost.models import VbaModule
from ghost.referee.locate import RefereeUnavailable, locate_soffice

ROOT = Path(__file__).resolve().parent.parent


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


needs_soffice = pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")


def small_book(path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calc"
    ws["A1"], ws["A2"] = 5, 7
    ws["B1"] = "=A1*A2"
    ws["B2"] = "=ROUND(B1/3,2)"
    wb.save(path)
    return path


def tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def fake_modules(monkeypatch, mods):
    monkeypatch.setattr(handoff, "_read_vba", lambda path: (list(mods), None))


# -- the kit -----------------------------------------------------------------------------------
def test_the_kit_holds_the_files_the_spec_lists(tmp_path):
    out = tmp_path / "kit"
    result = handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    names = set(tree(out))
    assert {"GHOST_CONTRACT.md", "mapping.yaml", "rules.md", "excel-semantics.md", "atx-config.yaml", "RUN.md",
            "vba/README.txt"} <= names
    assert result.mapping_written is True


def test_the_config_file_is_valid_yaml_and_points_the_agent_at_the_contract(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    cfg = yaml.safe_load((out / "atx-config.yaml").read_text(encoding="utf-8"))
    assert "GHOST_CONTRACT.md" in cfg["additionalPlanContext"]
    assert "logic.py" in cfg["additionalPlanContext"] and "compute(inputs)" in cfg["additionalPlanContext"]


def test_the_contract_names_the_inputs_outputs_tolerance_and_rounding(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    text = (out / "GHOST_CONTRACT.md").read_text(encoding="utf-8")
    m = yaml.safe_load((out / "mapping.yaml").read_text(encoding="utf-8"))
    for name, spec in {**m["inputs"], **m["outputs"]}.items():
        assert f"`{name}`" in text and spec["cell"] in text
    assert "compute(inputs: dict) -> dict" in text and "one self-contained file" in text.lower()
    assert "1e-6" in text.lower() and "half away from zero" in text.lower() and "15 significant" in text.lower()
    assert "#DIV/0!" in text and "compared by error type" in text.lower()
    assert "Decimal(repr(x))" in text
    assert "derived from the workbook" in text.lower() and "not confirmed by a person" in text.lower()
    assert "the check covers only outputs calculated by worksheet formulas" in text.lower()
    assert "correct" not in text.lower() and "proven" not in text.lower()


def test_run_md_starts_with_the_warning_and_gives_the_steps(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    text = (out / "RUN.md").read_text(encoding="utf-8")
    head = text[:900].lower()
    assert "passwords" in head and "connection strings" in head and "file paths" in head
    assert "service improvement" in text and "https://docs.aws.amazon.com/transform/latest/userguide/service-improvement.html" in text
    assert "ai services opt-out polic" in text.lower()
    for needle in ("Review vba/, rules.md and mapping.yaml before you upload anything", "git init", "git add .", "git commit", "Suggested command, not run", "atx custom def exec",
                   "$0.035", "agent minute", "ghost challenge", "--mapping", "exits 0", "Node.js 22"):
        assert needle in text, needle
    assert text.index("git init") < text.index("atx custom def exec") < text.index("ghost challenge")
    assert "-g atx-config.yaml" in text and "AWS/vba-to-python-migration" in text
    low = text.lower()
    assert "aws transform converts formulas" not in low and "handles workbook size" not in low
    assert "nothing in this folder has been run against aws" in low
    assert ("The workbook file and its cell values are not in this kit. rules.md restates the worksheet formulas in "
            "English so the agent can meet the contract; it is uploaded with the rest.") in text
    assert "formulas are not part of what you send" not in low
    assert "the check covers only outputs calculated by worksheet formulas" in low
    assert "values produced by the vba itself are not refereed, so a pass says nothing about the migrated vba" in low
    assert "file://atx-config.yaml" in text and "-g atx-config.yaml" in text
    assert "git diff" in text and "mapping.yaml GHOST_CONTRACT.md" in text and "must be empty" in text
    step6 = text[text.index("6. Referee the result"):]
    assert ("If you changed mapping.yaml yourself, run ghost challenge with --mapping; ghost receipt only referees the "
            "mapping Ghost derives.") in step6
    assert text.index("must be empty") < text.index("ghost challenge <workbook>")
    assert "documented by aws; not installed or tested with ghost" in low
    assert "Execution was not successful" in text and "not in the aws user guide" in low and "not observed by ghost" in low


def test_the_kit_is_byte_identical_across_runs_and_has_no_absolute_path(tmp_path):
    wb = small_book(tmp_path / "a.xlsx")
    handoff.write_kit(wb, tmp_path / "k1")
    handoff.write_kit(wb, tmp_path / "k2")
    assert tree(tmp_path / "k1") == tree(tmp_path / "k2")
    for name, data in tree(tmp_path / "k1").items():
        text = data.decode("utf-8")
        assert str(tmp_path) not in text, name
        assert not re.search(r"/(Users|home|tmp|var|private)/", text), name


def test_an_existing_non_empty_out_folder_is_refused(tmp_path):
    out = tmp_path / "kit"
    out.mkdir()
    (out / "x").write_text("x", encoding="utf-8")
    with pytest.raises(handoff.HandoffError):
        handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    assert (out / "x").read_text(encoding="utf-8") == "x"


def test_git_init_succeeds_in_the_kit(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    for cmd in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "kit"]):
        assert subprocess.run(cmd, cwd=out, capture_output=True).returncode == 0


# -- VBA modules (Property 3) ------------------------------------------------------------------
def test_every_module_appears_exactly_once_with_safe_distinct_names(tmp_path, monkeypatch):
    mods = [VbaModule(name="Module1.bas", source="Sub A()\nEnd Sub", line_count=2),
            VbaModule(name="../evil.bas", source="x", line_count=1),
            VbaModule(name="My Form.frm", source="y", line_count=1),
            VbaModule(name="My_Form.frm", source="z", line_count=1)]
    fake_modules(monkeypatch, mods)
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    files = sorted(p.name for p in (out / "vba").iterdir())
    assert len(files) == 4 and len(set(files)) == 4
    assert all(re.fullmatch(r"[A-Za-z0-9._-]+", f) and not f.startswith(".") for f in files)
    assert sorted(p.read_text(encoding="utf-8").rstrip("\n") for p in (out / "vba").iterdir()) == sorted(m.source for m in mods)
    assert not (tmp_path / "evil.bas").exists()


names = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=12)


# Feature: large-workbook-lane, Property 3: The kit is byte-identical, has no absolute path, and lists each VBA module once
@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(names, st.text(max_size=30)), min_size=1, max_size=8))
def test_property_3_each_module_once_and_names_are_safe(pairs):
    """Property 3: every VBA module the static read returns appears exactly once; names are safe and distinct."""
    mods = [VbaModule(name=n, source=s, line_count=len(s.split("\n"))) for n, s in pairs]
    files = handoff.module_files(mods)
    assert len(files) == len(mods) and len({f for f, _ in files}) == len(mods)
    assert all(re.fullmatch(r"[A-Za-z0-9._-]+", f) and not f.startswith(".") for f, _ in files)
    assert sorted(src for _, src in files) == sorted(m.source for m in mods)
    assert handoff.module_files(mods) == files  # deterministic


def test_unreadable_vba_is_said_in_the_kit(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "_read_vba", lambda path: ([], "ValueError: broken"))
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    assert "not readable" in (out / "vba" / "README.txt").read_text(encoding="utf-8").lower()
    assert "VBA: not readable" in (out / "RUN.md").read_text(encoding="utf-8")


def test_a_workbook_over_the_limits_gets_a_partial_kit_and_is_not_loaded(tmp_path, monkeypatch):
    import dataclasses
    from ghost.ingest.limits import MAX_CELLS
    import ghost.ingest.triage as tri
    wb = small_book(tmp_path / "a.xlsx")
    real = tri.scan_sizes
    monkeypatch.setattr(handoff, "scan_sizes", lambda p, *a, **k: dataclasses.replace(real(p), cells=MAX_CELLS + 5))
    monkeypatch.setattr(cli, "_load", lambda *a, **k: (_ for _ in ()).throw(AssertionError("loaded")))
    monkeypatch.setattr(cli, "_analyse", lambda *a, **k: (_ for _ in ()).throw(AssertionError("analysed")))
    out = tmp_path / "kit"
    r = handoff.write_kit(wb, out)
    names = set(tree(out))
    assert r.mapping_written is False and r.route == "Over Ghost's limits"
    assert "mapping.yaml" not in names and "rules.md" not in names
    assert {"GHOST_CONTRACT.md", "RUN.md", "atx-config.yaml"} <= names
    run = (out / "RUN.md").read_text(encoding="utf-8")
    assert "mapping.yaml and rules.md were not written" in run and "not loaded" in run
    assert f"{MAX_CELLS + 5:,} cells; the limit is {MAX_CELLS:,} cells" in run
    assert "cannot referee a workbook this size" in run


# -- front ends --------------------------------------------------------------------------------
def test_the_cli_writes_the_kit_and_refuses_a_non_empty_folder(tmp_path, capsys):
    wb = small_book(tmp_path / "a.xlsx")
    assert cli.main(["handoff", str(wb), "--out", str(tmp_path / "kit")]) == 0
    out = capsys.readouterr().out
    assert "Wrote the kit" in out and "Nothing was run" in out and "RUN.md" in out
    assert str(tmp_path) not in out.replace(str(tmp_path / "kit"), "")  # only the --out the user named
    assert cli.main(["handoff", str(wb), "--out", str(tmp_path / "kit")]) == 1
    assert "ghost: error:" in capsys.readouterr().err


def test_the_mcp_tool_writes_the_same_kit(tmp_path):
    from mcp_server import server as srv
    wb = small_book(tmp_path / "a.xlsx")
    res = srv.prepare_handoff(srv.PrepareHandoffArgs(workbook=str(wb), out=str(tmp_path / "kit")))
    assert "RUN.md" in res["files"] and res["executed"] is False
    handoff.write_kit(wb, tmp_path / "k2")
    assert tree(tmp_path / "kit") == tree(tmp_path / "k2")


@needs_soffice
def test_the_macro_sample_kit_holds_its_module_once_and_git_init_works(tmp_path):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_xlsm
    finally:
        sys.path.remove(str(ROOT / "samples"))
    wb = make_xlsm.build(tmp_path / "discount_vba.xlsm")
    out = tmp_path / "kit"
    handoff.write_kit(wb, out)
    mods = sorted(p.name for p in (out / "vba").iterdir())
    assert mods == ["Module1.bas"]
    assert "DeliveryFee" in (out / "vba" / "Module1.bas").read_text(encoding="utf-8")
    assert subprocess.run(["git", "init", "-q"], cwd=out, capture_output=True).returncode == 0
    run = (out / "RUN.md").read_text(encoding="utf-8")
    assert "VBA: " in run and "Module1.bas" not in run
    contract = (out / "GHOST_CONTRACT.md").read_text(encoding="utf-8")
    assert "not verifiable by the Referee" in contract
    assert ("On Ghost's generated macro sample a cell that calls a VBA function reads #MACRO? with macros off and with "
            "macros trusted. The cause was not found, an Excel-saved workbook was not tried, and listing the "
            "procedures works with macros off too.") in contract
    assert "project loads" not in contract.lower()


def test_a_definition_other_than_the_default_is_the_one_you_named(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out, definition="Team/my vba")
    run = (out / "RUN.md").read_text(encoding="utf-8")
    assert "the definition you named; Ghost has not checked it exists" in run
    assert "AWS-managed" not in run.replace("AWS-managed definition", "")
    assert "-n 'Team/my vba'" in run and "--definition 'Team/my vba'" in run


def test_the_default_definition_is_called_aws_managed_early_access(tmp_path):
    out = tmp_path / "kit"
    handoff.write_kit(small_book(tmp_path / "a.xlsx"), out)
    run = (out / "RUN.md").read_text(encoding="utf-8")
    assert "AWS-managed definition (Early access)" in run and "ghost has not checked it exists" not in run.lower()
