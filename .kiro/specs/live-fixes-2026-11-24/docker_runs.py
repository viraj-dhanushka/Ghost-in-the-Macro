"""Task 7.4: drive the local Docker container with curl and a cookie jar, one request at a time.
Run from the repo root with the container already up (see tasks.md 7.4):
  .venv/bin/python .kiro/specs/live-fixes-2026-11-24/docker_runs.py [outdir] [base_url]
Reads the pre-checked boxes from GET /autopsy and never chooses boxes. Compares each run with
repro_web_runs.results.json (task 7.3, LibreOffice 26.8.3). Changes no code.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from repro_web_runs import BOX, make_workbooks  # noqa: E402  (workbook builders + box regex)
import html as htmlmod  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="ghost-74-"))
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:18090"
OUT.mkdir(parents=True, exist_ok=True)
POLL_TIMEOUT_S = 900


def curl(jar: Path, method: str, path: str, *data: str, files: str | None = None, save: Path | None = None):
    cmd = ["curl", "-s", "-S", "-b", str(jar), "-c", str(jar), "-X", method, "-w", "\n%{http_code}"]
    for d in data:
        cmd += ["--data-urlencode", d]
    if files:
        cmd += ["-F", f"file=@{files}"]
    cmd.append(BASE + path)
    p = subprocess.run(cmd, capture_output=True, timeout=120)
    body, _, code = p.stdout.rpartition(b"\n")
    if save is not None and code.strip() == b"200":
        save.write_bytes(body)
    return int(code or 0), body.decode("utf-8", "replace")


def boxes(page: str) -> dict:
    out = {"inputs": [], "outputs": []}
    off = {"inputs": [], "outputs": []}
    for kind, value, rest in BOX.findall(page):
        value = htmlmod.unescape(value)
        off[kind].append(value)
        if "checked" in rest:
            out[kind].append(value)
    return {"checked": out, "offered": off}


def summarize(d: dict) -> dict:
    mut = d.get("mutation") or {}
    return {
        "mode": d.get("mode"), "passed": d.get("passed"),
        "mismatches": [{k: m.get(k) for k in ("cell", "inputs", "expected", "actual", "class")}
                       for m in d.get("mismatches", [])],
        "cases_tested": d.get("cases_tested"), "cases_generated": d.get("cases_generated"),
        "cases_targeted": d.get("cases_targeted"), "distinct_cases": d.get("distinct_cases"),
        "mutation": {"killed": mut.get("killed"), "total": mut.get("total")},
        "survivors": sorted(f'{m.get("operator")}@{m.get("location")}' for m in mut.get("mutants", [])
                            if not m.get("killed")),
        "boundaries": d.get("boundaries"), "boundary_notes": d.get("boundary_notes"),
        "not_converted": d.get("not_converted"),
        "sanity": (d.get("sanity") or {}).get("status"),
        "libreoffice": (d.get("versions") or {}).get("libreoffice"),
    }


def run_one(label: str, upload: Path | None = None, sample: str | None = None, decide: bool = False) -> dict:
    slug = re.sub(r"\W+", "_", label)
    d = OUT / slug
    d.mkdir(exist_ok=True)
    jar = d / "cookies.txt"
    jar.unlink(missing_ok=True)
    res: dict = {"label": label}
    if sample:
        code, body = curl(jar, "POST", f"/sample/{sample}")
    else:
        code, body = curl(jar, "POST", "/upload", files=str(upload))
    res["upload_status"] = code
    if code != 200:
        res["error"] = body[:300]
        return res
    code, page = curl(jar, "GET", "/autopsy")
    res["autopsy_status"] = code
    if decide:
        code, body = curl(jar, "POST", "/decision", "finding_id=F-001", "choice=set|Calculator!B9|>|>=",
                          "author=docker-run", "reason=D-001 bulk means 50 or more")
        res["decision_status"] = code
        code, page = curl(jar, "GET", "/autopsy")
        res["decision_recorded"] = "D-001" in page
    b = boxes(page)
    res["default_boxes"] = b["checked"]
    res["offered_boxes"] = b["offered"]
    code, body = curl(jar, "POST", "/verify",
                      *[f"inputs={v}" for v in b["checked"]["inputs"]],
                      *[f"outputs={v}" for v in b["checked"]["outputs"]])
    res["verify_status"] = code
    if code != 200 or "/run/" not in body:
        res["error"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))[:400]
        return res
    job_id = body.split("/run/")[1].split("/")[0]
    res["job_id"] = job_id
    t0 = time.time()
    snap: dict = {}
    while time.time() - t0 < POLL_TIMEOUT_S:
        code, jb = curl(jar, "GET", f"/jobs/{job_id}")
        snap = json.loads(jb) if code == 200 else {}
        if snap.get("status") in ("done", "failed", "cancelled", "timeout", "error"):
            break
        time.sleep(3)
    res["job_status"] = snap.get("status")
    res["job_error"] = snap.get("error")
    res["job_events_tail"] = (snap.get("events") or [])[-6:]
    res["job_seconds"] = round(time.time() - t0, 1)
    for kind in ("json", "html"):
        code, _ = curl(jar, "GET", f"/run/{job_id}/report.{kind}", save=d / f"proof-report.{kind}")
        res[f"report_{kind}_status"] = code
    code, _ = curl(jar, "GET", f"/run/{job_id}/report.json?mode=faithful", save=d / "proof-report-faithful.json")
    res["faithful_report_json_status"] = code
    if res["report_json_status"] == 200:
        res["report"] = summarize(json.loads((d / "proof-report.json").read_text()))
    if code == 200:
        res["faithful_report"] = summarize(json.loads((d / "proof-report-faithful.json").read_text()))
    curl(jar, "GET", f"/run/{job_id}/report.html?mode=faithful", save=d / "proof-report-faithful.html")
    return res


def diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    return [] if a == b else [f"{path}: local={json.dumps(a)[:200]} docker={json.dumps(b)[:200]}"]


def main() -> None:
    results = []
    code, body = curl(OUT / "health.txt", "GET", "/healthz")
    results.append({"label": "healthz", "status": code, "body": json.loads(body) if code in (200, 503) else body})
    results.append(run_one("haunted", sample="haunted", decide=True))
    wbs = make_workbooks(OUT)
    for label, p in wbs.items():
        results.append(run_one(label, upload=p))
    results.append(run_one("scenarios sample", sample="scenarios"))
    local = {r["label"]: r for r in json.loads((HERE / "repro_web_runs.results.json").read_text())}
    keys = ("upload_status", "autopsy_status", "default_boxes", "offered_boxes", "verify_status",
            "job_status", "faithful_report_json_status", "report")
    for r in results:
        l = local.get(r["label"])
        if l:
            r["diff_vs_local_26.8.3"] = diff({k: l.get(k) for k in keys}, {k: r.get(k) for k in keys})
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))
    print("OUTDIR", OUT)


if __name__ == "__main__":
    main()
