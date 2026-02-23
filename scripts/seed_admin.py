"""One-time script to create the initial super admin user.

Usage:
    cd staffhub/
    python -m scripts.seed_admin
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "db"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.access import UserRole
from models.identity import Organization, User, UserProfile
from src.core.database import SessionLocal
from src.core.security import hash_password


def seed() -> None:
    db: Session = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if existing:
            print(f"Admin user already exists (id={existing.id}). Skipping.")
            return

        org = db.execute(select(Organization).where(Organization.code == "HQ")).scalar_one_or_none()
        if not org:
            org = Organization(code="HQ", name="Headquarters")
            db.add(org)
            db.flush()
            print(f"Created organization: HQ (id={org.id})")

        user = User(
            org_id=org.id,
            username="admin",
            password_hash=hash_password("admin"),
            auth_method="PASSWORD",
        )
        db.add(user)
        db.flush()

        profile = UserProfile(
            user_id=user.id,
            first_name="System",
            last_name="Admin",
        )
        db.add(profile)

        user_role = UserRole(user_id=user.id, role_id=1)
        db.add(user_role)

        db.commit()
        print(f"Created admin user (id={user.id})")
        print("  username: admin")
        print("  password: admin")
        print("  role:     SUPER_ADMIN")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
