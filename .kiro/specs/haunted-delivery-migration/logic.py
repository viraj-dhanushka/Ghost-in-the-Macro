"""Haunted delivery calculator, written by hand from rules.md (Faithful: workbook quirks kept)."""
from decimal import Decimal, ROUND_HALF_UP

# Constants read from the workbook with evaluate_original.
BULK_THRESHOLD = Decimal("50")       # Calculator!E2
BULK_DISCOUNT_RATE = Decimal("0.1")  # Calculator!E3
BASE_DELIVERY_FEE = Decimal("5")     # Calculator!E4
FREE_DELIVERY_KM = Decimal("10")     # Calculator!E5
FEE_PER_EXTRA_KM = Decimal("0.4")    # Calculator!E6
VAT_RATE = Decimal("0.2")            # Calculator!E7
FREE_DELIVERY_QTY = Decimal("50")    # literal 50 in Calculator!B9 (rule R-5f32fa17)


def _dec(x):
    if x is None or x == "":
        return Decimal(0)
    if isinstance(x, bool):
        return Decimal(int(x))
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    return Decimal(repr(x))


def _round2(x):
    """Worksheet ROUND(x, 2): 15 significant digits, then half away from zero."""
    if x == 0:
        return Decimal(0)
    exp = x.adjusted()
    x15 = x.quantize(Decimal(1).scaleb(exp - 14), rounding=ROUND_HALF_UP)
    return x15.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute(inputs: dict) -> dict:
    quantity = _dec(inputs.get("quantity"))
    unit_price = _dec(inputs.get("unit_price"))
    distance = _dec(inputs.get("delivery_distance_km"))

    # R-02486486
    subtotal = quantity * unit_price
    # R-805f7c28 (quantity >= threshold)
    if quantity >= BULK_THRESHOLD:
        discount = _round2(subtotal * BULK_DISCOUNT_RATE)
    else:
        discount = Decimal(0)
    # R-f140cd0d
    net = subtotal - discount
    # R-5f32fa17 (quantity > 50, strictly: differs from the discount rule)
    if quantity > FREE_DELIVERY_QTY:
        delivery = Decimal(0)
    else:
        extra = max(Decimal(0), distance - FREE_DELIVERY_KM)
        delivery = _round2(BASE_DELIVERY_FEE + extra * FEE_PER_EXTRA_KM)
    # R-a7324324
    vat = _round2((net + delivery) * VAT_RATE)
    # R-794f519c
    total = net + delivery + vat
    return {"total": total}
