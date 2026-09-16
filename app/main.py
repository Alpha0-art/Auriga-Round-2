from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .config import Settings, get_settings
from .database import Base, build_engine
from .models import Booking, BookingLineItem, Offer, Seat, SeatStatus, SeatTier, Show
from .pricing_engine import PriceOffer, PriceTier, PricingError, calculate_price, money
from .schemas import AvailabilityItem, AvailabilityResponse, BillLineItem, BillResponse, BookingRequest, BookingResponse


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cents(value: Decimal) -> str:
    return f"{money(value):.2f}"


def get_show_or_404(db: Session, show_id: int) -> Show:
    show = db.scalar(select(Show).options(joinedload(Show.tiers)).where(Show.id == show_id))
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


def get_offer(db: Session, offer_code: str | None) -> Offer | None:
    if not offer_code:
        return None
    offer = db.scalar(select(Offer).where(Offer.code == offer_code))
    if not offer:
        raise HTTPException(status_code=400, detail="Invalid offer code")
    current = now_utc()
    if not (offer.active_from <= current <= offer.active_to):
        raise HTTPException(status_code=400, detail="Offer is not active")
    return offer


def build_quote(db: Session, show_id: int, request: BookingRequest, settings: Settings | None = None):
    show = get_show_or_404(db, show_id)
    tiers = {tier.id: tier for tier in show.tiers}
    selected: list[tuple[SeatTier, int]] = []
    seen: set[int] = set()
    for selection in request.selections:
        if selection.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        if selection.tier_id in seen:
            raise HTTPException(status_code=400, detail="Each seat tier may appear only once")
        tier = tiers.get(selection.tier_id)
        if not tier:
            raise HTTPException(status_code=400, detail="Invalid seat tier for this show")
        available = db.scalar(select(func.count(Seat.id)).where(Seat.tier_id == tier.id, Seat.status == SeatStatus.AVAILABLE)) or 0
        if selection.quantity > available:
            raise HTTPException(status_code=409, detail=f"Tier {tier.name} has only {available} available seats")
        selected.append((PriceTier(tier.name, Decimal(tier.base_price)), selection.quantity))
        seen.add(selection.tier_id)
    offer = get_offer(db, request.offer_code)
    pricing_settings = settings or get_settings()
    try:
        return calculate_price(
            selected,
            PriceOffer(offer.code, offer.type, Decimal(offer.value), Decimal(offer.cap) if offer.cap is not None else None, offer.stackable) if offer else None,
            pricing_settings.convenience_fee_per_ticket,
            pricing_settings.gst_rate,
            pricing_settings.gst_taxable_base,
            pricing_settings.currency_symbol,
        ), offer
    except PricingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def bill_response(bill) -> BillResponse:
    return BillResponse(line_items=[BillLineItem(description=item.description, amount=cents(item.amount)) for item in bill.line_items], total_payable=cents(bill.total_payable))


def create_app(database_url: str | None = None, settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Cinema Ticket Pricing and Booking Engine", version="1.0.0")
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    active_settings = settings or get_settings()
    app.state.engine = engine

    def db_dependency():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    @app.post("/shows/{show_id}/quote", response_model=BillResponse)
    def quote(show_id: int, request: BookingRequest, db: Session = Depends(db_dependency)):
        bill, _ = build_quote(db, show_id, request, active_settings)
        return bill_response(bill)

    @app.post("/shows/{show_id}/book", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
    def book(show_id: int, request: BookingRequest, db: Session = Depends(db_dependency)):
        try:
            bill, offer = build_quote(db, show_id, request, active_settings)
            booking = Booking(show_id=show_id, offer_code_used=offer.code if offer else None, total_amount=bill.total_payable)
            db.add(booking)
            db.flush()
            for selection in request.selections:
                seats = db.scalars(
                    select(Seat).where(Seat.tier_id == selection.tier_id, Seat.status == SeatStatus.AVAILABLE).order_by(Seat.id).limit(selection.quantity)
                ).all()
                if len(seats) != selection.quantity:
                    raise HTTPException(status_code=409, detail="Insufficient available seats; please retry")
                for seat in seats:
                    seat.status = SeatStatus.BOOKED
            booking.line_items = [BookingLineItem(description=item.description, amount=item.amount) for item in bill.line_items]
            db.commit()
            db.refresh(booking)
            return BookingResponse(
                id=booking.id, show_id=booking.show_id, offer_code_used=booking.offer_code_used,
                created_at=booking.created_at, line_items=[BillLineItem(description=i.description, amount=cents(i.amount)) for i in booking.line_items],
                total_payable=cents(booking.total_amount),
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    @app.get("/bookings/{booking_id}", response_model=BookingResponse)
    def get_booking(booking_id: int, db: Session = Depends(db_dependency)):
        booking = db.scalar(select(Booking).options(joinedload(Booking.line_items)).where(Booking.id == booking_id))
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return BookingResponse(
            id=booking.id, show_id=booking.show_id, offer_code_used=booking.offer_code_used,
            created_at=booking.created_at, line_items=[BillLineItem(description=i.description, amount=cents(i.amount)) for i in booking.line_items],
            total_payable=cents(booking.total_amount),
        )

    @app.get("/shows/{show_id}/availability", response_model=AvailabilityResponse)
    def availability(show_id: int, db: Session = Depends(db_dependency)):
        show = get_show_or_404(db, show_id)
        result = []
        for tier in show.tiers:
            available = db.scalar(select(func.count(Seat.id)).where(Seat.tier_id == tier.id, Seat.status == SeatStatus.AVAILABLE)) or 0
            result.append(AvailabilityItem(tier_id=tier.id, tier_name=tier.name, available_seats=available, total_seats=tier.total_seats))
        return AvailabilityResponse(show_id=show_id, tiers=result)

    return app


app = create_app()
