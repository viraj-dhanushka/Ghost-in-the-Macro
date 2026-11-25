"""R-21 (rest): exact-hits column, tested domains, Faithful download.

**Validates: Requirements 1.28, 2.28, 3.9**
"""

from __future__ import annotations

import sys
from decimal import Decimal

from fastapi.testclient import TestClient

from ghost.models import BoundaryResult, IOSpec, Mapping
from ghost.report.html import build_report, render_html
from ghost.report.model import report_to_dict, validate_report_dict
from ghost.report.domains import tested_domain_rows as domain_rows
from web.app import create_app
from web.jobs import JobRunner

_MAPPING = Mapping(
    inputs={
        "quantity": IOSpec(cell="S!A1", type="integer", min=0, max=100),
        "price": IOSpec(cell="S!A2", type="decimal", min=0, max=10),
        "label": IOSpec(cell="S!A3", type="string"),
    },
    outputs={"y": IOSpec(cell="S!B1", type="decimal")},
)
_CASES = [
    {"quantity": 0, "price": Decimal("1.5"), "label": "a"},
    {"quantity": 50, "price": Decimal("0.25"), "label": "b"},
    {"quantity": 7, "price": 3.0, "label": "a"},
]


def test_domain_rows_come_from_cases_run():
    rows = {r["input"]: r for r in domain_rows(_MAPPING, _CASES)}
    assert rows["quantity"] == {
        "input": "quantity", "type": "integer", "min": "0", "max": "50", "decimal_places": 0,
    }
    assert rows["price"]["min"] == "0.25" and rows["price"]["max"] == "3"
    assert rows["price"]["decimal_places"] == 2
    assert rows["label"]["type"] == "string" and rows["label"]["distinct_values"] == 2
    assert "min" not in rows["label"]


def test_domain_row_for_untested_input():
    rows = {r["input"]: r for r in domain_rows(_MAPPING, [{"quantity": 1}])}
    assert rows["price"] == {"input": "price", "type": "decimal", "not_tested": True}


def test_report_json_lists_domains_and_validates():
    rows = domain_rows(_MAPPING, _CASES)
    r = build_report(seed=1, mode="faithful", cases_tested=3, passed=True, tested_domains=rows)
    d = report_to_dict(r)
    validate_report_dict(d)
    assert [x["input"] for x in d["tested_domains"]] == ["label", "price", "quantity"]
    html = render_html(d)
    assert "Tested domains" in html and "quantity" in html and "0.25" in html


def test_old_report_without_domains_still_validates():
    d = report_to_dict(build_report(seed=1, mode="faithful", cases_tested=3, passed=True))
    assert "tested_domains" not in d
    validate_report_dict(d)
    assert "Tested domains" in render_html(d) and "not checked" in render_html(d)


def _boundaries():
    return [
        BoundaryResult(
            cell="S!B1", input_name="quantity", threshold=Decimal(50), change_point=Decimal(50),
            operator_includes="at",
            exact_hits=[{"last_unchanged": 49, "first_changed": 50}],
        ),
        BoundaryResult(
            cell="S!B2", input_name="price", threshold=Decimal(10), change_point=Decimal(10),
            kind="condition flip", condition_id="S!B2#1",
            below=Decimal(9), above=Decimal(11), exact=Decimal(10),
        ),
    ]


def test_html_separates_change_points_from_real_exact_hits():
    html = render_html(build_report(seed=1, mode="faithful", cases_tested=1, passed=True,
                                    boundaries=_boundaries()))
    assert "<th>Exact hits</th>" in html  # the real one, from flip probing
    assert "<th>Change-point bracket</th>" in html
    # The bracket (last unchanged / first changed) is under the renamed column,
    # and the plain boundary has no exact hit: it says so instead of repeating the bracket.
    section = html.split("<h2>Boundaries</h2>")[1].split("</section>")[0]
    rows = section.split("<tbody>")[1].split("</tr>")
    # L-06 (task 5.2): the bracket is readable text, not raw JSON, so the check is on "49 → 50".
    assert "49 → 50" in rows[0] and "first_changed" not in rows[0] and rows[0].endswith("<td>not checked</td>")
    assert rows[1].endswith("<td>10</td>")


# --- Faithful download -----------------------------------------------------


def _cmd(code):
    return lambda mdir, mode, seed, cases: [sys.executable, "-c", code]


def test_job_collects_both_mode_reports(tmp_path):
    mdir = tmp_path / "m"
    for mode in ("faithful", "intended"):
        (mdir / "reports" / mode).mkdir(parents=True)
        (mdir / "reports" / mode / "proof-report.json").write_text(f'{{"mode":"{mode}"}}')
        (mdir / "reports" / mode / "proof-report.html").write_text(f"<p>{mode}</p>")
    (mdir / "proof-report.json").write_text('{"mode":"intended"}')
    r = JobRunner(max_jobs=1, command=_cmd("pass"))
    job = r.wait(r.submit("s1", mdir).id, 10)
    assert job.artifacts["faithful/proof-report.json"] == b'{"mode":"faithful"}'
    assert job.artifacts["faithful/proof-report.html"] == b"<p>faithful</p>"


def test_faithful_report_download_and_links(tmp_path):
    app = create_app(session_root=tmp_path / "s")
    c = TestClient(app)
    app.state.runner._command = _cmd("pass")
    c.post("/sample/haunted")
    form = {"inputs": ["Calculator!B2", "Calculator!B3", "Calculator!B4"], "outputs": ["Calculator!B11"]}
    r = c.post("/verify", data=form)
    job_id = r.text.split("/run/")[1].split("/")[0]
    job = app.state.runner.wait(job_id, 15)
    job.artifacts.update({
        "proof-report.json": b'{"mode":"intended","passed":true,"cases_tested":1,"seed":1,"mismatches":[]}',
        "proof-report.html": b"<p>intended</p>",
    })
    # One report only: no Faithful link, and ?mode=faithful is a 404.
    assert "mode=faithful" not in c.get(f"/run/{job_id}/panel").text
    assert c.get(f"/run/{job_id}/report.html?mode=faithful").status_code == 404
    job.artifacts.update({
        "faithful/proof-report.json": b'{"mode":"faithful"}',
        "faithful/proof-report.html": b"<p>faithful</p>",
    })
    h = c.get(f"/run/{job_id}/report.html?mode=faithful")
    assert h.status_code == 200 and h.content == b"<p>faithful</p>"
    assert "attachment" in h.headers["content-disposition"]
    assert c.get(f"/run/{job_id}/report.json?mode=faithful").content == b'{"mode":"faithful"}'
    assert c.get(f"/run/{job_id}/report.html").content == b"<p>intended</p>"
    assert c.get(f"/run/{job_id}/report.html?mode=bogus").status_code == 404
    panel = c.get(f"/run/{job_id}/panel").text
    assert f"/run/{job_id}/report.html?mode=faithful" in panel
    assert f"/run/{job_id}/report.json?mode=faithful" in panel
    other = TestClient(create_app(session_root=tmp_path / "o"))
    assert other.get(f"/run/{job_id}/report.html?mode=faithful").status_code == 404
