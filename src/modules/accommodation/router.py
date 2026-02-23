from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser, get_current_user, require_permission
from src.modules.accommodation import service
from src.modules.accommodation.schemas import (
    AvailabilitySetRequest,
    OrgPlaceAccessSet,
    PlaceCreate,
    PlaceResponse,
    PlaceRoomSet,
    PlaceUpdate,
    PricingRuleCreate,
    PricingRuleResponse,
    ReservationCreate,
    ReservationResponse,
    ReservationReviewRequest,
    SpecialPlanCreate,
    SpecialPlanResponse,
)

router = APIRouter()


# ── Places ───────────────────────────────────────────────────────────────────

@router.get("/places", response_model=PaginatedResponse[PlaceResponse])
def list_places(
    city: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_places(db, current_user, params, city=city)


@router.get("/places/{place_id}", response_model=PlaceResponse)
def get_place(
    place_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_place(db, place_id)


@router.post("/places", response_model=PlaceResponse, status_code=201)
def create_place(
    body: PlaceCreate,
    current_user: CurrentUser = Depends(require_permission("place.manage")),
    db: Session = Depends(get_db),
):
    return service.create_place(db, body)


@router.patch("/places/{place_id}", response_model=PlaceResponse)
def update_place(
    place_id: int,
    body: PlaceUpdate,
    current_user: CurrentUser = Depends(require_permission("place.manage")),
    db: Session = Depends(get_db),
):
    return service.update_place(db, place_id, body)


@router.put("/places/{place_id}/rooms", response_model=PlaceResponse)
def set_rooms(
    place_id: int,
    body: list[PlaceRoomSet],
    current_user: CurrentUser = Depends(require_permission("place.manage")),
    db: Session = Depends(get_db),
):
    return service.set_rooms(db, place_id, body)


@router.put("/places/{place_id}/availability")
def set_availability(
    place_id: int,
    body: AvailabilitySetRequest,
    current_user: CurrentUser = Depends(require_permission("place.set_availability")),
    db: Session = Depends(get_db),
):
    return service.set_availability(db, place_id, body, admin_id=current_user.id)


@router.put("/places/{place_id}/org-access")
def set_org_access(
    place_id: int,
    body: OrgPlaceAccessSet,
    current_user: CurrentUser = Depends(require_permission("org.set_place_access")),
    db: Session = Depends(get_db),
):
    return service.set_org_access(db, place_id, body)


# ── Pricing ──────────────────────────────────────────────────────────────────

@router.post("/pricing-rules", response_model=PricingRuleResponse, status_code=201)
def create_pricing_rule(
    body: PricingRuleCreate,
    current_user: CurrentUser = Depends(require_permission("pricing.manage")),
    db: Session = Depends(get_db),
):
    return service.create_pricing_rule(db, body)


@router.get("/places/{place_id}/pricing-rules", response_model=list[PricingRuleResponse])
def list_pricing_rules(
    place_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_pricing_rules(db, place_id)


# ── Special Plans ────────────────────────────────────────────────────────────

@router.post("/special-plans", response_model=SpecialPlanResponse, status_code=201)
def create_special_plan(
    body: SpecialPlanCreate,
    current_user: CurrentUser = Depends(require_permission("special_plan.manage")),
    db: Session = Depends(get_db),
):
    return service.create_special_plan(db, body)


@router.get("/users/{user_id}/special-plans", response_model=list[SpecialPlanResponse])
def list_user_plans(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_user_plans(db, user_id)


# ── Reservations ─────────────────────────────────────────────────────────────

@router.post("/reservations", response_model=ReservationResponse, status_code=201)
def create_reservation(
    body: ReservationCreate,
    current_user: CurrentUser = Depends(require_permission("reservation.create")),
    db: Session = Depends(get_db),
):
    return service.create_reservation(db, current_user, body)


@router.get("/reservations/mine", response_model=PaginatedResponse[ReservationResponse])
def list_my_reservations(
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(require_permission("reservation.view_own")),
    db: Session = Depends(get_db),
):
    return service.list_my_reservations(db, current_user, params)


@router.get("/reservations", response_model=PaginatedResponse[ReservationResponse])
def list_all_reservations(
    status: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(require_permission("reservation.view_all")),
    db: Session = Depends(get_db),
):
    return service.list_all_reservations(db, current_user, params, status=status, org_id=org_id)


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_reservation(db, reservation_id, current_user)


@router.post("/reservations/{reservation_id}/review", response_model=ReservationResponse)
def review_reservation(
    reservation_id: int,
    body: ReservationReviewRequest,
    current_user: CurrentUser = Depends(require_permission("reservation.approve")),
    db: Session = Depends(get_db),
):
    return service.review_reservation(db, reservation_id, body.action, current_user)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.cancel_reservation(db, reservation_id, current_user)
