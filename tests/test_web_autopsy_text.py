"""R-22: the autopsy page text about unanswered findings must be true.

Validates: Requirements 1.29, 2.29. Needs LibreOffice for the listing check.
"""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from web.app import create_app

TEXT = "Unanswered findings keep the original behaviour and are listed in the report."


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


def test_autopsy_page_text_for_unanswered_findings(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    c.post("/sample/haunted")
    page = c.get("/autopsy").text
    assert TEXT in page
    assert "reported as mismatches" not in page


@pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")
def test_unanswered_finding_is_listed_in_the_report(tmp_path):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    c.post("/sample/haunted")
    r = c.post("/verify", data={"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
                                "outputs": ["Calculator!B11"]})
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
    data = json.loads(c.get(f"/run/{job_id}/report.json").content)
    assert data["mode"] == "faithful" and data["passed"] is True
    assert "F-001" in [f["finding_id"] for f in data["findings"]]
    assert not data["decisions"]
    assert "F-001" in c.get(f"/run/{job_id}/report.html").text
