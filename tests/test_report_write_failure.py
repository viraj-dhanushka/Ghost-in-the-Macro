"""L-02 (task 3.3): a job that fails for a reason other than mismatches says so.

The CLI keeps exit 1 for "mismatches not explained by a Decision" and uses
``EXIT_REPORT_NOT_WRITTEN`` (4) when the proof report could not be written,
printing ``ghost: error: <ExceptionType>: <message>``. The web panel maps exit 4,
an uncaught Python traceback (which also exits 1) and a ``ghost: error:`` line to
"The report could not be written (<ExceptionType>...)", with server paths scrubbed.
The MCP report tools return a structured ``report_not_written`` error.
**Validates: Requirements 1.1, 2.1, 3.12**
"""
from __future__ import annotations

import sys
import textwrap

import pytest

from ghost import cli
from mcp_server import server as srv
from web.jobs import DONE, FAILED, JobRunner, failure_message

SECRET_DIR = "/srv/ghost-sessions-x/abc123/run-1"


def _job(tmp_path, code: str):
    r = JobRunner(max_jobs=1, command=lambda m, mode, seed, cases: [sys.executable, "-c", code])
    return r.wait(r.submit("s", tmp_path / "m").id, 15)


# -- web: panel text per exit code -------------------------------------------------


def test_exit_0_is_done_without_error(tmp_path):
    job = _job(tmp_path, "print('[faithful] PASS')")
    assert job.status == DONE and job.error is None


def test_exit_1_without_crash_is_mismatches(tmp_path):
    code = "import sys; print('[faithful] FAIL: 1 cases'); " \
           "print('ghost: verification failed: mismatches not explained by a Decision', " \
           "file=sys.stderr); sys.exit(1)"
    job = _job(tmp_path, code)
    assert job.status == FAILED and job.error == "Verification found mismatches."


def test_exit_1_with_traceback_is_report_not_written(tmp_path):
    code = textwrap.dedent(f"""
        print('[faithful] PASS')
        raise TypeError('Object of type ExcelError is not JSON serializable in {SECRET_DIR}/x.json')
    """)
    job = _job(tmp_path, code)
    assert job.status == FAILED
    assert job.error.startswith("The report could not be written"), job.error
    assert "TypeError" in job.error and "mismatches" not in job.error
    assert SECRET_DIR not in job.error and "/srv/" not in job.error


def test_exit_4_names_exception_type_without_server_path(tmp_path):
    code = (
        "import sys; print('[faithful] PASS'); "
        f"print('ghost: error: PermissionError: [Errno 13] Permission denied: "
        f"\\'{SECRET_DIR}/reports/faithful/proof-report.json\\'', file=sys.stderr); "
        f"sys.exit({cli.EXIT_REPORT_NOT_WRITTEN})"
    )
    job = _job(tmp_path, code)
    assert job.status == FAILED
    assert job.error.startswith("The report could not be written (PermissionError"), job.error
    assert "mismatches" not in job.error
    assert SECRET_DIR not in job.error and "/srv/" not in job.error
    assert "proof-report.json" in job.error  # basename kept, directory removed


def test_exit_4_without_error_line_falls_back_to_exit_code(tmp_path):
    job = _job(tmp_path, f"import sys; sys.exit({cli.EXIT_REPORT_NOT_WRITTEN})")
    assert job.error == f"The report could not be written (exit code {cli.EXIT_REPORT_NOT_WRITTEN})."


def test_exit_1_with_cli_error_line_is_not_mismatches(tmp_path):
    code = ("import sys; print('ghost: error: Referee unavailable: soffice not found at "
            f"{SECRET_DIR}/soffice', file=sys.stderr); sys.exit(1)")
    job = _job(tmp_path, code)
    assert job.status == FAILED
    assert job.error.startswith("The report could not be written"), job.error
    assert "Referee unavailable" in job.error and SECRET_DIR not in job.error


def test_other_exit_codes_keep_exit_code_text(tmp_path):
    job = _job(tmp_path, "import sys; sys.exit(3)")
    assert job.error == "Verification stopped with exit code 3."


def test_failure_message_takes_last_traceback():
    lines = [
        "Traceback (most recent call last):",
        '  File "a.py", line 1, in <module>',
        "KeyError: 'x'",
        "",
        "During handling of the above exception, another exception occurred:",
        "",
        "Traceback (most recent call last):",
        '  File "b.py", line 2, in <module>',
        "    json.dumps(v)",
        "ghost.report.model.ReportValidationError: bad report",
    ]
    msg = failure_message(1, lines)
    assert msg == "The report could not be written (ReportValidationError: bad report).", msg


# -- CLI: distinct exit code and one error line ------------------------------------


def test_cli_maps_report_not_written_to_its_exit_code(monkeypatch, capsys):
    def boom(*a, **k):
        raise cli.ReportNotWritten(TypeError("Object of type ExcelError is not JSON serializable"))

    monkeypatch.setattr(cli, "run_verification", boom)
    assert cli.EXIT_REPORT_NOT_WRITTEN not in (0, 1, 2)  # 1: mismatches, 2: argparse usage
    assert cli.main(["verify", "."]) == cli.EXIT_REPORT_NOT_WRITTEN
    err = capsys.readouterr().err.strip().splitlines()
    assert err[-1] == "ghost: error: TypeError: Object of type ExcelError is not JSON serializable"


def test_cli_write_helper_wraps_any_write_failure(monkeypatch, tmp_path):
    def broken(report, out):
        raise OSError("disk full")

    monkeypatch.setattr(cli, "write_report", broken)
    with pytest.raises(cli.ReportNotWritten) as exc:
        cli._write_proof_report(object(), tmp_path / "out")
    assert exc.value.exception_type == "OSError" and isinstance(exc.value.cause, OSError)


def _has_soffice() -> bool:
    from ghost.referee.locate import RefereeUnavailable, locate_soffice

    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


@pytest.mark.skipif(not _has_soffice(), reason="LibreOffice (soffice) not installed")
def test_cli_verify_exits_4_when_the_report_write_fails(monkeypatch, tmp_path, capsys):
    sys.path.insert(0, str(cli.Path(cli.__file__).resolve().parent.parent / "samples"))
    try:
        import make_haunted
    finally:
        sys.path.pop(0)
    wb = make_haunted.build(tmp_path / "haunted.xlsx")
    mdir = tmp_path / "mig"
    assert cli.main(["convert", str(wb), "--migration", str(mdir)]) == 0

    def broken(report, out):
        raise TypeError("Object of type ExcelError is not JSON serializable")

    monkeypatch.setattr(cli, "write_report", broken)
    capsys.readouterr()
    rc = cli.main(["verify", str(mdir), "--mode", "faithful", "--cases", "5"])
    out = capsys.readouterr()
    assert rc == cli.EXIT_REPORT_NOT_WRITTEN, out
    assert "ghost: error: TypeError: Object of type ExcelError is not JSON serializable" in out.err
    assert "mismatches" not in out.err
    assert not (mdir / "proof-report.json").exists()


# -- MCP: structured error, no server path -----------------------------------------


@pytest.mark.parametrize("tool", ["generate_proof_report", "mutation_check"])
def test_mcp_report_tools_return_structured_error(monkeypatch, tmp_path, tool):
    def boom(*a, **k):
        raise cli.ReportNotWritten(PermissionError(f"denied: {SECRET_DIR}/proof-report.json"))

    monkeypatch.setattr(srv, "run_verification", boom)
    payload, is_error = srv.call_tool_sync(tool, {"migration_dir": str(tmp_path)})
    assert is_error, payload
    err = payload["error"]
    assert err["type"] == "report_not_written"
    assert err["message"] == "The report could not be written (PermissionError)."
    assert SECRET_DIR not in str(payload) and str(tmp_path) not in str(payload)
