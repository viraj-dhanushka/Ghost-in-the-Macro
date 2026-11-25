"""L-08 (task 5.8): one sentence explaining survivors that no tested input can kill.
**Validates: Requirements 1.7, 2.7, 3.7, 3.8** (live-fixes-2026-11-24)
The sentence is shown only when the engine marked survivors (``survivor_kind``), which it
does when the survivor changed no output on any tested input and the module's
MAX/MIN/MATCH selection never picked some row. It never claims equivalence.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import pytest

from ghost.models import Mutant, MutationResult
from ghost.report.html import build_report, render_html
from ghost.report.model import SURVIVOR_EXPLANATION, report_to_json, validate_report_dict
from ghost.referee.locate import RefereeUnavailable, locate_soffice

def _have() -> bool:
    try:
        locate_soffice()
        return True
    except RefereeUnavailable:
        return False


_NO_DIFF = "no difference found on 3 distinct cases"


def _report(kind: str | None):
    survivor = Mutant(
        mutant_id="M-00000002", operator="constant_plus_one", location="Model!B8", killed=False,
        survivor_reason=_NO_DIFF, survivor_kind=kind,
    )
    killed = Mutant(mutant_id="M-00000001", operator="constant_plus_one", location="Model!B10", killed=True)
    return build_report(
        seed=1, mode="faithful", cases_tested=5, passed=True,
        mutation=MutationResult(mutants=[killed, survivor], killed=1, total=2),
    )


def test_sentence_shown_in_json_and_html_when_survivors_are_marked():
    report = _report("no_output_change")
    data = json.loads(report_to_json(report))
    assert data["mutation"]["survivor_explanation"] == SURVIVOR_EXPLANATION
    assert data["mutation"]["mutants"][1]["survivor_kind"] == "no_output_change"
    validate_report_dict(data)
    html = render_html(report)
    assert html[html.index("<h2>Mutation self-check</h2>"):].count(escape(SURVIVOR_EXPLANATION)) == 1


def test_sentence_absent_when_no_survivor_is_marked():
    report = _report(None)
    data = json.loads(report_to_json(report))
    assert "survivor_explanation" not in data["mutation"]
    assert all("survivor_kind" not in m for m in data["mutation"]["mutants"])
    assert escape(SURVIVOR_EXPLANATION) not in render_html(report)


def test_sentence_does_not_claim_equivalence():
    low = SURVIVOR_EXPLANATION.lower()
    assert "equivalen" not in low and "tested inputs" in low and "any tested input" in low


def test_unpicked_rows_observed_needs_a_table_of_rows():
    from ghost.verifier.selection import unpicked_rows_observed
    # The scenarios run below covers the positive case; here only the empty-case edge.
    assert unpicked_rows_observed(lambda i, *a: {}, []) is False


@pytest.mark.skipif(not _have(), reason="soffice not available")
def test_scenarios_report_has_the_sentence_and_haunted_does_not(tmp_path):
    from ghost import cli
    from samples import make_haunted, make_scenarios

    scen = make_scenarios.build(tmp_path / "scenarios.xlsx")
    mig = tmp_path / "mig"
    assert cli.main(["convert", str(scen), "--migration", str(mig),
                     "--inputs", "Model!B2,Model!B3,Model!E2", "--outputs", "Model!B19,Model!B20"]) == 0
    assert cli.main(["mutate", str(mig), "--mode", "faithful"]) == 0
    data = _load(mig)
    assert data["mutation"]["survivor_explanation"] == SURVIVOR_EXPLANATION
    marked = [m for m in data["mutation"]["mutants"] if m.get("survivor_kind")]
    assert marked and all(not m["killed"] for m in marked)
    assert "equivalen" not in json.dumps(data["mutation"]).lower()

    hh = make_haunted.build(tmp_path / "haunted.xlsx")
    hmig = tmp_path / "hmig"
    assert cli.main(["convert", str(hh), "--migration", str(hmig)]) == 0
    assert cli.main(["mutate", str(hmig), "--mode", "faithful"]) == 0
    assert "survivor_explanation" not in _load(hmig)["mutation"]


def _load(mig: Path) -> dict:
    hits = sorted(Path(mig).rglob("proof-report.json"))
    assert hits, list(Path(mig).rglob("*"))
    return json.loads(hits[0].read_text(encoding="utf-8"))
