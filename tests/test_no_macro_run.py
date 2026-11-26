"""No code path in the web app or the macro sample builder can run a macro (vba-on-screen, Requirement 6).

Static checks read the syntax tree, so a positional argument, a variable or a dict entry cannot slip past a
text match; one behavioural check records what `build()` really passes to the Referee.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PY_FILES = sorted((ROOT / "web").rglob("*.py")) + [ROOT / "samples" / "make_xlsm.py"]
OTHER = sorted((ROOT / "web").rglob("*.html")) + sorted((ROOT / "web").rglob("*.js"))
DANGEROUS = {"run_macros", "trusted_source", "trust_macros"}


def _is_false(node):
    return isinstance(node, ast.Constant) and node.value is False


def test_the_python_sources_never_pass_a_macro_option_that_is_not_the_literal_false():
    assert len(PY_FILES) > 5
    seen_clients = 0
    for path in PY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name == "RefereeClient":
                    seen_clients += 1
                    assert len(node.args) <= 2, (path, "run_macros must not be passed positionally")
                for kw in node.keywords:
                    if kw.arg in DANGEROUS:
                        assert _is_false(kw.value), (path, kw.arg)
            if isinstance(node, ast.Dict):  # {"run_macros": True} and the like
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value in DANGEROUS:
                        assert _is_false(v), (path, k.value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.search(r"--?trust[-_]macros", node.value) or " " in node.value or len(node.value) > 80, (
                    path, node.value)  # a flag as a string literal; prose (docstrings) has spaces
    assert seen_clients >= 2  # the checks above looked at real Referee calls


def test_templates_and_scripts_have_no_macro_option():
    for path in OTHER:
        text = path.read_text(encoding="utf-8")
        assert "run_macros" not in text and "trust_macros" not in text and "trust-macros" not in text, path


def test_the_web_app_never_mentions_running_macros_in_any_python_file():
    for path in (ROOT / "web").rglob("*.py"):
        assert "run_macros" not in path.read_text(encoding="utf-8"), path


def test_build_asks_the_referee_for_macros_off(tmp_path, monkeypatch):
    import sys
    from ghost.referee import client as client_mod
    calls = []

    class Recorder:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def open(self, path, **kw):
            calls.append(("open", kw))

        def save_with_vba(self, out, modules):
            Path(out).write_bytes(b"x")

    monkeypatch.setattr(client_mod, "RefereeClient", Recorder)
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_xlsm
        make_xlsm.build(tmp_path / "x.xlsm")
        make_xlsm.build_pair(tmp_path / "pair")
    finally:
        sys.path.remove(str(ROOT / "samples"))
    clients = [c for c in calls if isinstance(c[0], tuple) and c[0] != "open"]
    assert len(clients) == 3  # one for build, two for build_pair
    for args, kwargs in clients:
        assert kwargs.get("run_macros") is False and not kwargs.get("trusted_source")
        assert len(args) <= 2
    assert all(not c[1].get("run_macros") for c in calls if c[0] == "open")
