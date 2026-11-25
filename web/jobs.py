"""Background verification jobs for the web app.

Each job runs `python -m ghost.cli verify <migration_dir>` in its own
subprocess process group. That gives one Referee (LibreOffice) per job and a
hard kill on timeout. Macros are never enabled: `--trust-macros` is never
passed and there is no parameter for it.

At most `GHOST_MAX_JOBS` jobs run at once. Extra jobs wait in a FIFO queue and
report their 1-based queue position. Progress is the job's output lines,
available by polling (`Job.snapshot`) or as server-sent events (`sse_stream`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ghost.cli import EXIT_FAIL, EXIT_REPORT_NOT_WRITTEN

from .paths import scrub_paths

DEFAULT_MAX_JOBS = 2
DEFAULT_TIMEOUT_S = 300.0
MAX_EVENTS = 500

QUEUED, RUNNING, DONE, FAILED, TIMEOUT = "queued", "running", "done", "failed", "timeout"
TERMINAL = {DONE, FAILED, TIMEOUT}

# Artifacts collected from the migration directory before cleanup.
ARTIFACT_FILES = (
    "proof-report.html", "proof-report.json", "logic.py", "logic_intended.py",
    "excel.py", "mapping.yaml", "rules.md", "decisions.yaml",
)
FAITHFUL_REPORT_FILES = ("proof-report.html", "proof-report.json")


SESSION_BUSY_MESSAGE = (
    "This session already has a verification queued or running. "
    "Wait for it to finish, then start a new run."
)


class SessionBusy(Exception):
    """Raised by `JobRunner.submit` when the session already has an active job."""

    def __init__(self, job: "Job") -> None:
        super().__init__(SESSION_BUSY_MESSAGE)
        self.job = job


MISMATCHES_MESSAGE = "Verification found mismatches."
REPORT_NOT_WRITTEN_MESSAGE = "The report could not be written"
_TRACEBACK_HEADER = "Traceback (most recent call last):"
_EXCEPTION_LINE = re.compile(r"^([A-Za-z_][\w.]*)(?::\s?(.*))?$")
_CLI_ERROR_PREFIX = "ghost: error: "
_CLI_TYPED_ERROR = re.compile(r"^([A-Za-z_]\w*): (.*)$")
_MAX_DETAIL = 300


def _uncaught_exception(lines: list[str]) -> tuple[str, str] | None:
    """(type, message) of the last uncaught Python traceback in the output, if any.

    The exception line is the first unindented line after the last
    "Traceback (most recent call last):" header; frames are indented.
    """
    starts = [i for i, line in enumerate(lines) if line.strip() == _TRACEBACK_HEADER]
    if not starts:
        return None
    for line in lines[starts[-1] + 1:]:
        if not line or line[0].isspace():
            continue
        m = _EXCEPTION_LINE.match(line)
        if m is None:
            return None
        return m.group(1).rsplit(".", 1)[-1], (m.group(2) or "")
    return None


def _cli_error(lines: list[str]) -> tuple[str | None, str] | None:
    """(type or None, message) from the last ``ghost: error: ...`` line, if any."""
    for line in reversed(lines):
        if line.startswith(_CLI_ERROR_PREFIX):
            rest = line[len(_CLI_ERROR_PREFIX):].strip()
            m = _CLI_TYPED_ERROR.match(rest)
            return (m.group(1), m.group(2)) if m else (None, rest)
    return None


def _report_not_written(etype: str | None, detail: str, code: int, run_dirs) -> str:
    if etype and detail:
        inner = f"{etype}: {detail}"
    else:
        inner = etype or detail or f"exit code {code}"
    inner = scrub_paths(inner, *run_dirs)  # R-21: no server paths in the panel
    if len(inner) > _MAX_DETAIL:
        inner = inner[: _MAX_DETAIL - 1].rstrip() + "…"
    return f"{REPORT_NOT_WRITTEN_MESSAGE} ({inner})."


def failure_message(code: int, lines: list[str], *run_dirs: Path | str) -> str:
    """Panel text for a verification process that exited with non-zero ``code`` (L-02).

    Exit 1 means "mismatches not explained by a Decision" only when the output
    holds no uncaught traceback (Python also exits 1 on a crash) and no
    ``ghost: error:`` line. ``EXIT_REPORT_NOT_WRITTEN`` and those two cases say
    "The report could not be written (<ExceptionType>: ...)"; other codes name
    the exit code.
    """
    crash = _uncaught_exception(lines)
    cli_error = _cli_error(lines)
    if code == EXIT_REPORT_NOT_WRITTEN:
        etype, detail = cli_error or crash or (None, "")
        return _report_not_written(etype, detail, code, run_dirs)
    if code == EXIT_FAIL:
        if crash is not None:
            return _report_not_written(*crash, code, run_dirs)
        if cli_error is not None:
            return _report_not_written(*cli_error, code, run_dirs)
        # The verifier ran and found mismatches: a result, not a crash.
        return MISMATCHES_MESSAGE
    return f"Verification stopped with exit code {code}."


def max_jobs_from_env() -> int:
    try:
        return max(1, int(os.environ.get("GHOST_MAX_JOBS", DEFAULT_MAX_JOBS)))
    except ValueError:
        return DEFAULT_MAX_JOBS


DEFAULT_MUTATION_CASES = 100


def mutation_cases_from_env() -> int:
    """Cases per Mutant for web jobs; GHOST_MUTATION_CASES=0 disables the check."""
    try:
        return max(0, int(os.environ.get("GHOST_MUTATION_CASES", DEFAULT_MUTATION_CASES)))
    except ValueError:
        return DEFAULT_MUTATION_CASES


def default_command(migration_dir: Path, mode: str, seed: int | None, cases: int | None) -> list[str]:
    cmd = [sys.executable, "-m", "ghost.cli", "verify", str(migration_dir), "--mode", mode]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if cases is not None:
        cmd += ["--cases", str(cases)]
    mutation_cases = mutation_cases_from_env()
    if mutation_cases:
        cmd += ["--mutation-cases", str(mutation_cases)]
    return cmd


@dataclass
class Job:
    id: str
    session_id: str
    migration_dir: Path
    mode: str = "auto"
    status: str = QUEUED
    error: str | None = None
    exit_code: int | None = None
    events: list[str] = field(default_factory=list)
    artifacts: dict[str, bytes] = field(default_factory=dict)
    _runner: "JobRunner | None" = field(default=None, repr=False)
    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _timed_out: bool = field(default=False, repr=False)
    _forgotten: bool = field(default=False, repr=False)

    def snapshot(self, since: int = 0) -> dict:
        """Polling view: status, queue position, new events from index `since`."""
        r = self._runner
        pos = r.queue_position(self.id) if r else None
        with (r._lock if r else threading.Lock()):
            return {
                "id": self.id,
                "status": self.status,
                "queue_position": pos,
                "error": self.error,
                "passed": self.status == DONE,
                "events": list(self.events[since:]),
                "next": len(self.events),
                "artifacts": sorted(self.artifacts),
            }


class JobRunner:
    def __init__(
        self,
        max_jobs: int | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        command: Callable[[Path, str, int | None, int | None], list[str]] = default_command,
        cleanup: Callable[[Job], None] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self.max_jobs = max_jobs if max_jobs is not None else max_jobs_from_env()
        self.timeout_s = timeout_s
        self._command = command
        self._cleanup = cleanup
        self._cwd = cwd or Path(__file__).resolve().parent.parent
        self._lock = threading.RLock()
        self._queue: deque[str] = deque()
        self._jobs: dict[str, Job] = {}
        self._running = 0

    # -- public API ---------------------------------------------------------
    def submit(
        self,
        session_id: str,
        migration_dir: Path,
        mode: str = "auto",
        seed: int | None = None,
        cases: int | None = None,
    ) -> Job:
        job = Job(id=secrets.token_urlsafe(12), session_id=session_id,
                  migration_dir=Path(migration_dir), mode=mode, _runner=self)
        job._args = (seed, cases)  # type: ignore[attr-defined]
        with self._lock:
            active = self.active_job(session_id)
            if active is not None:
                raise SessionBusy(active)
            self._jobs[job.id] = job
            self._queue.append(job.id)
        self._pump()
        return job

    def active_job(self, session_id: str) -> Job | None:
        """The session's queued or running job, if any (at most one exists)."""
        with self._lock:
            return next((j for j in self._jobs.values()
                         if j.session_id == session_id and j.status not in TERMINAL), None)

    def get(self, job_id: str, session_id: str | None = None) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None or (session_id is not None and job.session_id != session_id):
            return None
        return job

    def queue_position(self, job_id: str) -> int | None:
        with self._lock:
            try:
                return list(self._queue).index(job_id) + 1
            except ValueError:
                return None

    def wait(self, job_id: str, timeout: float | None = None) -> Job:
        job = self._jobs[job_id]
        end = None if timeout is None else time.monotonic() + timeout
        while job.status not in TERMINAL:
            if end is not None and time.monotonic() > end:
                break
            time.sleep(0.02)
        return job

    def forget_session(self, session_id: str) -> None:
        """Remove every job of an ended session and free its artifacts.

        Queued jobs leave the queue, running jobs have their process group
        killed. The jobs are then dropped from the runner, so `/jobs/{id}`
        returns 404 and the artifact bytes can be garbage collected.
        """
        with self._lock:
            mine = [j for j in self._jobs.values() if j.session_id == session_id]
            for job in mine:
                if job.status == QUEUED:
                    self._queue.remove(job.id)
                    job.status, job.error = FAILED, "Session ended."
                elif job.status not in TERMINAL:
                    job.error = "Session ended."
                    self._kill(job)
                del self._jobs[job.id]
                job._forgotten = True
                job.artifacts.clear()
                job.events.clear()

    # -- internals ----------------------------------------------------------
    def _pump(self) -> None:
        with self._lock:
            while self._running < self.max_jobs and self._queue:
                job = self._jobs[self._queue.popleft()]
                job.status = RUNNING
                self._running += 1
                threading.Thread(target=self._run, args=(job,), daemon=True).start()

    def _emit(self, job: Job, line: str) -> None:
        line = scrub_paths(line, job.migration_dir)
        with self._lock:
            job.events.append(line)
            if len(job.events) > MAX_EVENTS:
                del job.events[: len(job.events) - MAX_EVENTS]

    @staticmethod
    def _kill(job: Job) -> None:
        proc = job._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()

    def _run(self, job: Job) -> None:
        seed, cases = job._args  # type: ignore[attr-defined]
        status, error = FAILED, None
        timer: threading.Timer | None = None
        try:
            cmd = self._command(job.migration_dir, job.mode, seed, cases)
            self._emit(job, "Starting verification")
            job._proc = subprocess.Popen(
                cmd, cwd=self._cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            if job._forgotten:  # session ended between start and Popen
                self._kill(job)

            def on_timeout() -> None:
                job._timed_out = True
                self._kill(job)

            timer = threading.Timer(self.timeout_s, on_timeout)
            timer.daemon = True
            timer.start()
            assert job._proc.stdout is not None
            for line in job._proc.stdout:
                line = line.rstrip()
                if line:
                    self._emit(job, line)
            code = job._proc.wait()
            job.exit_code = code
            if job._timed_out:
                status, error = TIMEOUT, f"Verification exceeded the {self.timeout_s:g} s timeout."
            elif job.error == "Session ended.":
                status, error = FAILED, job.error
            elif code == 0:
                status = DONE
            else:
                with self._lock:
                    lines = list(job.events)
                status, error = FAILED, failure_message(code, lines, job.migration_dir)
        except Exception as exc:  # noqa: BLE001
            status, error = FAILED, scrub_paths(
                f"Could not run verification: {exc}", job.migration_dir)
        finally:
            if timer is not None:
                timer.cancel()
            if job._proc is not None:
                self._kill(job)  # reap any leftover soffice in the group
            self._collect(job)
            with self._lock:
                job.error = error
                job.status = status
                self._running -= 1
            self._do_cleanup(job)
            self._pump()

    def _collect(self, job: Job) -> None:
        if job._forgotten:
            return
        for name in ARTIFACT_FILES:
            p = job.migration_dir / name
            try:
                if p.is_file():
                    job.artifacts[name] = p.read_bytes()
            except OSError:
                pass
        # R-21: when both modes ran, the top-level report is the Intended one;
        # keep the Faithful report too, under "faithful/<name>".
        reports = job.migration_dir / "reports"
        if (reports / "intended").is_dir() and (reports / "faithful").is_dir():
            for name in FAITHFUL_REPORT_FILES:
                p = reports / "faithful" / name
                try:
                    if p.is_file():
                        job.artifacts[f"faithful/{name}"] = p.read_bytes()
                except OSError:
                    pass

    def _do_cleanup(self, job: Job) -> None:
        """Delete the migration directory (inside the Session_Folder) at job end."""
        try:
            if self._cleanup is not None:
                self._cleanup(job)
            else:
                shutil.rmtree(job.migration_dir, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass


# -- SSE and routes ---------------------------------------------------------
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def sse_stream(job: Job, interval_s: float = 0.25, heartbeat_s: float = 15.0) -> Iterable[str]:
    """Async generator of SSE frames until the job reaches a terminal state."""
    since, last = 0, time.monotonic()
    while True:
        snap = await asyncio.to_thread(job.snapshot, since)
        since = snap["next"]
        if snap["events"] or snap["status"] in TERMINAL or snap["status"] == QUEUED:
            yield _sse("progress", snap)
            last = time.monotonic()
        elif time.monotonic() - last > heartbeat_s:
            yield ": keep-alive\n\n"
            last = time.monotonic()
        if snap["status"] in TERMINAL:
            return
        await asyncio.sleep(interval_s)


def build_router(runner: JobRunner, session_id_for: Callable[[Request], str | None]) -> APIRouter:
    """Routes: GET /jobs/{id} (polling) and GET /jobs/{id}/events (SSE).

    `session_id_for` returns the caller's session id; jobs of other sessions
    appear as not found.
    """
    router = APIRouter()

    def _job(request: Request, job_id: str) -> Job:
        sid = session_id_for(request)
        job = runner.get(job_id, sid) if sid else None
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        return job

    @router.get("/jobs/{job_id}")
    async def poll(request: Request, job_id: str, since: int = 0) -> JSONResponse:
        return JSONResponse(_job(request, job_id).snapshot(max(0, since)))

    @router.get("/jobs/{job_id}/events")
    async def events(request: Request, job_id: str) -> StreamingResponse:
        return StreamingResponse(
            sse_stream(_job(request, job_id)), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
