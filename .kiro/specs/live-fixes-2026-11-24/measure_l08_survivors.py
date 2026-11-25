"""L-08 baseline, survivor analysis (task 5.6). Measurement only.

For every mutant in a proof-report.json, rebuild the mutation on an exact
integer replica of the scenarios sheet (default boxes: gross_income,
dependants, other_deductions; allowance E3 fixed at 800) and search the whole
domain (grid + seeded random) for an input where (B19, B20) differ from the
original. Reports, per survivor, the row, whether the row can win, and
whether ANY input in the domain separates the mutant from the original.

Usage: python measure_l08_survivors.py <proof-report.json> [--allow]
(--allow also varies the allowance 0..10000, as if E3 were a fourth box.)

Mutation model (constants in F{r} = ROUND(MAX(0, B2-C-E2-B3*E3)*B - B2*D + E, 2)):
  B,C,D,E cells: constant +/- 1.   F cells: the MAX floor 0 -> +/-1, the ROUND
  digits 2 -> 3 or 1; rounding_mode: half-up -> half-even, which can't matter
  here because every cost is already exact to 2 decimals (checked below).
"""
from __future__ import annotations

import itertools
import json
import random
import re
import sys

SCEN = {  # row: rate%, deduction, credit%, fee
    6: (20, 0, 0, 0), 7: (25, 2000, 0, 0), 8: (15, 0, 0, 1500), 9: (22, 1000, 5, 100),
    10: (24, 500, 8, 250), 11: (30, 5000, 0, 300), 12: (18, 1500, 2, 600),
    13: (12, 0, 0, 3000), 14: (21, 3000, 4, 200), 15: (10, 0, 0, 4500),
}
ROWS = sorted(SCEN)
SEED = 20261204


def half_away(num: int, den: int) -> int:
    """round(num/den) half away from zero, integers."""
    q, r = divmod(abs(num), den)
    if 2 * r >= den:
        q += 1
    return q if num >= 0 else -q


def cost_cents(p, g, dep, oth, allow, floor=0, digits=2) -> int:
    rate, ded, credit, fee = p
    taxable = max(floor, g - ded - oth - dep * allow)
    c = taxable * rate - g * credit + fee * 100  # exact, in cents
    if digits >= 2:
        return c
    return half_away(c, 10) * 10  # digits == 1


def outcome(params: dict, g, dep, oth, allow):
    cs = [cost_cents(params[r]["p"], g, dep, oth, allow, params[r]["floor"], params[r]["digits"]) for r in ROWS]
    best = min(cs)
    return ROWS[cs.index(best)], best  # (winning row, cost in cents)


def base_params():
    return {r: {"p": SCEN[r], "floor": 0, "digits": 2} for r in ROWS}


def variant(row: int, kind: str, delta: int):
    prm = base_params()
    p = list(SCEN[row])
    if kind == "B":
        p[0] += 100 * delta  # rate is stored in percent
    elif kind == "C":
        p[1] += delta
    elif kind == "D":
        p[2] += 100 * delta
    elif kind == "E":
        p[3] += delta
    prm[row]["p"] = tuple(p)
    if kind == "floor":
        prm[row]["floor"] = delta
    if kind == "digits":
        prm[row]["digits"] = 2 + delta
    return prm


def samples(vary_allow: bool, n_random: int):
    for g, d, o in itertools.product(range(0, 60001, 2500), [0, 1, 2, 3, 5, 10, 50, 100, 1000, 10000], range(0, 10001, 1000)):
        for a in ([0, 200, 800, 2000, 5000, 10000] if vary_allow else [800]):
            yield g, d, o, a
    rng = random.Random(SEED)

    def pick(hi):
        m = rng.random()
        if m < 0.5:
            return rng.randint(0, hi)
        if m < 0.9:
            return min(hi, int(10 ** rng.uniform(0, len(str(hi)))) - 1)
        return rng.choice([0, 1, hi, hi - 1])

    for _ in range(n_random):
        yield pick(60000), pick(10000), pick(10000), (pick(10000) if vary_allow else 800)


def main() -> None:
    rep = json.load(open(sys.argv[1]))
    vary = "--allow" in sys.argv
    pts = list(samples(vary, 200000))
    base = {pt: outcome(base_params(), *pt) for pt in pts}
    winners = sorted({w for w, _ in base.values()})
    # which operators/constants exist per mutant location
    cache: dict[tuple, tuple | None] = {}

    def separates(row, kind, delta):
        key = (row, kind, delta)
        if key not in cache:
            prm = variant(row, kind, delta)
            hit = None
            for pt in pts:
                if outcome(prm, *pt) != base[pt]:
                    hit = pt
                    break
            cache[key] = hit
        return cache[key]

    # rounding_mode check: all costs exact to the cent for rate/credit with 2 decimals
    out = {"winning_rows": winners, "survivors": []}
    for m in rep["mutation"]["mutants"]:
        if m["killed"]:
            continue
        cell = m["location"].split("!")[1]
        col, row = re.match(r"([A-Z]+)(\d+)", cell).groups()
        row = int(row)
        op = m["operator"]
        sign = 1 if op == "constant_plus_one" else -1
        if col in "BCDE":
            variants = [(col, sign)]
        elif col == "F" and op == "rounding_mode":
            variants = []  # equivalent: costs are exact in cents, so no rounding mode can change them
        elif col == "F":
            variants = [("floor", sign), ("digits", sign)]
        else:
            variants = None
        info = {"mutant": m["mutant_id"], "cell": cell, "row": row, "operator": op,
                "row_can_win": row in winners}
        if variants is None:
            info["note"] = "unmodelled"
        else:
            info["variants"] = {f"{k}{d:+d}": separates(row, k, d) for k, d in variants}
        out["survivors"].append(info)
    out["summary"] = summarise(out["survivors"])
    json.dump(out, sys.stdout, indent=1)


def summarise(surv: list) -> dict:
    """Group survivors. F cells hold two constants per operator (MAX floor 0, ROUND digits 2) and the
    report doesn't say which one a mutant changed, so for F cells the number of survivors that some input
    could kill is |separable variants| - (2 - survivors): the variants that died must have been separable."""
    from collections import defaultdict

    a_rows = b_rows = 0  # coarse: row can win somewhere / never wins
    fine_killable = fine_equiv = 0
    groups = defaultdict(list)
    for s in surv:
        groups[(s["cell"], s["operator"])].append(s)
        if s["row_can_win"]:
            a_rows += 1
        else:
            b_rows += 1
    per = []
    for (cell, op), lst in groups.items():
        n = len(lst)
        if op == "rounding_mode":
            killable = 0
        elif cell.startswith("F"):
            sep = sum(1 for v in lst[0]["variants"].values() if v)
            killable = max(0, sep - (2 - n))
        else:
            killable = sum(1 for v in lst[0]["variants"].values() if v)
        killable = min(killable, n)
        fine_killable += killable
        fine_equiv += n - killable
        per.append({"cell": cell, "operator": op, "survivors": n, "killable_by_some_domain_input": killable,
                    "row_can_win": lst[0]["row_can_win"]})
    return {
        "survivors": len(surv),
        "coarse_a_rows_that_can_win": a_rows,
        "coarse_b_rows_that_never_win": b_rows,
        "fine_killable_by_some_input": fine_killable,
        "fine_no_input_changes_any_output": fine_equiv,
        "fine_by_row_can_win": {
            "win_killable": sum(p["killable_by_some_domain_input"] for p in per if p["row_can_win"]),
            "win_equivalent": sum(p["survivors"] - p["killable_by_some_domain_input"] for p in per if p["row_can_win"]),
            "never_killable": sum(p["killable_by_some_domain_input"] for p in per if not p["row_can_win"]),
            "never_equivalent": sum(p["survivors"] - p["killable_by_some_domain_input"] for p in per if not p["row_can_win"]),
        },
        "per_cell_operator": sorted(per, key=lambda p: (p["cell"][0], int(p["cell"][1:]), p["operator"])),
    }


if __name__ == "__main__":
    main()
