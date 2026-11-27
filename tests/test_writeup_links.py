"""Every relative markdown link in docs/*.md resolves from docs/ (last fix round, item 7)."""
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def test_relative_links_in_the_write_up_resolve_from_docs():
    text = (DOCS / "DEVPOST_WRITEUP.md").read_text(encoding="utf-8")
    links = [m.group(1) for m in re.finditer(r"\]\(([^)\s]+)\)", text)]
    local = [l.split("#")[0] for l in links if not re.match(r"[a-z]+:", l) and not l.startswith("#")]
    assert len(local) >= 7
    bad = [l for l in local if l and not (DOCS / l).exists()]
    assert not bad, bad
