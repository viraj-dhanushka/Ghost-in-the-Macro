"""Single-page flow routes: autopsy, answer findings, verify, proof report.

No business logic here. Analysis, rules, conversion, Decisions and
verification all come from `ghost.*`. This module only turns form input into
calls and engine output into HTML partials. Macros are never enabled and no
macro flag exists in any route.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from ghost.autopsy.metrics import metrics as compute_metrics
from ghost.cli import (
    CliError,
    _analyse,
    cmd_convert,
    cmd_rules,
)
from ghost.converter.emit_python import InvalidPatch
from ghost.converter.mapping import read_mapping
from ghost.converter.subset import find_not_converted
from ghost.decisions.store import DECISIONS_FILE, InvalidDecision, load_decisions, record
from ghost.ingest.limits import IngestError

from .jobs import DONE, FAILED, TERMINAL, Job, JobRunner
from .sessions import Session

SPEC_DIR = "spec"  # per-session Decisions live here; each run gets a fresh copy
KEEP = "keep"
MAX_TEXT = 500


def reset_state(session: Session) -> None:
    """Forget analysis choices and Decisions when a different workbook is loaded."""
    session.data.clear()
    shutil.rmtree(session.folder / SPEC_DIR, ignore_errors=True)


def _spec_dir(session: Session) -> Path:
    d = session.folder / SPEC_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _loc_text(loc) -> str:
    return loc.cell or f"{loc.module}:{loc.line}"


def _finding_options(finding) -> list[dict]:
    """Answers offered for a Finding: keep as is, or change one comparison."""
    ops = sorted({op for _, op in finding.locations})
    options = [{
        "value": KEEP,
        "label": "Keep the original behaviour (reproduce it exactly)",
    }]
    for loc, op in finding.locations:
        if not loc.cell:
            continue  # macro lines cannot be patched
        for other in ops:
            if other != op:
                options.append({
                    "value": f"set|{loc.cell}|{op}|{other}",
                    "label": f"Change {loc.cell} from '{op}' to '{other}'",
                })
    return options


def _describe(session: Session) -> dict:
    wb_info = session.workbook
    inputs = session.data.get("inputs") or ""
    outputs = session.data.get("outputs") or ""
    a = _analyse(wb_info["path"], inputs or None, outputs or None)
    m = compute_metrics(a.wb)
    decisions = load_decisions(_spec_dir(session))
    by_finding = {d.finding_id: d for d in decisions if d.finding_id}
    findings = [
        {
            "id": f.finding_id,
            "cell": f.cell,
            "constant": str(f.constant),
            "locations": [{"where": _loc_text(loc), "op": op} for loc, op in f.locations],
            "options": _finding_options(f),
            "decision": by_finding.get(f.finding_id),
        }
        for f in a.findings
    ]
    in_cells = sorted(r for r, v in a.roles.items() if v in ("INPUT", "PARAMETER"))
    out_cells = sorted(r for r, v in a.roles.items() if v in ("OUTPUT", "INTERMEDIATE"))
    return {
        "name": wb_info["name"],
        "sheets": list(a.wb.sheets),
        "metrics": m,
        "excel_saved": a.wb.excel_saved,
        "inputs": [{"cell": r, "checked": a.roles[r] == "INPUT"} for r in in_cells],
        "outputs": [{"cell": r, "checked": a.roles[r] == "OUTPUT"} for r in out_cells],
        "findings": findings,
        "unanswered": sum(1 for f in findings if f["decision"] is None),
        "decisions": decisions,
        "rules": [{"id": r.rule_id, "text": r.text, "cells": list(r.cells)} for r in a.rules],
        "not_converted": [{"cell": e.cell or "", "reason": e.reason} for e in find_not_converted(a.wb)],
        "not_verifiable": [
            {"cell": f.cell, "kind": f.kind, "detail": f.detail}
            for f in a.wb.features if f.not_verifiable
        ],
    }


def _clean(text: str | None) -> str:
    return (text or "").strip()[:MAX_TEXT]


def _quiet(fn: Callable[[], None]) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        fn()


def prepare_run(session: Session, run_no: int) -> Path:
    """Write the migration directory for one verification run (engine calls only)."""
    wb_info = session.workbook
    mdir = session.folder / f"run-{run_no}"
    shutil.rmtree(mdir, ignore_errors=True)
    mdir.mkdir(parents=True)
    spec_decisions = _spec_dir(session) / DECISIONS_FILE
    if spec_decisions.is_file():
        shutil.copyfile(spec_decisions, mdir / DECISIONS_FILE)
    ns = argparse.Namespace(
        workbook=wb_info["path"],
        migration=str(mdir),
        inputs=session.data.get("inputs") or None,
        outputs=session.data.get("outputs") or None,
        mapping=None,
    )
    try:
        _quiet(lambda: cmd_rules(ns))
        _quiet(lambda: cmd_convert(ns))
        mapping = read_mapping(mdir / "mapping.yaml")
        if not mapping.outputs:
            raise CliError("No output cells are selected. Choose at least one output.")
        if not mapping.inputs:
            raise CliError("No input cells are selected. Choose at least one input.")
    except BaseException:
        shutil.rmtree(mdir, ignore_errors=True)
        raise
    return mdir


def _report_summary(job: Job) -> dict | None:
    raw = job.artifacts.get("proof-report.json")
    if raw is None:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    sanity = d.get("sanity") or {}
    mut = d.get("mutation") or {}
    mutation = None
    if "total" in mut:
        mutation = {
            "killed": mut.get("killed"),
            "total": mut.get("total"),
            "survivors": [
                {"id": m.get("mutant_id"), "operator": m.get("operator"),
                 "location": m.get("location"), "reason": m.get("survivor_reason") or ""}
                for m in mut.get("mutants") or [] if not m.get("killed")
            ],
        }
    return {
        "mutation": mutation,
        "passed": d.get("passed"),
        "mode": d.get("mode"),
        "seed": d.get("seed"),
        "cases_tested": d.get("cases_tested"),
        "mismatches": len(d.get("mismatches") or []),
        "excel_check": sanity.get("status", "not checked"),
        "libreoffice": (d.get("versions") or {}).get("libreoffice", "not checked"),
    }


def build_flow_router(
    runner: JobRunner,
    templates: Jinja2Templates,
    session_of: Callable[[Request], Session | None],
) -> APIRouter:
    router = APIRouter()

    def page(request: Request, name: str, ctx: dict, status: int = 200) -> Response:
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    def need_workbook(request: Request) -> tuple[Session | None, Response | None]:
        s = session_of(request)
        if s is None or s.workbook is None:
            return None, page(request, "_message.html",
                              {"error": "Choose a workbook or a sample first."}, 409)
        return s, None

    async def autopsy_view(request: Request, s: Session, error: str | None = None,
                           status: int = 200) -> Response:
        try:
            ctx = await asyncio.to_thread(_describe, s)
        except (CliError, IngestError) as exc:
            s.data.pop("inputs", None)
            s.data.pop("outputs", None)
            return page(request, "_message.html", {"error": str(exc)}, 422)
        ctx["error"] = error
        return page(request, "_autopsy.html", ctx, status)

    @router.get("/autopsy", response_class=HTMLResponse)
    async def autopsy(request: Request) -> Response:
        s, err = need_workbook(request)
        if err:
            return err
        return await autopsy_view(request, s)

    @router.post("/decision", response_class=HTMLResponse)
    async def decision(request: Request) -> Response:
        s, err = need_workbook(request)
        if err:
            return err
        form = await request.form()
        finding_id = _clean(form.get("finding_id"))
        choice = _clean(form.get("choice"))
        author = _clean(form.get("author"))
        reason = _clean(form.get("reason"))
        try:
            ctx = await asyncio.to_thread(_describe, s)
        except (CliError, IngestError) as exc:
            return page(request, "_message.html", {"error": str(exc)}, 422)
        finding = next((f for f in ctx["findings"] if f["id"] == finding_id), None)
        option = next((o for o in (finding or {}).get("options", []) if o["value"] == choice), None)
        if finding is None or option is None:
            return await autopsy_view(request, s, "Pick one of the offered answers.", 422)
        if finding["decision"] is not None:
            return await autopsy_view(request, s, f"{finding_id} already has a Decision.", 409)
        if choice == KEEP:
            patch: dict = {}
            behaviour = f"Keep the original behaviour for {finding_id}"
        else:
            _, cell, frm, to = choice.split("|")
            patch = {"op": "set_operator", "cell": cell, "from": frm, "to": to}
            behaviour = f"{option['label']} ({finding_id})"
        try:
            record(_spec_dir(s), {
                "finding_id": finding_id,
                "behaviour": behaviour,
                "reason": reason,
                "author": author,
                "date": date.today().isoformat(),
                "patch": patch,
            })
        except InvalidDecision as exc:
            return await autopsy_view(request, s, str(exc), 422)
        return await autopsy_view(request, s)

    @router.post("/verify", response_class=HTMLResponse)
    async def verify(request: Request) -> Response:
        s, err = need_workbook(request)
        if err:
            return err
        form = await request.form()
        ins = [str(v) for v in form.getlist("inputs")]
        outs = [str(v) for v in form.getlist("outputs")]
        if not ins or not outs:
            return page(request, "_message.html", {
                "error": "Confirm at least one input and one output cell before verifying."}, 422)
        # Cell names are validated against the workbook by the engine.
        s.data["inputs"] = ",".join(ins)
        s.data["outputs"] = ",".join(outs)
        run_no = s.data.get("runs", 0) + 1
        s.data["runs"] = run_no
        try:
            mdir = await asyncio.to_thread(prepare_run, s, run_no)
        except (CliError, IngestError, InvalidPatch) as exc:
            return page(request, "_message.html", {"error": str(exc)}, 422)
        job = runner.submit(s.sid, mdir, mode="auto")
        return page(request, "_job.html", _job_ctx(job))

    def _job_ctx(job: Job) -> dict:
        snap = job.snapshot()
        report = _report_summary(job) if job.status in TERMINAL else None
        return {
            "job": snap,
            "tail": snap["events"][-12:],
            "terminal": job.status in TERMINAL,
            "finished": job.status == DONE,
            "failed": job.status == FAILED,
            "report": report,
            "has_module": "logic.py" in job.artifacts,
            "has_intended": "logic_intended.py" in job.artifacts,
        }

    def _owned(request: Request, job_id: str) -> Job | None:
        s = session_of(request)
        return runner.get(job_id, s.sid) if s else None

    @router.get("/run/{job_id}/panel", response_class=HTMLResponse)
    async def panel(request: Request, job_id: str) -> Response:
        job = _owned(request, job_id)
        if job is None:
            return page(request, "_message.html", {"error": "Unknown verification run."}, 404)
        return page(request, "_job.html", _job_ctx(job))

    def _artifact(request: Request, job_id: str, name: str) -> tuple[Job | None, bytes | None]:
        job = _owned(request, job_id)
        return job, (job.artifacts.get(name) if job else None)

    def _download(data: bytes, media: str, filename: str, inline: bool = False) -> Response:
        disp = "inline" if inline else f'attachment; filename="{filename}"'
        headers = {"Content-Disposition": disp, "X-Content-Type-Options": "nosniff"}
        if inline:
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        return Response(data, media_type=media, headers=headers)

    @router.get("/run/{job_id}/report.html")
    async def report_html(request: Request, job_id: str, inline: int = 0) -> Response:
        _, data = _artifact(request, job_id, "proof-report.html")
        if data is None:
            return Response("Report not available.", status_code=404)
        return _download(data, "text/html; charset=utf-8", "proof-report.html", bool(inline))

    @router.get("/run/{job_id}/report.json")
    async def report_json(request: Request, job_id: str) -> Response:
        _, data = _artifact(request, job_id, "proof-report.json")
        if data is None:
            return Response("Report not available.", status_code=404)
        return _download(data, "application/json", "proof-report.json")

    @router.get("/run/{job_id}/module.py")
    async def module_py(request: Request, job_id: str) -> Response:
        _, data = _artifact(request, job_id, "logic.py")
        if data is None:
            return Response("Module not available.", status_code=404)
        return _download(data, "text/x-python; charset=utf-8", "logic.py")

    @router.get("/run/{job_id}/module.zip")
    async def module_zip(request: Request, job_id: str) -> Response:
        job = _owned(request, job_id)
        names = ("logic.py", "logic_intended.py", "excel.py", "mapping.yaml",
                 "rules.md", "decisions.yaml")
        if job is None or "logic.py" not in job.artifacts:
            return Response("Module not available.", status_code=404)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                if n in job.artifacts:
                    z.writestr(n, job.artifacts[n])
        return _download(buf.getvalue(), "application/zip", "ghost-module.zip")

    return router
