"""Task 7.3: L-02..L-05 repro workbooks and the scenarios sample through the web app.

Run from the repo root:  .venv/bin/python .kiro/specs/live-fixes-2026-11-24/repro_web_runs.py [outdir]
Uses FastAPI TestClient and real LibreOffice. The boxes are read from GET /autopsy (the
pre-checked ones) and are never chosen here. Writes results.json and each run's reports
into outdir (default: a temp folder). Changes no code.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from web.app import create_app  # noqa: E402

TIMEOUT_S = 600
BOX = re.compile(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>')


def book(path: Path, cells: dict, names=()) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Calc"
    for ref, value in cells.items():
        ws[ref] = value
    for name, target in names:
        wb.defined_names[name] = DefinedName(name, attr_text=target)
    wb.save(path)
    return path


def make_workbooks(d: Path) -> dict[str, Path]:
    idx = {"A1": "Amount", "B1": 4, "B2": "=B1*2", "M1": 7, "M2": 8, "M3": 9, "B4": "=INDEX(M1:M1,0)"}
    return {
        "L-02 sem_index": book(d / "sem_index.xlsx", idx),
        "L-03 sem_index + B3": book(d / "sem_index_b3.xlsx", {**idx, "B3": "=INDEX(M1:M3,0)"}),
        "L-04 tier": book(d / "tier.xlsx", {
            "A2": "Quantity", "B2": 3, "A3": "Price", "B3": 25.5,
            "A4": "Total", "B4": "=B2*B3", "A5": "Tier", "B5": '=IF(B4>=500,"Gold","Standard")'}),
        "L-05 sem_names": book(d / "sem_names.xlsx", {
            "A2": "Quantity", "B2": 30, "D1": "Bulk level", "E1": 50,
            "C2": "=Bulk*2", "C3": '=IF(B2>=Bulk,"bulk","small")', "C4": "=Dyn*2"},
            names=(("Bulk", "Calc!$E$1"), ("Dyn", "OFFSET(Calc!$E$1,0,0)"))),
    }


def boxes(page: str) -> dict:
    out = {"offered": {"inputs": [], "outputs": []}, "checked": {"inputs": [], "outputs": []}}
    for kind, value, rest in BOX.findall(page):
        value = htmlmod.unescape(value)
        out["offered"][kind].append(value)
        if "checked" in rest:
            out["checked"][kind].append(value)
    return out


def run_one(label: str, root: Path, upload: Path | None = None, sample: str | None = None) -> dict:
    app = create_app(session_root=root / "sessions")
    c = TestClient(app)
    if sample:
        r = c.post(f"/sample/{sample}")
    else:
        r = c.post("/upload", files={"file": (upload.name, upload.read_bytes(), "application/octet-stream")})
    res: dict = {"label": label, "upload_status": r.status_code}
    if r.status_code != 200:
        res["error"] = r.text[:300]
        return res
    page = c.get("/autopsy")
    res["autopsy_status"] = page.status_code
    b = boxes(page.text)
    res["default_boxes"] = b["checked"]
    res["offered_boxes"] = b["offered"]
    r = c.post("/verify", data={"inputs": b["checked"]["inputs"], "outputs": b["checked"]["outputs"]})
    res["verify_status"] = r.status_code
    if r.status_code != 200:
        res["error"] = re.sub(r"<[^>]+>", " ", r.text)[:400]
        return res
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, TIMEOUT_S)
    res["job_status"] = job.status
    res["job_error"] = job.error
    res["job_events_tail"] = list(job.events[-6:])
    panel = c.get(f"/run/{job_id}/panel").text
    res["panel_text"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", panel)).strip()[:600]
    out = root / re.sub(r"\W+", "_", label)
    out.mkdir(exist_ok=True)
    for kind, url in (("json", "report.json"), ("html", "report.html")):
        d = c.get(f"/run/{job_id}/{url}")
        res[f"report_{kind}"] = {"status": d.status_code, "bytes": len(d.content)}
        if d.status_code == 200:
            (out / f"proof-report.{kind}").write_bytes(d.content)
    jr = c.get(f"/run/{job_id}/report.json")
    if jr.status_code == 200:
        d = json.loads(jr.content)
        mut = d.get("mutation") or {}
        res["report"] = {
            "mode": d.get("mode"), "passed": d.get("passed"),
            "mismatches": [{k: m.get(k) for k in ("cell", "inputs", "expected", "actual", "class")}
                           for m in d.get("mismatches", [])],
            "cases_tested": d.get("cases_tested"), "cases_generated": d.get("cases_generated"),
            "cases_targeted": d.get("cases_targeted"), "distinct_cases": d.get("distinct_cases"),
            "mutation": {"killed": mut.get("killed"), "total": mut.get("total"),
                         "status": mut.get("status"), "raw_keys": sorted(mut)[:8]},
            "survivors": [{"id": m.get("mutant_id"), "op": m.get("operator"), "loc": m.get("location"),
                           "reason": m.get("survivor_reason")} for m in mut.get("mutants", [])
                          if not m.get("killed")],
            "boundaries": d.get("boundaries"),
            "boundary_notes": d.get("boundary_notes"),
            "not_converted": d.get("not_converted"),
            "sanity": (d.get("sanity") or {}).get("status"),
            "libreoffice": (d.get("versions") or {}).get("libreoffice"),
        }
    # The Faithful report of a two-mode run, when there is one.
    fj = c.get(f"/run/{job_id}/report.json?mode=faithful")
    res["faithful_report_json_status"] = fj.status_code
    return res


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="ghost-73-"))
    root.mkdir(parents=True, exist_ok=True)
    wbs = make_workbooks(root)
    results = [run_one(label, root, upload=p) for label, p in wbs.items()]
    results.append(run_one("scenarios sample", root, sample="scenarios"))
    (root / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))
    print("OUTDIR", root)


if __name__ == "__main__":
    main()
