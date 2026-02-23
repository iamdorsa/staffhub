"""Create accommodation tables.

Revision ID: 002
Revises: 001
Create Date: 2026-02-23

Tables: places, room_types, place_rooms, org_place_access,
        place_availability, pricing_rules, special_plans,
        discount_usage, reservations, reservation_guests
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Places ───────────────────────────────────────────────────────────
    op.create_table(
        "places",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("city", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Room Types ───────────────────────────────────────────────────────
    op.create_table(
        "room_types",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(32), unique=True, nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("max_capacity", sa.SmallInteger, nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Place Rooms (stock per place/type) ───────────────────────────────
    op.create_table(
        "place_rooms",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "room_type_id",
            sa.BigInteger,
            sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("total_rooms", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("place_id", "room_type_id", name="uq_place_room"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Org ↔ Place Access ───────────────────────────────────────────────
    op.create_table(
        "org_place_access",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "org_id",
            sa.BigInteger,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_allowed", sa.Boolean, nullable=False, server_default="1"),
        sa.UniqueConstraint("org_id", "place_id", name="uq_org_place"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Place Availability (date-level blocking) ─────────────────────────
    op.create_table(
        "place_availability",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "room_type_id",
            sa.BigInteger,
            sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("blocked_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "blocked_by_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("place_id", "room_type_id", "date", name="uq_place_avail_date"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Pricing Rules ────────────────────────────────────────────────────
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "room_type_id",
            sa.BigInteger,
            sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "person_group",
            sa.Enum("EMPLOYEE_FAMILY", "GUEST", name="person_group_enum"),
            nullable=False,
        ),
        sa.Column("price_per_night", sa.Numeric(15, 0), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.UniqueConstraint(
            "place_id", "room_type_id", "person_group", "effective_from", name="uq_pricing_rule"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Special Plans ────────────────────────────────────────────────────
    op.create_table(
        "special_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "plan_type",
            sa.Enum("NEW_MARRIAGE", "NEW_CHILD", name="special_plan_type_enum"),
            nullable=False,
        ),
        sa.Column("eligible_from", sa.Date, nullable=False),
        sa.Column("eligible_until", sa.Date, nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_special_plans_user_id", "special_plans", ["user_id"])

    # ── Discount Usage ───────────────────────────────────────────────────
    op.create_table(
        "discount_usage",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("usage_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "year", name="uq_discount_user_year"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Reservations ─────────────────────────────────────────────────────
    op.create_table(
        "reservations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "org_id",
            sa.BigInteger,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "room_type_id",
            sa.BigInteger,
            sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("check_in_date", sa.Date, nullable=False),
        sa.Column("check_out_date", sa.Date, nullable=False),
        sa.Column("nights", sa.SmallInteger, nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", name="reservation_status_enum"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("admin_deadline_at", sa.DateTime, nullable=False),
        sa.Column("total_price", sa.Numeric(15, 0), nullable=False, server_default="0"),
        sa.Column("discount_percent", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("final_price", sa.Numeric(15, 0), nullable=False, server_default="0"),
        sa.Column(
            "special_plan_id",
            sa.BigInteger,
            sa.ForeignKey("special_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])
    op.create_index("ix_reservations_org_id", "reservations", ["org_id"])
    op.create_index("ix_reservations_place_id", "reservations", ["place_id"])
    op.create_index("ix_reservations_status", "reservations", ["status"])
    op.create_index(
        "ix_reservations_place_dates",
        "reservations",
        ["place_id", "check_in_date", "check_out_date"],
    )

    # ── Reservation Guests ───────────────────────────────────────────────
    op.create_table(
        "reservation_guests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "reservation_id",
            sa.BigInteger,
            sa.ForeignKey("reservations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_type",
            sa.Enum("EMPLOYEE", "SPOUSE", "CHILD", "GUEST", name="person_type_enum"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("is_extra", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("extra_charge", sa.Numeric(15, 0), nullable=False, server_default="0"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_reservation_guests_reservation_id", "reservation_guests", ["reservation_id"])


def downgrade() -> None:
    op.drop_table("reservation_guests")
    op.drop_table("reservations")
    op.drop_table("discount_usage")
    op.drop_table("special_plans")
    op.drop_table("pricing_rules")
    op.drop_table("place_availability")
    op.drop_table("org_place_access")
    op.drop_table("place_rooms")
    op.drop_table("room_types")
    op.drop_table("places")
