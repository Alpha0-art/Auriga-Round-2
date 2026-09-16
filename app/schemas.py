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


class ImportedPriceResponse(BaseModel):
    row: str
    canonical_name: str
    price: str


class DeduplicatedPriceResponse(BaseModel):
    row: str
    merged_into: str
    reason: str


class RejectedPriceResponse(BaseModel):
    row: str
    reason: str


class ImportReportResponse(BaseModel):
    id: int
    source_filename: str
    imported_count: int
    deduplicated_count: int
    rejected_count: int
    created_at: datetime
    imported: list[ImportedPriceResponse]
    deduplicated: list[DeduplicatedPriceResponse]
    rejected: list[RejectedPriceResponse]
