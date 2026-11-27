"""Ghost web app skeleton: sessions, upload, sample, health.

No business logic here. Workbook parsing is done by `ghost.ingest`.
Macros are never enabled for anything that enters through this module, and
no macro flag is exposed in any request or response.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ghost.ingest.limits import ACCEPTED_FORMATS, MAX_FILE_BYTES, IngestError, TooManyCells, TooManyFormulas
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient, RefereeError
from ghost.referee.locate import RefereeUnavailable, locate_soffice

from .flow import build_flow_router, over_limit_route, reset_state
from .jobs import JobRunner, build_router as build_jobs_router
from .paths import scrub_paths
from .sessions import (
    COOKIE_NAME,
    DEFAULT_IDLE_TIMEOUT_S,
    DEFAULT_SWEEP_INTERVAL_S,
    Session,
    SessionStore,
)

WEB_DIR = Path(__file__).parent
REPO_ROOT = WEB_DIR.parent
SAMPLES_DIR = REPO_ROOT / "samples"
KIRO_FACTS_PATH = Path(__file__).resolve().parent / "kiro_facts.json"  # written by scripts/kiro_ledger.py; the image has no .kiro/ or docs/

PRIVACY_NOTE = (
    "Your workbook is copied to a temporary folder for this session only and "
    "is deleted when the session ends or after 30 minutes of inactivity. "
    "Macros in uploaded files are never run. No account is needed and no "
    "data is sent to any AI service."
)

# sample id -> (generator script, output file name, label)
SAMPLES: dict[str, tuple[str, str, str]] = {
    "discount": ("make_discount.py", "discount.xlsx", "Discount calculator (generated)"),
    "haunted": ("make_haunted.py", "haunted.xlsx", "Haunted discount calculator (generated)"),
    "scenarios": ("make_scenarios.py", "scenarios.xlsx", "Scenario model (generated)"),
    "macros": ("make_xlsm.py", "discount_vba.xlsm", "Macro workbook (generated)"),
}
# Built through LibreOffice (about 3 s on a Mac), so the bytes are kept for the life of the process.
_CACHED_SAMPLES = {"macros"}
_SAMPLE_CACHE: dict[str, bytes] = {}
_SAMPLE_LOCK = threading.Lock()
MACRO_MEDIA_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.12"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
REFEREE_NEEDED_MESSAGE = "The LibreOffice Referee could not start, so this sample could not be built. Try again in a minute."

SAMPLE_BLURBS: dict[str, str] = {
    "discount": (
        "A discount calculator with quantity, unit price and delivery distance as inputs; "
        "expect a Faithful run with no difference found on the cases tested."
    ),
    "haunted": (
        "The same calculator with one planted inconsistency, where the discount applies at 50 or more "
        "but free delivery only above 50; expect Finding F-001 and a Faithful run with no difference found."
    ),
    "scenarios": (
        "A model with ten tax scenarios that picks the lowest net cost with INDEX and MATCH; "
        "three inputs are checked by default and the other constants stay fixed; "
        "expect a Faithful run with no difference found on the cases tested."
    ),
    "macros": (
        "The discount calculator with a VBA module: Ghost reads the VBA, finds thresholds in it, converts the "
        "formulas it supports and recommends a migration route, but does not translate VBA to Python; "
        "expect a Faithful run with no difference found on the cases tested."
    ),
}
MEASURED_RUNS_FILE = Path(__file__).parent / "measured_runs.json"


def load_measured_runs(path: Path = MEASURED_RUNS_FILE) -> dict[str, dict]:
    """Committed measurements only; a missing or unreadable file shows no durations."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        k: v for k, v in data.items()
        if isinstance(v, dict) and {"seconds", "date", "cases"} <= v.keys()
    } if isinstance(data, dict) else {}


def _run_generator(sample_id: str, dest: Path) -> None:
    """Run the sample's committed generator script and write the workbook at ``dest``."""
    script, _, _ = SAMPLES[sample_id]
    spec = importlib.util.spec_from_file_location(f"_ghost_sample_{sample_id}", SAMPLES_DIR / script)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"Cannot load sample generator {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.build(dest)


def _build_sample(sample_id: str, dest: Path) -> Path:
    """Write the sample at ``dest``. A sample built through LibreOffice is built once per process, under
    a lock so that two requests never start two builds, and a failed build is not kept."""
    dest = Path(dest)
    if sample_id not in _CACHED_SAMPLES:
        _run_generator(sample_id, dest)
        return dest
    with _SAMPLE_LOCK:
        data = _SAMPLE_CACHE.get(sample_id)
        if data is None:
            with tempfile.TemporaryDirectory(prefix="ghost-build-") as tmp:
                built = Path(tmp) / SAMPLES[sample_id][1]
                _run_generator(sample_id, built)
                data = built.read_bytes()
            _SAMPLE_CACHE[sample_id] = data
    dest.write_bytes(data)
    return dest


def _summary(wb, name: str, source: str) -> dict:
    formulas = sum(1 for c in wb.cells.values() if c.formula)
    return {
        "name": name,
        "source": source,
        "sheets": list(wb.sheets),
        "cells": len(wb.cells),
        "formulas": formulas,
        "has_vba": bool(wb.vba_modules) or wb.vba_present,
        "vba_error": (
            f"VBA present but could not be read: {wb.vba_error}" if wb.vba_error else ""
        ),
    }


HEALTH_CACHE_S = 60.0


def _referee_check() -> dict:
    """One-shot Referee start-up check (Requirement 14.5)."""
    try:
        soffice = locate_soffice()
    except RefereeUnavailable as exc:
        return {"available": False, "reason": scrub_paths(str(exc))}
    try:
        with tempfile.TemporaryDirectory(prefix="ghost-health-") as tmp:
            xlsx = _build_sample("discount", Path(tmp) / "health.xlsx")
            with RefereeClient(soffice, xlsx, job_dir=Path(tmp) / "job"):
                pass
    except (RefereeError, OSError, RuntimeError) as exc:
        return {"available": False, "reason": scrub_paths(f"Referee failed to start: {exc}")}
    return {"available": True}


def create_app(
    session_root: Path | None = None,
    idle_timeout_s: float | None = None,
    sweep_interval_s: float = DEFAULT_SWEEP_INTERVAL_S,
    secret: bytes | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    if idle_timeout_s is None:
        idle_timeout_s = float(os.environ.get("GHOST_SESSION_IDLE_S", DEFAULT_IDLE_TIMEOUT_S))
    if secret is None and os.environ.get("GHOST_SESSION_SECRET"):
        secret = os.environ["GHOST_SESSION_SECRET"].encode()
    store = SessionStore(root=session_root, secret=secret, idle_timeout_s=idle_timeout_s, clock=clock)
    runner = JobRunner()
    store.on_delete.append(runner.forget_session)  # delete, sweep and close
    health: dict = {"at": None, "result": None}
    health_lock = threading.Lock()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async def sweeper() -> None:
            while True:
                await asyncio.sleep(sweep_interval_s)
                await asyncio.to_thread(store.sweep)

        task = asyncio.create_task(sweeper())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            store.close()

    app = FastAPI(title="Ghost in the Macro", lifespan=lifespan)
    app.state.sessions = store
    app.state.runner = runner
    app.state.referee_check = _referee_check
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app.state.templates = templates
    static_dir = WEB_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def session_of(request: Request) -> Session | None:
        return store.get(request.cookies.get(COOKIE_NAME))

    app.include_router(build_jobs_router(runner, lambda r: (session_of(r).sid if session_of(r) else None)))
    app.include_router(build_flow_router(runner, templates, session_of))

    def session_for(request: Request) -> tuple[Session, bool]:
        existing = store.get(request.cookies.get(COOKIE_NAME))
        if existing is not None:
            return existing, False
        return store.create(), True

    def attach(response: Response, session: Session, is_new: bool) -> Response:
        if is_new:
            response.set_cookie(
                COOKIE_NAME,
                store.token(session),
                httponly=True,
                samesite="lax",
                secure=os.environ.get("GHOST_COOKIE_SECURE", "") == "1",
            )
        return response

    def respond(request: Request, session: Session, is_new: bool, ok: bool, payload: dict, status: int) -> Response:
        if isinstance(payload.get("error"), str):
            payload = {**payload, "error": scrub_paths(payload["error"])}
        if request.headers.get("hx-request"):
            if ok:
                resp: Response = templates.TemplateResponse(
                    request, "_upload_result.html", {"ok": ok, **payload}, status_code=status
                )
            elif payload.get("route"):
                resp = templates.TemplateResponse(
                    request, "_route_card.html", {"error": payload.get("error", ""), "route": payload["route"]},
                    status_code=status,
                )
            else:
                kind = {404: "not_found", 503: "referee_unavailable"}.get(status, "file_rejected")
                resp = templates.TemplateResponse(
                    request, "_message.html", {"error": payload.get("error", ""), "kind": kind},
                    status_code=status,
                )
        else:
            resp = JSONResponse({"ok": ok, **payload}, status_code=status)
        return attach(resp, session, is_new)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        accept = request.headers.get("accept", "")
        if exc.status_code == 404 and ("text/html" in accept or request.headers.get("hx-request")):
            return templates.TemplateResponse(
                request, "404.html", {"error": "The page you asked for was not found."},
                status_code=404,
            )
        return await http_exception_handler(request, exc)

    @app.get("/kiro", response_class=HTMLResponse)
    async def built_with_kiro(request: Request) -> Response:
        """The "Built with Kiro" page: numbers counted by scripts/kiro_ledger.py, read from one JSON file. No session."""
        try:
            facts = json.loads(KIRO_FACTS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            facts = None
        return templates.TemplateResponse(request, "kiro.html", {"facts": facts})

    @app.get("/healthz")
    async def healthz() -> Response:
        def check() -> dict:
            with health_lock:  # one check at a time, cached for 60 s
                now = time.monotonic()
                if health["at"] is None or now - health["at"] > HEALTH_CACHE_S:
                    health["result"] = app.state.referee_check()
                    health["at"] = now
                return health["result"]

        referee = await asyncio.to_thread(check)
        ok = referee["available"]
        return JSONResponse(
            {"status": "ok" if ok else "unavailable", "referee": referee},
            status_code=200 if ok else 503,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Response:
        session, is_new = session_for(request)
        resp = templates.TemplateResponse(
            request,
            "index.html",
            {
                "privacy_note": PRIVACY_NOTE,
                "samples": {k: v[2] for k, v in SAMPLES.items()},
                "sample_blurbs": SAMPLE_BLURBS,
                "measured_runs": load_measured_runs(),
                "max_mb": MAX_FILE_BYTES // (1024 * 1024),
                "accepted": ", ".join(ACCEPTED_FORMATS),
            },
        )
        return attach(resp, session, is_new)

    @app.get("/sample/{sample_id:path}/workbook")
    async def sample_workbook(request: Request, sample_id: str) -> Response:
        if sample_id not in SAMPLES:
            return templates.TemplateResponse(
                request,
                "_failure_card.html",
                {"kind": "not_found", "message": "That sample was not found."},
                status_code=404,
            )
        _, fname, _ = SAMPLES[sample_id]

        def build() -> bytes:
            # Temporary directory only; read into memory so it is gone before we respond.
            with tempfile.TemporaryDirectory(prefix="ghost-dl-") as tmp:
                dest = Path(tmp) / fname
                _build_sample(sample_id, dest)
                return dest.read_bytes()

        try:
            data = await asyncio.to_thread(build)
        except (RefereeUnavailable, RefereeError):
            return templates.TemplateResponse(
                request,
                "_failure_card.html",
                {"kind": "referee_unavailable", "message": REFEREE_NEEDED_MESSAGE},
                status_code=503,
            )
        except IngestError as exc:
            return templates.TemplateResponse(
                request,
                "_failure_card.html",
                {"kind": "error", "message": scrub_paths(str(exc))},
                status_code=422,
            )
        return Response(
            content=data,
            media_type=MACRO_MEDIA_TYPE if fname.endswith(".xlsm") else XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile = File(...)) -> Response:
        session, is_new = session_for(request)
        # Fixed server-side name: the client file name is never used as a path.
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ACCEPTED_FORMATS:
            suffix = ".bin"
        dest = session.folder / f"upload{suffix}"
        size = 0
        too_big = False
        with dest.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    too_big = True
                    break
                fh.write(chunk)
        display = os.path.basename(file.filename or "upload")
        if too_big:
            dest.unlink(missing_ok=True)
            msg = (f"File is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MB limit: too large for the public demo; "
                   "run Ghost locally with: ghost route <file>")
            return respond(request, session, is_new, False, {"error": msg}, 413)
        try:
            # Uploads are read statically; macros are never executed.
            wb = await asyncio.to_thread(load_workbook, str(dest))
        except (TooManyCells, TooManyFormulas) as exc:
            # Under the byte cap but over a limit: show the route from the measured sizes, not a bare error.
            payload: dict = {"error": str(exc)}
            try:
                payload["route"] = await asyncio.to_thread(over_limit_route, dest)
            except IngestError:
                pass
            dest.unlink(missing_ok=True)
            return respond(request, session, is_new, False, payload, 422)
        except IngestError as exc:
            dest.unlink(missing_ok=True)
            return respond(request, session, is_new, False, {"error": str(exc)}, 422)
        except Exception:  # noqa: BLE001 - a malformed file must never become a 500 or leak internals
            dest.unlink(missing_ok=True)
            return respond(request, session, is_new, False,
                           {"error": "The file could not be read as a workbook; rejected."}, 422)
        reset_state(session)
        session.workbook = {"path": str(dest), "name": display, "source": "upload"}
        return respond(request, session, is_new, True, {"workbook": _summary(wb, display, "upload")}, 200)

    @app.post("/sample/{sample_id}")
    async def sample(request: Request, sample_id: str) -> Response:
        session, is_new = session_for(request)
        if sample_id not in SAMPLES:
            return respond(request, session, is_new, False, {"error": f"Unknown sample '{sample_id}'."}, 404)
        _, fname, _ = SAMPLES[sample_id]
        dest = session.folder / fname
        try:
            await asyncio.to_thread(_build_sample, sample_id, dest)
            wb = await asyncio.to_thread(load_workbook, str(dest))
        except (RefereeUnavailable, RefereeError):
            return respond(request, session, is_new, False, {"error": REFEREE_NEEDED_MESSAGE}, 503)
        except IngestError as exc:
            return respond(request, session, is_new, False, {"error": str(exc)}, 422)
        reset_state(session)
        session.workbook = {"path": str(dest), "name": fname, "source": "sample"}
        return respond(request, session, is_new, True, {"workbook": _summary(wb, fname, "sample")}, 200)

    @app.delete("/session")
    async def end_session(request: Request) -> Response:
        session = store.get(request.cookies.get(COOKIE_NAME))
        if session is not None:
            store.delete(session.sid)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE_NAME)
        return resp

    return app


app = create_app()
