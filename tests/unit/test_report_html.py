from datetime import date

import pytest

from ghost.decisions.store import record
from ghost.models import Case, Decision, Mismatch
from ghost.report.html import build_report, regenerate, render_html, write_report
from ghost.report.model import ReportValidationError


def _mismatch():
    return Mismatch(
        case=Case(inputs={"q": 50}, referee={"d": 1}, actual={"d": 0}),
        output="d",
        cell="Sheet1!B2",
        mismatch_class="translation bug",
    )


def test_not_checked_and_escaping(tmp_path):
    m = _mismatch().model_copy(update={"output": "<script>x</script>"})
    r = build_report(seed=1, mode="faithful", cases_tested=5, passed=False, mismatches=[m])
    html = render_html(r)
    assert "<script>x" not in html
    assert "&lt;script&gt;" in html
    assert html.count("not checked") >= 3
    assert render_html(r) == html


def test_write_validates_and_writes(tmp_path):
    r = build_report(seed=1, mode="faithful", cases_tested=5, passed=True)
    jp, hp = write_report(r, tmp_path)
    assert jp.exists() and hp.exists()
    bad = r.model_copy(update={"cases_tested": -1})
    out = tmp_path / "bad"
    with pytest.raises(ReportValidationError):
        write_report(bad, out)
    assert not out.exists()


def test_regenerate_uses_current_decisions(tmp_path):
    record(
        tmp_path,
        Decision(decision_id="x", finding_id="F-001", behaviour="b", reason="r", author="a", date=date(2026, 1, 1)),
    )
    seen = {}

    def rebuild(decisions):
        seen["ids"] = [d.decision_id for d in decisions]
        return build_report(seed=1, mode="intended", cases_tested=1, passed=True, decisions=decisions)

    _, hp = regenerate(tmp_path, rebuild)
    assert seen["ids"] == ["D-001"]
    assert "D-001" in hp.read_text(encoding="utf-8")
