"""Line-up: run every suspect of a workbook through the Referee and write lineup.json.

Trial by Workbook (Feature 5). A suspect is a foreign `compute()` shipped in `samples/suspects/<workbook>/`.
Each one is verified in Faithful mode against the original workbook recalculated by LibreOffice, on a
temporary migration folder; the result is written to `samples/suspects/<workbook>/lineup.json` and, with the
other workbook's, to `samples/suspects/MEASURED.md`. Nothing is written into a migration's `reports/` folder.

A challenge is `ghost challenge <workbook> --code <suspect> --mapping <pinned> --out <tmp>` run as a subprocess;
this script only builds the workbook and reads the proof report the command wrote. Every label in a suspect's header comes from this measurement.

Usage: scripts/ghost-py scripts/lineup.py [--seed N] [--no-headers] [haunted|discount ...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
SUSPECTS = SAMPLES / "suspects"
DEFAULT_SEED = 20261204
WORKBOOKS = {"haunted": "make_haunted.py", "discount": "make_discount.py"}


def suspects_of(name: str) -> list[str]:
    return sorted(p.stem for p in (SUSPECTS / name).glob("*.py"))


def _build_workbook(name: str, dest: Path) -> Path:
    spec = importlib.util.spec_from_file_location(f"_lineup_{name}", SAMPLES / WORKBOOKS[name])
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SAMPLES))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(SAMPLES))
    return Path(mod.build(dest))


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "ghost.cli", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=600, stdin=subprocess.DEVNULL)


def challenge(name: str, suspect: str, seed: int = DEFAULT_SEED) -> dict:
    """Challenge one suspect with `ghost challenge` and return the verdict as a dict (no paths, no timestamps)."""
    with tempfile.TemporaryDirectory(prefix="ghost-lineup-") as tmp:
        tmp = Path(tmp)
        workbook = _build_workbook(name, tmp / "workbook.xlsx")
        mdir = tmp / "migration"
        proc = _cli("challenge", str(workbook), "--code", str(SUSPECTS / name / f"{suspect}.py"),
                    "--mapping", str(SUSPECTS / name / "mapping.yaml"), "--seed", str(seed), "--out", str(mdir))
        report_path = mdir / "reports" / "faithful" / "proof-report.json"
        if proc.returncode not in (0, 1) or not report_path.is_file():
            raise RuntimeError(f"ghost challenge failed ({proc.returncode}): {proc.stderr.strip()[-400:]}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return _verdict(suspect, proc.returncode, report, proc.stdout)
def _verdict(suspect: str, exit_code: int, report: dict, stdout: str = "") -> dict:
    out = {
        "suspect": suspect,
        "exit_code": exit_code,
        "verdict": (f"no difference found on {report['cases_tested']} cases" if exit_code == 0
                    else "difference found"),
        "cases_tested": report["cases_tested"],
        "cases_generated": report.get("cases_generated"),
        "cases_targeted": report.get("cases_targeted"),
        "distinct_cases": report.get("distinct_cases"),
        "seed": report["seed"],
        "libreoffice": report["versions"]["libreoffice"],
        "counterexample": None,
        "how_found": None,
    }
    if exit_code == 1:
        ms = [m for m in report["mismatches"] if m.get("class") != "expected by decision"]
        m = next((x for x in ms if x.get("minimal") is True), ms[0])
        name = m.get("output") or next(iter(m["expected"]))
        out["counterexample"] = {
            "inputs": {k: str(v) for k, v in sorted(m["inputs"].items())},
            "output": name,
            "cell": m.get("cell"),
            "referee": float(m["expected"][name]),
            "candidate": float(m["actual"][name]),
            "rule_id": m.get("rule_id"),
        }
        # The command says how it found the counterexample; read that line, do not infer it.
        found = re.search(r"found by: (.+)", stdout)
        out["how_found"] = ("not available" if not found else
                            "targeted boundary case, not shrunk" if "not shrunk" in found.group(1) else "shrunk")
    return out


def label_for(entry: dict) -> str:
    """The sentence written in a suspect's header: only what the measurement showed."""
    if entry["exit_code"] == 0:
        text = f"{entry['verdict']} (seed {entry['seed']})."
        # An honest suspect has nothing to catch; any other suspect that passes escaped the Referee, and says so.
        return text if entry["suspect"] == "honest" else f"{text} The planted difference was not caught."
    ce = entry["counterexample"]
    inputs = ", ".join(f"{k}={v}" for k, v in ce["inputs"].items())
    return (f"difference found ({entry['how_found']}) at {inputs}: Referee {ce['referee']!r}, "
            f"suspect {ce['candidate']!r} (seed {entry['seed']}).")


def evaluate(name: str, suspect: str, inputs: dict) -> tuple[float, float]:
    """The Referee's value and the suspect's value for one set of inputs (used to check a counterexample)."""
    sys.path.insert(0, str(ROOT))
    try:
        from ghost.referee.client import RefereeClient
        from ghost.converter.mapping import read_mapping
    finally:
        sys.path.remove(str(ROOT))
    mapping = read_mapping(SUSPECTS / name / "mapping.yaml")
    with tempfile.TemporaryDirectory(prefix="ghost-lineup-eval-") as tmp:
        workbook = _build_workbook(name, Path(tmp) / "workbook.xlsx")
        wire = {mapping.inputs[k].cell: (int(v) if mapping.inputs[k].type == "integer" else float(Decimal(str(v))))
                for k, v in inputs.items()}
        out_name, out_spec = next(iter(mapping.outputs.items()))
        with RefereeClient(None, workbook, run_macros=False, job_dir=tmp) as ref:
            referee = ref.eval(wire, [out_spec.cell])[out_spec.cell]
    spec = importlib.util.spec_from_file_location(f"_suspect_{name}_{suspect}", SUSPECTS / name / f"{suspect}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    typed = {k: (int(v) if mapping.inputs[k].type == "integer" else Decimal(str(v))) for k, v in inputs.items()}
    return float(referee), float(mod.compute(typed)[out_name])


def _write_header_label(path: Path, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Measured result:"):
            lines[i] = f"Measured result: {label}"
            break
    else:
        raise ValueError(f"{path} has no 'Measured result:' line")
    path.write_text("\n".join(lines), encoding="utf-8")


def _measured_md(results: dict[str, dict]) -> str:
    out = ["# Measured line-up",
           "",
           "Written by `scripts/lineup.py` from real Faithful runs against the Referee. Do not edit by hand.",
           ""]
    for name, data in results.items():
        out += [f"## {name} (seed {data['seed']}, {data['libreoffice']})", "",
                "| Suspect | Exit | Result |", "|---|---|---|"]
        for s in data["suspects"]:
            out.append(f"| `{s['suspect']}.py` | {s['exit_code']} | {label_for(s)} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("workbooks", nargs="*", default=sorted(WORKBOOKS))
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--no-headers", action="store_true", help="do not rewrite the 'Measured result:' header lines")
    args = ap.parse_args(argv)
    results: dict[str, dict] = {}
    for name in args.workbooks:
        entries = []
        for suspect in suspects_of(name):
            entry = challenge(name, suspect, args.seed)
            print(f"{name}/{suspect}: exit {entry['exit_code']}  {label_for(entry)}")
            entries.append(entry)
            if not args.no_headers:
                _write_header_label(SUSPECTS / name / f"{suspect}.py", label_for(entry))
        data = {"workbook": name, "seed": args.seed, "libreoffice": entries[0]["libreoffice"], "suspects": entries}
        (SUSPECTS / name / "lineup.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        results[name] = data
    if len(results) == len(WORKBOOKS):
        (SUSPECTS / "MEASURED.md").write_text(_measured_md(results) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
