from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CENT = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceTier:
    name: str
    base_price: Decimal


@dataclass(frozen=True)
class PriceOffer:
    code: str
    kind: str
    value: Decimal
    cap: Decimal | None = None
    stackable: bool = False


@dataclass(frozen=True)
class LineItem:
    description: str
    amount: Decimal


@dataclass(frozen=True)
class PriceBreakdown:
    line_items: tuple[LineItem, ...]
    total_payable: Decimal


class PricingError(ValueError):
    pass


# Offers are intentionally limited to one per booking. This prevents discount stacking
# ambiguity and keeps the quote identical to the committed booking.
def calculate_price(
    selections: Iterable[tuple[PriceTier, int]],
    offer: PriceOffer | None = None,
    convenience_fee_per_ticket: Decimal = Decimal("20.00"),
    gst_rate: Decimal = Decimal("18.00"),
    gst_taxable_base: str = "fee",
    currency_symbol: str = "₹",
) -> PriceBreakdown:
    selections = tuple(selections)
    if not selections:
        raise PricingError("At least one seat selection is required")
    if offer and offer.stackable:
        raise PricingError("Stackable offers are not supported; only one offer is allowed per booking")

    items: list[LineItem] = []
    ticket_count = 0
    subtotal = Decimal("0.00")
    for tier, quantity in selections:
        if quantity <= 0:
            raise PricingError("Quantity must be greater than zero")
        line_amount = money(tier.base_price * quantity)
        subtotal = money(subtotal + line_amount)
        ticket_count += quantity
        items.append(LineItem(f"{tier.name} x{quantity} @ {currency_symbol}{money(tier.base_price)}", line_amount))
    items.append(LineItem(f"Subtotal ({currency_symbol}{subtotal})", Decimal("0.00")))

    discount = Decimal("0.00")
    if offer:
        if offer.kind == "FLAT":
            discount = min(money(offer.value), subtotal)
            items.append(LineItem(f"{offer.code} Discount (flat)", -discount))
        elif offer.kind == "PERCENT_CAPPED":
            percentage_discount = money(subtotal * offer.value / Decimal("100"))
            discount = min(percentage_discount, money(offer.cap)) if offer.cap is not None else percentage_discount
            items.append(LineItem(f"{offer.code} Discount ({money(offer.value)}%, capped {currency_symbol}{money(offer.cap)})", -discount))
        else:
            raise PricingError(f"Unsupported offer type: {offer.kind}")
    discounted_subtotal = money(subtotal - discount)
    if offer:
        items.append(LineItem(f"Discounted Subtotal ({currency_symbol}{discounted_subtotal})", Decimal("0.00")))

    fee = money(convenience_fee_per_ticket * ticket_count)
    items.append(LineItem(f"Convenience Fee ({ticket_count} x {currency_symbol}{money(convenience_fee_per_ticket)})", fee))
    if gst_taxable_base == "fee":
        taxable_base = fee
    elif gst_taxable_base == "discounted_subtotal":
        taxable_base = discounted_subtotal
    elif gst_taxable_base == "subtotal_plus_fee":
        taxable_base = money(discounted_subtotal + fee)
    else:
        raise PricingError("gst_taxable_base must be fee, discounted_subtotal, or subtotal_plus_fee")
    gst = money(taxable_base * gst_rate / Decimal("100"))
    items.append(LineItem(f"GST ({money(gst_rate)}% on {gst_taxable_base.replace('_', ' ')})", gst))
    total = money(sum((item.amount for item in items), Decimal("0.00")))
    return PriceBreakdown(tuple(items), total)
