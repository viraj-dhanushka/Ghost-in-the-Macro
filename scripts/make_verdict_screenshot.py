#!/usr/bin/env python3
"""Make docs/img/verdict-card.png from a real run (judge-kit, README first screen).

Drives the web app through the real flow with the bundled "haunted discount calculator" sample: autopsy, the
Decision D-001 ("bulk means 50 or more"), a verification in Intended mode against the LibreOffice Referee, then cuts
the verdict card out of the finished job panel and photographs it with headless Chrome. Nothing on the card is
typed in: it is what the app rendered from the real proof report. Needs LibreOffice and Google Chrome (path in
$GHOST_CHROME, or the macOS default). Not run by the test suite. Macros are never run (the sample has none).

Usage:  scripts/ghost-py scripts/make_verdict_screenshot.py [--theme light|dark]
"""
from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHROME_DEFAULT = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def run_flow(tmp: Path) -> str:
    from fastapi.testclient import TestClient
    from web.app import create_app

    app = create_app(session_root=tmp / "sessions")
    c = TestClient(app)
    assert c.post("/sample/haunted").status_code == 200
    page = c.get("/autopsy").text
    options = [htmlmod.unescape(x) for x in page.split('value="') if x.startswith("set|")]
    choice = next(o.split('"')[0] for o in options if "B9" in o and o.split('"')[0].endswith("|>="))
    r = c.post("/decision", data={"finding_id": "F-001", "choice": choice, "author": "Demo",
                                  "reason": "Bulk means 50 or more"})
    assert r.status_code == 200 and "D-001" in r.text
    r = c.post("/verify", data={"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"], "outputs": ["Calculator!B11"]})
    job_id = r.text.split("/run/")[1].split("/")[0]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        panel = c.get(f"/run/{job_id}/panel").text
        if "verdict-card" in panel and 'hx-trigger="every 1s"' not in panel:
            return panel
        time.sleep(1)
    raise SystemExit("the verification did not finish")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    args = ap.parse_args(argv)
    chrome = os.environ.get("GHOST_CHROME", CHROME_DEFAULT)
    if not Path(chrome).exists():
        print(f"Chrome not found at {chrome}; set GHOST_CHROME", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="ghost-shot-") as t:
        tmp = Path(t)
        panel = run_flow(tmp)
        m = re.search(r'<section class="verdict-card".*?</section>', panel, re.S)
        if not m:
            print("no verdict card in the panel", file=sys.stderr)
            return 1
        css = (ROOT / "web" / "static" / "style.css").read_text(encoding="utf-8")
        page = (f'<!doctype html><html lang="en" data-theme="{args.theme}"><head><meta charset="utf-8">'
                f"<style>{css}\nbody{{margin:0;padding:1rem;max-width:44rem}}</style></head><body>{m.group(0)}</body></html>")
        src = tmp / "card.html"
        src.write_text(page, encoding="utf-8")
        out = ROOT / "docs" / "img" / "verdict-card.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--window-size=720,580", f"--screenshot={out}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
