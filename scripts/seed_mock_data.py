"""Seed mock data: places, rooms, pricing, ratings, org access.

Usage:
    cd staffhub/
    python -m scripts.seed_mock_data
"""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "db"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.accommodation import (
    OrgPlaceAccess,
    Place,
    PlaceRating,
    PlaceRoom,
    PricingRule,
    RoomType,
)
from models.identity import Organization, User
from src.core.database import SessionLocal

PLACES = [
    {"city": "کیش", "name": "مجتمع مروارید"},
    {"city": "مشهد", "name": "هتل آپارتمان نور"},
    {"city": "اصفهان", "name": "اقامتگاه زاینده‌رود"},
    {"city": "شیراز", "name": "مجتمع پارسه"},
    {"city": "رامسر", "name": "ویلای ساحلی کاسپین"},
]

ROOM_TYPE_PRICING = {
    "ONE_BED": {"employee": Decimal("1500000"), "guest": Decimal("2500000")},
    "TWO_BED": {"employee": Decimal("2200000"), "guest": Decimal("3500000")},
}

RATINGS = [4, 5, 3, 5, 4]


def seed() -> None:
    db: Session = SessionLocal()
    try:
        existing = db.execute(select(Place)).scalars().first()
        if existing:
            print("Mock data already exists. Skipping.")
            return

        room_types = {rt.key: rt for rt in db.execute(select(RoomType)).scalars().all()}
        if not room_types:
            print("ERROR: No room types found. Run migrations first.")
            return

        org = db.execute(select(Organization).where(Organization.code == "HQ")).scalar_one_or_none()
        admin = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()

        created_places = []
        for p_data in PLACES:
            place = Place(city=p_data["city"], name=p_data["name"])
            db.add(place)
            db.flush()
            created_places.append(place)

            for rt_key, rt in room_types.items():
                db.add(PlaceRoom(
                    place_id=place.id,
                    room_type_id=rt.id,
                    total_rooms=8 if rt_key == "ONE_BED" else 4,
                    is_vip=False,
                ))
            if "ONE_BED" in room_types:
                db.add(PlaceRoom(
                    place_id=place.id,
                    room_type_id=room_types["ONE_BED"].id,
                    name="سوئیت VIP",
                    total_rooms=2,
                    is_vip=True,
                ))

            for rt_key, prices in ROOM_TYPE_PRICING.items():
                if rt_key not in room_types:
                    continue
                db.add(PricingRule(
                    place_id=place.id,
                    room_type_id=room_types[rt_key].id,
                    person_group="EMPLOYEE_FAMILY",
                    price_per_night=prices["employee"],
                    effective_from=date(2026, 1, 1),
                ))
                db.add(PricingRule(
                    place_id=place.id,
                    room_type_id=room_types[rt_key].id,
                    person_group="GUEST",
                    price_per_night=prices["guest"],
                    effective_from=date(2026, 1, 1),
                ))

            if org:
                db.add(OrgPlaceAccess(
                    org_id=org.id, place_id=place.id, is_allowed=True,
                ))

            print(f"  Created place: {place.city} - {place.name} (id={place.id})")

        if admin:
            for i, place in enumerate(created_places):
                db.add(PlaceRating(
                    user_id=admin.id,
                    place_id=place.id,
                    score=RATINGS[i],
                ))

        db.commit()
        print(f"\nSeeded {len(created_places)} places with rooms, pricing, org access, and ratings.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
