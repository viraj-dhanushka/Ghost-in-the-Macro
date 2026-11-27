"""Interface voice: every failure card has a ghost line; verdict templates have none."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARD = (ROOT / "web/templates/_failure_card.html").read_text()


def test_every_card_kind_has_a_ghost_line():
    kinds = re.findall(r'^  "(\w+)": \["', CARD, re.M)
    ghosts = re.findall(r'^  "(\w+)": "[^"]+",$', CARD, re.M)
    assert kinds and set(kinds) <= set(ghosts)


def test_ghost_lines_avoid_forbidden_words():
    block = CARD.split("{% set ghost = {")[1].split("} %}")[0]
    assert not re.search(r"correct|proven|\bproof\b|verified", block, re.I)
    assert not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", block)


def test_no_ghost_line_on_verdict_templates():
    for name in ("_verdict_card.html", "_job.html"):
        text = (ROOT / "web/templates" / name).read_text()
        assert "failure-ghost" not in text
    assert "ghost_line" not in (ROOT / "web/verdict.py").read_text()


def test_voice_doc_lists_waiting_messages():
    doc = (ROOT / "docs/INTERFACE_VOICE.md").read_text()
    for new in ("Waking the Referee", "The Referee is busy with another workbook",
                "Reading the workbook for conflicts, rules and decisions"):
        assert new in doc
        assert any(new in (ROOT / "web/templates" / f).read_text()
                   for f in ("_job.html", "_upload_result.html"))
