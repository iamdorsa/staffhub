from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from src.config import settings


# ── Place ────────────────────────────────────────────────────────────────────

class PlaceCreate(BaseModel):
    city: str
    name: str
    address: Optional[str] = None
    image_url: Optional[str] = None


class PlaceUpdate(BaseModel):
    city: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class RoomTypeResponse(BaseModel):
    id: int
    key: str
    label: str
    max_capacity: int
    model_config = {"from_attributes": True}


class PlaceRoomResponse(BaseModel):
    id: int
    room_type: RoomTypeResponse
    name: Optional[str] = None
    total_rooms: int
    capacity: Optional[int] = None
    is_vip: bool
    model_config = {"from_attributes": True}


class PlaceResponse(BaseModel):
    id: int
    city: str
    name: str
    address: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    rooms: list[PlaceRoomResponse] = []
    model_config = {"from_attributes": True}


class PlaceRoomSet(BaseModel):
    room_type_id: int
    name: Optional[str] = None
    total_rooms: int
    capacity: Optional[int] = None
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
    place_ids: list[int] = []


class OrgSpecialPlanUpdate(BaseModel):
    eligible_from: Optional[date] = None
    eligible_until: Optional[date] = None
    is_active: Optional[bool] = None
    place_ids: Optional[list[int]] = None


class OrgSpecialPlanResponse(BaseModel):
    id: int
    org_id: int
    plan_type: str
    eligible_from: date
    eligible_until: date
    is_active: bool
    place_ids: list[int] = []
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
    place_ids: list[int] = []
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
            raise ValueError("تاریخ خروج باید بعد از تاریخ ورود باشد")
        if nights > settings.MAX_STAY_NIGHTS:
            raise ValueError(f"حداکثر مدت اقامت {settings.MAX_STAY_NIGHTS} شب است")
        total_persons = 1 + len(self.guests)  # employee + guests
        if total_persons > settings.MAX_PERSONS_PER_RESERVATION:
            raise ValueError(f"حداکثر {settings.MAX_PERSONS_PER_RESERVATION} نفر در هر رزرو مجاز است")
        extra = sum(1 for g in self.guests if g.person_type == "GUEST")
        if extra > settings.MAX_EXTRA_GUESTS:
            raise ValueError(f"حداکثر {settings.MAX_EXTRA_GUESTS} مهمان اضافه مجاز است")
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
    user_display_name: Optional[str] = None
    place_name: Optional[str] = None
    model_config = {"from_attributes": True}


class AdminReservationCreate(BaseModel):
    user_id: int
    place_id: int
    room_type_id: int
    check_in_date: date
    check_out_date: date
    is_vip: bool = False
    status: str = "APPROVED"
    guests: list[GuestInput] = []

    @model_validator(mode="after")
    def validate_dates(self):
        if self.check_out_date <= self.check_in_date:
            raise ValueError("تاریخ خروج باید بعد از تاریخ ورود باشد")
        return self


class ReservationReviewRequest(BaseModel):
    action: str  # APPROVE or REJECT
    remove_plan: bool = False


# ── Calendar ────────────────────────────────────────────────────────────────

class CalendarReservationInfo(BaseModel):
    reservation_id: int
    user_display_name: Optional[str] = None
    status: str
    check_in_date: date
    check_out_date: date


class RoomReservationCalendarItem(BaseModel):
    date: date
    room_type_id: int
    room_type_key: str
    is_vip: bool
    total_rooms: int
    reserved_count: int
    blocked_count: int
    available_count: int
    reservations: list[CalendarReservationInfo]


# ── Ratings ─────────────────────────────────────────────────────────────────

class PlaceRatingCreate(BaseModel):
    place_id: int
    score: int

    @model_validator(mode="after")
    def validate_score(self):
        if self.score < 1 or self.score > 5:
            raise ValueError("امتیاز باید بین ۱ تا ۵ باشد")
        return self


class PlaceRatingResponse(BaseModel):
    id: int
    user_id: int
    place_id: int
    score: int
    created_at: datetime
    model_config = {"from_attributes": True}


class PlaceRatingSummary(BaseModel):
    place_id: int
    average_score: float
    total_ratings: int


# ── Special Plan Requests ───────────────────────────────────────────────────

class SpecialPlanRequestCreate(BaseModel):
    plan_type: str  # NEW_MARRIAGE or NEW_CHILD


class SpecialPlanRequestReview(BaseModel):
    action: str  # APPROVE or REJECT
    admin_note: Optional[str] = None
    place_id: Optional[int] = None
    room_type_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None


class SpecialPlanRequestResponse(BaseModel):
    id: int
    user_id: int
    org_id: int
    plan_type: str
    status: str
    admin_note: Optional[str] = None
    place_id: Optional[int] = None
    room_type_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    reservation_id: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    user_display_name: Optional[str] = None
    place_name: Optional[str] = None
    room_type_label: Optional[str] = None
    model_config = {"from_attributes": True}


class DiscountInfoResponse(BaseModel):
    shamsi_year: int
    usage_count: int
    next_discount_percent: int


# ── Banners ────────────────────────────────────────────────────────────────

class BannerCreate(BaseModel):
    title: str
    text: str
    image_url: Optional[str] = None


class BannerUpdate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class BannerResponse(BaseModel):
    id: int
    title: str
    text: str
    image_url: Optional[str]
    is_active: bool
    created_by_user_id: Optional[int]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
