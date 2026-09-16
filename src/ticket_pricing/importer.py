from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from .money import parse_money


@dataclass(frozen=True)
class PriceRecord:
    row: str
    canonical_name: str
    price: str


@dataclass(frozen=True)
class DeduplicatedRecord:
    row: str
    merged_into: str
    reason: str


@dataclass(frozen=True)
class RejectedRecord:
    row: str
    reason: str


@dataclass(frozen=True)
class ImportReport:
    total_rows_seen: int
    imported: tuple[PriceRecord, ...]
    deduplicated: tuple[DeduplicatedRecord, ...]
    rejected: tuple[RejectedRecord, ...]

    @property
    def imported_count(self) -> int:
        return len(self.imported)

    @property
    def deduplicated_count(self) -> int:
        return len(self.deduplicated)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows_seen": self.total_rows_seen,
            "imported_count": self.imported_count,
            "deduplicated_count": self.deduplicated_count,
            "rejected_count": self.rejected_count,
            "imported": [asdict(item) for item in self.imported],
            "deduplicated": [asdict(item) for item in self.deduplicated],
            "rejected": [asdict(item) for item in self.rejected],
        }


class PriceImportError(ValueError):
    pass


def canonical_name(value: str) -> str:
    return " ".join(value.strip().split()).title()


def _row_text(name: str, raw_price: str) -> str:
    return f"{name}, {raw_price}" if raw_price else f"{name},"


def _clean_rows(rows: Iterable[tuple[str, str]]) -> ImportReport:
    imported: list[PriceRecord] = []
    deduplicated: list[DeduplicatedRecord] = []
    rejected: list[RejectedRecord] = []
    seen: dict[str, PriceRecord] = {}
    row_count = 0
    for raw_name, raw_price in rows:
        row_count += 1
        name = raw_name.strip()
        price_text = raw_price.strip()
        row = _row_text(raw_name, raw_price)
        if not price_text:
            rejected.append(RejectedRecord(row, "blank price"))
            continue
        try:
            price = parse_money(price_text)
        except ValueError as error:
            rejected.append(RejectedRecord(row, str(error)))
            continue
        if not name:
            rejected.append(RejectedRecord(row, "blank seat class"))
            continue
        canonical = canonical_name(name)
        key = canonical.casefold()
        if key in seen:
            deduplicated.append(DeduplicatedRecord(row, canonical, "case-insensitive duplicate, first valid occurrence kept"))
            continue
        record = PriceRecord(row, canonical, f"{price:.2f}")
        seen[key] = record
        imported.append(record)
    return ImportReport(row_count, tuple(imported), tuple(deduplicated), tuple(rejected))


def import_text(text: str, fmt: str = "csv") -> ImportReport:
    if fmt.lower() == "csv":
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames or not {field.strip().lower() for field in reader.fieldnames} >= {"seat_class", "price"}:
            raise PriceImportError("CSV must contain seat_class and price columns")
        fields = {field.strip().lower(): field for field in reader.fieldnames}
        return _clean_rows((str(row.get(fields["seat_class"], "")), str(row.get(fields["price"], ""))) for row in reader)
    if fmt.lower() == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise PriceImportError("invalid JSON") from error
        if not isinstance(data, list):
            raise PriceImportError("JSON price list must be an array")
        return _clean_rows((str(item.get("seat_class", "")), str(item.get("price", ""))) for item in data if isinstance(item, dict))
    raise PriceImportError("supported formats are CSV and JSON")


def import_file(path: str | Path) -> ImportReport:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return import_text(source.read_text(encoding="utf-8-sig"), "csv")
    if suffix == ".json":
        return import_text(source.read_text(encoding="utf-8"), "json")
    if suffix in {".xlsx", ".xls"}:
        try:
            import openpyxl
        except ImportError as error:
            raise PriceImportError("Excel import requires openpyxl") from error
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
        worksheet = workbook.active
        if worksheet is None:
            raise PriceImportError("Excel workbook has no active worksheet")
        rows = worksheet.iter_rows(values_only=True)
        headers = [str(value).strip().lower() if value is not None else "" for value in next(rows)]
        try:
            name_index, price_index = headers.index("seat_class"), headers.index("price")
        except ValueError as error:
            raise PriceImportError("Excel must contain seat_class and price columns") from error
        return _clean_rows((str(row[name_index] or ""), str(row[price_index] or "")) for row in rows)
    raise PriceImportError("supported formats are CSV, JSON, and Excel")
