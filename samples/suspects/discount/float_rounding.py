"""Suspect (float rounding) for the discount calculator workbook (samples/make_discount.py).

Test fixture written for the Trial by Workbook line-up; not produced by Ghost's transpiler. No AI authorship is claimed here, because no prompt is committed beside it.
Author: not recorded.
The honest translation in binary floats with Python round() in place of the worksheet ROUND.
Planted difference: Python round() on binary floats in place of the worksheet ROUND.
Measured result: difference found (shrunk) at delivery_distance_km=0, quantity=3565, unit_price=0.01: Referee 38.5, suspect 38.51 (seed 20261204).
"""

THRESHOLD = 50
RATE, BASE, FREE_KM, PER_KM, VAT = 0.1, 5.0, 10.0, 0.4, 0.2


def compute(inputs):
    q = int(inputs["quantity"])
    price = float(inputs["unit_price"])
    km = float(inputs["delivery_distance_km"])
    subtotal = q * price
    discount = round(subtotal * RATE, 2) if q >= THRESHOLD else 0.0
    net = subtotal - discount
    delivery = 0.0 if q >= 50 else round(BASE + max(0.0, km - FREE_KM) * PER_KM, 2)
    vat = round((net + delivery) * VAT, 2)
    return {"total": net + delivery + vat}
