"""Single-page flow tests (task 12.3). Validates: Requirements 13.1, 13.2, 13.3, 13.11, 13.13, 14.5.

The end-to-end test runs the haunted sample through the web app against real
LibreOffice and is skipped when soffice is not installed.
"""
from __future__ import annotations

import html as htmlmod
import json
import time

import pytest
from fastapi.testclient import TestClient

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from web.app import create_app


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


def _client(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    return TestClient(app), app


def test_healthz_reports_referee_unavailable(tmp_path):
    c, app = _client(tmp_path)
    app.state.referee_check = lambda: {"available": False, "reason": "soffice not found"}
    r = c.get("/healthz")
    assert r.status_code == 503
    assert r.json()["referee"] == {"available": False, "reason": "soffice not found"}


def test_flow_requires_workbook(tmp_path):
    c, _ = _client(tmp_path)
    assert c.get("/autopsy").status_code == 409
    assert c.post("/verify").status_code == 409


def test_autopsy_and_decision_for_haunted(tmp_path):
    c, _ = _client(tmp_path)
    r = c.post("/sample/haunted", headers={"hx-request": "true"})
    assert r.status_code == 200 and 'hx-get="/autopsy"' in r.text
    r = c.get("/autopsy")
    assert r.status_code == 200 and "F-001" in r.text and "Business rules" in r.text
    assert "run_macros" not in r.text
    # Incomplete answers are rejected and nothing is recorded.
    bad = c.post("/decision", data={"finding_id": "F-001", "choice": "keep", "author": "", "reason": ""})
    assert bad.status_code == 422 and "F-001 already" not in bad.text
    # A choice that was not offered is rejected.
    bad = c.post("/decision", data={"finding_id": "F-001", "choice": "set|X!A1|>|<", "author": "a", "reason": "r"})
    assert bad.status_code == 422
    ok = c.post("/decision", data={"finding_id": "F-001", "choice": "keep", "author": "Ana", "reason": "Reproduce"})
    assert ok.status_code == 200 and "D-001" in ok.text
    again = c.post("/decision", data={"finding_id": "F-001", "choice": "keep", "author": "Ana", "reason": "x"})
    assert again.status_code == 409


def test_verify_without_outputs_is_a_visible_error(tmp_path):
    c, _ = _client(tmp_path)
    c.post("/sample/haunted")
    r = c.post("/verify", data={"inputs": ["Calculator!B2"]})
    assert r.status_code == 422 and "output" in r.text.lower()


@pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")
def test_haunted_end_to_end_through_web(tmp_path):
    c, _ = _client(tmp_path)
    assert c.post("/sample/haunted").status_code == 200
    page = c.get("/autopsy").text
    assert "F-001" in page
    options = [htmlmod.unescape(l) for l in page.split('value="') if l.startswith("set|")]
    # Decision D-001: bulk means 50 or more, so delivery uses '>=' at B9.
    choice = next(o.split('"')[0] for o in options if "B9" in o and o.split('"')[0].endswith("|>="))
    r = c.post("/decision", data={"finding_id": "F-001", "choice": choice,
                                  "author": "Test", "reason": "Bulk means 50 or more"})
    assert r.status_code == 200 and "D-001" in r.text
    r = c.post("/verify", data={
        "inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
        "outputs": ["Calculator!B11"],
    })
    assert r.status_code == 200, r.text
    job_id = r.text.split("/run/")[1].split("/")[0]
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        panel = c.get(f"/run/{job_id}/panel")
        if "Proof report" in panel.text and 'hx-trigger="every 1s"' not in panel.text:
            break
        time.sleep(1)
    else:
        pytest.fail("verification did not finish")
    assert 'class="verdict pass"' in panel.text, panel.text
    rep = c.get(f"/run/{job_id}/report.json")
    assert rep.status_code == 200 and "attachment" in rep.headers["content-disposition"]
    data = json.loads(rep.content)
    assert data["passed"] is True and data["mode"] == "intended"
    assert data["seed"] is not None
    html = c.get(f"/run/{job_id}/report.html")
    assert html.status_code == 200 and b"quantity" in html.content.lower()
    assert "sandbox" in c.get(f"/run/{job_id}/report.html?inline=1").headers["content-security-policy"]
    assert b"def compute" in c.get(f"/run/{job_id}/module.py").content
    assert c.get(f"/run/{job_id}/module.zip").headers["content-type"] == "application/zip"
    # Another session cannot read the job.
    other, _ = _client(tmp_path / "other")
    assert other.get(f"/run/{job_id}/report.json").status_code == 404
