"""Suspect (dropped branch) for the graveyard/haunted.xlsx (Discount calculator (haunted)) workbook.

Test fixture written for the Trial by Workbook line-up; not produced by Ghost's transpiler. No AI authorship is claimed here, because no prompt is committed beside it.
Author: not recorded.
The honest translation with the free-delivery branch left out.
Planted difference: no free delivery above 50: the delivery fee is always charged.
Measured result: difference found (targeted boundary case, not shrunk) at delivery_distance_km=12, quantity=51, unit_price=19.95: Referee 1098.84, suspect 1105.8 (seed 20261204).
"""

from decimal import Context, Decimal, ROUND_HALF_UP

THRESHOLD = 50          # Calculator!E2, bulk threshold (units)
RATE = Decimal("0.1")   # Calculator!E3, bulk discount rate
BASE = Decimal("5")     # Calculator!E4, base delivery fee
FREE_KM = Decimal("10") # Calculator!E5, free delivery within (km)
PER_KM = Decimal("0.4") # Calculator!E6, fee per extra km
VAT = Decimal("0.2")    # Calculator!E7, VAT rate
_NORMALISE = Context(prec=15, rounding=ROUND_HALF_UP)


def _d(x):
    return Decimal(repr(x)) if isinstance(x, float) else Decimal(str(x))


def _round(x, places):
    """Worksheet ROUND: 15 significant digits, then half away from zero."""
    return _NORMALISE.plus(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def compute(inputs):
    q = int(inputs["quantity"])
    price = _d(inputs["unit_price"])
    km = _d(inputs["delivery_distance_km"])
    subtotal = q * price                                              # B6
    discount = _round(subtotal * RATE, 2) if q >= THRESHOLD else Decimal(0)   # B7: at least 50
    net = subtotal - discount                                         # B8
    delivery = _round(BASE + max(Decimal(0), km - FREE_KM) * PER_KM, 2)                                 # dropped: no free-delivery branch
    vat = _round((net + delivery) * VAT, 2)                           # B10
    return {"total": net + delivery + vat}                          # B11
