"""``ghost challenge``: the original workbook referees a rewrite offered by someone else.

Additive: it builds a temporary migration folder around a foreign ``compute()`` and calls the existing
verifier in Faithful mode. It changes no verifier, report schema or other command.

WARNING: this runs the Candidate's code on this machine, with the permissions of this process.
A Candidate that loops will hang the command. Do not challenge code you do not trust.

Exit codes: 0 no difference found, 1 a difference found (both only when a proof report was written),
2 anything else, with one line on standard error giving the reason.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from ghost import cli
from ghost.converter.mapping import generate_mapping, read_mapping, write_mapping
from ghost.rules.spec_writer import write_spec
from ghost.repair_brief import build_brief
from ghost.verifier.run import load_compute

__all__ = ["run_challenge", "EXIT_ERROR"]

EXIT_ERROR = 2
NOT_AVAILABLE = "not available"
_RAISED = "<compute raised "


class ChallengeError(Exception):
    """A reason for exit 2, written as one line."""


def _verify(mdir: Path, **kwargs: Any) -> bool:
    return cli.run_verification(mdir, **kwargs)


def _one_line(text: str, hide: list[str]) -> str:
    line = next((ln for ln in str(text).splitlines() if ln.strip()), "").strip()
    for h in hide:
        if h:
            line = line.replace(h, "<migration>")
    return line[:300]


def _read_candidate(path: Path) -> str:
    if not path.is_file():
        raise ChallengeError(f"candidate file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ChallengeError(f"candidate file cannot be read: {type(exc).__name__}") from exc
    if text.startswith(cli.GENERATED_MARK):
        raise ChallengeError(
            "candidate starts with the generated-code marker; it would be regenerated, not verified as written"
        )
    return text


def _load_candidate(text: str) -> None:
    """Load once to fail early; SystemExit and any exception from the module body are exit 2."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            load_compute(text)
    except SyntaxError as exc:
        raise ChallengeError(f"candidate has a syntax error: {exc.msg} (line {exc.lineno})") from exc
    except SystemExit as exc:
        raise ChallengeError(f"candidate called exit at import (code {exc.code!r})") from exc
    except KeyboardInterrupt as exc:
        raise ChallengeError("candidate raised KeyboardInterrupt at import") from exc
    except ValueError as exc:
        raise ChallengeError(f"candidate does not define a callable compute(inputs): {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - the candidate is foreign code
        raise ChallengeError(f"candidate raised {type(exc).__name__} at import: {exc}") from exc


def _prepare(workbook: Path, mapping_file: Path | None, mdir: Path):
    """Write the migration folder's spec and mapping; return (rules, mapping, mapping_given)."""
    if mapping_file is not None:
        if not mapping_file.is_file():
            raise ChallengeError(f"mapping file not found: {mapping_file}")
        mapping = read_mapping(mapping_file)
        ins = ",".join(s.cell for s in mapping.inputs.values())
        outs = ",".join(s.cell for s in mapping.outputs.values())
        a = cli._analyse(workbook, ins, outs)
        for name, spec in {**mapping.inputs, **mapping.outputs}.items():
            if spec.cell not in a.wb.cells:
                raise ChallengeError(f"mapping: {name} points at {spec.cell}, not in the workbook")
    else:
        a = cli._analyse(workbook)
        mapping = generate_mapping(a.wb, a.roles)  # type: ignore[arg-type]
    write_spec(mdir, a.rules, a.findings)
    cli._write_source(mdir, workbook)
    write_mapping(mapping, mdir / cli.MAPPING_FILE)
    return a.rules, mapping, mapping_file is not None, a.wb


def _describe_mapping(mapping, given: bool) -> list[str]:
    ins = ", ".join(f"{n} ({s.cell})" for n, s in mapping.inputs.items())
    outs = ", ".join(f"{n} ({s.cell})" for n, s in mapping.outputs.items())
    head = ("mapping: given with --mapping" if given else
            "mapping: derived from the workbook; not confirmed by a person")
    return [head, f"  inputs: {ins}", f"  outputs: {outs}"]


def _missing_output(report: dict, outputs: list[str]) -> str | None:
    """The first mapped output name that a mismatch's candidate result lacks or holds as None.
    A naming mistake in the candidate is not a wrong value."""
    for m in report.get("mismatches", []):
        actual = m.get("actual") or {}
        for name in outputs:
            if actual.get(name) is None:
                return name
    return None


def _candidate_text(v: Any) -> str:
    if isinstance(v, str) and v.startswith(_RAISED) and v.endswith(">"):
        return v[len("<compute "):-1]  # "raised ValueError: nope"
    return _fmt(v)


def _pick(report: dict) -> dict:
    ms = [m for m in report.get("mismatches", []) if m.get("class") != "expected by decision"] or report["mismatches"]
    return next((m for m in ms if m.get("minimal") is True), ms[0])


def _fmt(v: Any) -> str:
    return repr(v)


def _verdict_lines(report: dict, rules: list) -> list[str]:
    gen, tgt, dist = report.get("cases_generated"), report.get("cases_targeted"), report.get("distinct_cases")
    lines = [
        "mode: faithful",
        f"cases: {gen} generated, {tgt} targeted, {dist} distinct",
        f"seed {report.get('seed')}; {report.get('versions', {}).get('libreoffice', 'LibreOffice: not checked')}",
        f"Excel cross-check: {(report.get('sanity') or {}).get('status', 'not checked')}",
    ]
    if report["passed"]:
        lines.append(f"result: no difference found on {report['cases_tested']} cases")
        return lines
    m = _pick(report)
    out = m.get("output") or next(iter(m["expected"]))
    shrunk = (report.get("cases_generated") or 0) > 0
    rule_id = m.get("rule_id") or NOT_AVAILABLE
    text = next((r.text for r in rules if r.rule_id == rule_id), NOT_AVAILABLE)
    lines += [
        "result: difference found",
        "  inputs: " + ", ".join(f"{k}={v}" for k, v in sorted(m["inputs"].items())),
        f"  Referee: {_fmt(m['expected'].get(out))}  (output {out}, cell {m.get('cell') or NOT_AVAILABLE})",
        f"  Candidate: {_candidate_text(m['actual'].get(out))}",
        "  found by: " + ("shrunk (generated search)" if shrunk else "targeted boundary case, not shrunk"),
        f"  rule: {rule_id}",
        f"  rule text: {text}",
    ]
    return lines


def _challenge(workbook: Path, code: Path, mapping_file: Path | None, out: Path | None,
               seed: int, cases: int, hide: list[str]) -> tuple[int, list[str]]:
    if not workbook.is_file():
        raise ChallengeError(f"workbook not found: {workbook}")
    text = _read_candidate(code)
    if mapping_file is not None and not mapping_file.is_file():
        raise ChallengeError(f"mapping file not found: {mapping_file}")
    _load_candidate(text)
    if out is not None:
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise ChallengeError(f"--out {out} exists and is not an empty folder")
        mdir = out
        mdir.mkdir(parents=True, exist_ok=True)
        hide += [str(mdir), str(mdir.resolve())]
        return _in_folder(workbook, text, mapping_file, mdir, seed, cases, hide, keep=True)
    with tempfile.TemporaryDirectory(prefix="ghost-challenge-") as tmp:
        hide += [tmp, str(Path(tmp).resolve())]
        return _in_folder(workbook, text, mapping_file, Path(tmp), seed, cases, hide)


def _in_folder(workbook: Path, text: str, mapping_file: Path | None, mdir: Path,
               seed: int, cases: int, hide: list[str], keep: bool = False) -> tuple[int, list[str]]:
    rules, mapping, given, wb = _prepare(workbook, mapping_file, mdir)
    (mdir / cli.LOGIC_FILE).write_text(text, encoding="utf-8", newline="\n")
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            _verify(mdir, mode="faithful", seed=seed, cases=cases, trust_macros=False)
    except SystemExit as exc:
        raise ChallengeError(f"candidate called exit while running (code {exc.code!r})") from exc
    except KeyboardInterrupt as exc:
        raise ChallengeError("candidate raised KeyboardInterrupt while running") from exc
    report_file = mdir / "reports" / "faithful" / "proof-report.json"
    if not report_file.is_file():
        raise ChallengeError("no proof report was written")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if not isinstance(report.get("passed"), bool):
        raise ChallengeError("the proof report has no pass or fail result")
    missing = _missing_output(report, list(mapping.outputs))
    if missing:
        raise ChallengeError(f"candidate did not return output {missing}")
    lines = _describe_mapping(mapping, given) + _verdict_lines(report, rules)
    # The engine writes the repair brief from the proof report (the same content as scripts/repair_brief.py).
    rules_text = (mdir / "rules.md").read_text(encoding="utf-8") if (mdir / "rules.md").is_file() else ""
    brief = build_brief(report, rules_text, lambda cell: (wb.cells[cell].formula if cell in wb.cells else None))
    (mdir / "repair-brief.json").write_text(json.dumps(brief, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if keep:
        lines.append("repair brief: repair-brief.json in the --out folder")
    return (0 if report["passed"] else 1), lines


def run_challenge(args) -> int:
    hide: list[str] = []
    try:
        code, lines = _challenge(
            Path(args.workbook), Path(args.code), Path(args.mapping) if args.mapping else None,
            Path(args.out) if args.out else None, args.seed, args.cases, hide,
        )
    except ChallengeError as exc:
        print(f"ghost: error: {_one_line(str(exc), hide)}", file=sys.stderr)
        return EXIT_ERROR
    except SystemExit as exc:
        print(f"ghost: error: candidate called exit (code {exc.code!r})", file=sys.stderr)
        return EXIT_ERROR
    except BaseException as exc:  # noqa: BLE001 - exit 1 must always mean a report exists
        print(f"ghost: error: {type(exc).__name__}: {_one_line(str(exc), hide)}", file=sys.stderr)
        return EXIT_ERROR
    print(f"challenge: {Path(args.workbook).name} against {Path(args.code).name}")
    print("\n".join(lines))
    return code
