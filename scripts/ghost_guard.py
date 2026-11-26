"""PreToolUse guard (Kiro hook): block `atx` and `aws` shell commands unless the Owner approved them for this session.
Ground rule 6 of the Kiro feature prompt, made something Kiro enforces.

Usage by Kiro:   scripts/ghost-py scripts/ghost_guard.py     (the hook payload, JSON, is on standard input)
Usage by the Owner, in a terminal outside the session:
                 scripts/ghost-py scripts/ghost_guard.py approve <session_id>
                 scripts/ghost-py scripts/ghost_guard.py revoke <session_id>

Exit 0 lets the tool call run. Exit 2 blocks it and the reason goes to the agent on standard error (Kiro documents
Pre Tool Use as able to block; exit code 2 is the code its pages agree on).

It reads text and writes one marker file per approved session under $GHOST_APPROVALS_DIR (default ~/.ghost/approvals),
outside the repository. It runs nothing it is given. Limits, stated plainly: it looks only at shell tool calls, it
reads the command text (a command built at run time, or run through another tool, is not seen), and a hook that does
not fire in some surface blocks nothing there. Whether it fires and blocks in the Kiro IDE is not checked.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

BLOCKED_PROGRAMS = {"atx", "aws"}
# programs that run another command: look at what follows them
WRAPPERS = {"sudo", "env", "time", "nohup", "nice", "command", "exec", "xargs", "watch", "timeout", "stdbuf", "doas", "builtin"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SESSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
RAW_RE = re.compile(r"(^|[\s;&|(`\"'$])(atx|aws)(\s|$)")
SPLIT_RE = re.compile(r"\|\||&&|[;&|\n]|\$\(|`|\(|\)")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def approvals_dir() -> Path:
    return Path(os.environ.get("GHOST_APPROVALS_DIR") or (Path.home() / ".ghost" / "approvals"))


def _words(segment: str) -> list[str]:
    # a light split: quotes are dropped, nothing is expanded or run
    return [w.strip("'\"") for w in re.findall(r"""(?:[^\s'"]+|'[^']*'|"[^"]*")+""", segment)]


def _program(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def runs_blocked_program(command: str, depth: int = 0) -> bool:
    for segment in SPLIT_RE.split(command):
        words = _words(segment)
        i = 0
        while i < len(words):
            w = words[i]
            if ASSIGN_RE.match(w):
                i += 1  # VAR=value prefix
                continue
            prog = _program(w)
            if prog in BLOCKED_PROGRAMS:
                return True
            if prog in SHELLS and depth < 3:
                for j in range(i + 1, len(words) - 1):
                    if words[j] in ("-c", "-lc", "-ic"):
                        if runs_blocked_program(words[j + 1], depth + 1):
                            return True
                break
            if prog in WRAPPERS:
                i += 1
                while i < len(words) and (words[i].startswith("-") or ASSIGN_RE.match(words[i])):
                    i += 1
                continue
            break
    return False


def touches_approvals(command: str) -> bool:
    if ".ghost/approvals" in command or "GHOST_APPROVALS_DIR" in command:
        return True
    return "ghost_guard.py" in command and re.search(r"\b(approve|revoke)\b", command) is not None


def _command_text(payload: dict) -> str | None:
    ti = payload.get("tool_input")
    if isinstance(ti, dict):
        for key in ("command", "cmd", "script"):
            if isinstance(ti.get(key), str):
                return ti[key]
        return " ".join(v for v in ti.values() if isinstance(v, str))
    return ti if isinstance(ti, str) else None


def check(stdin_text: str) -> tuple[int, str]:
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        if RAW_RE.search(stdin_text or ""):
            return 2, "Blocked: the hook payload could not be read and it mentions atx or aws. Ask the Owner."
        return 0, ""
    command = _command_text(payload)
    if command is None:
        return 0, ""
    session = payload.get("session_id")
    if touches_approvals(command):
        return 2, ("Blocked: only the Owner approves atx or aws commands, in a terminal outside this session. "
                   "Do not run or edit the approval files.")
    if not runs_blocked_program(command):
        return 0, ""
    if isinstance(session, str) and SESSION_RE.match(session) and (approvals_dir() / session).is_file():
        return 0, ""
    sid = session if isinstance(session, str) and SESSION_RE.match(session) else "<no session id: cannot be approved>"
    return 2, (f"Blocked: this runs atx or aws, which needs the Owner's approval in this session (session id {sid}). "
               f"Do not run it. Ask the Owner to read the command and, if they agree, run in a terminal: "
               f"scripts/ghost-py scripts/ghost_guard.py approve {sid}")


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("approve", "revoke"):
        sid = argv[1] if len(argv) > 1 else ""
        if not SESSION_RE.match(sid):
            print("ghost_guard: a session id of letters, digits, '.', '_' and '-' is required.", file=sys.stderr)
            return 1
        d = approvals_dir()
        if argv[0] == "approve":
            d.mkdir(parents=True, exist_ok=True)
            (d / sid).write_text("approved by the Owner in a terminal\n", encoding="utf-8")
            print(f"Approved atx and aws commands for session {sid}. Revoke with: ghost_guard.py revoke {sid}")
        else:
            (d / sid).unlink(missing_ok=True)
            print(f"Revoked session {sid}.")
        return 0
    code, message = check(sys.stdin.read())
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
