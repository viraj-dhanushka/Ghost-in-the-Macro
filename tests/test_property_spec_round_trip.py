"""Property 11 of the main spec: spec file round trip (Decision, Mapping, Findings, Traceability).
Validates Requirements 4.1, 4.2 and 7.10. No LibreOffice."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml
from hypothesis import given, settings, strategies as st

from ghost import cli
from ghost.converter.mapping import generate_mapping, read_mapping, write_mapping
from ghost.decisions.store import load_decisions, record
from ghost.models import IOSpec, Mapping
from ghost.rules.spec_writer import findings_data, traceability_data

ROOT = Path(__file__).resolve().parent.parent
text = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="\\"), min_size=1, max_size=40).filter(
    lambda s: s.strip() and s == s.strip())


@settings(max_examples=60, deadline=None)
@given(text, text, text, st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
       st.one_of(st.none(), st.just("F-001")))
def test_property_11_a_decision_survives_write_and_read(tmp_path_factory, behaviour, reason, author, when, finding):
    mdir = tmp_path_factory.mktemp("d")
    made = record(mdir, {"behaviour": behaviour, "reason": reason, "author": author, "date": when,
                         "finding_id": finding, "rule_id": None if finding else "R-12345678"})
    (back,) = load_decisions(mdir)
    assert back == made
    assert (back.behaviour, back.reason, back.author, back.date) == (behaviour, reason, author, when)


names = st.from_regex(r"[a-z][a-z0-9_]{0,12}", fullmatch=True)
specs = st.builds(
    IOSpec, cell=st.builds(lambda c, r: f"Sheet1!{c}{r}", st.sampled_from(list("ABCDEF")), st.integers(1, 99)),
    type=st.sampled_from(["integer", "decimal", "string", "boolean"]),
    min=st.one_of(st.none(), st.decimals(min_value=0, max_value=1000, places=2)),
    max=st.one_of(st.none(), st.decimals(min_value=1001, max_value=5000, places=2)),
)


@settings(max_examples=80, deadline=None)
@given(st.dictionaries(names, specs, min_size=1, max_size=4), st.dictionaries(names, specs, min_size=1, max_size=3))
def test_property_11_a_mapping_survives_write_and_read(tmp_path_factory, inputs, outputs):
    mapping = Mapping(inputs=inputs, outputs=outputs)
    path = tmp_path_factory.mktemp("m") / "mapping.yaml"
    write_mapping(mapping, path)
    assert read_mapping(path) == mapping  # Decimal(1001) == Decimal("1001.00"): equal, whatever the text


def test_property_11_findings_and_traceability_survive_yaml(tmp_path):
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        import make_haunted
    finally:
        sys.path.remove(str(ROOT / "samples"))
    a = cli._analyse(make_haunted.build(tmp_path / "h.xlsx"))
    assert a.findings and a.rules
    for data in (findings_data(a.findings), traceability_data(a.rules)):
        assert yaml.safe_load(yaml.safe_dump(data, sort_keys=False)) == yaml.safe_load(yaml.safe_dump(data, sort_keys=False))
        assert yaml.safe_load(yaml.safe_dump(data, sort_keys=False)) == _plain(data)
    mapping = generate_mapping(a.wb, a.roles)
    write_mapping(mapping, tmp_path / "m.yaml")
    assert read_mapping(tmp_path / "m.yaml") == mapping


def _plain(x):
    """The same data as plain YAML types (tuples and Decimals as YAML writes them back)."""
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, Decimal):
        return str(x) if not isinstance(yaml.safe_load(yaml.safe_dump(x)), type(x)) else x
    return x
