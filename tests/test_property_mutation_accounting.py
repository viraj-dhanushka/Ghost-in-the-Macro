"""Property 29 of the main spec: mutation score accounting.
Validates Requirements 9.1, 9.3 and 9.4. No LibreOffice (the Referee is not needed to count or to generate)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

from ghost import cli
from ghost.converter.emit_python import emit_module
from ghost.converter.mapping import generate_mapping
from ghost.models import Mutant, MutationResult
from ghost.mutation.mutants import generate_mutants
from ghost.mutation.run import score

ROOT = Path(__file__).resolve().parent.parent


# Feature: ghost-in-the-macro, Property 29: Mutation score accounting
@settings(max_examples=300, deadline=None)
@given(st.lists(st.booleans(), min_size=0, max_size=40))
def test_property_29_the_score_is_killed_over_total(flags):
    mutants = [Mutant(mutant_id=f"M-{i:08x}", operator="flip_comparison", location=f"S!B{i + 1}", killed=k)
               for i, k in enumerate(flags)]
    result = MutationResult(mutants=mutants, killed=sum(flags), total=len(flags))
    assert result.killed + sum(1 for m in result.mutants if not m.killed) == result.total
    expected = (sum(flags) / len(flags)) if flags else 0.0
    assert score(result) == expected == result.score
    assert 0.0 <= result.score <= 1.0


def _module(sample: str, tmp: Path) -> str:
    sys.path.insert(0, str(ROOT / "samples"))
    try:
        mod = __import__(sample)
    finally:
        sys.path.remove(str(ROOT / "samples"))
    a = cli._analyse(mod.build(tmp / "w.xlsx"))
    return emit_module(a.wb, generate_mapping(a.wb, a.roles), "faithful", []).code


def test_property_29_every_generated_mutant_differs_from_the_source_and_parses(tmp_path):
    for sample in ("make_discount", "make_haunted"):
        source = _module(sample, tmp_path)
        mutants = generate_mutants(source)
        assert mutants, sample
        ids = [m.mutant_id for m in mutants]
        assert len(set(ids)) == len(ids)
        base = ast.dump(ast.parse(source))
        for m in mutants:
            assert m.source != source
            assert ast.dump(ast.parse(m.source)) != base, m.mutant_id  # a real change, not only formatting
        assert [m.mutant_id for m in generate_mutants(source)] == ids  # deterministic


def test_property_29_a_surviving_mutant_carries_a_reason_in_the_description(tmp_path):
    from ghost.mutation.run import describe
    source = _module("make_discount", tmp_path)
    ms = generate_mutants(source)
    survivors = [Mutant(mutant_id=m.mutant_id, operator=m.operator, location=m.location, killed=False,
                        survivor_reason="no difference found on 62 distinct cases") for m in ms[:3]]
    result = MutationResult(mutants=survivors + [Mutant(mutant_id="M-killed00", operator="x", location="S!A1", killed=True)],
                            killed=1, total=4)
    lines = " ".join(describe(result))
    assert "mutation score: 1/4 killed (25%)" in lines
    for m in survivors:
        assert f"survived {m.mutant_id}" in lines and "no difference found on 62 distinct cases" in lines
    assert all(m.survivor_reason for m in result.mutants if not m.killed)
