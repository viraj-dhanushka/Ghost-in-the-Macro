"""The judge-kit documents and scripts (judge-kit items 5 to 8): checkable properties only, no network, no LibreOffice."""
from __future__ import annotations

import re
import sys
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
    for must in ("F-001", "D-001", "quantity", "6.0", ".venv/bin/python -m ghost.cli challenge", "Kiro"):
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
    n_owner = len(re.findall(r"\[OWNER", text))
    # a full draft (at least eight placeholders) or a finished text with none
    assert n_owner >= 8 if "Draft for the Owner" in text else n_owner == 0
    assert "Kiroween 2026, category: Resurrection" in text
    assert not re.search(r"\b(is|are|was|been|be) (correct|proven)\b|\bwe proved\b|\bproves\b", text.lower())
    assert "does not say unit tests would have missed them" in text  # the PBT claim is not overstated


def test_the_preflight_script_only_reads():
    text = (ROOT / "scripts/preflight_demo.sh").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    for bad in ("-X ", "--data", " -d ", "-F ", "--form", "-T ", "--upload", "rm ", "aws ", "atx "):
        assert bad not in code, bad
    assert not re.search(r"\b(POST|PUT|DELETE)\b", code)  # whole words: DEVPOST_WRITEUP.md is a file name
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


# -- the screenshot (correction 10) ---------------------------------------------------------------
def _png_size(path: Path) -> tuple[int, int]:
    import struct
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_the_screenshot_script_sizes_the_window_to_the_card_and_never_crops_from_the_centre():
    text = (ROOT / "scripts/make_verdict_screenshot.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "sips" not in code and "cropOffset" not in code and "-c" not in re.findall(r'"(-c)"', code)
    m = re.search(r'--window-size=(\d+),(\d+)', code)
    assert m and "--force-device-scale-factor=2" in code
    w, h = _png_size(ROOT / "docs/img/verdict-card.png")
    assert (w, h) == (2 * int(m.group(1)), 2 * int(m.group(2)))
    assert w > h * 1.1  # a landscape card, not a square window with the card cut out of its middle


def test_the_screenshot_card_starts_at_the_top_left_with_its_border_and_its_title():
    """Decode the PNG with the standard library only: the first rows hold the page margin, then the card's green
    border; the left edge column of the border is present; the title text ("Passed") is dark pixels in the top rows."""
    import struct
    import zlib
    data = (ROOT / "docs/img/verdict-card.png").read_bytes()
    pos, idat, w, h, depth, ctype = 8, b"", 0, 0, 0, 0
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    assert depth == 8 and ctype in (2, 6)
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(line)
        prev = line

    def px(x, y):
        return tuple(rows[y][x * bpp:x * bpp + 3])

    def is_green(c):
        return c[1] > c[0] + 25 and c[1] > c[2] + 25

    # the card's green border: a green pixel in the first 140 columns of some row in the top 300, and a green pixel
    # in the top 140 rows of some column; the page margin above and left of it is the plain page colour
    left_green = [x for x in range(0, 140) if any(is_green(px(x, y)) for y in range(200, 300))]
    top_green = [y for y in range(0, 140) if any(is_green(px(x, y)) for x in range(200, 400))]
    assert left_green and min(left_green) >= 4, "the card's left edge is cut off"
    assert top_green and min(top_green) >= 4, "the card's top edge is cut off"
    dark = [(x, y) for y in range(100, 360) for x in range(220, 1300) if sum(px(x, y)) < 330]
    assert len(dark) > 2000, "the title text is not in the top rows"


# -- preflight_demo.sh: /kiro, the header, and the submit check (corrections 12 and 17) ------------------
import http.server  # noqa: E402
import threading  # noqa: E402

PREFLIGHT = ROOT / "scripts/preflight_demo.sh"


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802
        body = self.routes.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


def _serve(routes):
    handler = type("H", (_Handler,), {"routes": routes})
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _run_preflight(*args, cwd=None, env_extra=None):
    import os
    env = dict(os.environ, **(env_extra or {}))
    return subprocess.run(["sh", str(PREFLIGHT), *args], capture_output=True, text=True, timeout=120, cwd=cwd, env=env)


def test_preflight_checks_kiro_so_an_old_deploy_fails():
    ok = {"/healthz": '{"status":"ok"}', "/": "<h1>Ghost in the Macro</h1>", "/kiro": "<title>Built with Kiro</title>"}
    srv, url = _serve(ok)
    try:
        r = _run_preflight(url)
        assert r.returncode == 0 and "GET /kiro -> 200" in r.stdout, r.stdout
    finally:
        srv.shutdown()
    old = {k: v for k, v in ok.items() if k != "/kiro"}  # an older build: /kiro answers 404
    srv, url = _serve(old)
    try:
        r = _run_preflight(url)
        assert r.returncode == 1 and "FAIL  GET /kiro -> 404" in r.stdout and "Do not record" in r.stdout, r.stdout
    finally:
        srv.shutdown()


def test_preflight_header_says_that_get_slash_starts_an_empty_session_and_nothing_else_is_written():
    head = "\n".join(PREFLIGHT.read_text(encoding="utf-8").splitlines()[:12])
    assert "GET / starts an empty session" in head
    assert "no upload, no POST, no session" not in head  # the old header claimed there was no session


def _submit_root(tmp_path, readme="# Ghost\nclean\n", writeup="# Write-up\nclean\n", story="# Story\nclean\n",
                 video="# Video\nclean\n"):
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    (tmp_path / "docs/DEVPOST_WRITEUP.md").write_text(writeup, encoding="utf-8")
    (tmp_path / "docs/KIRO_STORY.md").write_text(story, encoding="utf-8")
    (tmp_path / "docs/DEMO_VIDEO_SCRIPT.md").write_text(video, encoding="utf-8")
    return {"GHOST_SUBMIT_ROOT": str(tmp_path)}


def test_the_submit_check_passes_clean_files_and_needs_no_network(tmp_path):
    r = _run_preflight("--submit", env_extra=_submit_root(tmp_path))
    assert r.returncode == 0 and "submit check passed" in r.stdout.lower()


def test_the_submit_check_fails_on_an_owner_placeholder_or_a_draft_marker(tmp_path):
    for kwargs, where in (({"readme": "x [OWNER: fill me in] y"}, "README.md"),
                          ({"writeup": "# Write-up (draft)\n"}, "DEVPOST_WRITEUP.md"),
                          ({"story": "[OWNER: how it felt]"}, "KIRO_STORY.md"),
                          ({"writeup": "Draft for the Owner to edit.\n"}, "DEVPOST_WRITEUP.md"),
                          ({"video": "x for the Owner to complete"}, "DEMO_VIDEO_SCRIPT.md"),
                          ({"video": "[OWNER: shots]"}, "DEMO_VIDEO_SCRIPT.md")):
        r = _run_preflight("--submit", env_extra=_submit_root(tmp_path, **kwargs))
        assert r.returncode == 1, kwargs
        assert "FAIL" in r.stdout and where in r.stdout


def test_the_submit_check_reports_a_missing_file_as_a_failure(tmp_path):
    env = _submit_root(tmp_path)
    (tmp_path / "docs/KIRO_STORY.md").unlink()
    r = _run_preflight("--submit", env_extra=env)
    assert r.returncode == 1 and "missing" in r.stdout.lower()


def test_the_submit_check_never_touches_the_network_or_writes(tmp_path):
    before = sorted(p.name for p in tmp_path.rglob("*"))
    _run_preflight("--submit", env_extra=_submit_root(tmp_path))
    names = sorted(p.name for p in tmp_path.rglob("*"))
    assert names == sorted(set(before) | {"README.md", "DEVPOST_WRITEUP.md", "KIRO_STORY.md", "DEMO_VIDEO_SCRIPT.md", "docs"})
    text = PREFLIGHT.read_text(encoding="utf-8")
    sub = text[text.index("submit_check()"):text.index("submit_check()") + 900]
    assert "curl" not in sub


# -- README, write-up and video script corrections (items 13 to 16) -----------------------------------
def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_there_is_no_ghost_executable_so_no_runnable_example_starts_with_ghost():
    for rel in ("README.md", "docs/DEMO_VIDEO_SCRIPT.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(\$ )?ghost (route|handoff|challenge|receipt|autopsy|rules|convert|verify|report|decide|mutate|demo)\b",
                             text, re.M), rel
        assert not re.search(r"`ghost (route|handoff|challenge|receipt|verify)[^`]*`.*\bRun\b", text), rel
    assert "there is no `ghost` executable" in _readme().lower()
    assert ".venv/bin/python -m ghost.cli route" in _readme() and ".venv/bin/python -m ghost.cli receipt" in _readme()
    assert ".venv/bin/python -m ghost.cli challenge" in (ROOT / "docs/DEMO_VIDEO_SCRIPT.md").read_text(encoding="utf-8")


def test_the_readme_lists_all_twelve_subcommands():
    sys.path.insert(0, str(ROOT))
    from ghost.cli import build_parser
    names = sorted(next(a for a in build_parser()._actions if getattr(a, "choices", None)).choices)
    assert len(names) == 12
    for name in names:
        assert re.search(rf"^\| `{name}` \|", _readme(), re.M), name


def test_the_readme_says_the_hosted_copy_is_an_earlier_build():
    first = "\n".join(_readme().splitlines()[:14])
    assert "The hosted copy is an earlier build; the screenshot is from a local run of this commit" in first


def test_the_readme_describes_the_sample_routes_correctly():
    text = " ".join(_readme().split())
    assert "`POST /sample/{id}` starts a sample" in text and "`GET /sample/{id}/workbook` downloads it" in text
    assert "are served from `/sample/{id}`" not in text


def test_the_readme_hook_count_is_one_number_everywhere():
    text = " ".join(_readme().split())
    assert "six hooks" in text.lower()
    assert "The four hooks in" not in text
    assert "four of the five file hooks were seen to fire" in text.lower()
    assert "blocked the agent's own shell commands twice" in text
    assert "a real `atx` or `aws` block was not tried" in text
    hooks = list((ROOT / ".kiro/hooks").glob("*.json"))
    assert len(hooks) == 6


def test_the_readme_does_not_claim_correct_or_proven():
    assert not re.search(r"\b(correct|correctly|proven|proved|proves)\b", _readme(), re.I)


def test_the_writeup_numbers_and_wording_are_the_ones_the_repository_backs():
    text = (ROOT / "docs/DEVPOST_WRITEUP.md").read_text(encoding="utf-8")
    m = re.search(r"\((\d+) passed, (\d+) skipped on 2026-\d\d-\d\d", text)
    assert m and int(m.group(1)) >= 2035  # the form and a floor; the day and the skipped count are not pinned
    assert "Hypothesis with a fixed seed" not in text
    sys.path.insert(0, str(ROOT / "scripts"))
    import kiro_ledger
    pt = kiro_ledger.property_test_files()
    seeded = sum(1 for p in pt if p["seeded"])
    assert (f"The verifier uses a fixed seed (20261204); the test suite uses Hypothesis, and {seeded} of its {len(pt)} "
            "property files are seeded.") in " ".join(text.split())
    assert "blocked a shell command once" not in text and "twice" in text
    assert "Honest wording is enforced, not hoped for: the verdict card, the README and the kit" in text  # a README test exists above


def test_the_video_script_has_the_agreed_shape():
    text = (ROOT / "docs/DEMO_VIDEO_SCRIPT.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+):(\d+) to (\d+):(\d+) \((\d+) s\) \| ([^|]*) \|", text, re.M)
    assert len(rows) == 8
    durations = [int(r[4]) for r in rows]
    assert durations[0] == 15 and durations[2] <= 10 and durations[3] <= 22 and durations[6] == 40
    assert sum(durations) < 180
    first = rows[0][5]
    assert "B7" in first and "B9" in first and "overlay" in first.lower() and "title" in first.lower()
    for i in (1, 2, 3, 4):
        assert "local, or live after redeploy" in rows[i][5], i
    kiro = rows[6][5].lower()
    for needle in ("requirements.md", "correctness property", "ticked task", "guard hook", "harmless command", "mcp panel"):
        assert needle in kiro, needle
    assert "graveyard/haunted.xlsx" in text
