"""The suggested AWS Transform command (large-workbook-lane, Requirement 4, Property 4). Nothing is run."""
from __future__ import annotations

import shlex

import pytest
from hypothesis import given, strategies as st

from ghost.models import Metrics
from ghost.router import explain_route, recommend_route, with_atx_command
from ghost.router.explain import atx_dry_run_command


def test_the_command_uses_the_managed_definition_a_config_file_and_full_automation():
    parts = shlex.split(atx_dry_run_command("/w/book.xlsx"))
    assert parts[:4] == ["atx", "custom", "def", "exec"]
    assert parts[parts.index("-n") + 1] == "AWS/vba-to-python-migration"
    assert parts[parts.index("-g") + 1] == "atx-config.yaml"
    assert parts[parts.index("-p") + 1] == "<kit-folder>"
    assert parts[-2:] == ["-x", "-t"]
    assert "compileall" in parts[parts.index("-c") + 1]


def test_the_definition_name_comes_from_configuration():
    parts = shlex.split(atx_dry_run_command(None, definition="Team/my vba"))
    assert parts[parts.index("-n") + 1] == "Team/my vba"


def test_the_placeholder_directory_is_quoted_and_carries_no_path():
    assert "'<kit-folder>'" in atx_dry_run_command(None)


# Feature: large-workbook-lane, Property 4: The printed command always carries -g and the not-run label
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
    assert "says nothing about worksheet formulas" in low and "ghost asks it to migrate the vba only" in low
    assert "rules.md" in low and "restated in english" in low
    assert "does not convert the worksheet formulas" not in low  # the documentation is silent; do not assert more
    assert "kit folder" in low and "ghost handoff" in low and "not the folder the workbook" in low
    assert "documented by aws; not installed or tested with ghost" in low  # the official power
    for bad in ("aws transform converts formulas", "handles workbook size", "excel-vba-to-python"):
        assert bad not in low


def test_the_command_always_names_the_kit_folder_whatever_workbook_path_is_given():
    for wb in (None, "/w/a.xlsx", "samples/x.xlsm"):
        assert "'<kit-folder>'" in atx_dry_run_command(wb)


def test_a_definition_other_than_the_default_is_not_called_aws_managed():
    route = with_atx_command(recommend_route(Metrics(userform_count=9)), None, "Team/my-vba")
    text = explain_route(route).lower()
    assert "the definition you named; ghost has not checked it exists" in text
    assert "aws-managed" not in text.replace("aws-managed definition in early access", "")
    default = explain_route(with_atx_command(recommend_route(Metrics(userform_count=9)))).lower()
    assert "aws-managed" in default and "ghost has not checked it exists" not in default


# -- no VBA, no command, at any batch size (large-workbook-lane correction 4) -----------------------
NO_VBA_REASON = "no VBA in this workbook: nothing to hand to AWS Transform custom"


@pytest.mark.parametrize("batch", [1, 5, 10, 11, 50])
def test_a_workbook_with_no_vba_gets_no_atx_command_at_any_batch_size(batch):
    route = with_atx_command(recommend_route(Metrics(formula_count=12), batch), "/w/a.xlsx")
    assert route.atx_command is None
    if route.route != "Ghost converts":  # the batch rule still names the AWS route; the reason says why there is no command
        assert NO_VBA_REASON in route.reasons
    assert "atx" not in explain_route(route).lower().replace("atx custom def list", "")


def test_the_reason_is_not_added_when_there_is_vba():
    route = with_atx_command(recommend_route(Metrics(formula_count=12, vba_line_count=30, module_count=1), 10), None)
    assert route.atx_command and NO_VBA_REASON not in route.reasons
    ui = with_atx_command(recommend_route(Metrics(userform_count=9)), None)
    assert ui.atx_command and NO_VBA_REASON not in ui.reasons


def test_the_reason_is_added_once_and_the_ghost_converts_reasons_are_unchanged():
    r = recommend_route(Metrics(formula_count=3), 1)
    assert r.route == "Ghost converts" and NO_VBA_REASON not in r.reasons
    b = recommend_route(Metrics(formula_count=3), 10)
    assert b.reasons.count(NO_VBA_REASON) == 1
