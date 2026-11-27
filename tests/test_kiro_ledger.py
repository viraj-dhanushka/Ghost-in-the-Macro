"""scripts/kiro_ledger.py (judge-kit, items 1 to 3): read-only, byte-identical, checkable. No LibreOffice."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "kiro_ledger.py"
OUTPUTS = ["docs/KIRO_STORY.md", "docs/KIRO_PROPERTY_LEDGER.md", "web/kiro_facts.json", "README.md"]

sys.path.insert(0, str(ROOT / "scripts"))
import kiro_ledger  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, timeout=120)


def test_two_runs_give_byte_identical_outputs():
    assert kiro_ledger.outputs() == kiro_ledger.outputs()


def test_check_passes_on_the_committed_outputs_and_writes_nothing():
    before = {p: (ROOT / p).read_bytes() for p in OUTPUTS}
    r = run("--check")
    assert r.returncode == 0, r.stderr
    assert {p: (ROOT / p).read_bytes() for p in OUTPUTS} == before


def test_check_fails_when_a_committed_output_is_stale(monkeypatch):
    out = kiro_ledger.outputs()
    stale = dict(out)
    stale["docs/KIRO_STORY.md"] = out["docs/KIRO_STORY.md"] + "\nextra\n"
    monkeypatch.setattr(kiro_ledger, "read", lambda rel: stale.get(rel, ""))
    monkeypatch.setattr(kiro_ledger, "outputs", lambda: out)
    assert kiro_ledger.main(["--check"]) == 1


def test_the_script_only_writes_its_four_files():
    text = SCRIPT.read_text(encoding="utf-8")
    writes = re.findall(r"\.write_text\(", text)
    assert len(writes) == 1 and all(n in text for n in ("OUT_STORY", "OUT_LEDGER", "OUT_FACTS", "OUT_README"))
    for bad in ("subprocess", "os.system", "shutil", "unlink", "rmtree"):
        assert bad not in text


def test_the_story_has_one_section_per_topic_and_an_owner_placeholder_each():
    story = (ROOT / "docs/KIRO_STORY.md").read_text(encoding="utf-8")
    titles = re.findall(r"^## (\d)\. (.+)$", story, re.M)
    assert [n for n, _ in titles] == [str(i) for i in range(1, 9)]
    joined = " ".join(t.lower() for _, t in titles)
    for topic in ("surfaces", "custom agents", "hooks", "spec-driven", "steering", "mcp", "property-based", "powers"):
        assert topic in joined, topic
    # each section ends with the Owner's placeholder or, once docs/KIRO_OWNER_NOTES.md has text for it, the Owner's words
    placeholders = len(re.findall(r"^\[OWNER: .+\]$", story, re.M))
    owner_texts = len(re.findall(r"^\*\*Owner's words\*\*", story, re.M))
    assert placeholders + owner_texts == 8
    # only the machine-written text is checked: the Owner's own words (after "**Owner's words**", up to the next heading) are theirs
    machine = re.sub(r"^\*\*Owner's words\*\*.*?(?=^## |\Z)", "", story, flags=re.M | re.S)
    for forbidden in ("I loved", "I felt", "my favourite", "amazing"):
        assert forbidden not in machine


def test_every_counted_fact_names_its_source_path():
    facts = json.loads((ROOT / "web/kiro_facts.json").read_text(encoding="utf-8"))
    for item in facts["items"]:
        assert isinstance(item["count"], int) and item["source"]
        assert any(p in item["source"] for p in (".kiro/", "mcp_server/", "plugin/", "tests/", "docs/"))
    story = (ROOT / "docs/KIRO_STORY.md").read_text(encoding="utf-8")
    counted = re.compile(r"^- \d+ [^:]*\((?:\.kiro|mcp_server|plugin|tests|docs)[^)]*\)")
    lines = [ln for ln in story.splitlines() if re.match(r"^- \d+ (steering files|hooks|custom agents|MCP tools|skills|Kiro specs|test files)", ln)]
    assert len(lines) >= 7
    for ln in lines:
        assert counted.match(ln), ln


def test_the_ledger_is_keyed_by_spec_and_number_and_marks_caught_only_from_the_log():
    rows = kiro_ledger.collect()["ledger"]
    keys = [(r["spec"], r["n"]) for r in rows]
    assert len(keys) == len(set(keys)) and len(rows) > 30
    for r in rows:
        assert r["status"].split(":")[0] in ("covered", "ambiguous", "not covered")
        if r["caught"] != "none recorded":
            assert "docs/KIRO_USAGE.md" in r["caught"]
    caught = {(r["spec"], r["n"]) for r in rows if r["caught"] != "none recorded"}
    assert ("kiro-surfaces", 2) in caught and ("kiro-surfaces", 3) in caught
    by = {(r["spec"], r["n"]): r for r in rows}
    assert by[("ghost-in-the-macro", 9)]["status"].startswith("covered") and "test_property_rule_ids" in by[("ghost-in-the-macro", 9)]["status"]
    assert by[("large-workbook-lane", 6)]["status"].startswith("covered") and "test_receipt" in by[("large-workbook-lane", 6)]["status"]
    assert ("live-fixes-2026-11-24", 3) in by and ("review-fixes-2026-11-24", 4) in by


def test_the_eight_new_property_files_are_in_the_ledger_and_fast():
    rows = {(r["spec"], r["n"]): r["status"] for r in kiro_ledger.collect()["ledger"]}
    for n, name in ((9, "rule_ids"), (11, "spec_round_trip"), (12, "incomplete_decisions"), (18, "emit_determinism"),
                    (22, "tolerance"), (29, "mutation_accounting"), (30, "report_integrity"), (31, "routing_total")):
        assert f"test_property_{name}" in rows[("ghost-in-the-macro", n)], n


def test_the_readme_table_is_generated_and_the_rest_of_the_readme_is_untouched():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert kiro_ledger.outputs()["README.md"] == readme
    block = readme.split(kiro_ledger.TABLE_BEGIN)[1].split(kiro_ledger.TABLE_END)[0]
    assert "| Kiro specs |" in block and "MCP tools" in block and "`.kiro/hooks/*.json`" in block
    out = kiro_ledger.outputs()["README.md"]
    assert out.split(kiro_ledger.TABLE_BEGIN)[0] == readme.split(kiro_ledger.TABLE_BEGIN)[0]
    assert out.split(kiro_ledger.TABLE_END)[1] == readme.split(kiro_ledger.TABLE_END)[1]


def test_the_readme_first_screen_has_what_the_feature_asks_for():
    first = "\n".join((ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:48])
    assert "Kiroween 2026, category: Resurrection" in first
    assert "https://gh-180dc96b077a480c8aba859ff54261f2.ecs.us-east-1.on.aws" in first
    assert "```mermaid" in first and "Workbook" in first and "Referee" in first and "Proof report" in first
    assert "docs/img/verdict-card.png" in first and (ROOT / "docs/img/verdict-card.png").is_file()
    assert "Built with Kiro" in first and "| Kiro specs |" in first
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Limits, stated honestly" in readme and readme.index("## Limits, stated honestly") > readme.index("## Quick start")
    for limit in ("5 MB per file", "LibreOffice is not Excel", "Volatile or external constructs", "not converted", "R-24"):
        assert limit in readme


def test_every_relative_link_in_the_readme_first_screen_exists():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\((?!http|#)([^)#\s]+)", readme):
        assert (ROOT / target).exists(), target


# -- corrections of 2026-11-26 (judge-kit items 11 and 12) -------------------------------------------
FAKE_LOG = """# Usage log
### 2026-11-20: a vibe session
- Feature: vibe (free-form session, no spec task; checked against the pinned tests only afterwards).
- Used the Kiro IDE for this.
### 2026-11-21: a review
- Skeptic (real, read-only): PASS WITH CORRECTIONS. Applied: one thing.
- Kiro Web is not claimed here, and neither is Kiro CLI.
- The Kiro CLI was used once.
"""


def _with_log(monkeypatch, log, notes=None):
    real = kiro_ledger.read

    def fake(rel):
        if rel == "docs/KIRO_USAGE.md":
            return log
        if rel == "docs/KIRO_OWNER_NOTES.md":
            return notes or ""
        return real(rel)

    monkeypatch.setattr(kiro_ledger, "read", fake)


def test_lines_that_say_not_claimed_are_not_counted_as_naming_a_surface(monkeypatch):
    _with_log(monkeypatch, FAKE_LOG)
    assert kiro_ledger.log_mentions(["Kiro CLI"]) == 1  # the real use, not the "not claimed" line
    assert kiro_ledger.log_mentions(["Kiro Web"]) == 0
    assert kiro_ledger.log_mentions(["Kiro IDE"]) == 1


def test_the_story_says_crew_is_not_claimed_in_the_required_words():
    story = (ROOT / "docs/KIRO_STORY.md").read_text(encoding="utf-8")
    assert "Kiro Crew: no entry in the usage log names it, so it is not claimed" in story


def test_explicit_feature_property_comments_bind_a_row_before_any_guess():
    assert kiro_ledger.explicit_bindings("# Feature:" + " kiro-surfaces, Property 3: names\n# Feature:" + " front-door, Property 12: x") == [
        ("kiro-surfaces", 3), ("front-door", 12)]
    assert kiro_ledger.explicit_bindings("no comment, but Property 4 and the main spec") == []
    by = {(r["spec"], r["n"]): r for r in kiro_ledger.collect()["ledger"]}
    for n in (1, 2, 3):
        assert by[("kiro-surfaces", n)]["status"] == "covered: tests/test_kiro_config.py"
    # a file that names a number but not its spec stays "ambiguous": it is not guessed into a spec
    assert by[("review-fixes-2026-11-24", 3)]["status"].startswith("ambiguous")


def test_a_file_with_explicit_comments_is_not_guessed_onto_other_specs():
    rows = kiro_ledger.collect()["ledger"]
    for r in rows:
        if r["status"].startswith("ambiguous"):
            assert "tests/test_kiro_config.py" not in r["status"] and "tests/test_property_progress_module.py" not in r["status"]


def test_the_ledger_header_says_what_covered_means():
    text = (ROOT / "docs/KIRO_PROPERTY_LEDGER.md").read_text(encoding="utf-8")
    assert "covered means a test names the property; it may be an example test" in " ".join(text.split())


def test_the_vibe_session_is_in_section_4_and_the_skeptic_entries_in_section_2(monkeypatch):
    _with_log(monkeypatch, FAKE_LOG)
    story = kiro_ledger.render_story(kiro_ledger.collect())
    s2 = story.split("## 2. ")[1].split("## 3. ")[0]
    s4 = story.split("## 4. ")[1].split("## 5. ")[0]
    assert "Feature: vibe (free-form session" in s4 and "1 usage-log entry is marked `Feature: vibe`" in s4
    assert "Skeptic (real, read-only): PASS WITH CORRECTIONS" in s2


def test_the_real_story_has_both():
    story = (ROOT / "docs/KIRO_STORY.md").read_text(encoding="utf-8")
    assert "Feature: vibe" in story.split("## 4. ")[1].split("## 5. ")[0]
    assert "Skeptic" in story.split("## 2. ")[1].split("## 3. ")[0]


def test_duplicate_spec_ids_are_printed_as_prose_not_as_a_python_list():
    story = (ROOT / "docs/KIRO_STORY.md").read_text(encoding="utf-8")
    assert "[[" not in story and "['front-door'" not in story
    assert "front-door and kiro-surfaces share one specId" in story
    assert "live-fixes-2026-11-24 and review-fixes-2026-11-24 share one specId" in story or "share another" in story
    assert "Reported to the Owner, not changed" in story


def test_the_owners_notes_replace_the_placeholder_of_their_section_only(monkeypatch):
    notes = """# Notes
<!-- a comment that is ignored -->
## 1. Surfaces
I used the IDE.

Second paragraph.
## 3. Hooks
   <!-- only a comment: this section stays a placeholder -->
## 7. Property tests
They changed how I wrote the tolerance code.
"""
    _with_log(monkeypatch, FAKE_LOG, notes)
    story = kiro_ledger.render_story(kiro_ledger.collect())
    sec = lambda n, m: story.split(f"## {n}. ")[1].split(f"## {m}. ")[0] if m else story.split(f"## {n}. ")[1]
    assert "**Owner's words**" in sec(1, 2) and "I used the IDE.\n\nSecond paragraph." in sec(1, 2)
    assert "[OWNER:" not in sec(1, 2)
    assert "[OWNER:" in sec(3, 4) and "**Owner's words**" not in sec(3, 4)
    assert "They changed how I wrote the tolerance code." in sec(7, 8) and "[OWNER:" not in sec(7, 8)
    assert len(re.findall(r"^\[OWNER: .+\]$", story, re.M)) == 6
    assert len(re.findall(r"^\*\*Owner's words\*\*", story, re.M)) == 2


def test_the_notes_file_exists_as_a_template_with_eight_sections_and_changes_nothing_while_empty():
    text = (ROOT / "docs/KIRO_OWNER_NOTES.md").read_text(encoding="utf-8")
    assert [int(n) for n in re.findall(r"^## (\d)\.", text, re.M)] == list(range(1, 9))
    filled = kiro_ledger.owner_notes(text)  # empty template or the Owner's filled sections 1 to 8: both are fine
    assert set(filled) <= set(range(1, 9))

def test_a_story_with_all_eight_notes_has_no_owner_marker_and_one_without_has_it(monkeypatch):
    notes = "\n".join(f"## {n}. Section\nMy words for {n}." for n in range(1, 9))
    _with_log(monkeypatch, FAKE_LOG, notes)
    full = kiro_ledger.render_story(kiro_ledger.collect())
    assert "[OWNER" not in full
    assert "The Owner's own words close each section" in full
    _with_log(monkeypatch, FAKE_LOG, "## 1. Surfaces\nOne note only.")
    part = kiro_ledger.render_story(kiro_ledger.collect())
    assert "[OWNER: ...]" in part.split("## 1. ")[0]
