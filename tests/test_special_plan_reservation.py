"""
Comprehensive tests for the NEW_CHILD special plan reservation flow.

Covers:
  1. User creates reservation with use_special_plan=True (eligible, place matches)
  2. User creates reservation with use_special_plan=True (place NOT in plan's place_ids)
  3. User creates reservation with use_special_plan=True (plan has empty place_ids → all places)
  4. User creates reservation with use_special_plan=False (normal flow)
  5. User creates reservation when eligibility is already used
  6. Admin approves reservation that has a plan attached
  7. Admin approves with remove_plan=True (removes plan, recalculates discount)
  8. Admin rejects reservation with plan
  9. Edge cases: expired plan, inactive plan, wrong org user
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.modules.accommodation.schemas import GuestInput, ReservationCreate
from src.modules.accommodation.service import (
    create_reservation,
    review_reservation,
)
from src.core.exceptions import BadRequestError, ConflictError
from models.accommodation import (
    DiscountUsage,
    Reservation,
    UserPlanEligibility,
)
from models.identity import Organization
from tests.conftest import grant_eligibility, make_child_plan


# ── Helpers ─────────────────────────────────────────────────────────────────

def _reservation_data(place_id: int = 100, use_plan: bool = False) -> ReservationCreate:
    today = date.today()
    return ReservationCreate(
        place_id=place_id,
        check_in_date=today + timedelta(days=2),
        check_out_date=today + timedelta(days=4),
        guests=[GuestInput(person_type="SPOUSE", name="Sara")],
        use_special_plan=use_plan,
        vip=False,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. User creates reservation with plan — place matches plan's place_ids
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReservationWithPlanPlaceMatch:

    def test_plan_applied_when_place_in_plan_place_ids(self, db, seed, employee_user):
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id == elig.id
        assert res.discount_percent == 0
        assert res.status == "PENDING"

        db.refresh(elig)
        assert elig.is_used is True

    def test_plan_applied_final_price_equals_total(self, db, seed, employee_user):
        """With a plan, discount is 0% so final_price == total_price."""
        plan = make_child_plan(db, place_ids=[100])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.final_price == res.total_price


# ═══════════════════════════════════════════════════════════════════════════
# 2. User creates reservation with plan — place NOT in plan's place_ids
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReservationPlanPlaceMismatch:

    def test_plan_not_applied_when_place_not_in_plan(self, db, seed, employee_user):
        """Plan is restricted to place 200, but user books place 100 → no plan."""
        plan = make_child_plan(db, place_ids=[200])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None
        assert res.discount_percent == 50

        db.refresh(elig)
        assert elig.is_used is False

    def test_normal_discount_applied_when_plan_place_mismatch(self, db, seed, employee_user):
        """When plan doesn't match place, normal tiered discount applies."""
        plan = make_child_plan(db, place_ids=[200])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        expected_final = res.total_price * 50 // 100
        assert res.final_price == expected_final


# ═══════════════════════════════════════════════════════════════════════════
# 3. Plan with empty place_ids → applies to ALL places
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReservationPlanAllPlaces:

    def test_plan_applied_when_no_place_restriction(self, db, seed, employee_user):
        """Empty place_ids means plan applies to every place."""
        plan = make_child_plan(db, place_ids=[])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id == elig.id
        assert res.discount_percent == 0

    def test_plan_all_places_works_for_any_place(self, db, seed, employee_user):
        """Empty place_ids: plan works for place 200 too."""
        plan = make_child_plan(db, place_ids=[])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=200, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id == elig.id


# ═══════════════════════════════════════════════════════════════════════════
# 4. Normal reservation (use_special_plan=False)
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReservationNormal:

    def test_normal_reservation_no_plan(self, db, seed, employee_user):
        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None
        assert res.discount_percent == 50
        assert res.status == "PENDING"

    def test_normal_reservation_ignores_existing_eligibility(self, db, seed, employee_user):
        """Even if user has eligibility, use_special_plan=False means no plan."""
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None
        db.refresh(elig)
        assert elig.is_used is False

    def test_first_reservation_gets_50_percent_discount(self, db, seed, employee_user):
        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)
        assert res.discount_percent == 50

    def test_second_reservation_gets_30_percent_discount(self, db, seed, employee_user):
        """After one approved usage, second reservation gets 30% discount."""
        shamsi_year = date.today().year - 621
        db.add(DiscountUsage(user_id=10, year=shamsi_year, usage_count=1))
        db.commit()

        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)
        assert res.discount_percent == 30

    def test_third_reservation_gets_no_discount(self, db, seed, employee_user):
        shamsi_year = date.today().year - 621
        db.add(DiscountUsage(user_id=10, year=shamsi_year, usage_count=2))
        db.commit()

        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)
        assert res.discount_percent == 0


# ═══════════════════════════════════════════════════════════════════════════
# 5. Eligibility already used
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateReservationEligibilityUsed:

    def test_used_eligibility_falls_back_to_normal_discount(self, db, seed, employee_user):
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)
        elig.is_used = True
        db.commit()

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None
        assert res.discount_percent == 50


# ═══════════════════════════════════════════════════════════════════════════
# 6. Admin approves reservation with plan attached
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminApproveWithPlan:

    def test_approve_keeps_plan_and_zero_discount(self, db, seed, employee_user, admin):
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)
        assert res.user_plan_eligibility_id == elig.id

        reviewed = review_reservation(db, res.id, "APPROVE", admin, remove_plan=False)

        assert reviewed.status == "APPROVED"
        assert reviewed.user_plan_eligibility_id == elig.id
        assert reviewed.discount_percent == 0

    def test_approve_with_plan_increments_usage(self, db, seed, employee_user, admin):
        plan = make_child_plan(db, place_ids=[100])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        review_reservation(db, res.id, "APPROVE", admin, remove_plan=False)

        usage = db.query(DiscountUsage).filter_by(user_id=10).first()
        assert usage is not None
        assert usage.usage_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# 7. Admin approves with remove_plan=True
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminApproveRemovePlan:

    def test_remove_plan_restores_eligibility(self, db, seed, employee_user, admin):
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)
        assert res.user_plan_eligibility_id == elig.id

        db.refresh(elig)
        assert elig.is_used is True

        reviewed = review_reservation(db, res.id, "APPROVE", admin, remove_plan=True)

        assert reviewed.user_plan_eligibility_id is None

        db.refresh(elig)
        assert elig.is_used is False

    def test_remove_plan_applies_normal_discount(self, db, seed, employee_user, admin):
        """After removing plan, the reservation should get tiered discount."""
        plan = make_child_plan(db, place_ids=[100])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        reviewed = review_reservation(db, res.id, "APPROVE", admin, remove_plan=True)

        assert reviewed.discount_percent == 50
        expected_final = reviewed.total_price * 50 // 100
        assert reviewed.final_price == expected_final

    def test_remove_plan_second_usage_gets_30_percent(self, db, seed, employee_user, admin):
        """If user already has 1 usage, removing plan gives 30% discount."""
        shamsi_year = date.today().year - 621
        db.add(DiscountUsage(user_id=10, year=shamsi_year, usage_count=1))
        db.commit()

        plan = make_child_plan(db, place_ids=[100])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        reviewed = review_reservation(db, res.id, "APPROVE", admin, remove_plan=True)

        assert reviewed.discount_percent == 30

    def test_remove_plan_no_plan_on_reservation_is_noop(self, db, seed, employee_user, admin):
        """remove_plan=True on a reservation without a plan has no effect."""
        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)

        reviewed = review_reservation(db, res.id, "APPROVE", admin, remove_plan=True)

        assert reviewed.status == "APPROVED"
        assert reviewed.discount_percent == 50


# ═══════════════════════════════════════════════════════════════════════════
# 8. Admin rejects reservation with plan
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminRejectWithPlan:

    def test_reject_does_not_restore_eligibility(self, db, seed, employee_user, admin):
        """
        Current behavior: rejecting does NOT auto-restore eligibility.
        The eligibility was marked used during reservation creation.
        """
        plan = make_child_plan(db, place_ids=[100])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        reviewed = review_reservation(db, res.id, "REJECT", admin)

        assert reviewed.status == "REJECTED"
        db.refresh(elig)
        assert elig.is_used is True

    def test_reject_does_not_increment_usage_count(self, db, seed, employee_user, admin):
        plan = make_child_plan(db, place_ids=[100])
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        review_reservation(db, res.id, "REJECT", admin)

        usage = db.query(DiscountUsage).filter_by(user_id=10).first()
        assert usage is None


# ═══════════════════════════════════════════════════════════════════════════
# 9. Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_expired_plan_not_applied(self, db, seed, employee_user):
        """Plan whose eligible_until is in the past → no plan applied."""
        today = date.today()
        plan = make_child_plan(
            db,
            place_ids=[100],
            eligible_from=today - timedelta(days=60),
            eligible_until=today - timedelta(days=1),
        )
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None
        assert res.discount_percent == 50

    def test_future_plan_not_applied(self, db, seed, employee_user):
        """Plan whose eligible_from is in the future → no plan applied."""
        today = date.today()
        plan = make_child_plan(
            db,
            place_ids=[100],
            eligible_from=today + timedelta(days=10),
            eligible_until=today + timedelta(days=60),
        )
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None

    def test_inactive_plan_not_applied(self, db, seed, employee_user):
        """Plan with is_active=False → no plan applied."""
        plan = make_child_plan(db, place_ids=[100], is_active=False)
        grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None

    def test_wrong_org_plan_not_applied(self, db, seed, employee_user):
        """Plan belongs to org 2, user belongs to org 1 → no plan applied."""
        org2 = Organization(id=2, code="OTHER", name="Other Corp")
        db.add(org2)
        db.commit()

        plan = make_child_plan(db, org_id=2, place_ids=[100])
        elig = UserPlanEligibility(user_id=10, org_special_plan_id=plan.id)
        db.add(elig)
        db.commit()

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id is None

    def test_review_non_pending_reservation_fails(self, db, seed, employee_user, admin):
        """Cannot review a reservation that is not PENDING."""
        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)

        review_reservation(db, res.id, "APPROVE", admin)

        with pytest.raises(BadRequestError):
            review_reservation(db, res.id, "APPROVE", admin)

    def test_invalid_review_action_fails(self, db, seed, employee_user, admin):
        data = _reservation_data(use_plan=False)
        res = create_reservation(db, employee_user, data)

        with pytest.raises(BadRequestError):
            review_reservation(db, res.id, "INVALID", admin)

    def test_plan_with_multiple_places_works(self, db, seed, employee_user):
        """Plan restricted to [100, 200] — both places should work."""
        plan = make_child_plan(db, place_ids=[100, 200])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=100, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id == elig.id

    def test_plan_with_multiple_places_second_place(self, db, seed, employee_user):
        """Plan restricted to [100, 200] — booking place 200 also works."""
        plan = make_child_plan(db, place_ids=[100, 200])
        elig = grant_eligibility(db, user_id=10, plan=plan)

        data = _reservation_data(place_id=200, use_plan=True)
        res = create_reservation(db, employee_user, data)

        assert res.user_plan_eligibility_id == elig.id
