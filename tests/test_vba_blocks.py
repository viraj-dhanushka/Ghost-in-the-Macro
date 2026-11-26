"""Pure helpers for the VBA_Panel and the Route_Panel (vba-on-screen, Requirements 2.5 and 4).

Written before the helpers exist. `vba_blocks` cuts and describes what the engine extracted; it never
rewrites the source, and the template (autoescape on) is what escapes it.
"""
from __future__ import annotations

import pytest

from ghost.models import Metrics, Route
from ghost.router import DEFAULT_THRESHOLDS, ThresholdError, load_thresholds

from web.autopsy_view import (MAX_VBA_CHARS_PER_MODULE, MAX_VBA_CHARS_TOTAL, MAX_VBA_LINES_PER_MODULE,
                              MAX_VBA_LINES_TOTAL, MAX_VBA_MODULES, route_view, vba_blocks, vba_notice)
from web import flow


def module(name, lines):
    src = "\n".join(f"line {i + 1}" for i in range(lines))
    return {"name": name, "source": src, "line_count": lines}


def test_limits_are_the_documented_ones():
    assert (MAX_VBA_LINES_PER_MODULE, MAX_VBA_LINES_TOTAL) == (400, 2000)


def test_a_small_module_is_shown_whole_with_no_note():
    b = vba_blocks([module("Module1.bas", 23)])
    assert len(b) == 1 and b[0]["name"] == "Module1.bas" and b[0]["line_count"] == 23
    assert b[0]["text"].count("\n") == 22 and b[0]["note"] is None


def test_the_source_is_never_rewritten_or_escaped_by_the_helper():
    src = "' <script>alert(1)</script>\nSub A()\nEnd Sub"
    b = vba_blocks([{"name": "M", "source": src, "line_count": 3}])
    assert b[0]["text"] == src


def test_a_long_module_is_cut_at_400_lines_and_says_so():
    b = vba_blocks([module("Big.bas", 450)])[0]
    assert b["text"].splitlines()[-1] == "line 400" and len(b["text"].splitlines()) == 400
    assert b["note"] == "Showing the first 400 of 450 lines."


def test_a_module_of_exactly_400_lines_is_not_cut():
    b = vba_blocks([module("Edge.bas", 400)])[0]
    assert len(b["text"].splitlines()) == 400 and b["note"] is None


def test_the_total_cap_cuts_a_later_module_and_hides_none_silently():
    blocks = vba_blocks([module(f"M{i}.bas", 300) for i in range(8)])
    assert [len(b["text"].splitlines()) for b in blocks] == [300] * 6 + [200, 0]
    assert blocks[6]["note"] == "Showing the first 200 of 300 lines."
    assert blocks[7]["text"] == ""
    assert blocks[7]["note"] == "Not shown: the display limit of 2000 lines was reached. The module has 300 lines."
    assert [b["name"] for b in blocks] == [f"M{i}.bas" for i in range(8)]  # every module still listed


def test_an_empty_module_says_so():
    b = vba_blocks([{"name": "Empty.bas", "source": "", "line_count": 0}])[0]
    assert b["text"] == "" and b["note"] == "The module is empty."


def test_no_modules_no_blocks():
    assert vba_blocks([]) == []


def metrics(**kw):
    base = dict(formula_count=7, vba_line_count=23, module_count=1, userform_count=0, declare_count=0,
                external_link_count=0)
    base.update(kw)
    return Metrics(**base)


def test_route_view_for_ghost_converts_has_no_command():
    from ghost.router import recommend_route
    v = route_view(recommend_route(metrics()))
    assert v["route"] == "Ghost converts" and v["command"] is None
    assert any("23 VBA lines are within the threshold of 2000" in r for r in v["reasons"])


@pytest.mark.parametrize("m, name", [
    (metrics(vba_line_count=2500), "Split"),
    (metrics(vba_line_count=2500, formula_count=0), "AWS Transform custom"),
    (metrics(userform_count=4), "AWS Transform custom"),
])
def test_route_for_gives_the_three_routes_and_a_command_without_a_server_path(m, name):
    v = route_view(flow._route_for(m))
    assert v["route"] == name and v["reasons"]
    from ghost.router import atx_dry_run_command
    assert v["command"] == atx_dry_run_command(None)  # the fixed placeholder: no server path can be in it
    assert "<kit-folder>" in v["command"]


def test_route_for_falls_back_to_the_built_in_thresholds_when_the_steering_file_is_missing(monkeypatch):
    def boom(*a, **k):
        raise ThresholdError("cannot read routing-thresholds.md")
    monkeypatch.setattr(flow, "load_thresholds", boom)
    assert route_view(flow._route_for(metrics()))["route"] == "Ghost converts"
    assert route_view(flow._route_for(metrics(vba_line_count=2500)))["route"] == "Split"


def test_the_built_in_thresholds_equal_the_steering_file():
    # The Docker image has no .kiro folder, so the web app falls back to DEFAULT_THRESHOLDS.
    # If the file is edited, this test says the fallback needs the same edit.
    assert DEFAULT_THRESHOLDS == load_thresholds()


def test_the_character_and_module_limits_are_the_documented_ones():
    assert (MAX_VBA_CHARS_PER_MODULE, MAX_VBA_CHARS_TOTAL, MAX_VBA_MODULES) == (60000, 200000, 50)


def test_a_module_of_very_long_lines_is_cut_at_a_whole_line_and_the_notice_gives_the_lines_shown():
    src = "\n".join("x" * 5000 for _ in range(30))
    b = vba_blocks([{"name": "Wide.bas", "source": src, "line_count": 30}])[0]
    assert b["text"].count("\n") + 1 == 11 and len(b["text"]) == 11 * 5000 + 10 and len(b["text"]) <= 60000
    assert b["note"] == "Showing the first 11 of 30 lines, cut at 60000 characters."


def test_the_line_limit_and_the_character_limit_give_one_notice_with_the_lines_actually_shown():
    src = "\n".join("y" * 1000 for _ in range(450))
    b = vba_blocks([{"name": "Both.bas", "source": src, "line_count": 450}])[0]
    shown = b["text"].count("\n") + 1
    assert shown == 59 and len(b["text"]) == 59 * 1000 + 58  # 59 whole lines fit in 60000 characters (60 would be 60,059)
    assert b["note"] == "Showing the first 59 of 450 lines, cut at 60000 characters."


def test_a_first_line_longer_than_the_budget_is_cut_in_the_line_and_says_so():
    b = vba_blocks([{"name": "One.bas", "source": "z" * 70000 + "\nnext", "line_count": 2}])[0]
    assert len(b["text"]) == 60000 and "\n" not in b["text"]
    assert b["note"] == "Showing part of line 1 (its first 60000 characters) of 2 lines."


def test_the_total_character_budget_cuts_a_later_module_at_a_whole_line():
    big = "\n".join("b" * 250 for _ in range(400))  # 100,399 characters; 239 whole lines (59,988) fit in 60000
    blocks = vba_blocks([{"name": f"B{i}.bas", "source": big, "line_count": 400} for i in range(5)])
    assert [b["text"].count("\n") + 1 for b in blocks[:3]] == [239, 239, 239]
    assert sum(len(b["text"]) for b in blocks[:3]) == 3 * 59988
    # 200000 - 179964 = 20036 characters are left: 79 whole lines (19,828) fit
    assert blocks[3]["text"].count("\n") + 1 == 79 and len(blocks[3]["text"]) == 19828
    assert blocks[3]["note"] == "Showing the first 79 of 400 lines, cut at 20036 characters."


def test_a_module_that_gets_no_characters_says_the_character_limit_was_reached():
    big = "\n".join("b" * 250 for _ in range(400))  # 400 lines, 100,399 characters; cut to 60000 per module
    mods = [{"name": f"B{i}.bas", "source": big, "line_count": 400} for i in range(5)]
    blocks = vba_blocks(mods)
    assert sum(len(b["text"]) for b in blocks) <= MAX_VBA_CHARS_TOTAL
    last = blocks[-1]
    assert last["text"] == ""
    assert last["note"] == "Not shown: the display limit of 200000 characters was reached. The module has 400 lines."


def test_at_most_fifty_modules_are_listed_and_the_rest_are_counted():
    mods = [{"name": f"M{i:02d}.bas", "source": "x", "line_count": 1} for i in range(60)]
    blocks = vba_blocks(mods)
    assert len(blocks) == 50 and blocks[0]["name"] == "M00.bas" and blocks[-1]["name"] == "M49.bas"
    assert vba_notice(mods) == "10 more modules not shown."
    assert vba_notice(mods[:51]) == "1 more module not shown."
    assert vba_notice(mods[:50]) is None and vba_notice([]) is None


def test_route_view_adds_the_vba_note_only_when_ghost_converts_a_workbook_with_vba():
    from ghost.router import recommend_route
    assert route_view(recommend_route(metrics()))["vba_note"] == (
        "Ghost converts the formulas it supports. It does not translate the VBA: a cell that calls a VBA function "
        "is listed above as not converted. Such a cell is not verifiable by the Referee, so it cannot be chosen as an output.")
    assert route_view(recommend_route(metrics(vba_line_count=0, module_count=0)))["vba_note"] is None
    assert route_view(recommend_route(metrics(vba_line_count=2500)))["vba_note"] is None  # Split names the VBA path itself
