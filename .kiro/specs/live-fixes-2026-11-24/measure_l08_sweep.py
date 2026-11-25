"""L-08 baseline sweep (task 5.6). Measurement only; changes no engine code.

Question: across the scenarios domain, which scenario rows ever win
(B19 = INDEX/MATCH result, first match on ties)?

Usage (repo root):
  GHOST_SOFFICE=... .venv/bin/python .kiro/specs/live-fixes-2026-11-24/measure_l08_sweep.py \
      <migration dir with logic.py> <scenarios.xlsx> [--referee]

Steps:
  1. Replica of the sheet formula (exact Decimal) is checked against the
     transpiled logic.py on random cases (3 default inputs, allowance E3 = 800).
  2. Sweep A: default boxes (E3 fixed at 800). Sweep B: E3 also varied 0..10000.
     Each = coarse grid + seeded random (uniform and log-uniform mixes).
  3. With --referee, the first winning input per row is replayed on the Referee
     (default boxes only, since E3 is not an input there).
Output: JSON on stdout.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import random
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCENARIOS = [  # row, name, rate, deduction, credit rate, fee  (same as samples/make_scenarios.py)
    (6, "Flat 20", "0.20", 0, "0.00", 0),
    (7, "Flat 25 + deduction", "0.25", 2000, "0.00", 0),
    (8, "Low rate, high fee", "0.15", 0, "0.00", 1500),
    (9, "Credit A", "0.22", 1000, "0.05", 100),
    (10, "Credit B", "0.24", 500, "0.08", 250),
    (11, "Deduction heavy", "0.30", 5000, "0.00", 300),
    (12, "Hybrid", "0.18", 1500, "0.02", 600),
    (13, "Premium", "0.12", 0, "0.00", 3000),
    (14, "Family", "0.21", 3000, "0.04", 200),
    (15, "Minimal", "0.10", 0, "0.00", 4500),
]
ROWS = [(r, n, Decimal(rt), d, Decimal(cr), f) for r, n, rt, d, cr, f in SCENARIOS]
SEED = 20261204
G_MAX, D_MAX, O_MAX, A_MAX = 60000, 10000, 10000, 10000


def costs(g: int, dep: int, oth: int, allow: int) -> list[Decimal]:
    out = []
    for _r, _n, rate, ded, credit, fee in ROWS:
        taxable = max(0, g - ded - oth - dep * allow)
        c = Decimal(taxable) * rate - Decimal(g) * credit + Decimal(fee)
        out.append(c.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))  # half away from zero
    return out


def winner(g: int, dep: int, oth: int, allow: int = 800) -> int:
    cs = costs(g, dep, oth, allow)
    return 6 + cs.index(min(cs))  # MAX of negated cost, MATCH first hit


def pick(rng: random.Random, hi: int) -> int:
    m = rng.random()
    if m < 0.5:
        return rng.randint(0, hi)
    if m < 0.9:  # log-uniform
        return min(hi, int(10 ** rng.uniform(0, len(str(hi)))) - 1) if hi else 0
    return rng.choice([0, 1, hi, hi - 1])


def sweep(vary_allow: bool, n_random: int) -> dict:
    wins: dict[int, dict] = {}

    def see(g, dep, oth, allow, src):
        r = winner(g, dep, oth, allow)
        w = wins.setdefault(r, {"count": 0, "first": None, "first_src": src})
        w["count"] += 1
        if w["first"] is None:
            w["first"] = {"gross_income": g, "dependants": dep, "other_deductions": oth, "allowance": allow}

    gs = list(range(0, G_MAX + 1, 2500))
    ds = [0, 1, 2, 3, 5, 10, 20, 50, 100, 1000, 10000]
    os_ = list(range(0, O_MAX + 1, 1000))
    als = [0, 200, 800, 2000, 5000, 10000] if vary_allow else [800]
    n_grid = 0
    for g, d, o, a in itertools.product(gs, ds, os_, als):
        see(g, d, o, a, "grid")
        n_grid += 1
    rng = random.Random(SEED)
    for _ in range(n_random):
        a = pick(rng, A_MAX) if vary_allow else 800
        see(pick(rng, G_MAX), pick(rng, D_MAX), pick(rng, O_MAX), a, "random")
    return {"grid_cases": n_grid, "random_cases": n_random, "wins": wins}


def load_logic(path: Path):
    spec = importlib.util.spec_from_file_location("l08_logic", path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(m)
    return m


def main() -> None:
    mig = Path(sys.argv[1])
    wbk = sys.argv[2]
    use_ref = "--referee" in sys.argv
    mod = load_logic(mig / "logic.py")
    rng = random.Random(SEED + 1)
    mism = 0
    N = 3000
    for _ in range(N):
        g, d, o = pick(rng, G_MAX), pick(rng, D_MAX), pick(rng, O_MAX)
        got = mod.compute({"gross_income": g, "dependants": d, "other_deductions": o})
        exp_r = winner(g, d, o, 800)
        exp_name = ROWS[exp_r - 6][1]
        exp_cost = min(costs(g, d, o, 800))
        if got["best_scenario"] != exp_name or Decimal(str(got["best_net_cost"])) != exp_cost:
            mism += 1
    res = {"replica_vs_logic_py": {"cases": N, "mismatches": mism}}
    a = sweep(False, 300000)
    b = sweep(True, 600000)
    res["sweep_default_boxes"] = a
    res["sweep_with_allowance"] = b
    if use_ref:
        from ghost.referee.client import RefereeClient

        spot = {}
        with RefereeClient(None, wbk) as ref:
            for r, w in sorted(a["wins"].items()):
                f = w["first"]
                got = ref.eval(
                    {"Model!B2": f["gross_income"], "Model!B3": f["dependants"], "Model!E2": f["other_deductions"]},
                    ["Model!B19", "Model!B20"],
                )
                spot[r] = {"input": f, "referee_B19": got["Model!B19"], "referee_B20": got["Model!B20"],
                           "expected": ROWS[r - 6][1]}
        res["referee_spot_check_default_boxes"] = spot
    json.dump(res, sys.stdout, indent=1, default=str)


if __name__ == "__main__":
    main()
