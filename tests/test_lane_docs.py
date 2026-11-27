"""What the documents of the large-workbook lane may and may not say (corrections of 2026-11-26).
Text checks only: no LibreOffice, no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ("On Ghost's generated macro sample a cell that calls a VBA function reads #MACRO? with macros off and with "
         "macros trusted. The cause was not found, an Excel-saved workbook was not tried, and listing the procedures "
         "works with macros off too.")
PASS_COVERS = ("The check covers only outputs calculated by worksheet formulas. Values produced by the VBA itself are "
               "not refereed, so a pass says nothing about the migrated VBA.")
POWER = "documented by AWS; not installed or tested with Ghost"


def text(rel: str) -> str:
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split())


def lane_section() -> str:
    t = text("README.md")
    return t[t.index("## Large workbooks and the AWS Transform hand-off"):t.index("## Use the Kiro Power")]


def test_the_readme_no_longer_says_formulas_are_never_sent_and_says_what_is_uploaded():
    s = lane_section()
    assert "never sends formulas" not in s and "formulas are not part of what you send" not in s
    assert "rules.md restates the worksheet formulas in English" in s and "uploaded with the rest" in s
    assert "formula-fed outputs of the Python that comes back" in s
    assert "referee the Python that comes back" not in s


def test_what_a_pass_covers_is_in_the_readme_run_md_and_the_receipt():
    assert PASS_COVERS in lane_section()
    from ghost import receipt
    assert PASS_COVERS in " ".join(receipt.KNOWN_LIMITS)
    from ghost import handoff
    import inspect
    assert "the check covers only outputs calculated by worksheet formulas" in inspect.getsource(handoff).lower()


def test_the_macro_spike_sentence_is_the_same_everywhere_and_never_says_the_project_loads():
    for rel in ("README.md", "plugin/skills/route-migration/SKILL.md", ".kiro/specs/large-workbook-lane/design.md"):
        t = text(rel)
        assert SPIKE in t, rel
        assert "project loads" not in t.lower() and "vba project loads" not in t.lower(), rel
    assert "project loads" not in text("ghost/handoff.py").lower()
    assert "project loads" not in text("tests/test_macro_spike.py").lower().replace("never says the project loads", "")


def test_the_readme_says_challenge_has_no_trust_macros_and_marks_the_route_card_as_after_deploy():
    t = text("README.md")
    assert "`ghost challenge` has no `--trust-macros`" in t
    assert "route card" in lane_section()
    assert "larger files are rejected with a message naming the limit" not in t
    assert "route command" in t and "ghost.cli route" in t  # no bare `ghost route` in prose (final round, item 16)


def test_the_checklist_has_the_pythonpath_command_and_a_row_for_which_g_form_worked():
    t = text("docs/KIRO_OWNER_CHECKLIST.md")
    assert "PYTHONPATH=. python samples/make_xlsm.py" in t
    assert "file://atx-config.yaml" in t and "which form" in t.lower()


def test_the_steering_file_names_over_ghosts_limits_in_its_first_paragraph():
    line = (ROOT / ".kiro/steering/routing-thresholds.md").read_text(encoding="utf-8").splitlines()[6]
    assert "Over Ghost's limits" in line and "Split" in line


def test_the_power_and_the_log_line_are_described_as_the_aws_documents_say():
    facts = text("docs/AWS_TRANSFORM_FACTS.md")
    assert POWER in facts
    for url in ("kiro.dev/launch/powers/aws-transform", "github.com/kirodotdev/powers/tree/main/aws-transform",
                "developer-tools.html", "custom-get-started.html"):
        assert url in facts, url
    assert "transform.log" in facts and "Execution was not successful" in facts
    assert "not in the AWS user guide" in facts and "not observed by Ghost" in facts
    assert "3.5.0" in facts and "scripts/" in facts
    assert "**NOT VERIFIED.** No AWS documentation page I read names that line" not in facts
    for rel in ("ghost/router/explain.py", "plugin/skills/route-migration/SKILL.md", ".kiro/steering/routing-thresholds.md"):
        t = text(rel)
        assert POWER in t, rel
        assert "its existence is not verified" not in t and "existence is not verified" not in t, rel


def test_the_timeout_docstring_says_libreoffice_runs_in_its_own_session():
    from ghost import receipt
    assert "own session" in " ".join(receipt._default_runner.__doc__.split())
    t = lane_section()
    assert "kills the whole process group" not in t and "LibreOffice" in t and "own session" in t


def test_the_design_and_requirements_follow_the_corrections():
    d = text(".kiro/specs/large-workbook-lane/design.md")
    r = text(".kiro/specs/large-workbook-lane/requirements.md")
    assert "Ghost does not send formulas to AWS Transform" not in r
    assert "rules.md" in r and "mapping_equals_ghost_derived" in r and "mode" in r
    assert "-p <kit-folder>" in d or "`-p` is always the kit folder" in d


def test_the_readme_names_the_xml_element_cap_next_to_the_other_upload_limits():
    t = text("README.md")
    assert "2,000,000 XML start tags" in t and "Workbook has too many XML elements; rejected." in t
