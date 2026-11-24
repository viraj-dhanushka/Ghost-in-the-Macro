"""Dry-run command and design.md explanation. Requirements: 16.6, 16.8."""
from ghost.models import Metrics
from ghost.router import (
    explain_route,
    recommend_route,
    with_atx_command,
    write_route_explanation,
)


def test_atx_command_only_for_aws_and_split():
    ghost = with_atx_command(recommend_route(Metrics(formula_count=3)), "/w/a.xlsx")
    assert ghost.atx_command is None
    aws = with_atx_command(recommend_route(Metrics(userform_count=9)), "/w/a.xlsx")
    assert aws.atx_command.startswith("atx custom def exec ")
    split = with_atx_command(recommend_route(Metrics(formula_count=5, vba_line_count=3000)))
    assert split.route == "Split" and split.atx_command


def test_explanation_is_deterministic_and_replaced_in_place(tmp_path):
    route = with_atx_command(recommend_route(Metrics(userform_count=9)), "/w/a.xlsx")
    assert explain_route(route) == explain_route(route)
    (tmp_path / "design.md").write_text("# Design\n\nIntro\n")
    write_route_explanation(tmp_path, route)
    write_route_explanation(tmp_path, route)
    text = (tmp_path / "design.md").read_text()
    assert text.startswith("# Design\n\nIntro") and text.count("ghost:route:begin") == 1
    assert "never executed" in text and route.atx_command in text


def test_atx_command_uses_trust_flag_portable_build_and_names_prerequisite():
    route = with_atx_command(recommend_route(Metrics(userform_count=9)), "/w/a.xlsx")
    assert " -x -t" in route.atx_command
    assert "compileall" in route.atx_command and "**" not in route.atx_command
    text = explain_route(route)
    assert "atx custom def list" in text and "exact" not in text.lower()
