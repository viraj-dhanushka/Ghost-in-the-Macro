"""The PreToolUse guard hook: no `atx` or `aws` shell command without the Owner's approval in that session
(ground rule 6; large-workbook-lane Part E, corrected 2026-11-26). Kiro documents the Pre Tool Use trigger ("can
validate and block tool usage"; a shell category matcher; exit code 2 blocks): https://kiro.dev/docs/hooks/types/ and
https://kiro.dev/docs/hooks/actions/. Whether Kiro really fires it and blocks a real atx or aws command is NOT checked
here. The guard reads command text only; it stops accidents, not a determined agent (see its docstring)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "ghost_guard.py"
HOOKS = ROOT / ".kiro" / "hooks"
HOOK = HOOKS / "guard-atx-aws.json"

sys.path.insert(0, str(ROOT / "scripts"))
import ghost_guard  # noqa: E402


def run(payload, approvals: Path, *args: str, raw: str | None = None):
    env = dict(os.environ, GHOST_APPROVALS_DIR=str(approvals))
    return subprocess.run([sys.executable, str(GUARD), *args], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


def call(command: str, session="s1") -> dict:
    return {"hook_event_name": "PreToolUse", "session_id": session, "cwd": "/w", "tool_name": "execute_bash",
            "tool_input": {"command": command}}


# Commands that name atx or aws as a program (or hand one to a wrapper, a shell, eval or a substitution).
BLOCKED = [
    # the plain cases
    "atx custom def exec -n AWS/vba-to-python-migration -p . -x -t",
    "aws sts get-caller-identity",
    "cd kit && aws s3 ls",
    "FOO=1 atx --version",
    "FOO=1 BAR=2 aws s3 ls",
    "/usr/local/bin/atx update",
    "true; atx custom def list",
    "ls | aws s3 cp - s3://b/k",
    "nohup atx custom def exec -n x &",
    "echo hi\naws s3 ls",
    # wrappers and their options
    "sudo aws iam list-users",
    "sudo -u root aws s3 ls",
    "env AWS_PROFILE=x aws s3 ls",
    "env -u FOO aws s3 ls",
    "time atx custom def list",
    "timeout 30 aws s3 ls",
    "timeout -k 5 30 atx --version",
    "nice -n 5 atx --version",
    "xargs aws s3 rm",
    "xargs -n1 aws s3 rm",
    "command aws s3 ls",
    "exec aws s3 ls",
    # shells, eval and substitutions
    "bash -c 'aws sts get-caller-identity'",
    'sh -c "atx --version"',
    "bash -ec 'aws s3 ls'",
    "bash -xc 'atx update'",
    "zsh -lc 'aws s3 ls'",
    "eval 'aws s3 ls'",
    "eval aws s3 ls",
    "echo $(aws sts get-caller-identity)",
    'echo "$(aws sts get-caller-identity)"',
    "`aws sts get-caller-identity`",
    "x=`aws s3 ls`",
    "diff <(aws s3 ls) /dev/null",
    # keywords, groups, negation
    "if aws s3 ls; then echo yes; fi",
    "for i in 1 2; do aws s3 ls; done",
    "while atx --version; do break; done",
    "until aws s3 ls; do sleep 1; done",
    "! aws s3 ls",
    "{ aws s3 ls; }",
    "( aws s3 ls )",
    # redirect prefixes
    ">/dev/null aws s3 ls",
    "2>&1 aws s3 ls",
    "</dev/null atx --version",
    # quoting, escaping, case
    "\\aws s3 ls",
    '"aws" s3 ls',
    "'atx' --version",
    "AWS s3 ls",
    "Atx --version",
    # launchers
    "npx atx --version",
    "npx -y atx update",
    "bunx aws sts get-caller-identity",
    "npm exec atx -- --version",
    "pnpm dlx aws s3 ls",
    # a heredoc fed to a shell is a script; an unquoted heredoc body expands substitutions
    "bash <<'EOF'\naws s3 ls\nEOF",
    "cat <<EOF\n$(aws s3 ls)\nEOF",
]
# Commands that only mention the words.
ALLOWED = [
    "ls -la",
    "git status",
    "python -m pytest -q",
    "echo atx and aws are words here",
    "rg 'atx|aws' docs",
    "rg -n 'aws' docs/AWS_TRANSFORM_FACTS.md",
    "grep -n aws README.md",
    "grep -rn 'atx' .",
    "grep -q aws f; echo $?",
    "git grep -n aws -- docs",
    "git log --grep=aws",
    "git commit -m 'document the atx and aws rules'",
    'git commit -m "mention aws and atx in the guard docs"',
    "cat docs/AWS_TRANSFORM_FACTS.md",
    "sed -n 1,5p docs/aws.md",
    "ls awsdir/atx_notes",
    "printf 'atx\\n'",
    "python -m pytest tests/test_guard_hook.py",
    "scripts/ghost-py -m ghost.cli handoff wb.xlsx --out kit",
    ".venv/bin/python -m ghost.cli route wb.xlsx",
    "awk '{print $1}' f",
    "pip install awscli-local",
    "time rg aws docs",
    "sudo ls aws",
    "timeout 5 grep aws f",
    "env FOO=1 python x.py aws",
    "bash -c 'echo aws'",
    "if grep -q aws f; then echo y; fi",
    "for f in aws atx; do echo $f; done",
    "echo hi # aws s3 ls",
    "cat <<'EOF' > f.md\naws s3 ls\nEOF",
    "cat <<'EOF' > notes.md\nRun atx later.\nEOF\nls",
]


@pytest.mark.parametrize("command", BLOCKED, ids=lambda c: c.replace("\n", "\\n")[:60])
def test_commands_that_name_atx_or_aws_as_a_program_are_blocked(command, tmp_path):
    r = run(call(command), tmp_path)
    assert r.returncode == 2, (command, r.stderr)
    assert "this command names atx or aws as a program" in r.stderr
    assert "approval" in r.stderr and "s1" in r.stderr
    assert r.stdout == ""


@pytest.mark.parametrize("command", ALLOWED, ids=lambda c: c.replace("\n", "\\n")[:60])
def test_commands_that_only_mention_the_words_are_allowed(command, tmp_path):
    assert run(call(command), tmp_path).returncode == 0, command


def test_the_blocked_and_allowed_lists_do_not_overlap_and_are_not_trivial():
    assert not set(BLOCKED) & set(ALLOWED)
    assert len(BLOCKED) >= 55 and len(ALLOWED) >= 30


def test_an_approval_covers_that_session_only(tmp_path):
    ok = run({}, tmp_path, "approve", "s1")
    assert ok.returncode == 0 and "s1" in ok.stdout
    assert run(call("aws sts get-caller-identity", "s1"), tmp_path).returncode == 0
    assert run(call("aws sts get-caller-identity", "s2"), tmp_path).returncode == 2
    assert run({}, tmp_path, "revoke", "s1").returncode == 0
    assert run(call("aws sts get-caller-identity", "s1"), tmp_path).returncode == 2


def test_an_approval_covers_every_atx_and_aws_command_read_only_ones_included(tmp_path):
    run({}, tmp_path, "approve", "s1")
    for c in ("aws sts get-caller-identity", "aws s3 rm s3://b --recursive", "atx --version", "atx custom def exec -n x -x -t"):
        assert run(call(c), tmp_path).returncode == 0, c  # one approval, no per-command check: the docstring says so


def test_the_obvious_self_approval_commands_are_blocked(tmp_path):
    for cmd in ("scripts/ghost-py scripts/ghost_guard.py approve s1", "python scripts/ghost_guard.py approve s1",
                "python scripts/ghost_guard.py revoke s1",
                "mkdir -p ~/.ghost/approvals && touch ~/.ghost/approvals/s1",
                "GHOST_APPROVALS_DIR=/tmp/x python scripts/ghost_guard.py approve s1"):
        r = run(call(cmd), tmp_path)
        assert r.returncode == 2, cmd
        assert "owner" in r.stderr.lower()
    assert not (tmp_path / "s1").exists()


def test_the_guard_says_what_it_does_not_stop():
    doc = " ".join(ghost_guard.__doc__.split()).lower()
    assert "the obvious self-approval commands are blocked" in doc
    assert "can still create the marker or disable the hook" in doc
    assert "it stops accidents, not a determined agent" in doc
    assert "an approval lasts until revoked and covers every atx or aws command, read-only included" in doc


# -- fail closed (correction 8) ----------------------------------------------------------------
def test_a_payload_that_cannot_be_read_blocks_only_if_it_mentions_atx_or_aws(tmp_path):
    assert run(None, tmp_path, raw="not json at all").returncode == 0
    assert run(None, tmp_path, raw="not json; aws s3 ls").returncode == 2
    assert run(None, tmp_path, raw="").returncode == 0


def test_no_command_field_and_a_mention_of_atx_or_aws_is_blocked(tmp_path):
    p = {"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "x", "tool_input": {"script_body": "aws s3 ls"}}
    assert run(p, tmp_path).returncode == 2
    assert run({**p, "tool_input": {"args": ["atx", "--version"]}}, tmp_path).returncode == 2
    assert run({**p, "tool_input": {"path": "docs/readme.md"}}, tmp_path).returncode == 0
    assert run({"hook_event_name": "PreToolUse", "session_id": "s1"}, tmp_path).returncode == 0
    run({}, tmp_path, "approve", "s1")
    assert run(p, tmp_path).returncode == 0  # an approved session passes


def test_any_exception_in_the_guard_blocks_with_exit_2(monkeypatch, capsys):
    import io

    def boom(_text):
        raise RuntimeError("tokeniser bug")

    monkeypatch.setattr(ghost_guard, "check", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(call("ls"))))
    assert ghost_guard.main([]) == 2
    err = capsys.readouterr().err
    assert "blocked" in err.lower() and "RuntimeError" in err and "\n" not in err.strip()


def test_a_command_that_cannot_be_parsed_falls_back_to_a_raw_case_insensitive_match(tmp_path):
    assert run(call("echo 'unterminated aws"), tmp_path).returncode == 2
    assert run(call("echo 'unterminated ATX"), tmp_path).returncode == 2
    assert run(call("echo 'unterminated"), tmp_path).returncode == 0


def test_a_payload_with_no_session_id_cannot_be_approved(tmp_path):
    p = call("aws s3 ls")
    del p["session_id"]
    assert run(p, tmp_path).returncode == 2
    assert run({}, tmp_path, "approve", "").returncode != 0  # an empty session id is refused


def test_approve_refuses_odd_session_ids(tmp_path):
    for bad in ("../x", "a/b", "a b", "a;b"):
        assert run({}, tmp_path, "approve", bad).returncode != 0
    assert list(tmp_path.iterdir()) == []


# -- the hook files (correction 9) -------------------------------------------------------------
def test_the_hook_file_uses_the_documented_trigger_and_blocks_by_exit_code_2():
    data = json.loads(HOOK.read_text(encoding="utf-8"))
    assert data["version"] == "v1"
    (hook,) = data["hooks"]
    assert hook["trigger"] == "PreToolUse" and hook["matcher"] == "shell"
    assert hook["action"]["type"] == "command" and "ghost_guard.py" in hook["action"]["command"]
    assert isinstance(hook["timeout"], int) and 0 < hook["timeout"] <= 60
    assert "stops accidents, not a determined agent" in hook["description"]


def test_timeout_is_at_hook_level_in_every_command_hook_and_action_has_only_documented_keys():
    """Kiro's hooks page (https://kiro.dev/docs/hooks/, read 2026-11-26): `hooks[].timeout` is a hook field and
    `hooks[].action` holds `type`, `command` and `prompt`."""
    files = sorted(HOOKS.glob("*.json"))
    assert len(files) == 6
    commands = 0
    for f in files:
        for hook in json.loads(f.read_text(encoding="utf-8"))["hooks"]:
            assert set(hook["action"]) <= {"type", "command", "prompt"}, f.name
            if hook["action"]["type"] == "command":
                commands += 1
                assert isinstance(hook["timeout"], int) and hook["timeout"] > 0, f.name
            else:
                assert "timeout" not in hook, f.name
    assert commands == 5


def test_the_timeouts_are_the_ones_they_were():
    want = {"autopsy-on-graveyard-add.json": 120, "golden-tests-on-converter-save.json": 180,
            "regenerate-report-on-decision.json": 300, "reverify-on-logic-save.json": 300, "guard-atx-aws.json": 10}
    for name, secs in want.items():
        (hook,) = json.loads((HOOKS / name).read_text(encoding="utf-8"))["hooks"]
        assert hook["timeout"] == secs, name


def test_the_guard_runs_nothing_it_is_given():
    text = GUARD.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("#", '"""')))
    for bad in ("import subprocess", "os.system", "eval(", "exec(", "shell=True", "Popen"):
        assert bad not in code
