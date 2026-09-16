from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, build_engine
from app.main import create_app
from app.models import Cinema, Screen, Seat, SeatStatus, SeatTier, Show


@pytest.fixture
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'api.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        cinema = Cinema(name="Test Cinema")
        db.add(cinema)
        db.flush()
        screen = Screen(cinema_id=cinema.id, name="Screen A")
        db.add(screen)
        db.flush()
        show = Show(screen_id=screen.id, movie_name="Test Movie", start_time=datetime.utcnow() + timedelta(days=1))
        db.add(show)
        db.flush()
        tier = SeatTier(show_id=show.id, name="Silver", base_price=Decimal("100.00"), total_seats=2)
        db.add(tier)
        db.flush()
        db.add_all([Seat(tier_id=tier.id, seat_number=f"S{index}", status=SeatStatus.AVAILABLE) for index in range(1, 3)])
        db.commit()
        tier_id = tier.id
        show_id = show.id
    return TestClient(create_app(database_url)), show_id, tier_id


def test_quote_book_retrieve_and_availability(client):
    api, show_id, tier_id = client
    payload = {"selections": [{"tier_id": tier_id, "quantity": 1}]}
    quote = api.post(f"/shows/{show_id}/quote", json=payload)
    assert quote.status_code == 200
    assert quote.json()["total_payable"] == "123.60"
    booking = api.post(f"/shows/{show_id}/book", json=payload)
    assert booking.status_code == 201
    booking_body = booking.json()
    assert sum(Decimal(item["amount"]) for item in booking_body["line_items"]) == Decimal(booking_body["total_payable"])
    stored = api.get(f"/bookings/{booking_body['id']}")
    assert stored.status_code == 200
    assert stored.json()["line_items"] == booking_body["line_items"]
    availability = api.get(f"/shows/{show_id}/availability").json()
    assert availability["tiers"][0]["available_seats"] == 1


def test_invalid_and_sellout_requests_are_clear_conflicts(client):
    api, show_id, tier_id = client
    invalid = api.post(f"/shows/{show_id}/book", json={"selections": [{"tier_id": tier_id, "quantity": 0}]})
    assert invalid.status_code == 400
    first = api.post(f"/shows/{show_id}/book", json={"selections": [{"tier_id": tier_id, "quantity": 2}]})
    assert first.status_code == 201
    sold_out = api.post(f"/shows/{show_id}/book", json={"selections": [{"tier_id": tier_id, "quantity": 1}]})
    assert sold_out.status_code == 409
    assert "available seats" in sold_out.json()["detail"]


def test_price_list_import_persists_full_report(client):
    api, _, _ = client
    csv_content = "seat_class,price\nGold,400\nGOLD,399\nSilver,₹250.00\nBalcony,\nRecliner,-50\n"
    response = api.post("/price-lists/import?filename=prices.csv", content=csv_content, headers={"content-type": "text/csv"})
    assert response.status_code == 201
    body = response.json()
    assert body["imported_count"] == 2
    assert body["deduplicated_count"] == 1
    assert body["rejected_count"] == 2
    assert body["imported"][0]["price"] == "400.00"
    stored = api.get(f"/price-lists/imports/{body['id']}")
    assert stored.status_code == 200
    assert stored.json() == body


def test_price_list_import_rejects_non_csv(client):
    api, _, _ = client
    response = api.post("/price-lists/import?filename=prices.txt", content="Gold,400", headers={"content-type": "text/csv"})
    assert response.status_code == 400
