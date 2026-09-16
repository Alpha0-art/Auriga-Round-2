from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class SeatStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"


class OfferType(StrEnum):
    FLAT = "FLAT"
    PERCENT_CAPPED = "PERCENT_CAPPED"


class Cinema(Base):
    __tablename__ = "cinemas"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    screens: Mapped[list["Screen"]] = relationship(back_populates="cinema", cascade="all, delete-orphan")


class Screen(Base):
    __tablename__ = "screens"
    id: Mapped[int] = mapped_column(primary_key=True)
    cinema_id: Mapped[int] = mapped_column(ForeignKey("cinemas.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cinema: Mapped[Cinema] = relationship(back_populates="screens")
    shows: Mapped[list["Show"]] = relationship(back_populates="screen", cascade="all, delete-orphan")


class Show(Base):
    __tablename__ = "shows"
    id: Mapped[int] = mapped_column(primary_key=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("screens.id"), nullable=False, index=True)
    movie_name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    screen: Mapped[Screen] = relationship(back_populates="shows")
    tiers: Mapped[list["SeatTier"]] = relationship(back_populates="show", cascade="all, delete-orphan")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="show")


class SeatTier(Base):
    __tablename__ = "seat_tiers"
    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    show: Mapped[Show] = relationship(back_populates="tiers")
    seats: Mapped[list["Seat"]] = relationship(back_populates="tier", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("show_id", "name"),)


class Seat(Base):
    __tablename__ = "seats"
    id: Mapped[int] = mapped_column(primary_key=True)
    tier_id: Mapped[int] = mapped_column(ForeignKey("seat_tiers.id"), nullable=False, index=True)
    seat_number: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(String(20), nullable=False, default=SeatStatus.AVAILABLE)
    tier: Mapped[SeatTier] = relationship(back_populates="seats")
    __table_args__ = (UniqueConstraint("tier_id", "seat_number"),)


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type: Mapped[OfferType] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cap: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    active_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active_to: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=False, index=True)
    offer_code_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    show: Mapped[Show] = relationship(back_populates="bookings")
    line_items: Mapped[list["BookingLineItem"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class BookingLineItem(Base):
    __tablename__ = "booking_line_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    booking: Mapped[Booking] = relationship(back_populates="line_items")


class ImportReport(Base):
    __tablename__ = "import_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    deduplicated_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    report_detail: Mapped[str] = mapped_column(Text, nullable=False)
