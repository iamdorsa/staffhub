"""
Shared fixtures for StaffHub backend tests.

Uses SQLite in-memory for fast isolated tests.
Patches MySQL-specific DDL (ON UPDATE CURRENT_TIMESTAMP) before table creation.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT))

_mock_settings = type("Settings", (), {
    "DATABASE_URL": "sqlite://",
    "SECRET_KEY": "test-secret",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_EXPIRE_MINUTES": 30,
    "JWT_REFRESH_EXPIRE_DAYS": 7,
    "OTP_EXPIRY_SECONDS": 300,
    "OTP_LENGTH": 6,
    "SMS_PROVIDER": "console",
    "SMS_API_KEY": "",
    "RESERVATION_ADMIN_DEADLINE_HOURS": 72,
    "BOOKING_WINDOW_DAYS": 20,
    "MAX_STAY_NIGHTS": 3,
    "MAX_PERSONS_PER_RESERVATION": 8,
    "MAX_EXTRA_GUESTS": 2,
})()

import src.config  # noqa: E402
src.config.settings = _mock_settings

from models.base import Base  # noqa: E402
from models.identity import Organization, User, UserProfile  # noqa: E402
from models.access import Role, UserRole  # noqa: E402
from models.accommodation import (  # noqa: E402
    OrgPlaceAccess,
    OrgSpecialPlan,
    OrgSpecialPlanPlace,
    Place,
    PlaceRoom,
    PricingRule,
    RoomType,
    UserPlanEligibility,
)
from src.core.permissions import CurrentUser  # noqa: E402


def _fix_metadata_for_sqlite():
    """
    Walk all mapped tables and fix MySQL-specific DDL for SQLite:
    1. Replace CURRENT_TIMESTAMP ON UPDATE ... with plain CURRENT_TIMESTAMP
    2. Convert BigInteger PKs to Integer (SQLite only auto-increments INTEGER)
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            sd = col.server_default
            if sd is not None and hasattr(sd, "arg"):
                arg_text = str(sd.arg) if not isinstance(sd.arg, str) else sd.arg
                if "ON UPDATE" in arg_text.upper():
                    col.server_default = sa.schema.DefaultClause(sa.text("CURRENT_TIMESTAMP"))

            if col.primary_key and isinstance(col.type, sa.BigInteger):
                col.type = sa.Integer()


_fix_metadata_for_sqlite()


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", echo=False)

    @event.listens_for(eng, "connect")
    def _fk_pragma(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def seed(db: Session):
    """
    Seeds minimum data for reservation tests:
    - 1 org, 1 employee user (id=10), 1 admin user (id=1)
    - 2 places (100=Tehran, 200=Isfahan) with ONE_BED rooms
    - Org access, pricing rules, roles
    """
    org = Organization(id=1, code="HQ", name="Headquarters")
    db.add(org)
    db.flush()

    user = User(id=10, org_id=1, username="employee1", password_hash="x", auth_method="PASSWORD")
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=10, first_name="Ali", last_name="Ahmadi",
        marital_status="MARRIED", number_of_children=2,
    )
    db.add(profile)

    admin_user = User(id=1, org_id=1, username="admin1", password_hash="x", auth_method="PASSWORD")
    db.add(admin_user)
    db.flush()
    admin_profile = UserProfile(
        user_id=1, first_name="Admin", last_name="User",
        marital_status="SINGLE", number_of_children=0,
    )
    db.add(admin_profile)

    role_sa = Role(id=1, key="SUPER_ADMIN", name="Super Admin", scope="SYSTEM")
    role_emp = Role(id=2, key="EMPLOYEE", name="Employee", scope="ORGANIZATION")
    db.add_all([role_sa, role_emp])
    db.flush()

    db.add(UserRole(user_id=1, role_id=1))
    db.add(UserRole(user_id=10, role_id=2))

    place = Place(id=100, city="Tehran", name="Beach Resort")
    db.add(place)
    db.flush()

    place2 = Place(id=200, city="Isfahan", name="Mountain Lodge")
    db.add(place2)
    db.flush()

    rt = RoomType(id=1, key="ONE_BED", label="یک‌تخته", max_capacity=4)
    rt2 = RoomType(id=2, key="TWO_BED", label="دوتخته", max_capacity=8)
    db.add_all([rt, rt2])
    db.flush()

    pr = PlaceRoom(id=1, place_id=100, room_type_id=1, total_rooms=5, capacity=4, is_vip=False)
    pr2 = PlaceRoom(id=2, place_id=200, room_type_id=1, total_rooms=3, capacity=4, is_vip=False)
    db.add_all([pr, pr2])

    db.add(OrgPlaceAccess(org_id=1, place_id=100, is_allowed=True))
    db.add(OrgPlaceAccess(org_id=1, place_id=200, is_allowed=True))

    today = date.today()
    db.add(PricingRule(
        place_id=100, room_type_id=1, person_group="EMPLOYEE_FAMILY",
        price_per_night=500000, effective_from=today - timedelta(days=365),
    ))
    db.add(PricingRule(
        place_id=100, room_type_id=1, person_group="GUEST",
        price_per_night=800000, effective_from=today - timedelta(days=365),
    ))
    db.add(PricingRule(
        place_id=200, room_type_id=1, person_group="EMPLOYEE_FAMILY",
        price_per_night=400000, effective_from=today - timedelta(days=365),
    ))
    db.add(PricingRule(
        place_id=200, room_type_id=1, person_group="GUEST",
        price_per_night=700000, effective_from=today - timedelta(days=365),
    ))

    db.commit()

    class Seed:
        pass

    s = Seed()
    s.org = org
    s.user = user
    s.admin_user = admin_user
    s.place = place
    s.place2 = place2
    s.room_type = rt
    s.place_room = pr
    return s


@pytest.fixture()
def employee_user() -> CurrentUser:
    return CurrentUser(
        id=10, org_id=1, username="employee1", is_active=True,
        role_keys=["EMPLOYEE"], permissions=set(),
    )


@pytest.fixture()
def admin() -> CurrentUser:
    return CurrentUser(
        id=1, org_id=1, username="admin1", is_active=True,
        role_keys=["SUPER_ADMIN"], permissions=set(),
    )


def make_child_plan(
    db: Session, org_id: int = 1,
    place_ids: list[int] | None = None,
    is_active: bool = True,
    eligible_from: date | None = None,
    eligible_until: date | None = None,
) -> OrgSpecialPlan:
    today = date.today()
    plan = OrgSpecialPlan(
        org_id=org_id,
        plan_type="NEW_CHILD",
        eligible_from=eligible_from or (today - timedelta(days=30)),
        eligible_until=eligible_until or (today + timedelta(days=30)),
        is_active=is_active,
    )
    db.add(plan)
    db.flush()

    for pid in (place_ids or []):
        db.add(OrgSpecialPlanPlace(org_special_plan_id=plan.id, place_id=pid))

    db.commit()
    db.refresh(plan)
    return plan


def grant_eligibility(db: Session, user_id: int, plan: OrgSpecialPlan) -> UserPlanEligibility:
    elig = UserPlanEligibility(user_id=user_id, org_special_plan_id=plan.id)
    db.add(elig)
    db.commit()
    db.refresh(elig)
    return elig
