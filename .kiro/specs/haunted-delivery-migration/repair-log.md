# Repair log

Written by `scripts/ghost_hook.py repair` after each verification of a hand-written `logic.py`, from the proof report. Do not edit by hand.

## Round 1
- time: 2026-11-26T12:38:58
- seed: 20261204
- cases: 38 generated, 11 targeted, 43 distinct
- result: FAIL
- counterexample: delivery_distance_km=-1000000, quantity=50.1, unit_price=-192381013.90; output total (Calculator!B11): Referee -10409351900.100002, actual -10409351900.100; rule R-794f519c; found by search (shrunk)

## Round 2
- time: 2026-11-26T12:42:46
- seed: 20261204
- cases: 300 generated, 11 targeted, 200 distinct
- result: PASS
- counterexample: none

## Round 3
- time: 2026-11-26T12:44:43
- seed: 20261204
- cases: 0 generated, 2 targeted, 2 distinct
- result: FAIL
- counterexample: delivery_distance_km=12, quantity=50, unit_price=19.95; output total (Calculator!B11): Referee 1084.26, actual 1077.30; rule R-794f519c; found by targeted boundary case
- planted: the free-delivery comparison in logic.py was changed from > to >= (rule R-5f32fa17); planted by the repository owner's assistant to show the repair loop, not by the migration agent

## Round 4
- time: 2026-11-26T12:45:30
- seed: 20261204
- cases: 300 generated, 11 targeted, 200 distinct
- result: PASS
- counterexample: none
