"""R-14: a Decision patch is validated when it is recorded (CLI and MCP).

**Validates: Requirements 2.14, 3.3**
"""

from __future__ import annotations

import pytest

from ghost.cli import main
from ghost.decisions import load_decisions
from mcp_server.server import call_tool_sync
from samples import make_haunted

GOOD_PATCH = {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="}
BAD_PATCH = {"op": "set_operator", "cell": "Calculator!B2", "from": ">", "to": ">="}  # no comparison there


@pytest.fixture()
def migration(tmp_path):
    wb = make_haunted.build(tmp_path / "haunted.xlsx")
    mdir = tmp_path / "mig"
    assert main(["convert", str(wb), "--migration", str(mdir)]) == 0
    return mdir


def _decide(mdir, patch_json, finding="F-001"):
    return main(["decide", str(mdir), "--finding", finding, "--behaviour", "bulk is 50 or more",
                 "--reason", "policy", "--author", "ana", "--date", "2026-11-24", "--patch", patch_json])


def test_cli_rejects_patch_that_matches_no_comparison(migration, capsys):
    import json
    assert _decide(migration, json.dumps(BAD_PATCH)) != 0
    err = capsys.readouterr().err
    assert "patch cannot be applied" in err and "matched no comparison" in err
    assert not (migration / "decisions.yaml").exists()


def test_cli_accepts_good_patch_then_rejects_duplicate(migration, capsys):
    import json
    assert _decide(migration, json.dumps(GOOD_PATCH)) == 0
    assert _decide(migration, json.dumps(GOOD_PATCH)) != 0
    assert "D-001" in capsys.readouterr().err
    assert [d.decision_id for d in load_decisions(migration)] == ["D-001"]


def _mcp_args(mdir, patch):
    return {"migration_dir": str(mdir), "finding_id": "F-001", "behaviour": "bulk is 50 or more",
            "reason": "policy", "author": "ana", "date": "2026-11-24", "patch": patch}


def test_mcp_rejects_patch_that_matches_no_comparison(migration):
    payload, is_error = call_tool_sync("record_decision", _mcp_args(migration, BAD_PATCH))
    assert is_error and payload["error"]["type"] == "invalid_argument"
    assert "matched no comparison" in payload["error"]["message"]
    assert not (migration / "decisions.yaml").exists()


def test_mcp_accepts_good_patch_then_rejects_duplicate(migration):
    payload, is_error = call_tool_sync("record_decision", _mcp_args(migration, GOOD_PATCH))
    assert not is_error and payload["decision"]["decision_id"] == "D-001"
    payload, is_error = call_tool_sync("record_decision", _mcp_args(migration, GOOD_PATCH))
    assert is_error and "D-001" in payload["error"]["message"]
