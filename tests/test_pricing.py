from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from ticket_pricing.models import BookingRequest, SeatClass, SeatSelection
from ticket_pricing.pricing_engine import PricingConfig, PricingError, TicketPricingEngine


def test_mixed_booking_applies_rules_in_order():
    prices = {
        "Silver": SeatClass("Silver", Decimal("250.00")),
        "Gold": SeatClass("Gold", Decimal("350.00")),
    }
    config = PricingConfig(convenience_fee=Decimal("10"), member_discount_percent=Decimal("10"), member_discount_cap=Decimal("40"), gst_rate=Decimal("18"))
    result = TicketPricingEngine(prices, config).price(BookingRequest((SeatSelection("Silver", 2), SeatSelection("Gold", 1)), True, Decimal("50")))
    assert result.total == Decimal("932.20")
    assert sum(item.amount for item in result.line_items if item.contributes_to_total) == result.total


def test_cap_and_sold_out_protection():
    prices = {"Gold": SeatClass("Gold", Decimal("400"), available=1)}
    engine = TicketPricingEngine(prices)
    with pytest.raises(PricingError, match="sold out"):
        engine.price(BookingRequest((SeatSelection("Gold", 2),)))
    result = engine.price(BookingRequest((SeatSelection("Gold", 1),), member=True))
    assert any(item.amount == Decimal("-40.00") for item in result.line_items)


@given(
    st.lists(st.tuples(st.decimals(min_value="1", max_value="1000", allow_nan=False, allow_infinity=False, places=2), st.integers(1, 10)), min_size=1, max_size=5),
    st.integers(0, 200),
)
def test_property_line_items_are_exact(selections, festival):
    prices = {f"Tier{index}": SeatClass(f"Tier{index}", price) for index, (price, _) in enumerate(selections)}
    request = BookingRequest(tuple(SeatSelection(f"Tier{index}", quantity) for index, (_, quantity) in enumerate(selections)), member=True, festival_discount=Decimal(festival))
    result = TicketPricingEngine(prices).price(request)
    assert sum(item.amount for item in result.line_items if item.contributes_to_total) == result.total
    assert all(item.amount.as_tuple().exponent == -2 for item in result.line_items)
