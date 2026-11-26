"""``ghost receipt``: referee what came back from AWS Transform custom and record it honestly.

It runs ``ghost challenge`` in a separate process, with an absolute ``--out`` under the receipt's own folder
and from a working directory it owns, under a timeout. It reads the exit code and the proof report only; it
never reads what the candidate printed. A pass is recorded only when every condition in ``judge`` holds.
Nothing here calls AWS. The definition name and the log path are what the owner says, not something Ghost
verified.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from ghost.verifier.run import DEFAULT_SEED

__all__ = ["ReceiptError", "judge", "run_receipt"]

STATED = "stated by the owner, not verified by Ghost"
DEFAULT_TIMEOUT_S = 900.0
LIMITS_STATEMENT = (
    "The candidate runs in the verifier's own process, so the result holds for code that is not trying to "
    "defeat the check."
)
KNOWN_LIMITS = [
    "No sandbox: the candidate's code runs on this machine with this process's permissions.",
    "A candidate must be one self-contained file (logic.py).",
    "Recorded Decisions are not consulted by ghost challenge.",
    "The Referee is LibreOffice's recalculation of the workbook; nothing was checked in Excel.",
]


class ReceiptError(Exception):
    """The receipt could not be started; the reason is one line."""


def judge(exit_code: int | None, report: dict | None, expected_seed: int) -> tuple[str, str]:
    """(result, reason). ``pass`` only when ALL hold: exit code 0; a report exists; its ``passed`` is True;
    ``cases_tested`` is an integer above 0; its seed is the expected one. Exit 0 without them is an error."""
    if exit_code is None:
        return "error", "no exit status (the call did not finish)"
    if exit_code == 0:
        if report is None:
            return "error", "exit 0 but no proof report was found"
        cases = report.get("cases_tested")
        if (
            report.get("passed") is True
            and isinstance(cases, int) and not isinstance(cases, bool) and cases > 0
            and report.get("seed") == expected_seed
        ):
            return "pass", f"no difference found on {cases} cases"
        return "error", "exit 0 but the report does not show a pass on a positive number of cases with the expected seed"
    if exit_code == 1:
        if report is not None and report.get("passed") is False:
            return "difference found", "the report records a difference"
        return "error", "exit 1 but the report does not record a difference"
    if exit_code == 2:
        return "could not be refereed", "exit 2; run ghost challenge by hand to read the reason (this command does not read its output)"
    return "error", f"unexpected exit status {exit_code}"


def _default_runner(cmd, **kw):
    """Like subprocess.run, but in its own process group, so that a timeout stops the whole group (a LibreOffice
    the challenge started included) and not only the direct child."""
    timeout = kw.pop("timeout", None)
    proc = subprocess.Popen(cmd, start_new_session=True, **kw)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.wait()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_receipt(
    workbook: str | Path,
    kit: str | Path,
    definition: str,
    log: str,
    out: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    timeout: float = DEFAULT_TIMEOUT_S,
    runner: Callable[..., Any] | None = None,
) -> dict:
    workbook, kit, out = Path(workbook), Path(kit), Path(out)
    logic = kit / "logic.py"
    if not workbook.is_file():
        raise ReceiptError(f"workbook not found: {workbook}")
    if not logic.is_file():
        raise ReceiptError("the kit has no logic.py: copy the returned file there first")
    if not (isinstance(timeout, (int, float)) and math.isfinite(timeout) and timeout > 0):
        raise ReceiptError("--timeout must be a positive number of seconds")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ReceiptError(f"--out {out} exists and is not an empty folder")
    candidate_sha, workbook_sha = _sha(logic), _sha(workbook)  # of the files as they were before anything ran
    out.mkdir(parents=True, exist_ok=True)
    root = out.resolve()
    challenge_out = root / "challenge"      # absolute, under the receipt's own folder; challenge creates it
    work = root / "work"                    # a working directory this command owns
    work.mkdir()
    mapping = kit / "mapping.yaml"
    cmd = [sys.executable, "-m", "ghost.cli", "challenge", str(workbook.resolve()), "--code", str(logic.resolve())]
    if mapping.is_file():
        cmd += ["--mapping", str(mapping.resolve())]
    cmd += ["--out", str(challenge_out), "--seed", str(seed)]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parent.parent), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    run = runner or _default_runner
    exit_code: int | None = None
    timed_out = False
    try:
        done = run(cmd, cwd=str(work), env=env, timeout=timeout, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        exit_code = done.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    except OSError:
        exit_code = None
    report_file = challenge_out / "reports" / "faithful" / "proof-report.json"
    report: dict | None = None
    if report_file.is_file():
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            report = data if isinstance(data, dict) else None
        except (OSError, ValueError):
            report = None
    if timed_out:
        result, reason = "error", f"timed out after {timeout:g} s"
    else:
        result, reason = judge(exit_code, report, seed)
    receipt = {
        "result": result,
        "reason": reason,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "report_found": report is not None,
        "report": None if report is None else {
            "passed": report.get("passed"),
            "cases_tested": report.get("cases_tested"),
            "seed": report.get("seed"),
            "libreoffice": (report.get("versions") or {}).get("libreoffice"),
        },
        "expected_seed": seed,
        "mapping": "given" if mapping.is_file() else "derived",
        "mapping_confirmed_by_person": "not recorded",
        "mapping_note": (
            "given means a mapping.yaml was passed to ghost challenge. If it came from ghost handoff it was derived by "
            "Ghost from the workbook, and a person has not confirmed it unless the owner did; that is not recorded here."
        ),
        "definition": {"value": definition, "status": STATED},
        "log": {"value": log, "status": STATED},
        "origin": "Ghost has not seen where the file came from; it only refereed the file it was given.",
        "candidate_sha256": candidate_sha,
        "workbook_sha256": workbook_sha,
        "checked_in_excel": "not checked",
        "limits_statement": LIMITS_STATEMENT,
        "known_limits": KNOWN_LIMITS,
    }
    (out / "transform-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
