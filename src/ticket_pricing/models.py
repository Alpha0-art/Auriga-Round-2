from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .money import money


@dataclass(frozen=True)
class SeatClass:
    name: str
    price: Decimal
    available: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", money(self.price))
        if self.price <= 0:
            raise ValueError("seat class price must be greater than zero")
        if self.available is not None and self.available < 0:
            raise ValueError("available seats cannot be negative")


@dataclass(frozen=True)
class SeatSelection:
    seat_class: str
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")


@dataclass(frozen=True)
class BookingRequest:
    selections: tuple[SeatSelection, ...]
    member: bool = False
    festival_discount: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if not self.selections:
            raise ValueError("at least one seat selection is required")
        object.__setattr__(self, "festival_discount", money(self.festival_discount))
        if self.festival_discount < 0:
            raise ValueError("festival discount cannot be negative")

    @property
    def ticket_count(self) -> int:
        return sum(selection.quantity for selection in self.selections)
