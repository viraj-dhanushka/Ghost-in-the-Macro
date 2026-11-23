import asyncio
import sys
import time

from web.jobs import DONE, FAILED, QUEUED, RUNNING, TIMEOUT, JobRunner, default_command, sse_stream


def py(code):
    return lambda mdir, mode, seed, cases: [sys.executable, "-c", code]


def test_default_command_never_trusts_macros(tmp_path):
    cmd = default_command(tmp_path, "both", 1, 5)
    assert "--trust-macros" not in cmd and cmd[3] == "verify"


def test_job_completes_collects_artifacts_and_cleans_up(tmp_path):
    mdir = tmp_path / "m"
    mdir.mkdir()
    (mdir / "proof-report.json").write_text("{}")
    r = JobRunner(max_jobs=1, command=py("print('hello'); print('world')"))
    job = r.wait(r.submit("s1", mdir).id, 10)
    assert job.status == DONE
    assert job.events[-2:] == ["hello", "world"]
    assert job.artifacts["proof-report.json"] == b"{}"
    assert not mdir.exists()


def test_mismatch_exit_is_failed_result(tmp_path):
    r = JobRunner(max_jobs=1, command=py("import sys; sys.exit(1)"))
    job = r.wait(r.submit("s", tmp_path).id, 10)
    assert job.status == FAILED and "mismatches" in job.error


def test_timeout_kills_job(tmp_path):
    r = JobRunner(max_jobs=1, timeout_s=0.5, command=py("import time; time.sleep(30)"))
    t = time.monotonic()
    job = r.wait(r.submit("s", tmp_path).id, 10)
    assert job.status == TIMEOUT and time.monotonic() - t < 8


def test_concurrency_limit_and_queue_position(tmp_path):
    r = JobRunner(max_jobs=1, command=py("import time; time.sleep(0.6)"))
    a = r.submit("s", tmp_path / "a")
    b = r.submit("s", tmp_path / "b")
    c = r.submit("s", tmp_path / "c")
    assert a.status == RUNNING and b.status == QUEUED and c.status == QUEUED
    assert (b.snapshot()["queue_position"], c.snapshot()["queue_position"]) == (1, 2)
    for j in (a, b, c):
        assert r.wait(j.id, 15).status == DONE
    assert b.snapshot()["queue_position"] is None


def test_get_is_scoped_to_session(tmp_path):
    r = JobRunner(max_jobs=1, command=py("pass"))
    job = r.submit("s1", tmp_path)
    assert r.get(job.id, "s2") is None and r.get(job.id, "s1") is job
    r.wait(job.id, 10)


def test_sse_stream_ends_with_terminal_frame(tmp_path):
    r = JobRunner(max_jobs=1, command=py("print('x')"))
    job = r.submit("s", tmp_path)

    async def collect():
        return [f async for f in sse_stream(job, interval_s=0.05)]

    frames = asyncio.run(collect())
    assert frames and '"status": "done"' in frames[-1]
