"""The suggested AWS Transform command (large-workbook-lane, Requirement 4, Property 4). Nothing is run."""
from __future__ import annotations

import shlex
import subprocess

import pytest
from hypothesis import given, strategies as st

from ghost.models import Metrics
from ghost.router import explain_route, recommend_route, with_atx_command
from ghost.router.explain import atx_dry_run_command, is_git_repository


def test_the_command_uses_the_managed_definition_a_config_file_and_full_automation():
    parts = shlex.split(atx_dry_run_command("/w/book.xlsx"))
    assert parts[:4] == ["atx", "custom", "def", "exec"]
    assert parts[parts.index("-n") + 1] == "AWS/vba-to-python-migration"
    assert parts[parts.index("-g") + 1] == "atx-config.yaml"
    assert parts[parts.index("-p") + 1] == "/w"
    assert parts[-2:] == ["-x", "-t"]
    assert "compileall" in parts[parts.index("-c") + 1]


def test_the_definition_name_comes_from_configuration():
    parts = shlex.split(atx_dry_run_command(None, definition="Team/my vba"))
    assert parts[parts.index("-n") + 1] == "Team/my vba"


def test_the_placeholder_directory_is_quoted_and_carries_no_path():
    assert "'<workbook-directory>'" in atx_dry_run_command(None)


@given(st.text(min_size=1, max_size=40).filter(lambda s: s.strip()))
def test_property_4_every_printed_command_has_g_and_the_not_run_label(name):
    """Property 4: the printed command always carries -g and never appears without the label."""
    cmd = atx_dry_run_command("/w/a.xlsx", definition=name.strip())
    assert " -g " in cmd
    route = with_atx_command(recommend_route(Metrics(userform_count=9)), "/w/a.xlsx")
    text = explain_route(route)
    assert route.atx_command in text and "suggested command, not run" in text.lower()


def test_the_explanation_names_the_facts_and_never_claims_formulas():
    route = with_atx_command(recommend_route(Metrics(userform_count=9, formula_count=4)), "/w/a.xlsx")
    text = explain_route(route)
    low = text.lower()
    assert "suggested command, not run" in low
    assert "exits 0 even when" in low and "3.22.1" in text
    assert "node.js 22" in low
    assert "-t" in text and "approves all tool calls" in low
    assert "atx custom def list" in text and "never executed" in text
    assert "AWS/vba-to-python-migration" in text and "early access" in low
    assert "says nothing about worksheet formulas" in low and "ghost does not send formulas" in low
    assert "does not convert the worksheet formulas" not in low  # the documentation is silent; do not assert more
    assert "kit folder" in low and "ghost handoff" in low
    assert "unverified" in low or "not verified" in low  # the official power's existence
    for bad in ("aws transform converts formulas", "handles workbook size", "excel-vba-to-python"):
        assert bad not in low


def test_git_repository_check_reads_the_folder_only(tmp_path):
    assert is_git_repository(tmp_path) is False
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert is_git_repository(tmp_path) is True
    assert is_git_repository(tmp_path / "sub") is True  # inside a repository (a folder that does not exist yet)


def test_the_explanation_says_when_the_target_is_not_a_git_repository(tmp_path):
    route = with_atx_command(recommend_route(Metrics(userform_count=9)), str(tmp_path / "a.xlsx"))
    assert "not a git repository" in explain_route(route, target_dir=str(tmp_path)).lower()
