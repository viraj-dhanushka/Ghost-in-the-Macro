"""The judge-kit documents and scripts (judge-kit items 5 to 8): checkable properties only, no network, no LibreOffice."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_video_script_shots_add_up_to_under_three_minutes_and_are_contiguous():
    text = (ROOT / "docs/DEMO_VIDEO_SCRIPT.md").read_text(encoding="utf-8")
    shots = re.findall(r"^\| (\d+):(\d+) to (\d+):(\d+) \((\d+) s\) \|", text, re.M)
    assert len(shots) == 8
    total, prev_end = 0, 0
    for m1, s1, m2, s2, dur in shots:
        start, end = int(m1) * 60 + int(s1), int(m2) * 60 + int(s2)
        assert start == prev_end and end - start == int(dur), (m1, s1)
        total += int(dur)
        prev_end = end
    assert total < 180 and total == prev_end
    for must in ("F-001", "D-001", "quantity", "6.0", "ghost challenge", "Kiro"):
        assert must in text
    assert "atx" in text and "Do not show an AWS console" in text


def test_the_video_script_does_not_overclaim():
    text = (ROOT / "docs/DEMO_VIDEO_SCRIPT.md").read_text(encoding="utf-8").lower()
    assert not re.search(r"\b(is|are|was|been|be) (correct|proven)\b|\bproves\b|\bguarantee", text)


def test_the_writeup_covers_the_eight_topics_and_the_disclosure_paragraph_and_marks_owner_gaps():
    text = (ROOT / "docs/DEVPOST_WRITEUP.md").read_text(encoding="utf-8")
    for h in ("The problem", "Who has it", "What Ghost does", "What is different from existing tools", "How Kiro was used",
              "Pre-existing code and outside tools"):
        assert f"## {h}" in text, h
    topics = re.findall(r"^\d\. \*\*([^*]+)\*\*", text, re.M)
    assert [t.split(" (")[0].rstrip(".") for t in topics] == [
        "Surfaces", "Custom agents", "Agent hooks", "Spec-driven development compared with vibe coding",
        "Steering documents", "MCP", "Property-based testing", "Kiro Powers"]
    assert len(re.findall(r"\[OWNER", text)) >= 8
    assert "Kiroween 2026, category: Resurrection" in text
    assert not re.search(r"\b(is|are|was|been|be) (correct|proven)\b|\bwe proved\b|\bproves\b", text.lower())
    assert "does not say unit tests would have missed them" in text  # the PBT claim is not overstated


def test_the_preflight_script_only_reads():
    text = (ROOT / "scripts/preflight_demo.sh").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for bad in ("-X ", "--data", " -d ", "-F ", "--form", "-T ", "--upload", "POST", "PUT", "DELETE", "rm ", "aws ", "atx "):
        assert bad not in code, bad
    assert "/healthz" in code and 'check "landing" "/"' in code
    assert (ROOT / "scripts/preflight_demo.sh").stat().st_mode & 0o111
    out = subprocess.run(["sh", "-n", str(ROOT / "scripts/preflight_demo.sh")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_the_preflight_script_fails_on_a_dead_host_without_writing_anything(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    r = subprocess.run(["sh", str(ROOT / "scripts/preflight_demo.sh"), "http://127.0.0.1:9"], capture_output=True, text=True,
                       cwd=tmp_path, timeout=120)
    assert r.returncode == 1 and "FAIL" in r.stdout and "Do not record" in r.stdout
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_the_stale_task_19_is_explained_in_the_main_spec():
    text = (ROOT / ".kiro/specs/ghost-in-the-macro/tasks.md").read_text(encoding="utf-8")
    assert re.search(r"^\s*- \[x\] 19\.1 ", text, re.M) and re.search(r"^\s*- \[x\] 19\.3 ", text, re.M)
    assert re.search(r"^\s*- \[ \] 19\.2 ", text, re.M) and "Not ticked, on purpose" in text


def test_the_eight_property_tasks_judge_kit_asked_for_are_ticked_or_explained():
    text = (ROOT / ".kiro/specs/ghost-in-the-macro/tasks.md").read_text(encoding="utf-8")
    for task in ("5.9", "8.3", "15.3", "16.3"):
        assert re.search(rf"^\s*- \[x\]\* {re.escape(task)} ", text, re.M), task
    for task in ("5.8", "6.7", "7.7"):
        assert re.search(rf"^\s*- \[ \]\* {re.escape(task)} ", text, re.M), task
    assert text.count("Partly done (judge-kit, 2026-11-26)") == 3


def test_the_front_door_property_5_status_is_no_longer_failed():
    import json
    d = json.loads((ROOT / ".kiro/specs/front-door/tasks.meta.json").read_text(encoding="utf-8"))
    entry = d["pbtResults"]["1.6 Write property test: killed/survived tombstone counts match the finished report"]
    assert entry["status"] == "passed" and "failingExample" not in entry
