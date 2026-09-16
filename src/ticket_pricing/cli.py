from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any

from .importer import import_file
from .models import BookingRequest, SeatClass, SeatSelection
from .pricing_engine import PricingConfig, TicketPricingEngine


class PriceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, SeatClass]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {name: SeatClass(name, Decimal(item["price"]), item.get("available")) for name, item in raw.items()}

    def save(self, prices: dict[str, SeatClass]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: {"price": f"{seat_class.price:.2f}", "available": seat_class.available} for name, seat_class in prices.items()}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def config_from_env() -> PricingConfig:
    return PricingConfig(
        convenience_fee=Decimal(os.getenv("TICKET_CONVENIENCE_FEE", "20.00")),
        member_discount_percent=Decimal(os.getenv("TICKET_MEMBER_PERCENT", "10.00")),
        member_discount_cap=Decimal(os.getenv("TICKET_MEMBER_CAP", "150.00")),
        gst_rate=Decimal(os.getenv("TICKET_GST_RATE", "18.00")),
        gst_taxable_base=os.getenv("TICKET_GST_TAXABLE_BASE", "discounted_subtotal_plus_fee"),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ticket_pricing")
    parser.add_argument("--store", default=os.getenv("TICKET_PRICE_STORE", "data/prices.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    def add_store_option(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--store", default=argparse.SUPPRESS)

    import_parser = subparsers.add_parser("import-prices")
    add_store_option(import_parser)
    import_parser.add_argument("file")
    show_parser = subparsers.add_parser("show-prices")
    add_store_option(show_parser)
    book_parser = subparsers.add_parser("book")
    add_store_option(book_parser)
    book_parser.add_argument("--seats", required=True, help="Silver:2,Gold:1")
    book_parser.add_argument("--member", action="store_true")
    book_parser.add_argument("--festival-discount", default="0.00")
    sold_parser = subparsers.add_parser("sold-out")
    add_store_option(sold_parser)
    sold_parser.add_argument("seat_class")
    available_parser = subparsers.add_parser("available")
    add_store_option(available_parser)
    available_parser.add_argument("seat_class")
    return parser


def _booking_request(seats: str, member: bool, festival_discount: str) -> BookingRequest:
    selections = []
    for component in seats.split(","):
        try:
            name, quantity = component.split(":", 1)
            selections.append(SeatSelection(name.strip(), int(quantity)))
        except ValueError as error:
            raise ValueError(f"invalid seat selection {component!r}; use Class:quantity") from error
    return BookingRequest(tuple(selections), member=member, festival_discount=Decimal(festival_discount))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = PriceStore(Path(args.store))
    prices = store.load()
    if args.command == "import-prices":
        report = import_file(args.file)
        for imported_item in report.imported:
            current = prices.get(imported_item.canonical_name)
            prices[imported_item.canonical_name] = SeatClass(imported_item.canonical_name, Decimal(imported_item.price), current.available if current else None)
        store.save(prices)
        print(json.dumps(report.to_dict(), indent=2))
        return 0
    if args.command == "show-prices":
        print(json.dumps({name: {"price": f"{item.price:.2f}", "available": item.available} for name, item in prices.items()}, indent=2))
        return 0
    if args.command in {"sold-out", "available"}:
        key = args.seat_class.casefold()
        matching = next((item for name, item in prices.items() if name.casefold() == key), None)
        if matching is None:
            raise SystemExit(f"unknown seat class: {args.seat_class}")
        if args.command == "sold-out":
            print("yes" if matching.available == 0 else "no")
            return 0
        print(matching.available if matching.available is not None else "unlimited")
        return 0
    request = _booking_request(args.seats, args.member, args.festival_discount)
    result = TicketPricingEngine(prices, config_from_env()).price(request)
    for line_item in result.line_items:
        print(f"{line_item.description}: ₹{line_item.amount:.2f}")
    print(f"Grand Total: ₹{result.total:.2f}")
    updated = dict(prices)
    for selection in request.selections:
        seat_class = next(value for name, value in updated.items() if name.casefold() == selection.seat_class.casefold())
        if seat_class.available is not None:
            remaining = seat_class.available - selection.quantity
            updated[seat_class.name] = SeatClass(seat_class.name, seat_class.price, remaining)
    store.save(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
