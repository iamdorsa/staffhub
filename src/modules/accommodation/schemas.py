from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, model_validator

from src.config import settings


# ── Place ────────────────────────────────────────────────────────────────────

class PlaceCreate(BaseModel):
    city: str
    name: str


class PlaceUpdate(BaseModel):
    city: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None


class RoomTypeResponse(BaseModel):
    id: int
    key: str
    label: str
    max_capacity: int
    model_config = {"from_attributes": True}


class PlaceRoomResponse(BaseModel):
    room_type: RoomTypeResponse
    total_rooms: int
    is_vip: bool
    model_config = {"from_attributes": True}


class PlaceResponse(BaseModel):
    id: int
    city: str
    name: str
    is_active: bool
    rooms: list[PlaceRoomResponse] = []
    model_config = {"from_attributes": True}


class PlaceRoomSet(BaseModel):
    room_type_id: int
    total_rooms: int
    is_vip: bool = False


# ── Availability ─────────────────────────────────────────────────────────────

class AvailabilitySetRequest(BaseModel):
    dates: list[date]
    room_type_id: Optional[int] = None
    blocked_count: int = 0


class AvailabilityResponse(BaseModel):
    id: int
    place_id: int
    room_type_id: Optional[int]
    date: date
    blocked_count: int
    blocked_by_user_id: Optional[int]
    model_config = {"from_attributes": True}


# ── Org Place Access ─────────────────────────────────────────────────────────

class OrgPlaceAccessSet(BaseModel):
    org_id: int
    is_allowed: bool


class OrgPlaceAccessResponse(BaseModel):
    id: int
    org_id: int
    place_id: int
    is_allowed: bool
    model_config = {"from_attributes": True}


# ── Pricing ──────────────────────────────────────────────────────────────────

class PricingRuleCreate(BaseModel):
    place_id: int
    room_type_id: int
    person_group: str
    price_per_night: Decimal
    effective_from: date
    effective_to: Optional[date] = None


class PricingRuleResponse(BaseModel):
    id: int
    place_id: int
    room_type_id: int
    person_group: str
    price_per_night: Decimal
    effective_from: date
    effective_to: Optional[date]
    model_config = {"from_attributes": True}


# ── Org Special Plans ────────────────────────────────────────────────────────

class OrgSpecialPlanCreate(BaseModel):
    org_id: int
    plan_type: str  # NEW_MARRIAGE or NEW_CHILD
    eligible_from: date
    eligible_until: date


class OrgSpecialPlanUpdate(BaseModel):
    eligible_from: Optional[date] = None
    eligible_until: Optional[date] = None
    is_active: Optional[bool] = None


class OrgSpecialPlanResponse(BaseModel):
    id: int
    org_id: int
    plan_type: str
    eligible_from: date
    eligible_until: date
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class UserPlanEligibilityResponse(BaseModel):
    id: int
    user_id: int
    plan_type: str
    org_id: int
    is_used: bool
    eligible_from: date
    eligible_until: date
    created_at: datetime


# ── Reservation ──────────────────────────────────────────────────────────────

class GuestInput(BaseModel):
    person_type: str
    name: Optional[str] = None


class ReservationCreate(BaseModel):
    place_id: int
    check_in_date: date
    check_out_date: date
    guests: list[GuestInput]
    use_special_plan: bool = False
    vip: bool = False

    @model_validator(mode="after")
    def validate_dates_and_guests(self):
        nights = (self.check_out_date - self.check_in_date).days
        if nights < 1:
            raise ValueError("check_out_date must be after check_in_date")
        if nights > settings.MAX_STAY_NIGHTS:
            raise ValueError(f"Maximum stay is {settings.MAX_STAY_NIGHTS} nights")
        total_persons = 1 + len(self.guests)  # employee + guests
        if total_persons > settings.MAX_PERSONS_PER_RESERVATION:
            raise ValueError(f"Maximum {settings.MAX_PERSONS_PER_RESERVATION} persons per reservation")
        extra = sum(1 for g in self.guests if g.person_type == "GUEST")
        if extra > settings.MAX_EXTRA_GUESTS:
            raise ValueError(f"Maximum {settings.MAX_EXTRA_GUESTS} extra guests allowed")
        return self


class GuestResponse(BaseModel):
    id: int
    person_type: str
    name: Optional[str]
    is_extra: bool
    extra_charge: Decimal
    model_config = {"from_attributes": True}


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    org_id: int
    place_id: int
    room_type_id: int
    check_in_date: date
    check_out_date: date
    nights: int
    status: str
    is_vip: bool
    admin_deadline_at: datetime
    total_price: Decimal
    discount_percent: int
    final_price: Decimal
    user_plan_eligibility_id: Optional[int]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime
    guests: list[GuestResponse] = []
    model_config = {"from_attributes": True}


class ReservationReviewRequest(BaseModel):
    action: str  # APPROVE or REJECT
