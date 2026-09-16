from decimal import Decimal
import random

import pytest

from app.pricing_engine import PriceOffer, PriceTier, PricingError, calculate_price


def test_plain_total_calculation():
    result = calculate_price([(PriceTier("Silver", Decimal("250.00")), 2), (PriceTier("Gold", Decimal("400.00")), 1)])
    assert result.total_payable == Decimal("970.80")
    assert sum(item.amount for item in result.line_items) == result.total_payable


def test_flat_discount():
    result = calculate_price([(PriceTier("Silver", Decimal("250.00")), 2)], PriceOffer("FEST100", "FLAT", Decimal("100")))
    assert result.total_payable == Decimal("447.20")
    assert next(item.amount for item in result.line_items if "FEST100" in item.description) == Decimal("-100.00")


def test_percentage_discount_cap():
    result = calculate_price([(PriceTier("Gold", Decimal("400.00")), 10)], PriceOffer("MEMBER10", "PERCENT_CAPPED", Decimal("10"), Decimal("150")))
    assert next(item.amount for item in result.line_items if "MEMBER10" in item.description) == Decimal("-150.00")


def test_offer_stacking_is_explicitly_disallowed():
    with pytest.raises(PricingError, match="only one offer"):
        calculate_price([(PriceTier("Silver", Decimal("250")), 1)], PriceOffer("STACK", "FLAT", Decimal("10"), stackable=True))


def test_fee_and_gst_stack_on_fee():
    result = calculate_price([(PriceTier("Silver", Decimal("250")), 3)], convenience_fee_per_ticket=Decimal("20"), gst_rate=Decimal("18"))
    assert result.total_payable == Decimal("820.80")
    assert result.line_items[-2].amount == Decimal("60.00")
    assert result.line_items[-1].amount == Decimal("10.80")


def test_rounding_fuzz_preserves_exact_line_item_sum():
    randomizer = random.Random(20260916)
    for _ in range(50):
        selections = [(PriceTier(f"Tier{index}", Decimal(randomizer.randint(1, 99999)) / Decimal("100")), randomizer.randint(1, 12)) for index in range(1, randomizer.randint(2, 5))]
        offer = None
        if randomizer.choice([True, False]):
            offer = PriceOffer("FUZZ", "PERCENT_CAPPED", Decimal(randomizer.randint(1, 30)), Decimal(randomizer.randint(1, 500)))
        result = calculate_price(selections, offer, Decimal("19.99"), Decimal("18.00"))
        assert sum(item.amount for item in result.line_items) == result.total_payable
        assert all(item.amount.as_tuple().exponent >= -2 for item in result.line_items)
