"""R-18 (part 2): a session's jobs and artifacts are dropped when it ends."""

import sys
import time

from fastapi.testclient import TestClient

from web.app import create_app
from web.jobs import JobRunner

_FORM = {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
         "outputs": ["Calculator!B11"]}


def _cmd(code):
    return lambda mdir, mode, seed, cases: [sys.executable, "-c", code]


def _finished_job(client, app):
    app.state.runner._command = _cmd("pass")
    client.post("/sample/haunted")
    r = client.post("/verify", data=_FORM)
    assert r.status_code == 200
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, 15)
    job.artifacts["proof-report.json"] = b"{}"
    return job_id, job


def test_delete_session_drops_jobs_and_artifacts(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    job_id, job = _finished_job(c, app)
    assert c.get(f"/jobs/{job_id}").status_code == 200
    assert c.delete("/session").status_code == 200
    runner = app.state.runner
    assert runner._jobs == {} and runner.get(job_id) is None
    assert job.artifacts == {}
    assert c.get(f"/jobs/{job_id}").status_code == 404


class _Clock:
    """A clock the test moves by hand, so the idle sweep never depends on how long setup took."""
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now
def test_sweep_drops_jobs_and_artifacts(tmp_path):
    clock = _Clock()
    # The session is 60 s idle-limited on a clock that stands still: nothing can be swept
    # while the sample is loaded and the job runs, however slow the machine is.
    app = create_app(session_root=tmp_path / "s", idle_timeout_s=60, sweep_interval_s=0.05, clock=clock)
    with TestClient(app) as c:
        job_id, job = _finished_job(c, app)
        assert app.state.runner.get(job_id) is job and job.artifacts != {}
        clock.now = 61.0  # the session is now idle for longer than the timeout
        deadline = time.monotonic() + 30
        while app.state.runner._jobs and time.monotonic() < deadline:
            time.sleep(0.05)
        assert app.state.runner._jobs == {}
        assert job.artifacts == {}
        assert c.get(f"/jobs/{job_id}").status_code == 404
def test_other_sessions_keep_their_jobs(tmp_path):
    r = JobRunner(max_jobs=2, command=_cmd("pass"))
    a, b = r.submit("s1", tmp_path / "a"), r.submit("s2", tmp_path / "b")
    r.wait(a.id, 10), r.wait(b.id, 10)
    r.forget_session("s1")
    assert r.get(a.id) is None and r.get(b.id) is b


def test_forget_session_kills_running_process_and_dequeues(tmp_path):
    r = JobRunner(max_jobs=1, command=_cmd("import time; time.sleep(60)"))
    running = r.submit("s1", tmp_path / "a")
    queued = r.submit("s2", tmp_path / "b")
    deadline = time.monotonic() + 10
    while running._proc is None and time.monotonic() < deadline:
        time.sleep(0.02)
    proc = running._proc
    assert proc is not None and proc.poll() is None
    r.forget_session("s1")
    assert proc.wait(timeout=10) != 0
    assert r.get(running.id) is None and running.artifacts == {}
    # The freed slot starts the other session's job; ending that session kills it too.
    deadline = time.monotonic() + 10
    while queued._proc is None and time.monotonic() < deadline:
        time.sleep(0.02)
    proc2 = queued._proc
    r.forget_session("s2")
    assert proc2.wait(timeout=10) != 0
    assert r._jobs == {} and list(r._queue) == []
