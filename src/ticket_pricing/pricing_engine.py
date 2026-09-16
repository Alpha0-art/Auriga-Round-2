from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import Mapping

from .models import BookingRequest, SeatClass
from .money import money

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PricingConfig:
    convenience_fee: Decimal = Decimal("20.00")
    member_discount_percent: Decimal = Decimal("10.00")
    member_discount_cap: Decimal = Decimal("150.00")
    gst_rate: Decimal = Decimal("18.00")
    gst_taxable_base: str = "discounted_subtotal_plus_fee"

    def __post_init__(self) -> None:
        for name in ("convenience_fee", "member_discount_percent", "member_discount_cap", "gst_rate"):
            value = money(getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)
        if self.gst_taxable_base not in {"fee", "discounted_subtotal", "discounted_subtotal_plus_fee"}:
            raise ValueError("gst_taxable_base must be fee, discounted_subtotal, or discounted_subtotal_plus_fee")

    @classmethod
    def from_yaml(cls, path: str) -> "PricingConfig":
        try:
            import yaml
        except ImportError as error:
            raise RuntimeError("YAML configuration requires PyYAML") from error
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
        return cls(**{key: value for key, value in data.items() if key in {"convenience_fee", "member_discount_percent", "member_discount_cap", "gst_rate", "gst_taxable_base"}})


@dataclass(frozen=True)
class LineItem:
    description: str
    amount: Decimal
    contributes_to_total: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))


@dataclass(frozen=True)
class PricingResult:
    line_items: tuple[LineItem, ...]
    total: Decimal


class PricingError(ValueError):
    pass


class TicketPricingEngine:
    """Pure deterministic pricing service; inventory is checked, never mutated, here."""

    def __init__(self, prices: Mapping[str, SeatClass], config: PricingConfig | None = None) -> None:
        self._prices = {name.casefold(): seat_class for name, seat_class in prices.items()}
        self.config = config or PricingConfig()

    def price(self, request: BookingRequest) -> PricingResult:
        line_items: list[LineItem] = []
        subtotal = Decimal("0.00")
        for selection in request.selections:
            seat_class = self._prices.get(selection.seat_class.casefold())
            if seat_class is None:
                raise PricingError(f"unknown seat class: {selection.seat_class}")
            if seat_class.available is not None and selection.quantity > seat_class.available:
                raise PricingError(f"sold out: {seat_class.name} has {seat_class.available} seats available")
            line_total = money(seat_class.price * selection.quantity)
            subtotal = money(subtotal + line_total)
            line_items.append(LineItem(f"{seat_class.name} x {selection.quantity} @ ₹{seat_class.price:.2f}", line_total))
            logger.info("priced %s x %s at %s", seat_class.name, selection.quantity, line_total)

        line_items.append(LineItem(f"Subtotal (₹{subtotal:.2f})", Decimal("0.00"), False))
        festival_discount = min(request.festival_discount, subtotal)
        if festival_discount:
            line_items.append(LineItem("Festival Discount", -festival_discount))
        after_festival = money(subtotal - festival_discount)

        member_discount = Decimal("0.00")
        if request.member:
            member_discount = min(money(after_festival * self.config.member_discount_percent / Decimal("100")), self.config.member_discount_cap)
            line_items.append(LineItem(f"Member Discount ({self.config.member_discount_percent:.2f}%, capped)", -member_discount))
        discounted_subtotal = money(after_festival - member_discount)
        line_items.append(LineItem(f"Discounted Subtotal (₹{discounted_subtotal:.2f})", Decimal("0.00"), False))

        fee = money(self.config.convenience_fee * request.ticket_count)
        line_items.append(LineItem(f"Convenience Fee ({request.ticket_count} x ₹{self.config.convenience_fee:.2f})", fee))
        if self.config.gst_taxable_base == "fee":
            taxable_amount = fee
        elif self.config.gst_taxable_base == "discounted_subtotal":
            taxable_amount = discounted_subtotal
        else:
            taxable_amount = money(discounted_subtotal + fee)
        line_items.append(LineItem(f"Taxable Amount (₹{taxable_amount:.2f})", Decimal("0.00"), False))
        gst = money(taxable_amount * self.config.gst_rate / Decimal("100"))
        line_items.append(LineItem(f"GST @ {self.config.gst_rate:.2f}%", gst))
        total = money(sum((item.amount for item in line_items if item.contributes_to_total), Decimal("0.00")))
        logger.info("pricing complete tickets=%s total=%s", request.ticket_count, total)
        return PricingResult(tuple(line_items), total)
