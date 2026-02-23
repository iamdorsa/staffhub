from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.accommodation import (
    DiscountUsage,
    OrgPlaceAccess,
    OrgSpecialPlan,
    Place,
    PlaceAvailability,
    PlaceRoom,
    PricingRule,
    Reservation,
    ReservationGuest,
    RoomType,
    UserPlanEligibility,
)
from models.identity import User
from src.config import settings
from src.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser
from src.modules.accommodation.schemas import (
    AvailabilityResponse,
    AvailabilitySetRequest,
    OrgPlaceAccessResponse,
    OrgPlaceAccessSet,
    OrgSpecialPlanCreate,
    OrgSpecialPlanResponse,
    OrgSpecialPlanUpdate,
    PlaceCreate,
    PlaceResponse,
    PlaceRoomResponse,
    PlaceRoomSet,
    PlaceUpdate,
    PricingRuleCreate,
    PricingRuleResponse,
    ReservationCreate,
    ReservationResponse,
    RoomTypeResponse,
    UserPlanEligibilityResponse,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_shamsi_year() -> int:
    """Approximate Shamsi year from Gregorian. Good enough for V1."""
    now = datetime.now(timezone.utc)
    return now.year - 621


# ── Places ───────────────────────────────────────────────────────────────────

# ── Room Types ────────────────────────────────────────────────────────────────

def list_room_types(db: Session) -> list[RoomTypeResponse]:
    rows = db.execute(select(RoomType).order_by(RoomType.id)).scalars().all()
    return [RoomTypeResponse.model_validate(r) for r in rows]


# ── Places ────────────────────────────────────────────────────────────────────

def list_places(db: Session, current_user: CurrentUser, params: PaginationParams, city: str | None = None):
    base = select(Place).where(Place.is_active == True)  # noqa: E712

    if not current_user.is_super_admin:
        allowed_ids = select(OrgPlaceAccess.place_id).where(
            OrgPlaceAccess.org_id == current_user.org_id, OrgPlaceAccess.is_allowed == True  # noqa: E712
        )
        base = base.where(Place.id.in_(allowed_ids))

    if city:
        base = base.where(Place.city.ilike(f"%{city}%"))

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
        raise NotFoundError("Place not found")
    resp = PlaceResponse.model_validate(place)
    if not current_user.is_super_admin:
        resp.rooms = [r for r in resp.rooms if not r.is_vip]
    return resp


def create_place(db: Session, data: PlaceCreate) -> PlaceResponse:
    place = Place(city=data.city, name=data.name)
    db.add(place)
    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def update_place(db: Session, place_id: int, data: PlaceUpdate) -> PlaceResponse:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("Place not found")
    if data.city is not None:
        place.city = data.city
    if data.name is not None:
        place.name = data.name
    if data.is_active is not None:
        place.is_active = data.is_active
    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def set_rooms(db: Session, place_id: int, rooms: list[PlaceRoomSet]) -> PlaceResponse:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("Place not found")

    for r in rooms:
        existing = db.execute(
            select(PlaceRoom).where(PlaceRoom.place_id == place_id, PlaceRoom.room_type_id == r.room_type_id, PlaceRoom.is_vip == r.is_vip)
        ).scalar_one_or_none()
        if existing:
            existing.total_rooms = r.total_rooms
        else:
            db.add(PlaceRoom(place_id=place_id, room_type_id=r.room_type_id, total_rooms=r.total_rooms, is_vip=r.is_vip))

    db.commit()
    db.refresh(place)
    return PlaceResponse.model_validate(place)


def set_availability(db: Session, place_id: int, data: AvailabilitySetRequest, admin_id: int) -> dict:
    place = db.get(Place, place_id)
    if not place:
        raise NotFoundError("Place not found")

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
        raise NotFoundError("Place not found")

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
        raise NotFoundError("Place not found")
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
        raise NotFoundError("Place not found")
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
        raise NotFoundError("Place not found")
    rows = db.execute(
        select(OrgPlaceAccess).where(OrgPlaceAccess.place_id == place_id).order_by(OrgPlaceAccess.id)
    ).scalars().all()
    return [OrgPlaceAccessResponse.model_validate(r) for r in rows]


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

def create_org_special_plan(db: Session, data: OrgSpecialPlanCreate) -> OrgSpecialPlanResponse:
    existing = db.execute(
        select(OrgSpecialPlan).where(
            OrgSpecialPlan.org_id == data.org_id,
            OrgSpecialPlan.plan_type == data.plan_type,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Organization already has a {data.plan_type} plan")

    plan = OrgSpecialPlan(
        org_id=data.org_id, plan_type=data.plan_type,
        eligible_from=data.eligible_from, eligible_until=data.eligible_until,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return OrgSpecialPlanResponse.model_validate(plan)


def update_org_special_plan(db: Session, plan_id: int, data: OrgSpecialPlanUpdate) -> OrgSpecialPlanResponse:
    plan = db.get(OrgSpecialPlan, plan_id)
    if not plan:
        raise NotFoundError("Org special plan not found")
    if data.eligible_from is not None:
        plan.eligible_from = data.eligible_from
    if data.eligible_until is not None:
        plan.eligible_until = data.eligible_until
    if data.is_active is not None:
        plan.is_active = data.is_active
    db.commit()
    db.refresh(plan)
    return OrgSpecialPlanResponse.model_validate(plan)


def list_org_special_plans(db: Session, org_id: int) -> list[OrgSpecialPlanResponse]:
    rows = db.execute(select(OrgSpecialPlan).where(OrgSpecialPlan.org_id == org_id)).scalars().all()
    return [OrgSpecialPlanResponse.model_validate(r) for r in rows]


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

def create_reservation(db: Session, current_user: CurrentUser, data: ReservationCreate) -> ReservationResponse:
    today = date.today()
    if data.check_in_date < today:
        raise BadRequestError("Cannot book in the past")
    if (data.check_in_date - today).days > settings.BOOKING_WINDOW_DAYS:
        raise BadRequestError(f"Booking window is {settings.BOOKING_WINDOW_DAYS} days")

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
        raise ForbiddenError("Your organization does not have access to this place")

    user = db.get(User, current_user.id)
    profile = user.profile if user else None

    spouse_count = sum(1 for g in data.guests if g.person_type == "SPOUSE")
    child_count = sum(1 for g in data.guests if g.person_type == "CHILD")

    if spouse_count > 0:
        if not profile or profile.marital_status != "MARRIED":
            raise BadRequestError("Cannot add SPOUSE guest — user marital status is not MARRIED")
        if spouse_count > 1:
            raise BadRequestError("Cannot add more than 1 SPOUSE guest")

    if child_count > 0:
        recorded_children = profile.number_of_children if profile else 0
        if child_count > recorded_children:
            raise BadRequestError(
                f"Cannot add {child_count} CHILD guest(s) — user has {recorded_children} registered child(ren)"
            )

    if data.vip and not current_user.is_super_admin:
        raise ForbiddenError("Only main admin can book VIP rooms")

    room_type_key = "TWO_BED" if total_persons >= 5 else "ONE_BED"
    room_type = db.execute(select(RoomType).where(RoomType.key == room_type_key)).scalar_one_or_none()
    if not room_type:
        raise BadRequestError(f"Room type {room_type_key} not found")

    place_room = db.execute(
        select(PlaceRoom).where(
            PlaceRoom.place_id == data.place_id,
            PlaceRoom.room_type_id == room_type.id,
            PlaceRoom.is_vip == data.vip,
        )
    ).scalar_one_or_none()
    if not place_room or place_room.total_rooms <= 0:
        raise ConflictError("No rooms available at this place")

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
                Reservation.status.in_(["PENDING", "APPROVED"]),
                Reservation.check_in_date <= check_date,
                Reservation.check_out_date > check_date,
            )
        ).scalar() or 0

        available = place_room.total_rooms - int(blocked) - int(reserved)
        if available <= 0:
            raise ConflictError(f"No rooms available on {check_date}")

    eligibility = None
    if data.use_special_plan:
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
            ).order_by(UserPlanEligibility.created_at).limit(1)
        ).scalar_one_or_none()

    family_count = 1 + sum(1 for g in data.guests if g.person_type in ("SPOUSE", "CHILD"))
    guest_count = sum(1 for g in data.guests if g.person_type == "GUEST")

    family_price = _get_price(db, data.place_id, room_type.id, "EMPLOYEE_FAMILY", data.check_in_date)
    guest_price = _get_price(db, data.place_id, room_type.id, "GUEST", data.check_in_date)

    total_price = (family_price * family_count * nights) + (guest_price * guest_count * nights)

    discount_percent = 0
    if eligibility:
        discount_percent = 0
    else:
        shamsi_year = _get_shamsi_year()
        usage = db.execute(
            select(DiscountUsage).where(DiscountUsage.user_id == current_user.id, DiscountUsage.year == shamsi_year)
        ).scalar_one_or_none()
        count = usage.usage_count if usage else 0
        if count == 0:
            discount_percent = 50
        elif count == 1:
            discount_percent = 30

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

    db.commit()
    db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)


def list_my_reservations(db: Session, current_user: CurrentUser, params: PaginationParams):
    base = select(Reservation).where(Reservation.user_id == current_user.id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(Reservation.created_at.desc()).offset(params.offset).limit(params.page_size)).scalars().all()
    return PaginatedResponse.create([ReservationResponse.model_validate(r) for r in rows], total, params)


def list_all_reservations(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    status: str | None = None, org_id: int | None = None,
):
    base = select(Reservation)
    if not current_user.is_super_admin:
        base = base.where(Reservation.org_id == current_user.org_id)
    if status:
        base = base.where(Reservation.status == status)
    if org_id:
        base = base.where(Reservation.org_id == org_id)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(Reservation.created_at.desc()).offset(params.offset).limit(params.page_size)).scalars().all()
    return PaginatedResponse.create([ReservationResponse.model_validate(r) for r in rows], total, params)


def get_reservation(db: Session, reservation_id: int, current_user: CurrentUser) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("Reservation not found")
    if not current_user.is_super_admin and res.user_id != current_user.id and res.org_id != current_user.org_id:
        raise NotFoundError("Reservation not found")
    return ReservationResponse.model_validate(res)


def review_reservation(db: Session, reservation_id: int, action: str, current_user: CurrentUser) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("Reservation not found")
    if res.status != "PENDING":
        raise BadRequestError("Only PENDING reservations can be reviewed")

    now = datetime.now(timezone.utc)
    if action == "APPROVE":
        res.status = "APPROVED"

        shamsi_year = _get_shamsi_year()
        usage = db.execute(
            select(DiscountUsage).where(DiscountUsage.user_id == res.user_id, DiscountUsage.year == shamsi_year)
        ).scalar_one_or_none()
        if usage:
            usage.usage_count += 1
        else:
            db.add(DiscountUsage(user_id=res.user_id, year=shamsi_year, usage_count=1))

    elif action == "REJECT":
        res.status = "REJECTED"
    else:
        raise BadRequestError("Action must be APPROVE or REJECT")

    res.reviewed_by_user_id = current_user.id
    res.reviewed_at = now
    db.commit()
    db.refresh(res)
    return ReservationResponse.model_validate(res)


def cancel_reservation(db: Session, reservation_id: int, current_user: CurrentUser) -> ReservationResponse:
    res = db.get(Reservation, reservation_id)
    if not res:
        raise NotFoundError("Reservation not found")
    if res.user_id != current_user.id:
        raise ForbiddenError("You can only cancel your own reservations")
    if res.status != "PENDING":
        raise BadRequestError("Only PENDING reservations can be cancelled")

    res.status = "CANCELLED"
    db.commit()
    db.refresh(res)
    return ReservationResponse.model_validate(res)


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
            usage = db.execute(
                select(DiscountUsage).where(DiscountUsage.user_id == res.user_id, DiscountUsage.year == shamsi_year)
            ).scalar_one_or_none()
            count = usage.usage_count if usage else 0
            scored.append((count, res.created_at, res))

        scored.sort(key=lambda x: (x[0], x[1]))

        winner = scored[0][2]
        winner.status = "APPROVED"
        winner.reviewed_at = now
        approved_count += 1

        usage = db.execute(
            select(DiscountUsage).where(DiscountUsage.user_id == winner.user_id, DiscountUsage.year == shamsi_year)
        ).scalar_one_or_none()
        if usage:
            usage.usage_count += 1
        else:
            db.add(DiscountUsage(user_id=winner.user_id, year=shamsi_year, usage_count=1))

        for _, _, res in scored[1:]:
            res.status = "EXPIRED"
            res.reviewed_at = now

    db.commit()
    return approved_count
