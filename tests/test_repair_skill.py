"""The "Repair loop" section of the implement-from-rules skill (trial-by-workbook, Requirement 5)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "plugin" / "skills" / "implement-from-rules" / "SKILL.md").read_text(encoding="utf-8")


def section():
    m = re.search(r"^## Repair loop\n(.*?)(?=^## |\Z)", SKILL, re.S | re.M)
    assert m, "the skill has no 'Repair loop' section"
    return m.group(1)


def test_the_section_tells_the_agent_to_read_the_brief_and_change_only_what_it_shows():
    s = section()
    assert "repair-brief.json" in s and "smallest failing input" in s
    assert "Change only what the brief demonstrates" in s


def test_it_forbids_touching_the_workbook_the_mapping_the_decisions_and_the_tests():
    s = section()
    for item in ("the workbook", "`mapping.yaml`", "`decisions.yaml`", "the tests"):
        assert item in s, item
    assert "Never touch" in s


def test_it_stops_at_not_converged_and_keeps_the_log_untouched():
    s = section()
    assert "not converged" in s and "five failed rounds" in s
    assert "`repair-log.md`" in s and "do not edit" in s.lower()


def test_the_rest_of_the_skill_is_still_there():
    assert SKILL.startswith("---\nname: implement-from-rules")
    for head in ("## Contract", "## Rules for the code", "## Check your own work"):
        assert head in SKILL


def test_the_section_does_not_claim_correctness():
    assert not re.search(r"\b(correct|proven|proved)\b", section(), re.I)


def test_the_mappings_in_the_skill_are_accepted_by_the_engine_and_declare_each_inputs_domain():
    # Found in the first agent run (2026-11-26): the skill's example `quantity: Sheet1!B2` was rejected by the
    # engine, and a mapping without types and minimums let the search try negative prices.
    import yaml
    from ghost.converter.mapping import read_mapping
    import tempfile
    blocks = re.findall(r"```yaml\n(.*?)```", SKILL, re.S)
    assert blocks
    for text in blocks:
        path = Path(tempfile.mkdtemp()) / "mapping.yaml"
        path.write_text(text, encoding="utf-8")
        m = read_mapping(path)
        assert m.inputs and m.outputs
        assert all(spec.type in ("integer", "decimal") for spec in m.inputs.values())
        assert all(spec.min is not None for spec in m.inputs.values())
        assert yaml.safe_load(text)["inputs"]


def test_the_skill_tells_the_agent_to_ask_for_the_domain_and_not_to_narrow_it_to_hide_a_difference():
    assert "searched over" in SKILL and "Ask the user" in SKILL and "hide a difference" in SKILL


def test_the_repair_loop_allows_a_mapping_change_only_when_the_user_asks_for_it():
    s = section()
    assert "change `mapping.yaml` only when the user tells you to" in s.lower()


def test_step_1_tells_the_agent_to_stop_on_not_converged_and_to_ask_when_a_brief_lists_decisions():
    step1 = " ".join(section().split("2. Change only")[0].split())
    assert '"not converged"' in step1 and "stop" in step1.lower()
    assert "decision_ids" in step1 and "ask the user" in step1.lower()
