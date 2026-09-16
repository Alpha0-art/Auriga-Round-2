from decimal import Decimal

from app.price_import import import_prices, parse_price


def test_case_insensitive_dedup_keeps_first_occurrence():
    report = import_prices("seat_class,price\nGold,400\nGOLD,399\ngold,401\n")
    assert [(item.canonical_name, item.price) for item in report.imported] == [("Gold", Decimal("400.00"))]
    assert len(report.deduplicated) == 2
    assert all(item.merged_into == "Gold" for item in report.deduplicated)
    assert "first occurrence kept" in report.deduplicated[0].reason


def test_currency_formats_normalize_to_decimal_cents():
    assert parse_price("250") == Decimal("250.00")
    assert parse_price("₹250.00") == Decimal("250.00")
    assert parse_price("250.5") == Decimal("250.50")
    assert parse_price("Rs. 300") == Decimal("300.00")
    assert parse_price("300/-") == Decimal("300.00")
    assert parse_price("₹1,200.00") == Decimal("1200.00")


def test_blank_and_negative_prices_are_rejected():
    report = import_prices("seat_class,price\nBalcony,\nRecliner,-50\n")
    assert [item.reason for item in report.rejected] == ["blank price", "negative price"]


def test_every_data_row_lands_in_exactly_one_bucket():
    source = "seat_class,price\nGold,400\nGOLD,399\nSilver,250.5\nBalcony,\nRecliner,-50\nExecutive,bad\n"
    report = import_prices(source)
    data_row_count = 6
    assert len(report.imported) + len(report.deduplicated) + len(report.rejected) == data_row_count
    rows = [item.row for item in report.imported] + [item.row for item in report.deduplicated] + [item.row for item in report.rejected]
    assert len(rows) == len(set(rows)) == data_row_count
    assert len(report.imported) == 2
    assert len(report.deduplicated) == 1
    assert len(report.rejected) == 3
