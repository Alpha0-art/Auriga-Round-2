from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from ticket_pricing.money import money, parse_money


def test_parse_money_formats_and_rejects_invalid_values():
    assert parse_money("250") == Decimal("250.00")
    assert parse_money("₹250.00") == Decimal("250.00")
    assert parse_money("250,00") == Decimal("250.00")
    assert parse_money("₹1,200.00") == Decimal("1200.00")
    assert parse_money("Rs. 300") == Decimal("300.00")
    assert parse_money("300/-") == Decimal("300.00")
    with pytest.raises(ValueError, match="zero price"):
        parse_money("0")
    with pytest.raises(ValueError, match="negative price"):
        parse_money("-1")


def test_float_money_is_rejected():
    with pytest.raises(TypeError):
        money(1.1)


@given(st.integers(min_value=-1_000_000, max_value=1_000_000))
def test_integer_money_always_has_two_decimal_places(value: int):
    result = money(value)
    assert result == Decimal(value).quantize(Decimal("0.01"))
    assert result.as_tuple().exponent == -2
