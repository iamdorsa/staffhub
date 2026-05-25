from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.accommodation import (
    Banner,
    DiscountUsage,
    OrgPlaceAccess,
    OrgSpecialPlan,
    OrgSpecialPlanPlace,
    Place,
    PlaceAvailability,
    PlaceRating,
    PlaceRoom,
    PricingRule,
    Reservation,
    ReservationGuest,
    RoomType,
    SpecialPlanRequest,
    UserPlanEligibility,
)
from models.identity import User, UserProfile
from src.config import settings
from src.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from src.modules.notifications.service import NotificationType, create_notification, notify_admins
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser
from src.modules.accommodation.schemas import (
    AdminReservationCreate,
    AvailabilityResponse,
    AvailabilitySetRequest,
    BannerCreate,
    BannerResponse,
    BannerUpdate,
    CalendarReservationInfo,
    OrgPlaceAccessResponse,
    OrgPlaceAccessSet,
    OrgSpecialPlanCreate,
    OrgSpecialPlanResponse,
    OrgSpecialPlanUpdate,
    PlaceCreate,
    PlaceRatingCreate,
    PlaceRatingResponse,
    PlaceRatingSummary,
    PlaceResponse,
    PlaceRoomResponse,
    PlaceRoomSet,
    PlaceUpdate,
    PricingRuleCreate,
    PricingRuleResponse,
    ReservationCreate,
    ReservationResponse,
    RoomReservationCalendarItem,
    RoomTypeResponse,
    SpecialPlanRequestCreate,
    SpecialPlanRequestResponse,
    SpecialPlanRequestReview,
    UserPlanEligibilityResponse,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _place_label(db: Session, place_id: int) -> str:
    place = db.get(Place, place_id)
    return f"{place.city} - {place.name}" if place else ""


def _plan_type_label(plan_type: str) -> str:
    return "ازدواج جدید" if plan_type == "NEW_MARRIAGE" else "فرزند جدید"


def _get_shamsi_year() -> int:
    now = datetime.now(timezone.utc)
    return now.year - 621


def _get_usage_count(db: Session, user_id: int, shamsi_year: int) -> int:
    usage = db.execute(
        select(DiscountUsage).where(
            DiscountUsage.user_id == user_id, DiscountUsage.year == shamsi_year
        )
    ).scalar_one_or_none()
    return usage.usage_count if usage else 0


def _calc_discount_percent(usage_count: int) -> int:
    if usage_count == 0:
        return 50
    if usage_count == 1:
        return 30
    return 0


def _increment_usage(db: Session, user_id: int, shamsi_year: int) -> None:
    usage = db.execute(
        select(DiscountUsage).where(
            DiscountUsage.user_id == user_id, DiscountUsage.year == shamsi_year
        )
    ).scalar_one_or_none()
    if usage:
        usage.usage_count += 1
    else:
        db.add(DiscountUsage(user_id=user_id, year=shamsi_year, usage_count=1))


# ── Discount Info ─────────────────────────────────────────────────────────────

def get_discount_info(db: Session, user_id: int) -> dict:
    shamsi_year = _get_shamsi_year()
    count = _get_usage_count(db, user_id, shamsi_year)
    return {
        "shamsi_year": shamsi_year,
        "usage_count": count,
        "next_discount_percent": _calc_discount_percent(count),
    }


# ── Room Types ────────────────────────────────────────────────────────────────

def list_room_types(db: Session) -> list[RoomTypeResponse]:
    rows = db.execute(select(RoomType).order_by(RoomType.id)).scalars().all()
    return [RoomTypeResponse.model_validate(r) for r in rows]


# ── Places ────────────────────────────────────────────────────────────────────

def list_places(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    city: str | None = None, is_active: bool | None = None, search: str | None = None,
):
    base = select(Place)

    if current_user.is_super_admin:
        if is_active is not None:
            base = base.where(Place.is_active == is_active)
    else:
        base = base.where(Place.is_active == True)  # noqa: E712
        allowed_ids = select(OrgPlaceAccess.place_id).where(
            OrgPlaceAccess.org_id == current_user.org_id, OrgPlaceAccess.is_allowed == True  # noqa: E712
        )
        base = base.where(Place.id.in_(allowed_ids))

    if city:
        base = base.where(Place.city.ilike(f"%{city}%"))
    if search:
        pattern = f"%{search}%"
        base = base.where(or_(Place.name.ilike(pattern), Place.city.ilike(pattern)))

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(Place.id).offset(params.offset).limit(params.page_size)).scalars().all()
    items = [PlaceResponse.model_validate(p) for p in rows]
    if not current_user.is_super_admin:
        for item in items:
            item.rooms = [r for r in item.rooms if not r.is_vip]
    return PaginatedResponse.create(items, total, params)


def get_place(db: Session, place_id: int, current_user: CurrentUser) -> PlaceResponse:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")
    resp = PlaceResponse.model_validate(place)
    if not current_user.is_super_admin:
        resp.rooms = [r for r in resp.rooms if not r.is_vip]
    return resp


def create_place(db: Session, data: PlaceCreate) -> PlaceResponse:
    place = Place(city=data.city, name=data.name, address=data.address, image_url=data.image_url)
    db.add(place)
    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def update_place(db: Session, place_id: int, data: PlaceUpdate) -> PlaceResponse:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")
    if data.city is not None:
        place.city = data.city
    if data.name is not None:
        place.name = data.name
    if data.address is not None:
        place.address = data.address
    if data.image_url is not None:
        place.image_url = data.image_url
    if data.is_active is not None:
        place.is_active = data.is_active
    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def set_rooms(db: Session, place_id: int, rooms: list[PlaceRoomSet]) -> PlaceResponse:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    for r in rooms:
        existing = db.execute(
            select(PlaceRoom).where(PlaceRoom.place_id == place_id, PlaceRoom.room_type_id == r.room_type_id, PlaceRoom.is_vip == r.is_vip)
        ).scalar_one_or_none()
        if existing:
            existing.total_rooms = r.total_rooms
            if r.name is not None:
                existing.name = r.name
            if r.capacity is not None:
                existing.capacity = r.capacity
        else:
            db.add(PlaceRoom(place_id=place_id, room_type_id=r.room_type_id, name=r.name, total_rooms=r.total_rooms, capacity=r.capacity, is_vip=r.is_vip))

    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def set_availability(db: Session, place_id: int, data: AvailabilitySetRequest, admin_id: int) -> dict:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    for d in data.dates:
        existing = db.execute(
            select(PlaceAvailability).where(
                PlaceAvailability.place_id == place_id,
                PlaceAvailability.room_type_id == data.room_type_id,
                PlaceAvailability.date == d,
            )
        ).scalar_one_or_none()
        if existing:
            existing.blocked_count = data.blocked_count
            existing.blocked_by_user_id = admin_id
        else:
            db.add(PlaceAvailability(
                place_id=place_id, room_type_id=data.room_type_id,
                date=d, blocked_count=data.blocked_count, blocked_by_user_id=admin_id,
            ))

    db.commit()
    return {"updated": len(data.dates)}


def set_org_access(db: Session, place_id: int, data: OrgPlaceAccessSet) -> dict:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    existing = db.execute(
        select(OrgPlaceAccess).where(OrgPlaceAccess.org_id == data.org_id, OrgPlaceAccess.place_id == place_id)
    ).scalar_one_or_none()
    if existing:
        existing.is_allowed = data.is_allowed
    else:
        db.add(OrgPlaceAccess(org_id=data.org_id, place_id=place_id, is_allowed=data.is_allowed))

    db.commit()
    return {"org_id": data.org_id, "place_id": place_id, "is_allowed": data.is_allowed}


def list_rooms(db: Session, place_id: int, current_user: CurrentUser) -> list[PlaceRoomResponse]:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")
    query = select(PlaceRoom).where(PlaceRoom.place_id == place_id)
    if not current_user.is_super_admin:
        query = query.where(PlaceRoom.is_vip == False)  # noqa: E712
    rows = db.execute(query.order_by(PlaceRoom.id)).scalars().all()
    return [PlaceRoomResponse.model_validate(r) for r in rows]


def list_availability(
    db: Session, place_id: int, from_date: date | None = None, to_date: date | None = None, room_type_id: int | None = None,
) -> list[AvailabilityResponse]:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")
    query = select(PlaceAvailability).where(PlaceAvailability.place_id == place_id)
    if from_date:
        query = query.where(PlaceAvailability.date >= from_date)
    if to_date:
        query = query.where(PlaceAvailability.date <= to_date)
    if room_type_id:
        query = query.where(PlaceAvailability.room_type_id == room_type_id)
    rows = db.execute(query.order_by(PlaceAvailability.date)).scalars().all()
    return [AvailabilityResponse.model_validate(r) for r in rows]


def list_org_access(db: Session, place_id: int) -> list[OrgPlaceAccessResponse]:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")
    rows = db.execute(
        select(OrgPlaceAccess).where(OrgPlaceAccess.place_id == place_id).order_by(OrgPlaceAccess.id)
    ).scalars().all()
    return [OrgPlaceAccessResponse.model_validate(r) for r in rows]


# ── Unavailable Dates ───────────────────────────────────────────────────────

def get_unavailable_dates(
    db: Session, place_id: int, from_date: date, to_date: date, is_vip: bool = False,
    room_type_id: int | None = None,
) -> list[date]:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    q = select(PlaceRoom).where(PlaceRoom.place_id == place_id, PlaceRoom.is_vip == is_vip)
    if room_type_id:
        q = q.where(PlaceRoom.room_type_id == room_type_id)
    place_rooms = db.execute(q).scalars().all()
    if not place_rooms:
        delta = (to_date - from_date).days
        return [from_date + timedelta(days=i) for i in range(delta)]

    unavailable = []
    delta = (to_date - from_date).days
    for i in range(delta):
        check_date = from_date + timedelta(days=i)
        any_available = False
        for pr in place_rooms:
            blocked = db.execute(
                select(func.coalesce(func.sum(PlaceAvailability.blocked_count), 0)).where(
                    PlaceAvailability.place_id == place_id,
                    PlaceAvailability.date == check_date,
                    or_(PlaceAvailability.room_type_id == pr.room_type_id, PlaceAvailability.room_type_id == None),  # noqa: E711
                )
            ).scalar() or 0
            reserved = db.execute(
                select(func.count()).where(
                    Reservation.place_id == place_id,
                    Reservation.room_type_id == pr.room_type_id,
                    Reservation.is_vip == pr.is_vip,
                    Reservation.status.in_(["PENDING", "APPROVED"]),
                    Reservation.check_in_date <= check_date,
                    Reservation.check_out_date > check_date,
                )
            ).scalar() or 0
            if pr.total_rooms - int(blocked) - int(reserved) > 0:
                any_available = True
                break
        if not any_available:
            unavailable.append(check_date)
    return unavailable


# ── Pricing ──────────────────────────────────────────────────────────────────

def create_pricing_rule(db: Session, data: PricingRuleCreate) -> PricingRuleResponse:
    rule = PricingRule(
        place_id=data.place_id, room_type_id=data.room_type_id,
        person_group=data.person_group, price_per_night=data.price_per_night,
        effective_from=data.effective_from, effective_to=data.effective_to,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return PricingRuleResponse.model_validate(rule)


def list_pricing_rules(db: Session, place_id: int) -> list[PricingRuleResponse]:
    rows = db.execute(select(PricingRule).where(PricingRule.place_id == place_id)).scalars().all()
    return [PricingRuleResponse.model_validate(r) for r in rows]


def _get_price(db: Session, place_id: int, room_type_id: int, person_group: str, on_date: date) -> Decimal:
    rule = db.execute(
        select(PricingRule).where(
            PricingRule.place_id == place_id,
            PricingRule.room_type_id == room_type_id,
            PricingRule.person_group == person_group,
            PricingRule.effective_from <= on_date,
            or_(PricingRule.effective_to == None, PricingRule.effective_to >= on_date),  # noqa: E711
        ).order_by(PricingRule.effective_from.desc()).limit(1)
    ).scalar_one_or_none()
    return rule.price_per_night if rule else Decimal(0)


# ── Org Special Plans ────────────────────────────────────────────────────────

def _build_plan_response(plan: OrgSpecialPlan) -> OrgSpecialPlanResponse:
    resp = OrgSpecialPlanResponse.model_validate(plan)
    resp.place_ids = [pp.place_id for pp in plan.plan_places]
    return resp


def create_org_special_plan(db: Session, data: OrgSpecialPlanCreate) -> OrgSpecialPlanResponse:
    existing = db.execute(
        select(OrgSpecialPlan).where(
            OrgSpecialPlan.org_id == data.org_id,
            OrgSpecialPlan.plan_type == data.plan_type,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("این نوع طرح ویژه قبلاً برای این سازمان ثبت شده")

    plan = OrgSpecialPlan(
        org_id=data.org_id, plan_type=data.plan_type,
        eligible_from=data.eligible_from, eligible_until=data.eligible_until,
    )
    db.add(plan)
    db.flush()

    for pid in data.place_ids:
        db.add(OrgSpecialPlanPlace(org_special_plan_id=plan.id, place_id=pid))

    db.commit()
    db.refresh(plan)
    return _build_plan_response(plan)


def update_org_special_plan(db: Session, plan_id: int, data: OrgSpecialPlanUpdate) -> OrgSpecialPlanResponse:
    plan = db.get(OrgSpecialPlan, plan_id)
    if not plan:
        raise NotFoundError("طرح ویژه یافت نشد")
    if data.eligible_from is not None:
        plan.eligible_from = data.eligible_from
    if data.eligible_until is not None:
        plan.eligible_until = data.eligible_until
    if data.is_active is not None:
        plan.is_active = data.is_active

    if data.place_ids is not None:
        db.execute(
            sa.delete(OrgSpecialPlanPlace).where(OrgSpecialPlanPlace.org_special_plan_id == plan_id)
        )
        for pid in data.place_ids:
            db.add(OrgSpecialPlanPlace(org_special_plan_id=plan_id, place_id=pid))

    db.commit()
    db.refresh(plan)
    return _build_plan_response(plan)


def list_org_special_plans(db: Session, org_id: int) -> list[OrgSpecialPlanResponse]:
    rows = db.execute(select(OrgSpecialPlan).where(OrgSpecialPlan.org_id == org_id)).scalars().all()
    return [_build_plan_response(r) for r in rows]


def list_user_eligibility(db: Session, user_id: int) -> list[UserPlanEligibilityResponse]:
    rows = db.execute(
        select(UserPlanEligibility).where(UserPlanEligibility.user_id == user_id)
    ).scalars().all()
    result = []
    for e in rows:
        result.append(UserPlanEligibilityResponse(
            id=e.id, user_id=e.user_id,
            plan_type=e.org_plan.plan_type, org_id=e.org_plan.org_id,
            is_used=e.is_used,
            eligible_from=e.org_plan.eligible_from, eligible_until=e.org_plan.eligible_until,
            place_ids=[pp.place_id for pp in e.org_plan.plan_places],
            created_at=e.created_at,
        ))
    return result


def grant_user_plan_eligibility(
    db: Session, user_id: int, org_id: int, plan_type: str,
) -> UserPlanEligibility | None:
    """Auto-grant eligibility if the user's org has an active plan of this type."""
    org_plan = db.execute(
        select(OrgSpecialPlan).where(
            OrgSpecialPlan.org_id == org_id,
            OrgSpecialPlan.plan_type == plan_type,
            OrgSpecialPlan.is_active == True,  # noqa: E712
            OrgSpecialPlan.eligible_until >= date.today(),
        )
    ).scalar_one_or_none()
    if not org_plan:
        return None

    eligibility = UserPlanEligibility(user_id=user_id, org_special_plan_id=org_plan.id)
    db.add(eligibility)
    return eligibility


# ── Reservations ─────────────────────────────────────────────────────────────

def _enrich_reservation(reservation: Reservation) -> ReservationResponse:
    """Build a ReservationResponse with user_display_name and place_name populated."""
    resp = ReservationResponse.model_validate(reservation)

    # User display name from profile
    user = reservation.user
    if user and user.profile:
        resp.user_display_name = f"{user.profile.first_name} {user.profile.last_name}"

    # Place name (city + name)
    place = reservation.place
    if place:
        resp.place_name = f"{place.city} - {place.name}"

    return resp

def create_reservation(db: Session, current_user: CurrentUser, data: ReservationCreate) -> ReservationResponse:
    today = date.today()
    if data.check_in_date < today:
        raise BadRequestError("امکان رزرو در تاریخ گذشته وجود ندارد")
    if (data.check_in_date - today).days > settings.BOOKING_WINDOW_DAYS:
        raise BadRequestError(f"امکان رزرو فقط تا {settings.BOOKING_WINDOW_DAYS} روز آینده وجود دارد")

    nights = (data.check_out_date - data.check_in_date).days
    total_persons = 1 + len(data.guests)

    access = db.execute(
        select(OrgPlaceAccess).where(
            OrgPlaceAccess.org_id == current_user.org_id,
            OrgPlaceAccess.place_id == data.place_id,
            OrgPlaceAccess.is_allowed == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if not access and not current_user.is_super_admin:
        raise ForbiddenError("سازمان شما دسترسی به این اقامتگاه را ندارد")

    user = db.get(User, current_user.id)
    profile = user.profile if user else None

    spouse_count = sum(1 for g in data.guests if g.person_type == "SPOUSE")
    child_count = sum(1 for g in data.guests if g.person_type == "CHILD")

    if spouse_count > 0:
        if not profile or profile.marital_status != "MARRIED":
            raise BadRequestError("امکان افزودن همسر وجود ندارد — وضعیت تأهل کاربر متأهل نیست")
        if spouse_count > 1:
            raise BadRequestError("فقط یک همسر می‌توان به رزرو اضافه کرد")

    if child_count > 0:
        recorded_children = profile.number_of_children if profile else 0
        if child_count > recorded_children:
            raise BadRequestError(
                f"امکان افزودن {child_count} فرزند وجود ندارد — کاربر {recorded_children} فرزند ثبت‌شده دارد"
            )

    if data.vip and not current_user.is_super_admin:
        raise ForbiddenError("فقط مدیر کل امکان رزرو اتاق VIP را دارد")

    room_type_key = "TWO_BED" if total_persons >= 5 else "ONE_BED"
    room_type = db.execute(select(RoomType).where(RoomType.key == room_type_key)).scalar_one_or_none()
    if not room_type:
        raise BadRequestError("نوع اتاق مورد نظر یافت نشد")

    place_room = db.execute(
        select(PlaceRoom).where(
            PlaceRoom.place_id == data.place_id,
            PlaceRoom.room_type_id == room_type.id,
            PlaceRoom.is_vip == data.vip,
        )
    ).scalar_one_or_none()
    if not place_room or place_room.total_rooms <= 0:
        raise ConflictError("اتاق موجود در این اقامتگاه وجود ندارد")

    room_capacity = place_room.capacity or room_type.max_capacity
    if total_persons > room_capacity:
        raise BadRequestError(f"حداکثر ظرفیت اتاق {room_capacity} نفر است — شما {total_persons} نفر وارد کرده‌اید")

    for day_offset in range(nights):
        check_date = data.check_in_date + timedelta(days=day_offset)

        blocked = db.execute(
            select(func.coalesce(func.sum(PlaceAvailability.blocked_count), 0)).where(
                PlaceAvailability.place_id == data.place_id,
                PlaceAvailability.date == check_date,
                or_(PlaceAvailability.room_type_id == room_type.id, PlaceAvailability.room_type_id == None),  # noqa: E711
            )
        ).scalar() or 0

        reserved = db.execute(
            select(func.count()).where(
                Reservation.place_id == data.place_id,
                Reservation.room_type_id == room_type.id,
                Reservation.is_vip == data.vip,
                Reservation.status.in_(["PENDING", "APPROVED"]),
                Reservation.check_in_date <= check_date,
                Reservation.check_out_date > check_date,
            )
        ).scalar() or 0

        available = place_room.total_rooms - int(blocked) - int(reserved)
        if available <= 0:
            raise ConflictError(f"اتاق خالی در تاریخ {check_date} موجود نیست")

    eligibility = None
    if data.use_special_plan:
        plan_ids_for_place = select(OrgSpecialPlanPlace.org_special_plan_id).where(
            OrgSpecialPlanPlace.place_id == data.place_id,
        )
        plans_with_no_places = (
            select(OrgSpecialPlan.id)
            .outerjoin(OrgSpecialPlanPlace)
            .where(OrgSpecialPlanPlace.id == None)  # noqa: E711
        )
        eligibility = db.execute(
            select(UserPlanEligibility)
            .join(OrgSpecialPlan)
            .where(
                UserPlanEligibility.user_id == current_user.id,
                UserPlanEligibility.is_used == False,  # noqa: E712
                OrgSpecialPlan.org_id == current_user.org_id,
                OrgSpecialPlan.is_active == True,  # noqa: E712
                OrgSpecialPlan.eligible_from <= today,
                OrgSpecialPlan.eligible_until >= today,
                or_(
                    OrgSpecialPlan.id.in_(plan_ids_for_place),
                    OrgSpecialPlan.id.in_(plans_with_no_places),
                ),
            ).order_by(UserPlanEligibility.created_at).limit(1)
        ).scalar_one_or_none()

    family_count = 1 + sum(1 for g in data.guests if g.person_type in ("SPOUSE", "CHILD"))
    guest_count = sum(1 for g in data.guests if g.person_type == "GUEST")

    family_price = _get_price(db, data.place_id, room_type.id, "EMPLOYEE_FAMILY", data.check_in_date)
    guest_price = _get_price(db, data.place_id, room_type.id, "GUEST", data.check_in_date)

    total_price = (family_price * family_count * nights) + (guest_price * guest_count * nights)

    if eligibility:
        discount_percent = 0
    else:
        count = _get_usage_count(db, current_user.id, _get_shamsi_year())
        discount_percent = _calc_discount_percent(count)

    final_price = total_price * (100 - discount_percent) // 100

    now = datetime.now(timezone.utc)
    reservation = Reservation(
        user_id=current_user.id,
        org_id=current_user.org_id,
        place_id=data.place_id,
        room_type_id=room_type.id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        nights=nights,
        status="PENDING",
        is_vip=data.vip,
        admin_deadline_at=now + timedelta(hours=settings.RESERVATION_ADMIN_DEADLINE_HOURS),
        total_price=total_price,
        discount_percent=discount_percent,
        final_price=final_price,
        user_plan_eligibility_id=eligibility.id if eligibility else None,
    )
    db.add(reservation)
    db.flush()

    db.add(ReservationGuest(
        reservation_id=reservation.id, person_type="EMPLOYEE", name=None, is_extra=False,
    ))
    for g in data.guests:
        is_extra = g.person_type == "GUEST"
        charge = guest_price * nights if is_extra else Decimal(0)
        db.add(ReservationGuest(
            reservation_id=reservation.id, person_type=g.person_type,
            name=g.name, is_extra=is_extra, extra_charge=charge,
        ))

    if eligibility:
        eligibility.is_used = True

    place_label = _place_label(db, data.place_id)
    notify_admins(
        db,
        org_id=current_user.org_id,
        type=NotificationType.NEW_RESERVATION,
        title="رزرو جدید",
        message=f"رزرو جدید برای {place_label} ثبت شد",
        reference_type="reservation",
        reference_id=reservation.id,
    )

    db.commit()
    db.refresh(reservation)
    return _enrich_reservation(reservation)


def get_reservations_calendar(
    db: Session, place_id: int, from_date: date, to_date: date,
) -> list[RoomReservationCalendarItem]:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    place_rooms = db.execute(
        select(PlaceRoom).where(PlaceRoom.place_id == place_id).order_by(PlaceRoom.id)
    ).scalars().all()

    # Group by (room_type_id, is_vip) — each group is one calendar row per date
    room_groups: dict[tuple[int, bool], list[PlaceRoom]] = {}
    for pr in place_rooms:
        key = (pr.room_type_id, pr.is_vip)
        room_groups.setdefault(key, []).append(pr)

    results: list[RoomReservationCalendarItem] = []
    num_days = (to_date - from_date).days
    if num_days < 1:
        return results

    for day_offset in range(num_days):
        check_date = from_date + timedelta(days=day_offset)
        for (rt_id, is_vip), prs in room_groups.items():
            total_rooms = sum(pr.total_rooms for pr in prs)
            room_type = prs[0].room_type

            blocked = db.execute(
                select(func.coalesce(func.sum(PlaceAvailability.blocked_count), 0)).where(
                    PlaceAvailability.place_id == place_id,
                    PlaceAvailability.date == check_date,
                    or_(PlaceAvailability.room_type_id == rt_id, PlaceAvailability.room_type_id == None),  # noqa: E711
                )
            ).scalar() or 0
            blocked = int(blocked)

            overlapping = db.execute(
                select(Reservation).where(
                    Reservation.place_id == place_id,
                    Reservation.room_type_id == rt_id,
                    Reservation.is_vip == is_vip,
                    Reservation.status.in_(["PENDING", "APPROVED"]),
                    Reservation.check_in_date <= check_date,
                    Reservation.check_out_date > check_date,
                )
            ).scalars().all()
            reserved_count = len(overlapping)
            available = max(total_rooms - blocked - reserved_count, 0)

            reservations_info: list[CalendarReservationInfo] = []
            for res in overlapping:
                user_name = None
                if res.user and res.user.profile:
                    user_name = f"{res.user.profile.first_name} {res.user.profile.last_name}"
                reservations_info.append(CalendarReservationInfo(
                    reservation_id=res.id,
                    user_display_name=user_name,
                    status=res.status,
                    check_in_date=res.check_in_date,
                    check_out_date=res.check_out_date,
                ))

            results.append(RoomReservationCalendarItem(
                date=check_date,
                room_type_id=rt_id,
                room_type_key=room_type.key,
                is_vip=is_vip,
                total_rooms=total_rooms,
                reserved_count=reserved_count,
                blocked_count=blocked,
                available_count=available,
                reservations=reservations_info,
            ))

    return results


def admin_create_reservation(
    db: Session, current_user: CurrentUser, data: AdminReservationCreate,
) -> ReservationResponse:
    target_user = db.get(User, data.user_id)
    if not target_user:
        raise NotFoundError("کاربر مورد نظر یافت نشد")
    target_profile = target_user.profile

    target_org_id = target_user.org_id

    room_type = db.get(RoomType, data.room_type_id)
    if not room_type:
        raise NotFoundError("نوع اتاق یافت نشد")

    place_room = db.execute(
        select(PlaceRoom).where(
            PlaceRoom.place_id == data.place_id,
            PlaceRoom.room_type_id == data.room_type_id,
            PlaceRoom.is_vip == data.is_vip,
        )
    ).scalar_one_or_none()
    if not place_room or place_room.total_rooms <= 0:
        raise ConflictError("اتاق موجود در این اقامتگاه وجود ندارد")

    nights = (data.check_out_date - data.check_in_date).days

    for day_offset in range(nights):
        check_date = data.check_in_date + timedelta(days=day_offset)

        blocked = db.execute(
            select(func.coalesce(func.sum(PlaceAvailability.blocked_count), 0)).where(
                PlaceAvailability.place_id == data.place_id,
                PlaceAvailability.date == check_date,
                or_(PlaceAvailability.room_type_id == data.room_type_id, PlaceAvailability.room_type_id == None),  # noqa: E711
            )
        ).scalar() or 0

        reserved = db.execute(
            select(func.count()).where(
                Reservation.place_id == data.place_id,
                Reservation.room_type_id == data.room_type_id,
                Reservation.is_vip == data.is_vip,
                Reservation.status.in_(["PENDING", "APPROVED"]),
                Reservation.check_in_date <= check_date,
                Reservation.check_out_date > check_date,
            )
        ).scalar() or 0

        available = place_room.total_rooms - int(blocked) - int(reserved)
        if available <= 0:
            raise ConflictError(f"اتاق خالی در تاریخ {check_date} موجود نیست")

    # Pricing based on target user's org, not the admin's
    family_count = 1 + sum(1 for g in data.guests if g.person_type in ("SPOUSE", "CHILD"))
    guest_count = sum(1 for g in data.guests if g.person_type == "GUEST")

    family_price = _get_price(db, data.place_id, data.room_type_id, "EMPLOYEE_FAMILY", data.check_in_date)
    guest_price = _get_price(db, data.place_id, data.room_type_id, "GUEST", data.check_in_date)

    total_price = (family_price * family_count * nights) + (guest_price * guest_count * nights)

    # Admin reservations: NO discount
    discount_percent = 0
    final_price = total_price

    now = datetime.now(timezone.utc)
    reservation = Reservation(
        user_id=data.user_id,
        org_id=target_org_id,
        place_id=data.place_id,
        room_type_id=data.room_type_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        nights=nights,
        status=data.status,
        is_vip=data.is_vip,
        admin_deadline_at=now,
        total_price=total_price,
        discount_percent=discount_percent,
        final_price=final_price,
        reviewed_by_user_id=current_user.id,
        reviewed_at=now,
    )
    db.add(reservation)
    db.flush()

    # Create guest records
    db.add(ReservationGuest(
        reservation_id=reservation.id, person_type="EMPLOYEE", name=None, is_extra=False,
    ))
    for g in data.guests:
        is_extra = g.person_type == "GUEST"
        charge = guest_price * nights if is_extra else Decimal(0)
        db.add(ReservationGuest(
            reservation_id=reservation.id, person_type=g.person_type,
            name=g.name, is_extra=is_extra, extra_charge=charge,
        ))

    db.commit()
    db.refresh(reservation)
    return _enrich_reservation(reservation)


_RESERVATION_SORT_COLUMNS = {
    "id": Reservation.id,
    "check_in_date": Reservation.check_in_date,
    "check_out_date": Reservation.check_out_date,
    "nights": Reservation.nights,
    "final_price": Reservation.final_price,
    "status": Reservation.status,
    "created_at": Reservation.created_at,
}


def list_my_reservations(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    status: str | None = None, sort_by: str | None = None, sort_dir: str | None = None,
):
    base = select(Reservation).where(Reservation.user_id == current_user.id)
    if status:
        base = base.where(Reservation.status == status)
    col = _RESERVATION_SORT_COLUMNS.get(sort_by, Reservation.created_at)
    order = col.asc() if sort_dir == "asc" else col.desc()
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(order).offset(params.offset).limit(params.page_size)).scalars().all()
    return PaginatedResponse.create([_enrich_reservation(r) for r in rows], total, params)


def list_all_reservations(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    status: str | None = None, org_id: int | None = None, search: str | None = None,
    sort_by: str | None = None, sort_dir: str | None = None,
    from_date: date | None = None, to_date: date | None = None,
    place_id: int | None = None,
):
    base = select(Reservation)
    if not current_user.is_super_admin:
        base = base.where(Reservation.org_id == current_user.org_id)
    if status:
        base = base.where(Reservation.status == status)
    if org_id:
        base = base.where(Reservation.org_id == org_id)
    if place_id:
        base = base.where(Reservation.place_id == place_id)
    if from_date:
        base = base.where(Reservation.check_in_date >= from_date)
    if to_date:
        base = base.where(Reservation.check_out_date <= to_date)
    if search:
        pattern = f"%{search}%"
        base = base.outerjoin(User, User.id == Reservation.user_id).outerjoin(
            UserProfile, UserProfile.user_id == User.id
        ).outerjoin(Place, Place.id == Reservation.place_id).where(
            or_(
                UserProfile.first_name.ilike(pattern),
                UserProfile.last_name.ilike(pattern),
                Place.name.ilike(pattern),
                Place.city.ilike(pattern),
            )
        )

    col = _RESERVATION_SORT_COLUMNS.get(sort_by, Reservation.created_at)
    order = col.asc() if sort_dir == "asc" else col.desc()
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(order).offset(params.offset).limit(params.page_size)).scalars().all()
    return PaginatedResponse.create([_enrich_reservation(r) for r in rows], total, params)


def get_reservation(db: Session, reservation_id: int, current_user: CurrentUser) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("رزرو یافت نشد")
    if not current_user.is_super_admin and res.user_id != current_user.id and res.org_id != current_user.org_id:
        raise NotFoundError("رزرو یافت نشد")
    return _enrich_reservation(res)


def review_reservation(
    db: Session, reservation_id: int, action: str, current_user: CurrentUser, remove_plan: bool = False,
) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("رزرو یافت نشد")
    if res.status != "PENDING":
        raise BadRequestError("فقط رزروهای در انتظار بررسی قابل تغییر وضعیت هستند")

    if not current_user.is_super_admin and res.org_id != current_user.org_id:
        raise ForbiddenError("شما دسترسی به بررسی این رزرو را ندارید")

    if remove_plan and res.user_plan_eligibility_id:
        elig = db.get(UserPlanEligibility, res.user_plan_eligibility_id)
        if elig:
            elig.is_used = False
        res.user_plan_eligibility_id = None
        shamsi_year = _get_shamsi_year()
        count = _get_usage_count(db, res.user_id, shamsi_year)
        new_discount = _calc_discount_percent(count)
        res.discount_percent = new_discount
        res.final_price = res.total_price * (100 - new_discount) // 100

    now = datetime.now(timezone.utc)
    if action == "APPROVE":
        res.status = "APPROVED"
        shamsi_year = _get_shamsi_year()
        if not res.user_plan_eligibility_id:
            count = _get_usage_count(db, res.user_id, shamsi_year)
            new_discount = _calc_discount_percent(count)
            if new_discount != res.discount_percent:
                res.discount_percent = new_discount
                res.final_price = res.total_price * (100 - new_discount) // 100
        _increment_usage(db, res.user_id, shamsi_year)
    elif action == "REJECT":
        res.status = "REJECTED"
    else:
        raise BadRequestError("عملیات باید تایید یا رد باشد")

    res.reviewed_by_user_id = current_user.id
    res.reviewed_at = now

    status_label = "تایید" if action == "APPROVE" else "رد"
    create_notification(
        db,
        user_id=res.user_id,
        type=NotificationType.RESERVATION_REVIEWED,
        title=f"رزرو {status_label} شد",
        message=f"رزرو شما برای {_place_label(db, res.place_id)} {status_label} شد",
        reference_type="reservation",
        reference_id=res.id,
    )

    db.commit()
    db.refresh(res)
    return _enrich_reservation(res)


def cancel_reservation(db: Session, reservation_id: int, current_user: CurrentUser) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("رزرو یافت نشد")
    if res.user_id != current_user.id:
        raise ForbiddenError("فقط امکان لغو رزروهای خودتان وجود دارد")
    if res.status != "PENDING":
        raise BadRequestError("فقط رزروهای در انتظار بررسی قابل لغو هستند")

    res.status = "CANCELLED"

    notify_admins(
        db,
        org_id=res.org_id,
        type=NotificationType.RESERVATION_CANCELLED,
        title="لغو رزرو",
        message=f"رزرو {_place_label(db, res.place_id)} لغو شد",
        reference_type="reservation",
        reference_id=res.id,
    )

    db.commit()
    db.refresh(res)
    return _enrich_reservation(res)


# ── Ratings ──────────────────────────────────────────────────────────────────

def rate_place(db: Session, current_user: CurrentUser, data: PlaceRatingCreate) -> PlaceRatingResponse:
    place = db.get(Place, data.place_id)
    if not place:
        raise NotFoundError("اقامتگاه یافت نشد")

    existing = db.execute(
        select(PlaceRating).where(
            PlaceRating.user_id == current_user.id,
            PlaceRating.place_id == data.place_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.score = data.score
        db.commit()
        db.refresh(existing)
        return PlaceRatingResponse.model_validate(existing)

    rating = PlaceRating(user_id=current_user.id, place_id=data.place_id, score=data.score)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return PlaceRatingResponse.model_validate(rating)


def get_place_rating_summary(db: Session, place_id: int) -> PlaceRatingSummary:
    result = db.execute(
        select(
            func.coalesce(func.avg(PlaceRating.score), 0),
            func.count(PlaceRating.id),
        ).where(PlaceRating.place_id == place_id)
    ).one()
    return PlaceRatingSummary(
        place_id=place_id,
        average_score=round(float(result[0]), 1),
        total_ratings=int(result[1]),
    )


def list_all_place_ratings(db: Session) -> list[PlaceRatingSummary]:
    rows = db.execute(
        select(
            PlaceRating.place_id,
            func.avg(PlaceRating.score),
            func.count(PlaceRating.id),
        ).group_by(PlaceRating.place_id)
    ).all()
    return [
        PlaceRatingSummary(
            place_id=row[0],
            average_score=round(float(row[1]), 1),
            total_ratings=int(row[2]),
        )
        for row in rows
    ]


def get_place_analytics(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            Reservation.place_id,
            func.count(Reservation.id).label("reservation_count"),
        )
        .where(Reservation.status.in_(["PENDING", "APPROVED"]))
        .group_by(Reservation.place_id)
        .order_by(func.count(Reservation.id).desc())
    ).all()

    results = []
    for row in rows:
        place = db.get(Place, row[0])
        rating = get_place_rating_summary(db, row[0])
        results.append({
            "place_id": row[0],
            "place_name": f"{place.city} - {place.name}" if place else "نامشخص",
            "reservation_count": row[1],
            "average_score": rating.average_score,
            "total_ratings": rating.total_ratings,
        })
    return results


def expire_pending_reservations(db: Session) -> int:
    """Called by background job. Auto-resolves expired PENDING reservations."""
    now = datetime.now(timezone.utc)
    expired = db.execute(
        select(Reservation).where(Reservation.status == "PENDING", Reservation.admin_deadline_at < now)
    ).scalars().all()

    if not expired:
        return 0

    groups: dict[tuple, list[Reservation]] = {}
    for res in expired:
        key = (res.place_id, res.room_type_id, res.check_in_date, res.check_out_date)
        groups.setdefault(key, []).append(res)

    approved_count = 0
    shamsi_year = _get_shamsi_year()

    for _key, reservations in groups.items():
        scored = []
        for res in reservations:
            count = _get_usage_count(db, res.user_id, shamsi_year)
            scored.append((count, res.created_at, res))

        scored.sort(key=lambda x: (x[0], x[1]))

        winner = scored[0][2]
        winner.status = "APPROVED"
        winner.reviewed_at = now
        approved_count += 1
        if not winner.user_plan_eligibility_id:
            count = _get_usage_count(db, winner.user_id, shamsi_year)
            new_discount = _calc_discount_percent(count)
            if new_discount != winner.discount_percent:
                winner.discount_percent = new_discount
                winner.final_price = winner.total_price * (100 - new_discount) // 100
        _increment_usage(db, winner.user_id, shamsi_year)

        for _, _, res in scored[1:]:
            res.status = "EXPIRED"
            res.reviewed_at = now

    db.commit()
    return approved_count


# ── Special Plan Requests ───────────────────────────────────────────────────

def _enrich_plan_request(req: SpecialPlanRequest) -> SpecialPlanRequestResponse:
    user = req.user
    display_name = None
    if user and user.profile:
        display_name = f"{user.profile.first_name or ''} {user.profile.last_name or ''}".strip() or None
    return SpecialPlanRequestResponse(
        id=req.id,
        user_id=req.user_id,
        org_id=req.org_id,
        plan_type=req.plan_type,
        status=req.status,
        admin_note=req.admin_note,
        place_id=req.place_id,
        room_type_id=req.room_type_id,
        check_in_date=req.check_in_date,
        check_out_date=req.check_out_date,
        reservation_id=req.reservation_id,
        reviewed_by_user_id=req.reviewed_by_user_id,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
        user_display_name=display_name,
        place_name=f"{req.place.city} - {req.place.name}" if req.place else None,
        room_type_label=req.room_type.label if req.room_type else None,
    )


def create_plan_request(db: Session, current_user: CurrentUser, data: SpecialPlanRequestCreate) -> SpecialPlanRequestResponse:
    if data.plan_type not in ("NEW_MARRIAGE", "NEW_CHILD"):
        raise BadRequestError("نوع طرح نامعتبر است")

    existing = db.execute(
        select(SpecialPlanRequest).where(
            SpecialPlanRequest.user_id == current_user.id,
            SpecialPlanRequest.plan_type == data.plan_type,
            SpecialPlanRequest.status == "PENDING",
        )
    ).scalar_one_or_none()
    if existing:
        raise BadRequestError("شما یک درخواست در انتظار بررسی دارید")

    today = date.today()
    eligibility = db.execute(
        select(UserPlanEligibility)
        .join(OrgSpecialPlan)
        .where(
            UserPlanEligibility.user_id == current_user.id,
            UserPlanEligibility.is_used == False,  # noqa: E712
            OrgSpecialPlan.org_id == current_user.org_id,
            OrgSpecialPlan.plan_type == data.plan_type,
            OrgSpecialPlan.is_active == True,  # noqa: E712
            OrgSpecialPlan.eligible_from <= today,
            OrgSpecialPlan.eligible_until >= today,
        ).order_by(UserPlanEligibility.created_at).limit(1)
    ).scalar_one_or_none()

    req = SpecialPlanRequest(
        user_id=current_user.id,
        org_id=current_user.org_id,
        user_plan_eligibility_id=eligibility.id if eligibility else None,
        plan_type=data.plan_type,
        status="PENDING",
    )
    db.add(req)
    db.flush()

    notify_admins(
        db,
        org_id=current_user.org_id,
        type=NotificationType.NEW_PLAN_REQUEST,
        title="درخواست طرح ویژه جدید",
        message=f"درخواست طرح ویژه ({_plan_type_label(data.plan_type)}) ثبت شد",
        reference_type="plan_request",
        reference_id=req.id,
    )

    db.commit()
    db.refresh(req)
    return _enrich_plan_request(req)


def list_plan_requests(db: Session, current_user: CurrentUser, params: PaginationParams, status: str | None = None) -> PaginatedResponse:
    base = select(SpecialPlanRequest)
    if not current_user.is_super_admin:
        base = base.where(SpecialPlanRequest.org_id == current_user.org_id)

    if status:
        base = base.where(SpecialPlanRequest.status == status)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(SpecialPlanRequest.id.desc()).offset(params.offset).limit(params.page_size)).scalars().all()
    items = [_enrich_plan_request(r) for r in rows]
    return PaginatedResponse.create(items, total, params)


def list_my_plan_requests(db: Session, current_user: CurrentUser, params: PaginationParams) -> PaginatedResponse:
    base = select(SpecialPlanRequest).where(SpecialPlanRequest.user_id == current_user.id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(SpecialPlanRequest.id.desc()).offset(params.offset).limit(params.page_size)).scalars().all()
    items = [_enrich_plan_request(r) for r in rows]
    return PaginatedResponse.create(items, total, params)


def review_plan_request(db: Session, request_id: int, data: SpecialPlanRequestReview, current_user: CurrentUser) -> SpecialPlanRequestResponse:
    req = db.get(SpecialPlanRequest, request_id)
    if not req:
        raise NotFoundError("درخواست یافت نشد")
    if req.status != "PENDING":
        raise BadRequestError("فقط درخواست‌های در انتظار بررسی قابل تغییر هستند")
    if not current_user.is_super_admin and req.org_id != current_user.org_id:
        raise ForbiddenError("شما دسترسی به بررسی این درخواست را ندارید")

    now = datetime.now(timezone.utc)

    if data.action == "APPROVE":
        if not data.place_id or not data.check_in_date or not data.check_out_date:
            raise BadRequestError("برای تایید باید اقامتگاه و تاریخ اقامت مشخص شود")

        nights = (data.check_out_date - data.check_in_date).days
        if nights < 1:
            raise BadRequestError("تاریخ خروج باید بعد از تاریخ ورود باشد")

        room_type_key = "ONE_BED"
        if data.room_type_id:
            rt = db.get(RoomType, data.room_type_id)
            if not rt:
                raise BadRequestError("نوع اتاق یافت نشد")
        else:
            rt = db.execute(select(RoomType).where(RoomType.key == room_type_key)).scalar_one_or_none()
            if not rt:
                raise BadRequestError("نوع اتاق پیش‌فرض یافت نشد")

        place_room = db.execute(
            select(PlaceRoom).where(PlaceRoom.place_id == data.place_id, PlaceRoom.room_type_id == rt.id, PlaceRoom.is_vip == False)
        ).scalar_one_or_none()
        if not place_room:
            raise BadRequestError("اتاقی با این مشخصات در اقامتگاه یافت نشد")

        family_price = _get_price(db, data.place_id, rt.id, "EMPLOYEE_FAMILY", data.check_in_date)
        total_price = family_price * nights
        final_price = total_price  # special plan = no discount applied, full coverage

        reservation = Reservation(
            user_id=req.user_id,
            org_id=req.org_id,
            place_id=data.place_id,
            room_type_id=rt.id,
            check_in_date=data.check_in_date,
            check_out_date=data.check_out_date,
            nights=nights,
            status="APPROVED",
            is_vip=False,
            admin_deadline_at=now,
            total_price=total_price,
            discount_percent=0,
            final_price=0,
            user_plan_eligibility_id=req.user_plan_eligibility_id,
            reviewed_by_user_id=current_user.id,
            reviewed_at=now,
        )
        db.add(reservation)
        db.flush()

        db.add(ReservationGuest(
            reservation_id=reservation.id, person_type="EMPLOYEE", name=None, is_extra=False,
        ))

        eligibility = db.get(UserPlanEligibility, req.user_plan_eligibility_id)
        if eligibility:
            eligibility.is_used = True

        req.status = "APPROVED"
        req.place_id = data.place_id
        req.room_type_id = rt.id
        req.check_in_date = data.check_in_date
        req.check_out_date = data.check_out_date
        req.reservation_id = reservation.id

    elif data.action == "REJECT":
        req.status = "REJECTED"
    else:
        raise BadRequestError("عملیات باید تایید یا رد باشد")

    req.admin_note = data.admin_note
    req.reviewed_by_user_id = current_user.id
    req.reviewed_at = now

    status_label = "تایید" if data.action == "APPROVE" else "رد"
    msg = f"درخواست {_plan_type_label(req.plan_type)} شما {status_label} شد"
    if data.admin_note:
        msg += f" — {data.admin_note}"
    create_notification(
        db,
        user_id=req.user_id,
        type=NotificationType.PLAN_REQUEST_REVIEWED,
        title=f"درخواست طرح ویژه {status_label} شد",
        message=msg,
        reference_type="plan_request",
        reference_id=req.id,
    )

    db.commit()
    db.refresh(req)
    return _enrich_plan_request(req)


# ── Banners ────────────────────────────────────────────────────────────────

def get_active_banner(db: Session) -> BannerResponse | None:
    banner = db.execute(
        select(Banner).where(Banner.is_active == True).order_by(Banner.created_at.desc()).limit(1)  # noqa: E712
    ).scalar_one_or_none()
    return BannerResponse.model_validate(banner) if banner else None


def list_banners(db: Session) -> list[BannerResponse]:
    rows = db.execute(select(Banner).order_by(Banner.created_at.desc())).scalars().all()
    return [BannerResponse.model_validate(b) for b in rows]


def create_banner(db: Session, data: BannerCreate, user_id: int) -> BannerResponse:
    # Deactivate all existing banners — only one active at a time
    db.execute(
        sa.update(Banner).where(Banner.is_active == True).values(is_active=False)  # noqa: E712
    )
    banner = Banner(
        title=data.title,
        text=data.text,
        image_url=data.image_url,
        is_active=True,
        created_by_user_id=user_id,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return BannerResponse.model_validate(banner)


def update_banner(db: Session, banner_id: int, data: BannerUpdate) -> BannerResponse:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise NotFoundError("بنر یافت نشد")
    # If activating this banner, deactivate all others first
    if data.is_active is True:
        db.execute(
            sa.update(Banner).where(Banner.id != banner_id, Banner.is_active == True).values(is_active=False)  # noqa: E712
        )
    if data.title is not None:
        banner.title = data.title
    if data.text is not None:
        banner.text = data.text
    if data.image_url is not None:
        banner.image_url = data.image_url
    if data.is_active is not None:
        banner.is_active = data.is_active
    db.commit()
    db.refresh(banner)
    return BannerResponse.model_validate(banner)


def delete_banner(db: Session, banner_id: int) -> None:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise NotFoundError("بنر یافت نشد")
    db.delete(banner)
    db.commit()


# ── Export ──────────────────────────────────────────────────────────────────

def export_reservations(
    db: Session, current_user: CurrentUser,
    status: str | None = None, place_id: int | None = None,
    from_date: date | None = None, to_date: date | None = None,
    search: str | None = None,
) -> list[dict]:
    base = select(Reservation)
    if not current_user.is_super_admin:
        base = base.where(Reservation.org_id == current_user.org_id)
    if status:
        base = base.where(Reservation.status == status)
    if place_id:
        base = base.where(Reservation.place_id == place_id)
    if from_date:
        base = base.where(Reservation.check_in_date >= from_date)
    if to_date:
        base = base.where(Reservation.check_out_date <= to_date)
    if search:
        pattern = f"%{search}%"
        base = base.outerjoin(User, User.id == Reservation.user_id).outerjoin(
            UserProfile, UserProfile.user_id == User.id
        ).outerjoin(Place, Place.id == Reservation.place_id).where(
            or_(
                UserProfile.first_name.ilike(pattern),
                UserProfile.last_name.ilike(pattern),
                Place.name.ilike(pattern),
            )
        )

    rows = db.execute(base.order_by(Reservation.created_at.desc()).limit(5000)).scalars().all()
    result = []
    for r in rows:
        enriched = _enrich_reservation(r)
        guests_str = " / ".join(
            f"{g.person_type}{(' - ' + g.name) if g.name else ''}" for g in enriched.guests
        )
        result.append({
            "id": enriched.id,
            "user_display_name": enriched.user_display_name or "",
            "place_name": enriched.place_name or "",
            "check_in_date": str(enriched.check_in_date),
            "check_out_date": str(enriched.check_out_date),
            "nights": enriched.nights,
            "status": enriched.status,
            "is_vip": enriched.is_vip,
            "total_price": str(enriched.total_price),
            "discount_percent": enriched.discount_percent,
            "final_price": str(enriched.final_price),
            "has_special_plan": enriched.user_plan_eligibility_id is not None,
            "guests": guests_str,
            "created_at": str(enriched.created_at),
        })
    return result
