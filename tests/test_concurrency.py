from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, build_engine
from app.main import create_app
from app.models import Cinema, Screen, Seat, SeatStatus, SeatTier, Show


def test_ten_racers_against_one_last_seat(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'race.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        cinema = Cinema(name="Race Cinema")
        db.add(cinema)
        db.flush()
        screen = Screen(cinema_id=cinema.id, name="Screen")
        db.add(screen)
        db.flush()
        show = Show(screen_id=screen.id, movie_name="Race Movie", start_time=datetime.utcnow() + timedelta(days=1))
        db.add(show)
        db.flush()
        tier = SeatTier(show_id=show.id, name="Last Seat", base_price=Decimal("100"), total_seats=1)
        db.add(tier)
        db.flush()
        db.add(Seat(tier_id=tier.id, seat_number="L1", status=SeatStatus.AVAILABLE))
        db.commit()
        show_id, tier_id = show.id, tier.id

    app = create_app(database_url)
    payload = {"selections": [{"tier_id": tier_id, "quantity": 1}]}

    def book_once(_):
        with TestClient(app) as client:
            return client.post(f"/shows/{show_id}/book", json=payload).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(book_once, range(10)))

    assert statuses.count(201) == 1
    assert statuses.count(409) == 9
    with Session(engine) as db:
        assert db.scalar(select(func.count(Seat.id)).where(Seat.tier_id == tier_id, Seat.status == SeatStatus.BOOKED)) == 1
