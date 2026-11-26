"""Suspect (honest translation) for the graveyard/haunted.xlsx (Discount calculator (haunted)) workbook.

Test fixture written for the Trial by Workbook line-up; not produced by Ghost's transpiler. No AI authorship is claimed here, because no prompt is committed beside it.
Author: not recorded.
A line-by-line translation of the cell formulas, keeping the workbook's quirk: the discount applies at 50 or more, free delivery only above 50.
Planted difference: none.
Measured result: no difference found on 311 cases (seed 20261204).
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
    delivery = Decimal(0) if q > 50 else _round(BASE + max(Decimal(0), km - FREE_KM) * PER_KM, 2)      # B9: greater than 50 (the workbook's own quirk)
    vat = _round((net + delivery) * VAT, 2)                           # B10
    return {"total": net + delivery + vat}                          # B11
