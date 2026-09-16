from datetime import datetime
from pydantic import BaseModel, Field


class TierSelection(BaseModel):
    tier_id: int = Field(gt=0)
    quantity: int


class BookingRequest(BaseModel):
    selections: list[TierSelection] = Field(min_length=1)
    offer_code: str | None = None


class BillLineItem(BaseModel):
    description: str
    amount: str


class BillResponse(BaseModel):
    line_items: list[BillLineItem]
    total_payable: str


class BookingResponse(BillResponse):
    id: int
    show_id: int
    offer_code_used: str | None
    created_at: datetime


class AvailabilityItem(BaseModel):
    tier_id: int
    tier_name: str
    available_seats: int
    total_seats: int


class AvailabilityResponse(BaseModel):
    show_id: int
    tiers: list[AvailabilityItem]
