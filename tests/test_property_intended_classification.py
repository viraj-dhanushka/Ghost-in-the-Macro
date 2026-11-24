"""Property 3: Intended-mode classification soundness (PBT). Needs LibreOffice.

For any module (haunted Intended code, with or without an unrelated edit) and any case
where Intended mode reports a mismatch, the mismatch is "expected by decision" if and
only if all three conditions of clause 2.5 hold on that case:

  (a) the transpiled Faithful module matches the Referee,
  (b) the module under test differs from the Faithful module,
  (c) the Decision's patched comparison (Calculator!B9#1) evaluates differently in the
      two modules (read through the trace hook).

Any other mismatch is a "translation bug".

**Validates: Requirements 2.5, 2.6** (design Property 3)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, seed, settings
from hypothesis import strategies as st

from ghost.autopsy.classify import classify
from ghost.autopsy.findings import detect_inconsistencies
from ghost.autopsy.thresholds import extract_thresholds
from ghost.converter.emit_python import emit_python
from ghost.converter.mapping import generate_mapping
from ghost.decisions.store import load_decisions, record
from ghost.ingest.workbook import load_workbook
from ghost.referee.client import RefereeClient
from ghost.referee.locate import RefereeUnavailable, locate_soffice
from ghost.rules.ears import generate_rules
from ghost.verifier.classify import make_classifier
from ghost.verifier.compare import values_equal
from ghost.verifier.run import VerifyConfig, load_compute, verify
from samples import make_haunted

try:
    locate_soffice()
except RefereeUnavailable:  # pragma: no cover
    pytest.skip("soffice not available", allow_module_level=True)

PBT_SEED = 20261204
USER_INPUTS = ("Calculator!B2", "Calculator!B3", "Calculator!B4")
PATCHED_HOOK = "Calculator!B9#1"
VAT_OLD, VAT_NEW = "'Calculator!E7': Decimal('0.2'),", "'Calculator!E7': Decimal('0.21'),"

@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("prop3")
    path = make_haunted.build(d / "haunted.xlsx")
    wb = load_workbook(str(path))
    mig = d / "mig"
    mig.mkdir()
    record(mig, {
        "finding_id": "F-001", "behaviour": "bulk means 50 or more", "reason": "agree with discount",
        "author": "pbt", "date": "2026-11-24",
        "patch": {"op": "set_operator", "cell": "Calculator!B9", "from": ">", "to": ">="},
    })
    decisions = load_decisions(mig)

    roles = {r: ("PARAMETER" if v == "INPUT" else v) for r, v in classify(wb, ["Calculator!B11"]).items()}
    roles.update({r: "INPUT" for r in USER_INPUTS})
    for r, v in list(roles.items()):
        if v == "OUTPUT" and r != "Calculator!B11":
            roles[r] = "INTERMEDIATE"
    mapping = generate_mapping(wb, roles)

    thresholds = extract_thresholds(wb)
    findings = detect_inconsistencies(thresholds)
    io_roles = {s.cell: "INPUT" for s in mapping.inputs.values()} | {s.cell: "OUTPUT" for s in mapping.outputs.values()}
    rules = generate_rules(wb, io_roles, thresholds)
    cfg_args = dict(
        mode="intended", thresholds=thresholds, max_examples=1,
        classifier=make_classifier("intended", findings, decisions, rules, wb.deps),
    )

    intended_src = emit_python(wb, mapping, "intended", decisions)
    assert intended_src.count(VAT_OLD) == 1
    modules = {
        "intended": intended_src,
        "intended+vat21": intended_src.replace(VAT_OLD, VAT_NEW),
    }
    faithful = load_compute(emit_python(wb, mapping))
    with RefereeClient(None, path) as ref:
        yield {
            "mapping": mapping, "ref": ref, "cfg_args": cfg_args, "faithful": faithful,
            "modules": modules, "loaded": {k: load_compute(v) for k, v in modules.items()},
        }


def _trace_of(compute, inputs) -> tuple[dict, dict]:
    seen: dict[str, bool] = {}
    out = compute(dict(inputs), trace=lambda hook, val: seen.__setitem__(hook, val))
    return out, seen


def _same(a: dict, b: dict) -> bool:
    return all(values_equal(a[k], b.get(k)) for k in a)


@seed(PBT_SEED)
@settings(max_examples=40, derandomize=False, database=None, deadline=None,
          suppress_health_check=list(HealthCheck))
@given(
    variant=st.sampled_from(["intended", "intended+vat21"]),
    quantity=st.one_of(st.integers(0, 120), st.integers(45, 55)),
    unit_price=st.decimals(min_value=0, max_value=200, places=2),
    km=st.one_of(st.integers(0, 40).map(Decimal), st.decimals(min_value=0, max_value=40, places=1)),
)
def test_property_3_intended_classification_soundness(world, variant, quantity, unit_price, km):
    if variant == "intended+vat21":
        # At quantity 50 the VAT edit and D-001 overlap, so clause 2.5 is ambiguous there.
        assume(quantity != 50)
    case = {"quantity": quantity, "unit_price": unit_price, "delivery_distance_km": km}
    mapping = world["mapping"]
    res = verify(world["modules"][variant], mapping, world["ref"],
                 VerifyConfig(extra_cases=[case], **world["cfg_args"]))

    candidate = world["loaded"][variant]
    faithful = world["faithful"]
    for m in res.mismatches:
        inputs = m.case.inputs
        cand_out, cand_trace = _trace_of(candidate, inputs)
        faith_out, faith_trace = _trace_of(faithful, inputs)
        a = all(values_equal(m.case.referee[k], faith_out[k]) for k in m.case.referee)
        b = not _same(cand_out, faith_out)
        c = cand_trace.get(PATCHED_HOOK) != faith_trace.get(PATCHED_HOOK)
        expected = a and b and c
        got = m.mismatch_class == "expected by decision"
        assert got == expected, (variant, inputs, m.mismatch_class, {"a": a, "b": b, "c": c})
    # A candidate that differs from the Referee on a generated case must not pass Intended mode
    # unless every mismatch is explained by the Decision.
    if variant == "intended+vat21" and any(
        not values_equal(m.case.referee[m.output], m.case.actual[m.output]) for m in res.mismatches
    ):
        assert not res.passed
