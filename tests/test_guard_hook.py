"""The PreToolUse guard hook: no `atx` or `aws` shell command without the Owner's approval in that session
(ground rule 6; large-workbook-lane Part E). Kiro documents the Pre Tool Use trigger ("can validate and block tool
usage"; a shell category matcher; exit code 2 blocks): https://kiro.dev/docs/hooks/types/ and
https://kiro.dev/docs/hooks/actions/. Whether Kiro really fires it and blocks in this IDE is NOT checked here."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "ghost_guard.py"
HOOK = ROOT / ".kiro" / "hooks" / "guard-atx-aws.json"


def run(payload, approvals: Path, *args: str, raw: str | None = None):
    env = dict(os.environ, GHOST_APPROVALS_DIR=str(approvals))
    return subprocess.run([sys.executable, str(GUARD), *args], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


def call(command: str, session="s1") -> dict:
    return {"hook_event_name": "PreToolUse", "session_id": session, "cwd": "/w", "tool_name": "execute_bash",
            "tool_input": {"command": command}}


BLOCKED = [
    "atx custom def exec -n AWS/vba-to-python-migration -p . -x -t",
    "aws sts get-caller-identity",
    "cd kit && aws s3 ls",
    "FOO=1 atx --version",
    "/usr/local/bin/atx update",
    "sudo aws iam list-users",
    "echo $(aws sts get-caller-identity)",
    "ls | aws s3 cp - s3://b/k",
    "true; atx custom def list",
    "env AWS_PROFILE=x aws s3 ls",
    "time atx custom def list",
    "nohup atx custom def exec -n x &",
    "bash -c 'aws sts get-caller-identity'",
    'sh -c "atx --version"',
    "xargs aws s3 rm",
    "`aws sts get-caller-identity`",
]
ALLOWED = [
    "ls -la",
    "git status",
    "python -m pytest -q",
    "echo atx and aws are words here",
    "grep -n aws README.md",
    "cat docs/AWS_TRANSFORM_FACTS.md",
    "scripts/ghost-py -m ghost.cli handoff wb.xlsx --out kit",
    "ghost route wb.xlsx",
    "awk '{print $1}' f",
    "pip install awscli-local",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_atx_and_aws_are_blocked_with_exit_2_and_a_reason(command, tmp_path):
    r = run(call(command), tmp_path)
    assert r.returncode == 2, (command, r.stderr)
    assert "approval" in r.stderr and "s1" in r.stderr
    assert r.stdout == ""


@pytest.mark.parametrize("command", ALLOWED)
def test_other_commands_are_allowed(command, tmp_path):
    assert run(call(command), tmp_path).returncode == 0, command


def test_an_approval_covers_that_session_only(tmp_path):
    ok = run({}, tmp_path, "approve", "s1")
    assert ok.returncode == 0 and "s1" in ok.stdout
    assert run(call("aws sts get-caller-identity", "s1"), tmp_path).returncode == 0
    assert run(call("aws sts get-caller-identity", "s2"), tmp_path).returncode == 2
    assert run({}, tmp_path, "revoke", "s1").returncode == 0
    assert run(call("aws sts get-caller-identity", "s1"), tmp_path).returncode == 2


def test_the_agent_cannot_approve_itself_through_the_shell(tmp_path):
    for cmd in ("scripts/ghost-py scripts/ghost_guard.py approve s1", "python scripts/ghost_guard.py approve s1",
                "mkdir -p ~/.ghost/approvals && touch ~/.ghost/approvals/s1"):
        r = run(call(cmd), tmp_path)
        assert r.returncode == 2, cmd
        assert "owner" in r.stderr.lower()
    assert not (tmp_path / "s1").exists()


def test_a_payload_that_cannot_be_read_blocks_only_if_it_mentions_atx_or_aws(tmp_path):
    assert run(None, tmp_path, raw="not json at all").returncode == 0
    assert run(None, tmp_path, raw="not json; aws s3 ls").returncode == 2
    assert run(None, tmp_path, raw="").returncode == 0


def test_a_payload_with_no_session_id_cannot_be_approved(tmp_path):
    p = call("aws s3 ls")
    del p["session_id"]
    assert run(p, tmp_path).returncode == 2
    assert run({}, tmp_path, "approve", "").returncode != 0  # an empty session id is refused


def test_approve_refuses_odd_session_ids(tmp_path):
    for bad in ("../x", "a/b", "a b", "a;b"):
        assert run({}, tmp_path, "approve", bad).returncode != 0
    assert list(tmp_path.iterdir()) == []


def test_the_hook_file_uses_the_documented_trigger_and_blocks_by_exit_code_2():
    data = json.loads(HOOK.read_text(encoding="utf-8"))
    assert data["version"] == "v1"
    (hook,) = data["hooks"]
    assert hook["trigger"] == "PreToolUse" and hook["matcher"] == "shell"
    assert hook["action"]["type"] == "command" and "ghost_guard.py" in hook["action"]["command"]
    assert isinstance(hook["action"]["timeout"], int) and 0 < hook["action"]["timeout"] <= 60


def test_the_guard_runs_nothing_it_is_given():
    text = GUARD.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("#", '"""')))
    for bad in ("import subprocess", "os.system", "eval(", "exec(", "shell=True", "Popen"):
        assert bad not in code
