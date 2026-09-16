from decimal import Decimal
import json

from ticket_pricing.importer import import_text


def test_importer_reports_each_row_once_and_keeps_first_valid_duplicate():
    source = 'seat_class,price\n Gold , ₹250\nGOLD,399\nSilver,"250,00"\nRecliner,\nVIP,-5\nExecutive,garbage\n'
    report = import_text(source)
    assert report.total_rows_seen == 6
    assert report.imported_count == 2
    assert report.deduplicated_count == 1
    assert report.rejected_count == 3
    assert {item.canonical_name for item in report.imported} == {"Gold", "Silver"}
    all_rows = [item.row for item in report.imported] + [item.row for item in report.deduplicated] + [item.row for item in report.rejected]
    assert len(all_rows) == len(set(all_rows)) == 6


def test_json_import():
    report = import_text(json.dumps([{"seat_class": " Gold ", "price": "₹250"}, {"seat_class": "GOLD", "price": "251"}]), "json")
    assert report.imported[0].price == "250.00"
    assert report.deduplicated_count == 1
