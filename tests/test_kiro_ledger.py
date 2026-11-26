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
    assert len(re.findall(r"^\[OWNER: .+\]$", story, re.M)) == 8
    for forbidden in ("I loved", "I felt", "my favourite", "amazing"):
        assert forbidden not in story


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
