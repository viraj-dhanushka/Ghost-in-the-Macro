"""GET /kiro, the "Built with Kiro" page (judge-kit, item 4). Rendered from web/kiro_facts.json only: the container
has no .kiro/ or docs/, so the page cannot count at runtime. No LibreOffice."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
FACTS = ROOT / "web" / "kiro_facts.json"


def _client(tmp_path):
    return TestClient(create_app(session_root=tmp_path / "s"))


def test_the_page_renders_every_fact_with_its_source_path(tmp_path):
    r = _client(tmp_path).get("/kiro")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    html = r.text
    assert "<title>Built with Kiro" in html and 'lang="en"' in html
    for item in facts["items"]:
        assert item["label"] in html
        assert f'<span class="fact-count">{item["count"]}</span>' in html
        assert item["source"] in html
    assert "Counted from the working tree when the file was written" in html


def test_the_page_does_not_start_a_session_and_needs_no_libreoffice(tmp_path):
    c = _client(tmp_path)
    r = c.get("/kiro")
    assert "set-cookie" not in r.headers and not c.cookies


def test_the_landing_page_links_to_it(tmp_path):
    html = _client(tmp_path).get("/").text
    assert re.search(r'<a href="/kiro"[^>]*>[^<]*Built with Kiro', html)


def test_the_page_reads_only_the_json_file_not_the_repo(tmp_path, monkeypatch):
    """From another working directory, with .kiro and docs unreachable, the page is the same."""
    before = _client(tmp_path).get("/kiro").text
    monkeypatch.chdir(tmp_path)
    after = _client(tmp_path / "again").get("/kiro").text
    assert before == after
    src = (ROOT / "web" / "app.py").read_text(encoding="utf-8")
    assert '".kiro"' not in src and "'.kiro'" not in src and '"docs"' not in src.split("def create_app")[0]


def test_a_missing_facts_file_says_so_instead_of_inventing_numbers(tmp_path, monkeypatch):
    import web.app as webapp
    monkeypatch.setattr(webapp, "KIRO_FACTS_PATH", tmp_path / "nope.json")
    r = _client(tmp_path).get("/kiro")
    assert r.status_code == 200 and "not available" in r.text.lower()
    assert 'class="fact-count"' not in r.text


def test_the_page_makes_no_claim_it_cannot_back(tmp_path):
    text = _client(tmp_path).get("/kiro").text.lower()
    for bad in ("correct", "proven", "proved", "best", "award"):
        assert not re.search(rf"\b{bad}\b", text), bad
    assert "docs/kiro_story.md" in text and "[owner" not in text  # placeholders stay in the repo's story, not on the live page


def test_the_facts_file_is_small_and_in_the_image_folder():
    assert FACTS.is_file() and FACTS.stat().st_size < 20_000
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY web web" in dockerfile
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "web" not in [ln.strip() for ln in ignore]
