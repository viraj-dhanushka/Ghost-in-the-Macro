"""PreToolUse guard (Kiro hook): block `atx` and `aws` shell commands unless the Owner approved them for this session.
Ground rule 6 of the Kiro feature prompt, made something Kiro enforces.

Usage by Kiro:   scripts/ghost-py scripts/ghost_guard.py     (the hook payload, JSON, is on standard input)
Usage by the Owner, in a terminal outside the session:
                 scripts/ghost-py scripts/ghost_guard.py approve <session_id>
                 scripts/ghost-py scripts/ghost_guard.py revoke <session_id>

Exit 0 lets the tool call run. Exit 2 blocks it and the reason goes to the agent on standard error (Kiro documents
Pre Tool Use as able to block; exit code 2 is the code its pages agree on).

What it does: it reads the command text of a shell tool call, removes shell comments, and splits it with a quote-aware
tokeniser (shlex with punctuation characters, so quotes, escapes, redirects and separators are understood). It blocks
the call when atx or aws is named as a program: after a separator, a keyword (if, while, !, a brace), a redirect prefix,
a variable assignment, a wrapper (sudo, env, timeout, nice, nohup, xargs, command, exec and similar, with their
options), inside bash -c or -ec, inside eval or a command substitution, as the program an npx-style launcher runs,
as the command a find -exec, -execdir, -ok or -okdir runs, as the AWS CLI run as a Python module (python -m awscli),
or as the repository's own scripts/deploy_ecs_express.sh, run directly, through a shell, or sourced. A command that only mentions
the words (a grep, a commit message, a file name) is not blocked. If the text cannot be parsed it falls back to a raw
case-insensitive match; a tool call with no command field whose payload mentions atx or aws is blocked; and any
exception in the guard blocks. It reads text and writes one marker file per approved session under
$GHOST_APPROVALS_DIR (default ~/.ghost/approvals), outside the repository. It runs nothing it is given.

What it does not do, stated plainly. The obvious self-approval commands are blocked, but an agent with a shell or file
tools can still create the marker or disable the hook, so it stops accidents, not a determined agent. An approval
lasts until revoked and covers every atx or aws command, read-only included: there is no per-command approval. It
looks only at the command text of shell tool calls: a script file that runs atx or aws, a command assembled at run
time, a heredoc fed to an interpreter other than a shell, or a tool that is not a shell tool is not seen, and a hook
that does not fire in some surface blocks nothing there. Whether Kiro fires it and blocks a real atx or aws command is
not checked.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

BLOCKED_PROGRAMS = {"atx", "aws"}
DEPLOY_SCRIPT = "deploy_ecs_express.sh"  # the repository's deploy script: it runs aws and docker against a real account
PYTHON_RE = re.compile(r"^python[0-9.]*$")
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
SESSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# A raw mention: atx or aws as a whole word, not part of a path, a file name or a longer identifier.
RAW_RE = re.compile(r"(^|[^A-Za-z0-9_./-])(atx|aws)($|[^A-Za-z0-9_-])", re.IGNORECASE)
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEP_CHARS = ";&|()\n"
PUNCT_CHARS = SEP_CHARS + "<>"
MAX_DEPTH = 6

SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "csh", "fish"}
# Words that leave the next word in command position.
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "done", "fi", "esac"}
# wrapper -> (options that take an argument, number of positional arguments before the wrapped command)
WRAPPERS: dict[str, tuple[set[str], int]] = {
    "sudo": ({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "-r", "-t", "--user", "--group", "--host",
              "--prompt", "--chdir", "--role", "--type"}, 0),
    "doas": ({"-u", "-C"}, 0),
    "env": ({"-u", "-C", "--unset", "--chdir"}, 0),
    "time": ({"-f", "-o", "--format", "--output"}, 0),
    "timeout": ({"-s", "-k", "--signal", "--kill-after"}, 1),
    "nice": ({"-n", "--adjustment"}, 0),
    "ionice": ({"-c", "-n", "-p", "-P", "-u"}, 0),
    "nohup": (set(), 0),
    "command": (set(), 0),
    "exec": ({"-a"}, 0),
    "builtin": (set(), 0),
    "xargs": ({"-I", "-i", "-n", "-P", "-L", "-l", "-s", "-E", "-e", "-d", "-a", "--arg-file", "--max-args",
               "--max-procs", "--delimiter", "--replace", "--max-lines", "--eof"}, 0),
    "watch": ({"-n", "--interval"}, 0),
    "stdbuf": ({"-i", "-o", "-e"}, 0),
    "setsid": (set(), 0),
    "caffeinate": ({"-t", "-w"}, 0),
}
# launcher -> subcommands that run a program (empty: the first positional is the program)
LAUNCHERS: dict[str, set[str]] = {
    "npx": set(), "bunx": set(), "pnpx": set(), "uvx": set(),
    "pipx": {"run"}, "npm": {"exec", "x"}, "pnpm": {"exec", "dlx"}, "yarn": {"exec", "dlx"}, "bun": {"x"}, "uv": {"run"},
}
LAUNCHER_ARG_OPTIONS = {"-p", "--package", "-c", "--call", "--from", "--with", "--prefix", "-w", "--workspace"}

HEREDOC_RE = re.compile(r"(?<!<)<<(-?)[ \t]*(\\?)(['\"]?)([A-Za-z_][A-Za-z0-9_.-]*)\3")
SHELL_BEFORE_HEREDOC_RE = re.compile(r"(^|[\s;&|(])(?:\S*/)?(?:ba|z|da|k|c)?sh(\s|$)")


def approvals_dir() -> Path:
    return Path(os.environ.get("GHOST_APPROVALS_DIR") or (Path.home() / ".ghost" / "approvals"))


# --------------------------------------------------------------------------------------------- comments
def _strip_comments(text: str) -> str:
    """Remove shell comments (a `#` that starts a word, outside quotes), keeping the newline that ends each one. An
    apostrophe inside a comment ("# it's") would otherwise open a quote that runs to the end of the command and hide
    every line after it from the tokeniser."""
    out: list[str] = []
    i, n = 0, len(text)
    single = double = False
    while i < n:
        c = text[i]
        if single:
            out.append(c)
            single = c != "'"
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == "'" and not double:
            single = True
        elif c == '"':
            double = not double
        elif c == "#" and not double and (i == 0 or text[i - 1] in " \t\n;&|()"):
            j = text.find("\n", i)
            if j == -1:
                break
            i = j  # the newline itself is kept
            continue
        out.append(c)
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------------------------- tokens
def _tokens(text: str) -> list[str]:
    lex = shlex.shlex(text, posix=True, punctuation_chars=PUNCT_CHARS)
    lex.whitespace = " \t\r"  # a newline is a separator, so it is not whitespace
    lex.whitespace_split = True
    lex.commenters = ""  # `a#b` is one word in a shell; do not let a '#' hide the rest of the line
    return list(lex)


def _punct(tok: str) -> bool:
    return bool(tok) and all(c in PUNCT_CHARS for c in tok)


def _is_redirect(tok: str) -> bool:
    return _punct(tok) and ("<" in tok or ">" in tok) and "(" not in tok


def _prog(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


# --------------------------------------------------------------------------------------------- substitutions
def _substitutions(text: str) -> list[str]:
    """Command text inside $( ), backticks, <( ) and >( ) that the shell would run: outside single quotes only."""
    out: list[str] = []
    i, n = 0, len(text)
    single = double = False
    while i < n:
        c = text[i]
        if single:
            single = c != "'"
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "'" and not double:
            single = True
            i += 1
            continue
        if c == '"':
            double = not double
            i += 1
            continue
        if c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i + 1:j])
            i = j + 1
            continue
        if text.startswith("(", i + 1) and (c == "$" or (c in "<>" and not double)):
            depth, j = 1, i + 2
            while j < n and depth:
                if text[j] == "\\":
                    j += 2
                    continue
                depth += text[j] == "("
                depth -= text[j] == ")"
                j += 1
            out.append(text[i + 2:j - 1 if depth == 0 else j])
            i = j
            continue
        i += 1
    return out


def _split_heredocs(command: str) -> tuple[str, list[tuple[str, bool, bool]]]:
    """(the command without its heredoc bodies, [(body, literal, fed_to_a_shell)]). A heredoc with no terminating
    line is not treated as one (a `<<` inside a quoted message must not hide the lines after it)."""
    lines = command.split("\n")
    kept: list[str] = []
    bodies: list[tuple[str, bool, bool]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        m = HEREDOC_RE.search(line)
        if m:
            delim, literal, strip = m.group(4), bool(m.group(2) or m.group(3)), m.group(1) == "-"
            j, body = i + 1, []
            while j < len(lines):
                probe = (lines[j].lstrip("\t") if strip else lines[j]).rstrip("\r")
                if probe == delim:
                    break
                body.append(lines[j])
                j += 1
            if j < len(lines):
                before = line[:m.start()]
                bodies.append(("\n".join(body), literal, bool(SHELL_BEFORE_HEREDOC_RE.search(before)) and " -c" not in before))
                i = j + 1
                continue
        i += 1
    return "\n".join(kept), bodies


# --------------------------------------------------------------------------------------------- the decision
def runs_blocked_program(command: str, depth: int = 0) -> bool:
    """True when ``command`` names atx or aws as a program. Quote-aware; falls back to a raw match on a parse error."""
    if depth > MAX_DEPTH:
        return True  # nested too deep to follow: fail closed
    command = command.replace("\\\n", " ")
    text, bodies = _split_heredocs(command)
    for body, literal, to_shell in bodies:
        if to_shell and runs_blocked_program(body, depth + 1):
            return True
        if not literal and any(runs_blocked_program(s, depth + 1) for s in _substitutions(body)):
            return True
    stripped = _strip_comments(text)
    try:
        toks = _tokens(stripped)
    except ValueError:
        return bool(RAW_RE.search(text)) or DEPLOY_SCRIPT in text  # cannot parse it: a raw, conservative match
    if any(runs_blocked_program(s, depth + 1) for s in _substitutions(stripped)):
        return True
    return _scan(toks, depth)


def _words_until_separator(toks: list[str], start: int) -> list[str]:
    out = []
    for t in toks[start:]:
        if _punct(t) and not _is_redirect(t):
            break
        if not _punct(t):
            out.append(t)
    return out


def _skip_wrapper_options(toks: list[str], j: int, spec: tuple[set[str], int], name: str, depth: int) -> tuple[int, bool]:
    """Index of the word a wrapper runs, and whether a nested command was found to be blocked (env -S)."""
    arg_options, positional = spec
    n = len(toks)
    while j < n and not (_punct(toks[j]) and not _is_redirect(toks[j])):
        w = toks[j]
        if _is_redirect(w):
            j += 2
            continue
        if w == "--":
            return j + 1, False
        if name == "env" and w in ("-S", "--split-string") and j + 1 < n:
            return j + 2, runs_blocked_program(toks[j + 1], depth + 1)
        if w.startswith("-") and len(w) > 1:
            j += 2 if w in arg_options else 1
            continue
        if ASSIGN_RE.match(w):
            j += 1
            continue
        if positional > 0:
            positional -= 1
            j += 1
            continue
        break
    return j, False


def _scan(toks: list[str], depth: int) -> bool:
    i, n = 0, len(toks)
    at_start = True
    while i < n:
        t = toks[i]
        if _punct(t):
            if _is_redirect(t):
                i += 2  # a redirect and its target word; command position is unchanged
                continue
            at_start = True  # a separator, a parenthesis, a newline, a process substitution
            i += 1
            continue
        if not at_start:
            i += 1
            continue
        if t.isdigit() and i + 1 < n and _is_redirect(toks[i + 1]):
            i += 1  # a file descriptor number in front of a redirect
            continue
        if ASSIGN_RE.match(t):
            i += 1  # VAR=value prefix; its value was checked as a substitution
            continue
        name = _prog(t)
        if name in BLOCKED_PROGRAMS or name == DEPLOY_SCRIPT:
            return True
        if name in KEYWORDS:
            i += 1
            continue
        args = _words_until_separator(toks, i + 1)
        if name in SHELLS:
            for k, w in enumerate(args[:-1]):
                if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
                    if runs_blocked_program(args[k + 1], depth + 1):
                        return True
                    break
            if any(_prog(w) == DEPLOY_SCRIPT for w in args):  # bash scripts/deploy_ecs_express.sh
                return True
        elif name in ("source", "."):
            if any(_prog(w) == DEPLOY_SCRIPT for w in args):
                return True
        elif PYTHON_RE.match(name):
            if _runs_awscli_module(args):
                return True
        elif name == "find":
            if _find_runs_blocked(toks, i + 1, depth):
                return True
        elif name == "eval":
            if runs_blocked_program(" ".join(args), depth + 1):
                return True
        elif name in LAUNCHERS:
            if _launcher_runs_blocked(name, args):
                return True
        elif name in WRAPPERS:
            if name == "command" and any(a in ("-v", "-V") for a in args[:2]):
                at_start = False  # `command -v aws` only looks the program up
                i += 1
                continue
            j, nested = _skip_wrapper_options(toks, i + 1, WRAPPERS[name], name, depth)
            if nested:
                return True
            i = j  # the wrapped command is in command position
            continue
        at_start = False
        i += 1
    return False


def _runs_awscli_module(args: list[str]) -> bool:
    """python -m awscli ... (or -mawscli): the AWS CLI as a module."""
    for k, w in enumerate(args):
        if w == "-m" and k + 1 < len(args):
            return args[k + 1].split(".")[0] == "awscli"
        if w.startswith("-m") and len(w) > 2:
            return w[2:].split(".")[0] == "awscli"
        if not w.startswith("-"):
            return False  # the script name: what follows belongs to the script
    return False


def _find_runs_blocked(toks: list[str], start: int, depth: int) -> bool:
    """find ... -exec CMD ... ; | + : CMD is a command in command position. An escaped `\\;` and a real `;` are the same
    token, so the whole rest of the line is searched for -exec, -execdir, -ok and -okdir."""
    n = len(toks)
    j = start
    while j < n:
        if toks[j] in FIND_EXEC:
            sub: list[str] = []
            k = j + 1
            while k < n and toks[k] not in (";", "+") and not (_punct(toks[k]) and toks[k] not in ("(", ")")):
                sub.append(toks[k])
                k += 1
            if sub and _scan(sub, depth + 1):
                return True
            j = k
        j += 1
    return False


def _launcher_runs_blocked(name: str, args: list[str]) -> bool:
    subs = LAUNCHERS[name]
    k = 0
    if subs:
        while k < len(args) and args[k].startswith("-"):
            k += 1
        if k >= len(args) or args[k] not in subs:
            return False
        k += 1
    while k < len(args):
        w = args[k]
        if w == "--":
            k += 1
            continue
        if w.startswith("-"):
            k += 2 if w in LAUNCHER_ARG_OPTIONS else 1
            continue
        return _prog(w) in BLOCKED_PROGRAMS or _prog(w) == "awscli" or _prog(w) == DEPLOY_SCRIPT
    return False


def touches_approvals(command: str) -> bool:
    if ".ghost/approvals" in command or "GHOST_APPROVALS_DIR" in command:
        return True
    return "ghost_guard.py" in command and re.search(r"\b(approve|revoke)\b", command) is not None


def _command_text(payload: dict) -> str | None:
    """The shell command in a tool call, or None when there is no command field."""
    ti = payload.get("tool_input")
    if isinstance(ti, str):
        return ti
    if isinstance(ti, dict):
        for key in ("command", "cmd", "script"):
            if isinstance(ti.get(key), str):
                return ti[key]
    return None


def _approved(session: object) -> bool:
    return isinstance(session, str) and bool(SESSION_RE.match(session)) and (approvals_dir() / session).is_file()


def check(stdin_text: str) -> tuple[int, str]:
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("not an object")
    except ValueError:
        if RAW_RE.search(stdin_text or ""):
            return 2, "Blocked: the hook payload could not be read and it mentions atx or aws. Ask the Owner."
        return 0, ""
    session = payload.get("session_id")
    sid = session if isinstance(session, str) and SESSION_RE.match(session) else "<no session id: cannot be approved>"
    command = _command_text(payload)
    if command is None:
        if not RAW_RE.search(stdin_text) or _approved(session):
            return 0, ""
        return 2, (f"Blocked: no command field was found in this tool call and its payload mentions atx or aws, so it "
                   f"cannot be checked (session id {sid}). Do not run it. Ask the Owner.")
    if touches_approvals(command):
        return 2, ("Blocked: only the Owner approves atx or aws commands, in a terminal outside this session. "
                   "Do not run or edit the approval files.")
    if not runs_blocked_program(command):
        return 0, ""
    if _approved(session):
        return 0, ""
    return 2, (f"Blocked: this command names atx or aws as a program, which needs the Owner's approval in this session "
               f"(session id {sid}). Do not run it. Ask the Owner to read the command and, if they agree, run in a "
               f"terminal: scripts/ghost-py scripts/ghost_guard.py approve {sid}")


def _run(argv: list[str]) -> int:
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


def main(argv: list[str]) -> int:
    try:
        return _run(argv)
    except BaseException as exc:  # noqa: BLE001 - fail closed: a guard that crashes must not let the call through
        reason = " ".join(str(exc).split())[:200]
        print(f"ghost_guard: blocked: the guard failed ({type(exc).__name__}: {reason}). Ask the Owner.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
