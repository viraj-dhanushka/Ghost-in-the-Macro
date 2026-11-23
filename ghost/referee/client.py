"""Engine side of the Referee: launches headless LibreOffice and talks JSON lines."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ghost.referee.locate import locate_soffice
from ghost.referee.profile import SCRIPT_NAME, build_profile, profile_url

HOST = "127.0.0.1"
MACRO_URL = f"vnd.sun.star.script:{SCRIPT_NAME}$serve?language=Python&location=user"
PORT_ENV = "GHOST_REFEREE_PORT"

DEFAULT_STARTUP_TIMEOUT = 90.0
DEFAULT_COMMAND_TIMEOUT = 60.0
_POLL = 0.25


class RefereeError(Exception):
    """The Referee failed, timed out, exited, or refused a command."""


class RefereeClient:
    """Context manager owning one long-lived Referee process for a job.

    The workbook is copied into the job folder and the copy is opened, so the
    uploaded file is never modified. ``run_macros=True`` is only accepted when
    ``trusted_source`` is also True (bundled sample or local CLI
    ``--trust-macros``); web uploads must never pass either.
    """

    def __init__(
        self,
        soffice_path: str | None,
        workbook_path: str | os.PathLike[str],
        run_macros: bool = False,
        *,
        trusted_source: bool = False,
        job_dir: str | os.PathLike[str] | None = None,
        startup_timeout: float = DEFAULT_STARTUP_TIMEOUT,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        if run_macros and not trusted_source:
            raise RefereeError("run_macros is only allowed for a trusted source")
        self.soffice_path = soffice_path or locate_soffice()
        self.workbook_path = Path(workbook_path)
        self.run_macros = run_macros
        self.startup_timeout = startup_timeout
        self.command_timeout = command_timeout
        self._job_dir_arg = Path(job_dir) if job_dir else None
        self._owns_job_dir = False
        self.job_dir: Path | None = None
        self.copy_path: Path | None = None
        self._profile: Path | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._listener: socket.socket | None = None
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 1

    # -- lifecycle --------------------------------------------------------
    def __enter__(self) -> "RefereeClient":
        try:
            self.start()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        if not self.workbook_path.is_file():
            raise RefereeError(f"workbook not found: {self.workbook_path}")
        if self._job_dir_arg is not None:
            self._job_dir_arg.mkdir(parents=True, exist_ok=True)
            self.job_dir = self._job_dir_arg
        else:
            self.job_dir = Path(tempfile.mkdtemp(prefix="ghost-job-"))
            self._owns_job_dir = True
        self.copy_path = self.job_dir / ("referee-" + self.workbook_path.name)
        shutil.copyfile(self.workbook_path, self.copy_path)
        self._profile = build_profile(parent=self.job_dir, run_macros=self.run_macros)

        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind((HOST, 0))
        self._listener.listen(1)
        port = self._listener.getsockname()[1]

        env = dict(os.environ)
        env[PORT_ENV] = str(port)
        cmd = [
            self.soffice_path,
            "--headless",
            "--invisible",
            "--norestore",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            profile_url(self._profile),
            MACRO_URL,
        ]
        self._proc = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._accept()
        self.open(self.copy_path, run_macros=self.run_macros)

    def _accept(self) -> None:
        assert self._listener is not None
        deadline = time.monotonic() + self.startup_timeout
        self._listener.settimeout(_POLL)
        while True:
            self._check_alive("starting")
            try:
                conn, _ = self._listener.accept()
                break
            except socket.timeout:
                if time.monotonic() > deadline:
                    raise RefereeError(
                        f"Referee did not connect within {self.startup_timeout:g}s"
                    ) from None
        conn.settimeout(_POLL)
        self._sock = conn

    def _check_alive(self, doing: str) -> None:
        if self._proc is None or self._proc.poll() is not None:
            code = None if self._proc is None else self._proc.returncode
            raise RefereeError(f"Referee process exited while {doing} (exit code {code})")

    def _kill_group(self) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            # leader gone; sweep stragglers (soffice.bin) in its group
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

    def close(self) -> None:
        """Ask the Referee to quit, then release process, sockets and temp files."""
        if self._sock is not None and self._proc is not None and self._proc.poll() is None:
            try:
                self._send_recv({"cmd": "quit"}, timeout=5.0)
            except Exception:
                pass
        if self._proc is not None:
            if self._proc.poll() is None:
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    pass
            self._kill_group()
        for s in (self._sock, self._listener):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        self._sock = self._listener = None
        self._proc = None
        if self._profile is not None:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._profile = None
        if self.copy_path is not None:
            try:
                self.copy_path.unlink()
            except OSError:
                pass
        if self._owns_job_dir and self.job_dir is not None:
            shutil.rmtree(self.job_dir, ignore_errors=True)

    # -- protocol ---------------------------------------------------------
    def _fail(self, message: str) -> RefereeError:
        self._kill_group()
        return RefereeError(message)

    def _send_recv(self, req: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        if self._sock is None:
            raise RefereeError("Referee is not running")
        timeout = self.command_timeout if timeout is None else timeout
        req = dict(req)
        req["id"] = self._next_id
        self._next_id += 1
        data = (json.dumps(req) + "\n").encode("utf-8")
        deadline = time.monotonic() + timeout
        try:
            self._sock.settimeout(timeout)
            self._sock.sendall(data)
        except OSError as exc:
            raise self._fail(f"Referee connection failed: {exc}") from exc
        self._sock.settimeout(_POLL)
        while b"\n" not in self._buf:
            if self._proc is None or self._proc.poll() is not None:
                code = None if self._proc is None else self._proc.returncode
                raise self._fail(
                    f"Referee process exited during '{req['cmd']}' (exit code {code})"
                )
            if time.monotonic() > deadline:
                raise self._fail(f"Referee timed out after {timeout:g}s on '{req['cmd']}'")
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as exc:
                raise self._fail(f"Referee connection failed: {exc}") from exc
            if not chunk:
                raise self._fail(f"Referee closed the connection during '{req['cmd']}'")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        try:
            resp = json.loads(line.decode("utf-8"))
        except ValueError as exc:
            raise self._fail(f"Referee sent invalid JSON: {exc}") from exc
        if not isinstance(resp, dict):
            raise self._fail("Referee sent a non-object response")
        if not resp.get("ok", False):
            raise RefereeError(f"Referee command '{req['cmd']}' failed: {resp.get('error')}")
        return resp

    # -- commands ---------------------------------------------------------
    def open(self, path: str | os.PathLike[str], run_macros: bool | None = None) -> None:
        rm = self.run_macros if run_macros is None else run_macros
        if rm and not self.run_macros:
            raise RefereeError("run_macros is only allowed for a trusted source")
        self._send_recv({"cmd": "open", "path": str(path), "run_macros": bool(rm)})

    def eval(self, inputs: dict[str, Any], outputs: list[str]) -> dict[str, Any]:
        return self._send_recv({"cmd": "eval", "inputs": inputs, "outputs": list(outputs)})["values"]

    def read(self, cells: list[str]) -> dict[str, Any]:
        return self._send_recv({"cmd": "read", "cells": list(cells)})["values"]

    def macros(self) -> list[dict[str, Any]]:
        return self._send_recv({"cmd": "macros"})["macros"]

    def run_macro(
        self, name: str, inputs: dict[str, Any], outputs: list[str]
    ) -> dict[str, Any]:
        if not self.run_macros:
            raise RefereeError("macros disabled")
        return self._send_recv(
            {"cmd": "run_macro", "name": name, "inputs": inputs, "outputs": list(outputs)}
        )["values"]

    def save_with_vba(self, out: str | os.PathLike[str], modules: dict[str, str]) -> None:
        self._send_recv({"cmd": "save_with_vba", "out": str(out), "modules": modules})

    def quit(self) -> None:
        self.close()
