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
import hashlib
import io
import logging
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
    require_verifiable_outputs,
)
from ghost.converter.emit_python import InvalidPatch
from ghost.autopsy.classify import cell_label, not_offerable_outputs
from ghost.router import DEFAULT_THRESHOLDS, ThresholdError, load_thresholds, recommend_route, with_atx_command
from ghost.converter.mapping import read_mapping
from ghost.converter.subset import find_not_converted
from ghost.decisions.store import DECISIONS_FILE, InvalidDecision, load_decisions, record
from ghost.ingest.limits import IngestError
from ghost.report.html import describe_cases

from .jobs import DONE, FAILED, TIMEOUT, SESSION_BUSY_MESSAGE, TERMINAL, Job, JobRunner, SessionBusy
from .paths import scrub_paths
from .autopsy_view import checkbox_text, consequence, finding_title, formula_segments, route_view, vba_blocks, vba_notice
from .progress import rail_context
from .verdict import build_verdict, verdict_text  # noqa: F401  (verdict_text is re-exported)
from .sessions import Session

SPEC_DIR = "spec"  # per-session Decisions live here; each run gets a fresh copy
KEEP = "keep"
MAX_TEXT = 500


def reset_state(session: Session) -> None:
    """Forget analysis choices and Decisions when a different workbook is loaded."""
    session.data.clear()
    session.analysis_cache = None
    shutil.rmtree(session.folder / SPEC_DIR, ignore_errors=True)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _analysis(session: Session):
    """Parsed workbook and analysis, cached once per session (R-17).

    The key is the workbook path, its sha256 and the confirmed inputs and
    outputs (thresholds are recomputed when those change). Decisions are not
    part of the analysis: they are read from the session's spec folder on each
    call, so their state is never stale.
    """
    path = session.workbook["path"]
    if not Path(path).is_file():
        session.analysis_cache = None
        return _analyse(path)  # raises the engine's "workbook not found"
    key = (path, _sha256(path), session.data.get("inputs") or "",
           session.data.get("outputs") or "")
    cached = session.analysis_cache
    if cached is not None and cached[0] == key:
        return cached[1]
    a = _analyse(path, key[2] or None, key[3] or None)
    session.analysis_cache = (key, a)  # replaces any older entry: one per session
    return a


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


def _choice_view(wb, ref: str, checked: bool, as_input: bool) -> dict:
    """An input or output choice: the address, whether it is pre-checked, and the text beside the box."""
    cell = wb.cells.get(ref)
    label = cell_label(wb, ref)
    value = cell.value if (as_input and cell is not None and cell.formula is None) else None
    formula = cell.formula if (not as_input and cell is not None) else None
    return {"cell": ref, "checked": checked, "label": label, "value": value, "formula": formula,
            "text": checkbox_text(ref, label, value=value, formula=formula)}
def _location_view(wb, finding, loc, op: str) -> dict:
    """One Finding location for the template: a cell shows its formula, a macro line shows module and line."""
    cell = wb.cells.get(loc.cell) if loc.cell else None
    formula = cell.formula if cell is not None and cell.formula else None
    return {
        "where": _loc_text(loc), "op": op, "cell": loc.cell or None, "module": loc.module, "line": loc.line,
        "formula": formula,
        "segments": formula_segments(formula, op, str(finding.constant)) if formula else None,
    }
def _vba_dicts(wb) -> list[dict]:
    return [{"name": v.name, "source": v.source, "line_count": v.line_count} for v in wb.vba_modules]


def _route_for(metrics):
    """The router's recommendation for the autopsy metrics. The image ships the thresholds file (one negated
    .dockerignore pattern); the built-in defaults are still used if it cannot be read, and a test pins that they
    equal the file. No workbook path is passed, so the suggested command carries a placeholder."""
    try:
        thresholds = load_thresholds()
    except ThresholdError as exc:  # missing in the image; also hides a broken file in development, so say so
        logging.getLogger("ghost.web").warning("routing thresholds not read, using the built-in defaults: %s", exc)
        thresholds = DEFAULT_THRESHOLDS
    return with_atx_command(recommend_route(metrics, thresholds=thresholds))


WEB_COUNT_TIMEOUT_S = 5.0  # a hostile upload cannot hold the public app for the full 60 s while it is counted


def over_limit_route(path) -> dict:
    """The route card for a workbook that is over a limit, from measured sizes; the workbook is not loaded.
    No server path is in it: the suggested command carries the fixed placeholder."""
    from ghost.ingest.limits import Limits
    from ghost.ingest.triage import scan_sizes
    from ghost.router import route_for_sizes
    try:
        thresholds = load_thresholds()
    except ThresholdError:
        thresholds = DEFAULT_THRESHOLDS
    route = with_atx_command(route_for_sizes(scan_sizes(path, Limits(timeout_s=WEB_COUNT_TIMEOUT_S)), thresholds), None, thresholds.transform_definition)
    view = route_view(route)
    view["parts"] = list(route.parts)
    return view


def _describe(session: Session) -> dict:
    wb_info = session.workbook
    a = _analysis(session)
    m = compute_metrics(a.wb)
    decisions = load_decisions(_spec_dir(session))
    by_finding = {d.finding_id: d for d in decisions if d.finding_id}
    findings = []
    for f in a.findings:
        locations = [_location_view(a.wb, f, loc, op) for loc, op in f.locations]
        findings.append({
            "id": f.finding_id,
            "kind": f.kind,
            "title": finding_title(f.kind),
            "cell": f.cell,
            "constant": str(f.constant),
            "locations": locations,
            "consequence": consequence(str(f.constant), f.cell, locations),
            "options": _finding_options(f),
            "decision": by_finding.get(f.finding_id),
        })
    in_cells = sorted(r for r, v in a.roles.items() if v in ("INPUT", "PARAMETER"))
    not_offered = not_offerable_outputs(a.wb)
    out_cells = sorted(
        r for r, v in a.roles.items()
        if v in ("OUTPUT", "INTERMEDIATE") and r not in not_offered
    )
    return {
        "name": wb_info["name"],
        "sheets": list(a.wb.sheets),
        "metrics": m,
        "excel_saved": a.wb.excel_saved,
        "vba_error": f"VBA present but could not be read: {a.wb.vba_error}" if a.wb.vba_error else "",
        "inputs": [_choice_view(a.wb, r, a.roles[r] == "INPUT", as_input=True) for r in in_cells],
        "outputs": [_choice_view(a.wb, r, a.roles[r] == "OUTPUT", as_input=False) for r in out_cells],
        "findings": findings,
        "unanswered": sum(1 for f in findings if f["decision"] is None),
        "decisions": decisions,
        "vba_blocks": vba_blocks(_vba_dicts(a.wb)),
        "vba_notice": vba_notice(_vba_dicts(a.wb)),
        "route": route_view(_route_for(m)),
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


def _mutation_block(job: Job) -> dict | None:
    """The finished job's proof-report `mutation` object, or None (presentation only)."""
    if job.status != DONE:
        return None
    raw = job.artifacts.get("proof-report.json")
    if raw is None:
        return None
    try:
        block = json.loads(raw).get("mutation")
    except ValueError:
        return None
    return block if isinstance(block, dict) else None


def _load_report(job: Job) -> dict | None:
    """The job's parsed proof-report.json, or None when it is missing or not a JSON object."""
    raw = job.artifacts.get("proof-report.json")
    if raw is None:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    return d if isinstance(d, dict) else None
def _report_summary(job: Job) -> dict | None:
    d = _load_report(job)
    if d is None:
        return None
    sanity = d.get("sanity") if isinstance(d.get("sanity"), dict) else {}
    mut = d.get("mutation") if isinstance(d.get("mutation"), dict) else {}
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
        "verdict_text": verdict_text(d),
        "mode": d.get("mode"),
        "seed": d.get("seed"),
        "cases_tested": d.get("cases_tested"),
        "cases_text": describe_cases(d) if d.get("cases_tested") is not None else "not checked",
        "mismatches": len(d["mismatches"]) if isinstance(d.get("mismatches"), list) else 0,
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
        # R-21: no server paths in text shown to the browser.
        for key in ("error", "vba_error"):
            if isinstance(ctx.get(key), str):
                ctx = {**ctx, key: scrub_paths(ctx[key])}
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    def need_workbook(request: Request) -> tuple[Session | None, Response | None]:
        s = session_of(request)
        if s is None or s.workbook is None:
            return None, page(request, "_message.html",
                              {"error": "Choose a workbook or a sample first.",
                               "kind": "session_expired"}, 409)
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
        active = runner.active_job(s.sid)
        if active is not None:
            return _busy(request, active)
        # L-05: a not-converted or not-verifiable output is rejected, naming cell and reason.
        try:
            a = await asyncio.to_thread(_analysis, s)
            require_verifiable_outputs(a.wb, [o.replace("$", "").replace("'", "") for o in outs])
        except (CliError, IngestError) as exc:
            return page(request, "_message.html", {"error": str(exc)}, 422)
        # Cell names are validated against the workbook by the engine.
        s.data["inputs"] = ",".join(ins)
        s.data["outputs"] = ",".join(outs)
        run_no = s.data.get("runs", 0) + 1
        s.data["runs"] = run_no
        try:
            mdir = await asyncio.to_thread(prepare_run, s, run_no)
        except (CliError, IngestError, InvalidPatch) as exc:
            return page(request, "_message.html", {"error": str(exc)}, 422)
        try:
            job = runner.submit(s.sid, mdir, mode="auto")
        except SessionBusy as busy:  # lost a race with another request
            shutil.rmtree(mdir, ignore_errors=True)
            return _busy(request, busy.job)
        return _job_page(request, job)

    def _busy(request: Request, active: Job) -> Response:
        """429: say why, and keep showing the job that is already active."""
        return page(request, "_busy.html",
                    {"error": SESSION_BUSY_MESSAGE, **_job_ctx(active)}, 429)

    def _job_page(request: Request, job: Job) -> Response:
        """Job panel; a failed or timed-out job without a report renders a Failure_Card."""
        ctx = _job_ctx(job)
        if ctx["terminal"] and not ctx["report"] and job.status in (FAILED, TIMEOUT):
            msg = job.error or "Verification did not produce a report."
            low = msg.lower()
            if job.status == TIMEOUT:
                kind = "job_timed_out"
            elif "referee" in low or "soffice" in low:
                kind = "referee_unavailable"
            else:
                kind = "job_failed"
            return page(request, "_message.html", {"error": msg, "kind": kind, "rail": ctx["rail"]})
        return page(request, "_job.html", ctx)

    def _job_ctx(job: Job) -> dict:
        snap = job.snapshot()
        report = _report_summary(job) if job.status in TERMINAL else None
        parsed = _load_report(job) if job.status in TERMINAL else None
        return {
            "job": snap,
            "rail": rail_context(snap["events"], job.status, _mutation_block(job)),
            "terminal": job.status in TERMINAL,
            "finished": job.status == DONE,
            "failed": job.status == FAILED,
            "report": report,
            "verdict": build_verdict(parsed) if parsed is not None else None,
            "has_module": "logic.py" in job.artifacts,
            "has_intended": "logic_intended.py" in job.artifacts,
            "has_faithful_report": "faithful/proof-report.html" in job.artifacts,
        }

    def _report_key(mode: str, name: str) -> str | None:
        """Artifact name for ``?mode=``: none/"" is the main report, "faithful" the Faithful one."""
        if mode == "":
            return name
        return f"faithful/{name}" if mode == "faithful" else None

    def _owned(request: Request, job_id: str) -> Job | None:
        s = session_of(request)
        return runner.get(job_id, s.sid) if s else None

    @router.get("/run/{job_id}/panel", response_class=HTMLResponse)
    async def panel(request: Request, job_id: str) -> Response:
        job = _owned(request, job_id)
        if job is None:
            return page(request, "_message.html", {"error": "Unknown verification run.", "kind": "not_found"}, 404)
        return _job_page(request, job)

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
    async def report_html(request: Request, job_id: str, inline: int = 0, mode: str = "") -> Response:
        key = _report_key(mode, "proof-report.html")
        _, data = _artifact(request, job_id, key) if key else (None, None)
        if data is None:
            return Response("Report not available.", status_code=404)
        fname = "proof-report-faithful.html" if mode == "faithful" else "proof-report.html"
        return _download(data, "text/html; charset=utf-8", fname, bool(inline))

    @router.get("/run/{job_id}/report.json")
    async def report_json(request: Request, job_id: str, mode: str = "") -> Response:
        key = _report_key(mode, "proof-report.json")
        _, data = _artifact(request, job_id, key) if key else (None, None)
        if data is None:
            return Response("Report not available.", status_code=404)
        fname = "proof-report-faithful.json" if mode == "faithful" else "proof-report.json"
        return _download(data, "application/json", fname)

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
