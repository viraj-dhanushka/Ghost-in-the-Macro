"""Boundary probing: binary search for the exact change point of a calculated cell.

``probe`` varies one numeric input between ``lo`` and ``hi`` and locates the
adjacent pair of grid values (spaced ``step`` apart) where the output cell
changes. When the threshold is known, the result says which side of it the
operator includes: ``"at"`` for ``>=`` (the threshold value already gets the new
behaviour) or ``"above"`` for ``>`` (only values above it do).

``exact_hits`` finds input combinations that make an output equal a target
exactly (for example 500.00).

The ``referee`` argument is anything with ``eval(inputs, outputs) -> dict``
(``ghost.referee.client.RefereeClient`` or generated ``compute`` wrapped to the
same shape). Only values returned by the evaluator are reported.

Requirements: 8.4.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Iterable, Protocol

from ghost.models import BoundaryResult, CellRef
from ghost.verifier.compare import values_equal


class Evaluator(Protocol):
    def eval(self, inputs: dict[str, Any], outputs: list[str]) -> dict[str, Any]: ...


def _dec(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(x)


def _wire(x: Decimal) -> int | float:
    """Convert a Decimal to a JSON-friendly int or float for the Referee."""
    return int(x) if x == x.to_integral_value() else float(x)


class _Probe:
    def __init__(self, referee: Evaluator, base_inputs: dict[str, Any], output_cell: CellRef):
        self.referee = referee
        self.base = dict(base_inputs)
        self.cell = output_cell
        self.calls = 0

    def value_at(self, name: str, v: Decimal) -> Any:
        inputs = dict(self.base)
        inputs[name] = _wire(v)
        self.calls += 1
        return self.referee.eval(inputs, [self.cell])[self.cell]


def probe(
    referee: Evaluator,
    base_inputs: dict[str, Any],
    input_name: str,
    output_cell: CellRef,
    lo: Any,
    hi: Any,
    *,
    threshold: Any | None = None,
    step: Any = 1,
) -> BoundaryResult:
    """Binary search ``input_name`` in [lo, hi] for where ``output_cell`` changes.

    Assumes the output is a step function of the input in the range (one change
    point). If the output at ``lo`` equals the output at ``hi`` no change point
    is reported (``change_point`` is None). ``threshold`` defaults to the
    discovered change point's neighbour and is only used to name the operator
    side; pass the literal found by autopsy.
    """
    lo_d, hi_d, step_d = _dec(lo), _dec(hi), _dec(step)
    if step_d <= 0:
        raise ValueError("step must be positive")
    if hi_d < lo_d:
        raise ValueError("hi must be >= lo")
    t = _dec(threshold) if threshold is not None else None

    p = _Probe(referee, base_inputs, output_cell)
    n_hi = int(((hi_d - lo_d) / step_d).to_integral_value(rounding="ROUND_FLOOR"))
    at = lambda n: lo_d + step_d * n  # noqa: E731

    base_val = p.value_at(input_name, at(0))
    result = dict(cell=output_cell, input_name=input_name, threshold=t if t is not None else Decimal(0))
    if n_hi == 0 or values_equal(base_val, p.value_at(input_name, at(n_hi))):
        return BoundaryResult(**result, change_point=None, operator_includes=None)

    a, b = 0, n_hi  # invariant: value(a) == base, value(b) != base
    while b - a > 1:
        m = (a + b) // 2
        if values_equal(p.value_at(input_name, at(m)), base_val):
            a = m
        else:
            b = m
    v_lo, v_hi = at(a), at(b)

    if t is None:
        # No literal supplied: the first value with new behaviour is the change point.
        return BoundaryResult(
            **result,
            threshold=v_hi,
            change_point=v_hi,
            operator_includes="at",
            exact_hits=[{"last_unchanged": _wire(v_lo), "first_changed": _wire(v_hi)}],
        )
    if v_hi == t:
        side, change = "at", v_hi
    elif v_lo == t:
        side, change = "above", v_lo
    else:
        side, change = None, v_hi  # change point does not sit on the threshold
    return BoundaryResult(
        **result,
        change_point=change,
        operator_includes=side,
        exact_hits=[{"last_unchanged": _wire(v_lo), "first_changed": _wire(v_hi)}],
    )


def exact_hits(
    referee: Evaluator,
    base_inputs: dict[str, Any],
    count_input: str,
    price_input: str,
    output_cell: CellRef,
    target: Any,
    counts: Iterable[int],
    *,
    price_lo: Any = 0,
    price_hi: Any = 100000,
    price_step: Any = "0.01",
    tol: float = 1e-6,
) -> list[dict[str, object]]:
    """For each count, find the smallest price whose output reaches ``target``.

    Reports only combinations where the Referee output equals ``target`` within
    ``tol`` (for example ``1 x 411.67`` and ``7 x 58.81`` reaching 500.00).
    Assumes the output is non-decreasing in price. Counts that cannot reach the
    target exactly are omitted.
    """
    target_d = _dec(target)
    plo, phi, pstep = _dec(price_lo), _dec(price_hi), _dec(price_step)
    hits: list[dict[str, object]] = []
    for count in counts:
        inputs = dict(base_inputs)
        inputs[count_input] = int(count)
        p = _Probe(referee, inputs, output_cell)

        def ge_target(n: int) -> bool:
            v = p.value_at(price_input, plo + pstep * n)
            if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                return _dec(v) >= target_d - Decimal(repr(tol))
            return False

        n_max = int(((phi - plo) / pstep).to_integral_value(rounding="ROUND_FLOOR"))
        if not ge_target(n_max):
            continue
        a, b = -1, n_max  # value(a) < target (virtual), value(b) >= target
        while b - a > 1:
            m = (a + b) // 2
            if ge_target(m):
                b = m
            else:
                a = m
        price = plo + pstep * b
        value = p.value_at(price_input, price)
        if values_equal(value, _wire(target_d), tol):
            hits.append(
                {
                    "inputs": {count_input: int(count), price_input: _wire(price)},
                    "output": output_cell,
                    "value": value,
                }
            )
    return hits
