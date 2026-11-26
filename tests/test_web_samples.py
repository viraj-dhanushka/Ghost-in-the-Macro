"""Every bundled sample through the web flow with the autopsy's default checkboxes.

Task 3.1 of review-fixes-2026-11-24 (R-05, R-12). Validates: Requirements 1.1, 2.1.
Unlike tests/test_product_samples.py, nothing overrides the proposed inputs: the
test posts exactly the boxes the autopsy page pre-checks, as a browser would.
"""
from __future__ import annotations

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from ghost.referee.locate import RefereeUnavailable, locate_soffice
from web.app import SAMPLES, create_app


def _has_soffice() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


_BOX = re.compile(r'<input type="checkbox" name="(inputs|outputs)" value="([^"]+)"([^>]*)>')


def _prechecked(page: str) -> dict[str, list[str]]:
    import html as htmlmod

    boxes: dict[str, list[str]] = {"inputs": [], "outputs": []}
    for kind, value, rest in _BOX.findall(page):
        if "checked" in rest:
            boxes[kind].append(htmlmod.unescape(value))
    return boxes


@pytest.mark.skipif(not _has_soffice(), reason="LibreOffice not installed")
@pytest.mark.parametrize("sample_id", list(SAMPLES))
def test_bundled_sample_passes_faithful_with_default_inputs(tmp_path, sample_id):
    c = TestClient(create_app(session_root=tmp_path / "s"))
    assert c.post(f"/sample/{sample_id}").status_code == 200
    page = c.get("/autopsy")
    assert page.status_code == 200
    boxes = _prechecked(page.text)
    assert boxes["inputs"] and boxes["outputs"], f"autopsy pre-checked nothing for {sample_id}"

    r = c.post("/verify", data=boxes)
    assert r.status_code == 200, r.text
    job_id = r.text.split("/run/")[1].split("/")[0]
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        panel = c.get(f"/run/{job_id}/panel")
        if 'hx-trigger="every 1s"' not in panel.text and (
            "Proof report" in panel.text or "verdict" in panel.text or "failed" in panel.text.lower()
        ):
            break
        time.sleep(1)
    else:
        pytest.fail("verification did not finish")

    rep = c.get(f"/run/{job_id}/report.json")
    assert rep.status_code == 200, panel.text
    data = json.loads(rep.content)
    assert data["mode"] == "faithful"
    assert data["passed"] is True, data.get("mismatches") or panel.text


# Clause 3.11 of .kiro/specs/live-fixes-2026-11-24 (task 2, Property 2: Preservation).
# Measured on the unfixed code; L-05 must not change them (no sample has a
# not-converted or not-verifiable output).
DEFAULT_BOXES = {
    "discount": {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
                 "outputs": ["Calculator!B11"]},
    "haunted": {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
                "outputs": ["Calculator!B11"]},
    "scenarios": {"inputs": ["Model!B2", "Model!B3", "Model!E2"],
                  "outputs": ["Model!B19", "Model!B20"]},
    "macros": {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"],
               "outputs": ["Calculator!B11"]},
}


@pytest.mark.parametrize("sample_id", sorted(DEFAULT_BOXES))
def test_bundled_sample_default_boxes_are_unchanged(tmp_path, sample_id):
    """**Validates: Requirements 3.11**"""
    assert set(DEFAULT_BOXES) == set(SAMPLES)
    if sample_id == "macros" and not _has_soffice():
        pytest.skip("the macro sample is built through LibreOffice")
    c = TestClient(create_app(session_root=tmp_path / "s"))
    assert c.post(f"/sample/{sample_id}").status_code == 200
    page = c.get("/autopsy")
    assert page.status_code == 200
    assert _prechecked(page.text) == DEFAULT_BOXES[sample_id]
