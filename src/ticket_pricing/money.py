from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str) -> Decimal:
    """Convert a value to deterministic, half-up rounded paise."""
    if isinstance(value, float):
        raise TypeError("float money values are not accepted")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_money(value: str | Decimal | int, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, (Decimal, int)):
        parsed = money(value)
    else:
        if not isinstance(value, str):
            raise ValueError("price must be text, Decimal, or integer")
        cleaned = value.strip()
        cleaned = re.sub(r"^(?:₹|Rs\.?|INR)\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*/-\s*$", "", cleaned)
        if not cleaned:
            raise ValueError("blank price")
        if "," in cleaned and "." not in cleaned:
            groups = cleaned.split(",")
            if len(groups) == 2 and len(groups[-1]) == 2 and groups[0].isdigit():
                cleaned = ".".join(groups)
            else:
                cleaned = "".join(groups)
        else:
            cleaned = cleaned.replace(",", "")
        try:
            parsed = money(Decimal(cleaned))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("unparseable price") from error
    if parsed < ZERO:
        raise ValueError("negative price")
    if not allow_zero and parsed == ZERO:
        raise ValueError("zero price")
    return parsed
