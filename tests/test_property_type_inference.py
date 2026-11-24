"""Property 5: Type inference (review-fixes-2026-11-24, task 4.5).

**Validates: Requirements 2.7**

For any input cell with data validation and sample value, the mapping type
(ghost/converter/mapping.py) and the verifier strategy type
(ghost/verifier/strategies.py:infer_spec) are equal, and `decimal`
validation always gives a decimal type. Whole-valued floats
with no validation are decimal in both (see ghost/converter/typeinfer.py).
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from ghost.converter.mapping import _type_of
from ghost.verifier.strategies import infer_spec

PBT_SEED = 20261204

validations = st.sampled_from([None, "decimal", "whole", "decimal:between", "whole:greaterThan"])
samples = st.one_of(
    st.integers(min_value=-10_000, max_value=10_000),
    st.integers(min_value=-1_000, max_value=1_000).map(float),  # whole-valued floats
    st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
)


@seed(PBT_SEED)
@settings(max_examples=200, derandomize=False, database=None, deadline=None,
          suppress_health_check=list(HealthCheck))
@given(validation=validations, value=samples)
def test_property_5_type_inference(validation, value):
    mapping_type = _type_of(value, validation)
    verifier_type = infer_spec("S!A1", [value], validation).type
    assert mapping_type == verifier_type, (validation, value, mapping_type, verifier_type)
    if validation and validation.startswith("decimal"):
        assert mapping_type == "decimal"
