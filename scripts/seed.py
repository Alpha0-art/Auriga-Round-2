from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import Base, build_engine
from app.models import Cinema, Offer, OfferType, Screen, Seat, SeatStatus, SeatTier, Show


def seed(database_url: str = "sqlite:///./cinema.db") -> None:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.query(Seat).delete()
        db.query(SeatTier).delete()
        db.query(Show).delete()
        db.query(Screen).delete()
        db.query(Cinema).delete()
        db.query(Offer).delete()
        now = datetime.utcnow()
        cinemas = [Cinema(name="Auriga Central"), Cinema(name="Auriga Riverside")]
        db.add_all(cinemas)
        db.flush()
        screens = [Screen(cinema_id=cinemas[0].id, name="Screen 1"), Screen(cinema_id=cinemas[0].id, name="IMAX"), Screen(cinema_id=cinemas[1].id, name="Screen 1")]
        db.add_all(screens)
        db.flush()
        for index, screen in enumerate(screens):
            show = Show(screen_id=screen.id, movie_name=["The Last Orbit", "Monsoon Letters", "City of Glass"][index], start_time=now + timedelta(days=1, hours=index * 2))
            db.add(show)
            db.flush()
            for name, price, count in [("Silver", "250.00", 20), ("Gold", "400.00", 12), ("Recliner", "650.00", 6)]:
                tier = SeatTier(show_id=show.id, name=name, base_price=Decimal(price), total_seats=count)
                db.add(tier)
                db.flush()
                db.add_all([Seat(tier_id=tier.id, seat_number=f"{name[:1]}{number}", status=SeatStatus.AVAILABLE) for number in range(1, count + 1)])
        db.add_all([
            Offer(code="FEST100", type=OfferType.FLAT, value=Decimal("100.00"), active_from=now - timedelta(days=1), active_to=now + timedelta(days=30), stackable=False),
            Offer(code="MEMBER10", type=OfferType.PERCENT_CAPPED, value=Decimal("10.00"), cap=Decimal("150.00"), active_from=now - timedelta(days=1), active_to=now + timedelta(days=30), stackable=False),
        ])
        db.commit()
        print("Seeded cinemas, shows, tiers, seats, and offers into cinema.db")


if __name__ == "__main__":
    seed()
