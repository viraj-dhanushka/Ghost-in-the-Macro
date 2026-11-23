"""Signed-cookie sessions with per-session temp folders and an idle sweeper.

No login. The cookie holds only a random session id plus an HMAC signature.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

COOKIE_NAME = "ghost_session"
DEFAULT_IDLE_TIMEOUT_S = 30 * 60
DEFAULT_SWEEP_INTERVAL_S = 60.0


def sign(secret: bytes, sid: str) -> str:
    mac = hmac.new(secret, sid.encode(), hashlib.sha256).hexdigest()
    return f"{sid}.{mac}"


def unsign(secret: bytes, token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    sid, _, mac = token.partition(".")
    expected = hmac.new(secret, sid.encode(), hashlib.sha256).hexdigest()
    return sid if hmac.compare_digest(mac, expected) else None


@dataclass
class Session:
    sid: str
    folder: Path
    last_seen: float
    # Upload/sample records: {"path": str, "name": str}. Internal only.
    workbook: dict | None = None
    data: dict = field(default_factory=dict)


class SessionStore:
    def __init__(
        self,
        root: Path | None = None,
        secret: bytes | None = None,
        idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root = Path(root) if root else Path(tempfile.mkdtemp(prefix="ghost-sessions-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret = secret or secrets.token_bytes(32)
        self.idle_timeout_s = idle_timeout_s
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        sid = secrets.token_urlsafe(24)
        folder = self.root / sid
        folder.mkdir(parents=True, exist_ok=True)
        s = Session(sid=sid, folder=folder, last_seen=self._clock())
        with self._lock:
            self._sessions[sid] = s
        return s

    def get(self, token: str | None) -> Session | None:
        sid = unsign(self.secret, token)
        if sid is None:
            return None
        with self._lock:
            s = self._sessions.get(sid)
            if s is not None:
                s.last_seen = self._clock()
            return s

    def token(self, session: Session) -> str:
        return sign(self.secret, session.sid)

    def delete(self, sid: str) -> None:
        with self._lock:
            s = self._sessions.pop(sid, None)
        folder = s.folder if s else self.root / sid
        shutil.rmtree(folder, ignore_errors=True)

    def sweep(self) -> list[str]:
        """Delete sessions idle longer than the timeout. Returns removed ids."""
        now = self._clock()
        with self._lock:
            stale = [
                sid for sid, s in self._sessions.items()
                if now - s.last_seen > self.idle_timeout_s
            ]
        for sid in stale:
            self.delete(sid)
        return stale

    def close(self) -> None:
        with self._lock:
            sids = list(self._sessions)
        for sid in sids:
            self.delete(sid)
        shutil.rmtree(self.root, ignore_errors=True)

    def __len__(self) -> int:
        return len(self._sessions)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default
