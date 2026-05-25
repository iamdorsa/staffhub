"""Comprehensive mock data covering all scenarios for UI testing.

Creates:
  - 2 additional orgs with employees and admins
  - Place images on existing places + 1 inactive place
  - Rooms with varied configurations (VIP, different capacities)
  - Reservations in ALL statuses (PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED)
  - Reservations that fully book rooms on certain dates (to test date picker blocking)
  - VIP reservations
  - Availability blocks (admin-blocked dates)
  - Additional pricing rules
  - Org access configurations (some denied)
  - Additional ratings from multiple users
  - Special plan eligibility + requests in all statuses
  - Discount usage entries
  - Notifications of various types

Usage:
    cd staffhub/
    DATABASE_URL="mysql+pymysql://root:root@127.0.0.1:3306/staffhub_db?charset=utf8mb4" \
        python -m scripts.seed_comprehensive_mock
"""
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "db"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.accommodation import (
    DiscountUsage,
    Notification,
    OrgPlaceAccess,
    OrgSpecialPlan,
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
from models.identity import Organization, User, UserChild, UserProfile
from models.access import Role, UserRole
from src.core.database import SessionLocal
from src.core.security import hash_password

now = datetime.now(timezone.utc)

PLACE_IMAGES = {
    "مجتمع مروارید": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&h=500&fit=crop&q=80",
    "هتل آپارتمان نور": "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=800&h=500&fit=crop&q=80",
    "اقامتگاه زاینده‌رود": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800&h=500&fit=crop&q=80",
    "مجتمع پارسه": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800&h=500&fit=crop&q=80",
    "ویلای ساحلی کاسپین": "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=800&h=500&fit=crop&q=80",
}


def seed() -> None:
    db: Session = SessionLocal()
    try:
        rt_map = {rt.key: rt for rt in db.execute(select(RoomType)).scalars().all()}
        one_bed = rt_map["ONE_BED"]
        two_bed = rt_map["TWO_BED"]

        roles = {r.key: r for r in db.execute(select(Role)).scalars().all()}
        hq = db.execute(select(Organization).where(Organization.code == "HQ")).scalar_one()
        admin_user = db.execute(select(User).where(User.username == "admin")).scalar_one()

        # ── 1. Update existing places with images ───────────────────────
        print("Updating place images...")
        for place in db.execute(select(Place)).scalars().all():
            if place.name in PLACE_IMAGES and not place.image_url:
                place.image_url = PLACE_IMAGES[place.name]
        db.flush()

        # ── 2. Create additional organizations ──────────────────────────
        print("Creating organizations...")
        org_alpha = db.execute(select(Organization).where(Organization.code == "ALPHA")).scalar_one_or_none()
        if not org_alpha:
            org_alpha = Organization(code="ALPHA", name="شرکت آلفا", is_active=True)
            db.add(org_alpha)
            db.flush()

        org_beta = db.execute(select(Organization).where(Organization.code == "BETA")).scalar_one_or_none()
        if not org_beta:
            org_beta = Organization(code="BETA", name="شرکت بتا", is_active=True)
            db.add(org_beta)
            db.flush()

        # ── 3. Create users across orgs ─────────────────────────────────
        print("Creating users...")
        users_spec = [
            # (username, org, first, last, national_id, marital, roles_list, phone, auth)
            ("ali.rezaei", org_alpha, "علی", "رضایی", "0012345678", "MARRIED", ["ORG_ADMIN"], "09121234567", "PASSWORD"),
            ("maryam.hosseini", org_alpha, "مریم", "حسینی", "0023456789", "SINGLE", ["EMPLOYEE"], "09131234567", "OTP"),
            ("reza.mohammadi", org_alpha, "رضا", "محمدی", "0034567890", "MARRIED", ["EMPLOYEE"], "09141234567", "BOTH"),
            ("sara.ahmadi", org_beta, "سارا", "احمدی", "0045678901", "MARRIED", ["ORG_ADMIN"], "09151234567", "PASSWORD"),
            ("hassan.karimi", org_beta, "حسن", "کریمی", "0056789012", "SINGLE", ["EMPLOYEE"], "09161234567", "PASSWORD"),
            ("fatemeh.moradi", hq, "فاطمه", "مرادی", "0067890123", "MARRIED", ["EMPLOYEE"], "09171234567", "BOTH"),
        ]

        created_users = {}
        for uname, org, fname, lname, nid, marital, role_keys, phone, auth in users_spec:
            u = db.execute(select(User).where(User.username == uname)).scalar_one_or_none()
            if u:
                created_users[uname] = u
                continue
            u = User(
                org_id=org.id,
                username=uname,
                password_hash=hash_password("Test1234"),
                phone_number=phone,
                auth_method=auth,
                is_active=True,
            )
            db.add(u)
            db.flush()

            db.add(UserProfile(
                user_id=u.id,
                first_name=fname,
                last_name=lname,
                national_id=nid,
                marital_status=marital,
                marriage_date=date(2025, 3, 21) if marital == "MARRIED" else None,
                spouse_first_name="همسر" if marital == "MARRIED" else None,
                spouse_last_name=lname if marital == "MARRIED" else None,
                number_of_children=2 if marital == "MARRIED" else 0,
            ))

            for rk in role_keys:
                db.add(UserRole(user_id=u.id, role_id=roles[rk].id, assigned_at=now))

            if marital == "MARRIED":
                db.add(UserChild(user_id=u.id, first_name="آرمین", birth_date=date(2022, 6, 15)))
                db.add(UserChild(user_id=u.id, first_name="آیدا", birth_date=date(2024, 1, 10)))

            created_users[uname] = u
            db.flush()

        ali = created_users["ali.rezaei"]
        maryam = created_users["maryam.hosseini"]
        reza = created_users["reza.mohammadi"]
        sara = created_users["sara.ahmadi"]
        hassan = created_users["hassan.karimi"]
        fatemeh = created_users["fatemeh.moradi"]

        # ── 4. Create an inactive place (no rooms) ─────────────────────
        print("Creating inactive place...")
        inactive_place = db.execute(
            select(Place).where(Place.name == "هتل قدیمی تبریز")
        ).scalar_one_or_none()
        if not inactive_place:
            inactive_place = Place(
                city="تبریز",
                name="هتل قدیمی تبریز",
                address="تبریز، خیابان شهریار، پلاک ۴۵",
                image_url="https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=800&h=500&fit=crop&q=80",
                is_active=False,
            )
            db.add(inactive_place)
            db.flush()

        # ── 5. Create a new place with varied room config ───────────────
        print("Creating new place with special config...")
        new_place = db.execute(
            select(Place).where(Place.name == "اقامتگاه ساحلی بندرعباس")
        ).scalar_one_or_none()
        if not new_place:
            new_place = Place(
                city="بندرعباس",
                name="اقامتگاه ساحلی بندرعباس",
                address="بندرعباس، بلوار ساحلی، کیلومتر ۵",
                image_url="https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800&h=500&fit=crop&q=80",
                is_active=True,
            )
            db.add(new_place)
            db.flush()

            db.add(PlaceRoom(place_id=new_place.id, room_type_id=one_bed.id, total_rooms=3, capacity=4, is_vip=False))
            db.add(PlaceRoom(place_id=new_place.id, room_type_id=two_bed.id, total_rooms=2, capacity=6, is_vip=False))
            db.add(PlaceRoom(place_id=new_place.id, room_type_id=one_bed.id, name="سوئیت رویال", total_rooms=1, capacity=3, is_vip=True))
            db.flush()

            for rt_key, prices in [("ONE_BED", (1800000, 3000000)), ("TWO_BED", (2800000, 4200000))]:
                db.add(PricingRule(
                    place_id=new_place.id, room_type_id=rt_map[rt_key].id,
                    person_group="EMPLOYEE_FAMILY", price_per_night=Decimal(str(prices[0])),
                    effective_from=date(2026, 1, 1),
                ))
                db.add(PricingRule(
                    place_id=new_place.id, room_type_id=rt_map[rt_key].id,
                    person_group="GUEST", price_per_night=Decimal(str(prices[1])),
                    effective_from=date(2026, 1, 1),
                ))

            db.add(OrgPlaceAccess(org_id=hq.id, place_id=new_place.id, is_allowed=True))
            db.add(OrgPlaceAccess(org_id=org_alpha.id, place_id=new_place.id, is_allowed=True))
            db.flush()

        # ── 6. Org access: Alpha gets most, Beta gets limited ──────────
        print("Setting org access...")
        places = db.execute(select(Place).where(Place.is_active == True)).scalars().all()
        for p in places:
            existing = db.execute(
                select(OrgPlaceAccess).where(
                    OrgPlaceAccess.org_id == org_alpha.id,
                    OrgPlaceAccess.place_id == p.id,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(OrgPlaceAccess(org_id=org_alpha.id, place_id=p.id, is_allowed=True))

        beta_allowed_ids = [p.id for p in places[:3]]
        for p in places:
            existing = db.execute(
                select(OrgPlaceAccess).where(
                    OrgPlaceAccess.org_id == org_beta.id,
                    OrgPlaceAccess.place_id == p.id,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(OrgPlaceAccess(
                    org_id=org_beta.id, place_id=p.id,
                    is_allowed=(p.id in beta_allowed_ids),
                ))
        db.flush()

        # ── 7. Reservations in ALL statuses ─────────────────────────────
        print("Creating reservations in all statuses...")
        kish = db.execute(select(Place).where(Place.name == "مجتمع مروارید")).scalar_one()
        mashad = db.execute(select(Place).where(Place.name == "هتل آپارتمان نور")).scalar_one()
        isfahan = db.execute(select(Place).where(Place.name.like("%زاینده%"))).scalar_one()
        shiraz = db.execute(select(Place).where(Place.name == "مجتمع پارسه")).scalar_one()
        ramsar = db.execute(select(Place).where(Place.name.like("%کاسپین%"))).scalar_one()

        reservation_specs = [
            # (user, org, place, room_type, checkin, checkout, status, is_vip, total, discount, final, guests)
            (ali, org_alpha, kish, one_bed, date(2026, 6, 1), date(2026, 6, 4), "APPROVED", False,
             4500000, 50, 2250000,
             [("EMPLOYEE", "علی رضایی", False), ("SPOUSE", "همسر رضایی", False), ("CHILD", "آرمین", False)]),

            (ali, org_alpha, mashad, two_bed, date(2026, 6, 10), date(2026, 6, 13), "PENDING", False,
             6600000, 30, 4620000,
             [("EMPLOYEE", "علی رضایی", False), ("SPOUSE", None, False), ("CHILD", "آرمین", False),
              ("CHILD", "آیدا", False), ("GUEST", "رضا جعفری", True)]),

            (maryam, org_alpha, isfahan, one_bed, date(2026, 5, 25), date(2026, 5, 27), "REJECTED", False,
             3000000, 50, 1500000,
             [("EMPLOYEE", "مریم حسینی", False)]),

            (reza, org_alpha, shiraz, one_bed, date(2026, 5, 20), date(2026, 5, 23), "EXPIRED", False,
             4500000, 50, 2250000,
             [("EMPLOYEE", "رضا محمدی", False), ("SPOUSE", None, False)]),

            (sara, org_beta, kish, one_bed, date(2026, 7, 1), date(2026, 7, 4), "CANCELLED", False,
             4500000, 50, 2250000,
             [("EMPLOYEE", "سارا احمدی", False), ("SPOUSE", None, False), ("CHILD", "آرمین", False)]),

            (hassan, org_beta, kish, one_bed, date(2026, 6, 1), date(2026, 6, 4), "APPROVED", True,
             4500000, 0, 4500000,
             [("EMPLOYEE", "حسن کریمی", False)]),

            (fatemeh, hq, ramsar, two_bed, date(2026, 6, 5), date(2026, 6, 8), "APPROVED", False,
             6600000, 50, 3300000,
             [("EMPLOYEE", "فاطمه مرادی", False), ("SPOUSE", None, False), ("CHILD", "آرمین", False),
              ("CHILD", "آیدا", False), ("GUEST", "مینا احمدی", True), ("GUEST", "نرگس رحیمی", True)]),

            (fatemeh, hq, new_place, one_bed, date(2026, 6, 15), date(2026, 6, 17), "PENDING", False,
             3600000, 30, 2520000,
             [("EMPLOYEE", "فاطمه مرادی", False), ("SPOUSE", None, False)]),

            # VIP reservation for new place
            (ali, org_alpha, new_place, one_bed, date(2026, 6, 20), date(2026, 6, 22), "APPROVED", True,
             3600000, 0, 3600000,
             [("EMPLOYEE", "علی رضایی", False), ("SPOUSE", None, False)]),
        ]

        for u, org, place, rt, ci, co, status, vip, total, disc, final, guests in reservation_specs:
            existing = db.execute(
                select(Reservation).where(
                    Reservation.user_id == u.id,
                    Reservation.place_id == place.id,
                    Reservation.check_in_date == ci,
                )
            ).scalar_one_or_none()
            if existing:
                continue

            nights = (co - ci).days
            reviewed_at = now - timedelta(days=2) if status in ("APPROVED", "REJECTED") else None
            reviewed_by = admin_user.id if reviewed_at else None

            res = Reservation(
                user_id=u.id,
                org_id=org.id,
                place_id=place.id,
                room_type_id=rt.id,
                check_in_date=ci,
                check_out_date=co,
                nights=nights,
                status=status,
                is_vip=vip,
                admin_deadline_at=now + timedelta(hours=72) if status == "PENDING" else now - timedelta(hours=1),
                total_price=Decimal(str(total)),
                discount_percent=disc,
                final_price=Decimal(str(final)),
                reviewed_by_user_id=reviewed_by,
                reviewed_at=reviewed_at,
            )
            db.add(res)
            db.flush()

            for pt, name, is_extra in guests:
                db.add(ReservationGuest(
                    reservation_id=res.id,
                    person_type=pt,
                    name=name,
                    is_extra=is_extra,
                    extra_charge=Decimal("500000") if is_extra else Decimal("0"),
                ))
        db.flush()

        # ── 8. Fully book rooms on specific dates (date picker blocking test) ─
        print("Creating reservations to fully book rooms on specific dates...")
        # Bandar Abbas has only 3 ONE_BED non-VIP rooms.
        # Create 3 APPROVED reservations to fill them for June 25-27.
        for i, u in enumerate([ali, maryam, reza]):
            existing = db.execute(
                select(Reservation).where(
                    Reservation.user_id == u.id,
                    Reservation.place_id == new_place.id,
                    Reservation.check_in_date == date(2026, 6, 25),
                )
            ).scalar_one_or_none()
            if existing:
                continue
            res = Reservation(
                user_id=u.id,
                org_id=u.org_id,
                place_id=new_place.id,
                room_type_id=one_bed.id,
                check_in_date=date(2026, 6, 25),
                check_out_date=date(2026, 6, 27),
                nights=2,
                status="APPROVED",
                is_vip=False,
                admin_deadline_at=now - timedelta(hours=1),
                total_price=Decimal("3600000"),
                discount_percent=0,
                final_price=Decimal("3600000"),
                reviewed_by_user_id=admin_user.id,
                reviewed_at=now - timedelta(days=1),
            )
            db.add(res)
            db.flush()
            db.add(ReservationGuest(
                reservation_id=res.id, person_type="EMPLOYEE",
                name=None, is_extra=False, extra_charge=Decimal("0"),
            ))
        db.flush()

        # ── 9. Admin-blocked availability ───────────────────────────────
        print("Setting availability blocks...")
        block_dates = [date(2026, 7, 10), date(2026, 7, 11), date(2026, 7, 12)]
        for d in block_dates:
            existing = db.execute(
                select(PlaceAvailability).where(
                    PlaceAvailability.place_id == kish.id,
                    PlaceAvailability.room_type_id == one_bed.id,
                    PlaceAvailability.date == d,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(PlaceAvailability(
                    place_id=kish.id,
                    room_type_id=one_bed.id,
                    date=d,
                    blocked_count=8,
                    blocked_by_user_id=admin_user.id,
                ))
        db.flush()

        # ── 10. Additional ratings from multiple users ──────────────────
        print("Adding ratings...")
        rating_specs = [
            (ali.id, kish.id, 5), (ali.id, mashad.id, 4), (ali.id, isfahan.id, 3),
            (maryam.id, kish.id, 4), (maryam.id, mashad.id, 5),
            (sara.id, kish.id, 3), (sara.id, ramsar.id, 5),
            (fatemeh.id, ramsar.id, 4), (fatemeh.id, shiraz.id, 5),
            (hassan.id, mashad.id, 2),
        ]
        for uid, pid, score in rating_specs:
            existing = db.execute(
                select(PlaceRating).where(
                    PlaceRating.user_id == uid,
                    PlaceRating.place_id == pid,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(PlaceRating(user_id=uid, place_id=pid, score=score))
        db.flush()

        # ── 11. Org special plans ───────────────────────────────────────
        print("Setting up special plans...")
        alpha_marriage = db.execute(
            select(OrgSpecialPlan).where(
                OrgSpecialPlan.org_id == org_alpha.id,
                OrgSpecialPlan.plan_type == "NEW_MARRIAGE",
            )
        ).scalar_one_or_none()
        if not alpha_marriage:
            alpha_marriage = OrgSpecialPlan(
                org_id=org_alpha.id,
                plan_type="NEW_MARRIAGE",
                eligible_from=date(2026, 1, 1),
                eligible_until=date(2026, 12, 29),
                is_active=True,
            )
            db.add(alpha_marriage)
            db.flush()

        alpha_child = db.execute(
            select(OrgSpecialPlan).where(
                OrgSpecialPlan.org_id == org_alpha.id,
                OrgSpecialPlan.plan_type == "NEW_CHILD",
            )
        ).scalar_one_or_none()
        if not alpha_child:
            alpha_child = OrgSpecialPlan(
                org_id=org_alpha.id,
                plan_type="NEW_CHILD",
                eligible_from=date(2026, 1, 1),
                eligible_until=date(2026, 12, 29),
                is_active=True,
            )
            db.add(alpha_child)
            db.flush()

        # ── 12. User plan eligibility ───────────────────────────────────
        print("Creating plan eligibility...")
        ali_elig = db.execute(
            select(UserPlanEligibility).where(
                UserPlanEligibility.user_id == ali.id,
            )
        ).scalar_one_or_none()
        if not ali_elig:
            ali_elig = UserPlanEligibility(
                user_id=ali.id,
                org_special_plan_id=alpha_marriage.id,
                is_used=True,
            )
            db.add(ali_elig)
            db.flush()

        reza_elig = db.execute(
            select(UserPlanEligibility).where(
                UserPlanEligibility.user_id == reza.id,
            )
        ).scalar_one_or_none()
        if not reza_elig:
            reza_elig = UserPlanEligibility(
                user_id=reza.id,
                org_special_plan_id=alpha_child.id,
                is_used=False,
            )
            db.add(reza_elig)
            db.flush()

        # ── 13. Special plan requests in all statuses ───────────────────
        print("Creating plan requests...")
        plan_req_specs = [
            (maryam, org_alpha, "NEW_MARRIAGE", "PENDING", None, None, None, None, None, None, None),
            (reza, org_alpha, "NEW_CHILD", "APPROVED", "مبارکه! رزرو ثبت شد",
             kish.id, one_bed.id, date(2026, 7, 5), date(2026, 7, 8), admin_user.id, now - timedelta(days=3)),
            (sara, org_beta, "NEW_MARRIAGE", "REJECTED", "واجد شرایط نیستید",
             None, None, None, None, admin_user.id, now - timedelta(days=5)),
        ]
        for u, org, plan_type, status, note, pid, rtid, ci, co, reviewer, rev_at in plan_req_specs:
            existing = db.execute(
                select(SpecialPlanRequest).where(
                    SpecialPlanRequest.user_id == u.id,
                    SpecialPlanRequest.plan_type == plan_type,
                )
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(SpecialPlanRequest(
                user_id=u.id,
                org_id=org.id,
                plan_type=plan_type,
                status=status,
                admin_note=note,
                place_id=pid,
                room_type_id=rtid,
                check_in_date=ci,
                check_out_date=co,
                reviewed_by_user_id=reviewer,
                reviewed_at=rev_at,
            ))
        db.flush()

        # ── 14. Discount usage entries ──────────────────────────────────
        print("Adding discount usage...")
        disc_specs = [
            (ali.id, 1405, 3),
            (maryam.id, 1405, 1),
            (fatemeh.id, 1405, 2),
            (sara.id, 1405, 1),
        ]
        for uid, yr, cnt in disc_specs:
            existing = db.execute(
                select(DiscountUsage).where(
                    DiscountUsage.user_id == uid,
                    DiscountUsage.year == yr,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(DiscountUsage(user_id=uid, year=yr, usage_count=cnt))
        db.flush()

        # ── 15. Notifications ───────────────────────────────────────────
        print("Creating notifications...")
        notif_specs = [
            (ali.id, "RESERVATION_APPROVED", "رزرو تایید شد", "رزرو شما در مجتمع مروارید کیش تایید شد.", "reservation"),
            (ali.id, "RESERVATION_CREATED", "رزرو جدید", "رزرو جدید شما در هتل آپارتمان نور ثبت شد.", "reservation"),
            (maryam.id, "RESERVATION_REJECTED", "رزرو رد شد", "رزرو شما در اقامتگاه زاینده‌رود رد شد.", "reservation"),
            (reza.id, "RESERVATION_EXPIRED", "رزرو منقضی شد", "رزرو شما در مجتمع پارسه منقضی شد.", "reservation"),
            (sara.id, "PLAN_REQUEST_REJECTED", "درخواست طرح ویژه رد شد", "درخواست طرح ازدواج جدید شما رد شد.", "plan_request"),
            (fatemeh.id, "RESERVATION_APPROVED", "رزرو تایید شد", "رزرو شما در ویلای ساحلی کاسپین تایید شد.", "reservation"),
            (hassan.id, "RESERVATION_CANCELLED", "رزرو لغو شد", "رزرو شما لغو شد.", "reservation"),
        ]
        for uid, ntype, title, msg, ref_type in notif_specs:
            existing = db.execute(
                select(Notification).where(
                    Notification.user_id == uid,
                    Notification.title == title,
                    Notification.type == ntype,
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(Notification(
                    user_id=uid, type=ntype, title=title, message=msg,
                    is_read=False, reference_type=ref_type,
                ))
        db.flush()

        db.commit()
        print("\nComprehensive mock data seeded successfully!")
        print(f"  Organizations: HQ, ALPHA, BETA (+ existing Taher)")
        print(f"  Users: 6 new users across orgs")
        print(f"  Places: updated images + 1 inactive + 1 new")
        print(f"  Reservations: all statuses (PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED) + VIP")
        print(f"  Fully booked dates: Bandar Abbas Jun 25-26 (ONE_BED non-VIP)")
        print(f"  Blocked dates: Kish Jul 10-12 (ONE_BED)")
        print(f"  Ratings from multiple users")
        print(f"  Special plans + eligibility + requests in all statuses")
        print(f"  Discount usage + Notifications")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
