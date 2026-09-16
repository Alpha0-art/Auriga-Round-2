import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class ImportedPrice:
    row: str
    canonical_name: str
    price: Decimal


@dataclass(frozen=True)
class DeduplicatedPrice:
    row: str
    merged_into: str
    reason: str


@dataclass(frozen=True)
class RejectedPrice:
    row: str
    reason: str


@dataclass(frozen=True)
class ImportReportData:
    imported: tuple[ImportedPrice, ...]
    deduplicated: tuple[DeduplicatedPrice, ...]
    rejected: tuple[RejectedPrice, ...]


class PriceImportError(ValueError):
    pass


def canonical_name(value: str) -> str:
    return " ".join(value.strip().split()).title()


def parse_price(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "")
    cleaned = re.sub(r"^\s*(?:₹|Rs\.?|INR)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*/-\s*$", "", cleaned)
    if not cleaned:
        raise PriceImportError("blank price")
    try:
        price = Decimal(cleaned)
    except InvalidOperation as error:
        raise PriceImportError("unparseable price") from error
    if price < 0:
        raise PriceImportError("negative price")
    return price.quantize(Decimal("0.01"))


def import_prices(csv_text: str) -> ImportReportData:
    reader = csv.reader(io.StringIO(csv_text))
    imported: list[ImportedPrice] = []
    deduplicated: list[DeduplicatedPrice] = []
    rejected: list[RejectedPrice] = []
    first_by_key: dict[str, str] = {}
    rows = list(reader)
    if rows and [cell.strip().lower() for cell in rows[0]] == ["seat_class", "price"]:
        rows = rows[1:]
    for row_values in rows:
        row = ", ".join(row_values)
        if not row_values or not any(cell.strip() for cell in row_values):
            rejected.append(RejectedPrice(row, "blank price"))
            continue
        name = row_values[0].strip() if row_values else ""
        price_text = ",".join(row_values[1:]).strip() if len(row_values) > 1 else ""
        if not price_text:
            rejected.append(RejectedPrice(row, "blank price"))
            continue
        try:
            price = parse_price(price_text)
        except PriceImportError as error:
            rejected.append(RejectedPrice(row, str(error)))
            continue
        if not name:
            rejected.append(RejectedPrice(row, "unparseable price"))
            continue
        display_name = canonical_name(name)
        key = display_name.casefold()
        if key in first_by_key:
            deduplicated.append(DeduplicatedPrice(row, first_by_key[key], "case-insensitive duplicate, first occurrence kept"))
            continue
        first_by_key[key] = display_name
        imported.append(ImportedPrice(row, display_name, price))
    return ImportReportData(tuple(imported), tuple(deduplicated), tuple(rejected))