"""Domain 2 — Accommodation: places, rooms, pricing, reservations."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from models.base import Base, SoftDeleteMixin


class Place(Base, SoftDeleteMixin):
    __tablename__ = "places"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    city = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    rooms = relationship("PlaceRoom", back_populates="place", lazy="select")

    def __repr__(self) -> str:
        return f"<Place {self.city}/{self.name}>"


class RoomType(Base):
    __tablename__ = "room_types"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(32), unique=True, nullable=False, comment="ONE_BED / TWO_BED")
    label = Column(String(64), nullable=False)
    max_capacity = Column(SmallInteger, nullable=False, comment="Max persons for this room type")

    def __repr__(self) -> str:
        return f"<RoomType {self.key}>"


class PlaceRoom(Base):
    """Room stock per place per type."""

    __tablename__ = "place_rooms"
    __table_args__ = (
        UniqueConstraint("place_id", "room_type_id", name="uq_place_room"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    place_id = Column(
        BigInteger,
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_type_id = Column(
        BigInteger,
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    total_rooms = Column(Integer, nullable=False, server_default="0")

    place = relationship("Place", back_populates="rooms")
    room_type = relationship("RoomType", lazy="joined")


class OrgPlaceAccess(Base):
    """Controls which organizations may book which places."""

    __tablename__ = "org_place_access"
    __table_args__ = (
        UniqueConstraint("org_id", "place_id", name="uq_org_place"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    place_id = Column(
        BigInteger,
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_allowed = Column(Boolean, nullable=False, default=True, server_default="1")


class PlaceAvailability(Base):
    """Per-date room blocking managed by main admin."""

    __tablename__ = "place_availability"
    __table_args__ = (
        UniqueConstraint("place_id", "room_type_id", "date", name="uq_place_avail_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    place_id = Column(
        BigInteger,
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_type_id = Column(
        BigInteger,
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL means entire place is blocked on this date",
    )
    date = Column(Date, nullable=False)
    blocked_count = Column(Integer, nullable=False, server_default="0")
    blocked_by_user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class PricingRule(Base):
    """Price matrix: per place, room type, and person group with temporal validity."""

    __tablename__ = "pricing_rules"
    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "room_type_id",
            "person_group",
            "effective_from",
            name="uq_pricing_rule",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    place_id = Column(
        BigInteger,
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    room_type_id = Column(
        BigInteger,
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    person_group = Column(
        Enum("EMPLOYEE_FAMILY", "GUEST", name="person_group_enum"),
        nullable=False,
    )
    price_per_night = Column(
        Numeric(15, 0),
        nullable=False,
        comment="Price in Toman",
    )
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True, comment="NULL = open-ended")


class SpecialPlan(Base):
    """Time-limited eligibility plans (new marriage / new child)."""

    __tablename__ = "special_plans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_type = Column(
        Enum("NEW_MARRIAGE", "NEW_CHILD", name="special_plan_type_enum"),
        nullable=False,
    )
    eligible_from = Column(Date, nullable=False)
    eligible_until = Column(Date, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", lazy="select")


class DiscountUsage(Base):
    """Tracks per-user yearly reservation count for tiered discounts."""

    __tablename__ = "discount_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "year", name="uq_discount_user_year"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(SmallInteger, nullable=False, comment="Shamsi year (app layer converts)")
    usage_count = Column(SmallInteger, nullable=False, server_default="0")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    org_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    place_id = Column(
        BigInteger,
        ForeignKey("places.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_type_id = Column(
        BigInteger,
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    nights = Column(SmallInteger, nullable=False)
    status = Column(
        Enum("PENDING", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED", name="reservation_status_enum"),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    admin_deadline_at = Column(
        DateTime,
        nullable=False,
        comment="created_at + 72 hours; auto-expire after this",
    )
    total_price = Column(Numeric(15, 0), nullable=False, server_default="0")
    discount_percent = Column(SmallInteger, nullable=False, server_default="0")
    final_price = Column(Numeric(15, 0), nullable=False, server_default="0")
    special_plan_id = Column(
        BigInteger,
        ForeignKey("special_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user = relationship("User", foreign_keys=[user_id], lazy="select")
    organization = relationship("Organization", lazy="select")
    place = relationship("Place", lazy="select")
    room_type = relationship("RoomType", lazy="joined")
    special_plan = relationship("SpecialPlan", lazy="select")
    guests = relationship("ReservationGuest", back_populates="reservation", lazy="select")

    def __repr__(self) -> str:
        return f"<Reservation {self.id} status={self.status}>"


class ReservationGuest(Base):
    """Individual people included in a reservation."""

    __tablename__ = "reservation_guests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id = Column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_type = Column(
        Enum("EMPLOYEE", "SPOUSE", "CHILD", "GUEST", name="person_type_enum"),
        nullable=False,
    )
    name = Column(String(255), nullable=True, comment="Nullable for known family members")
    is_extra = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="TRUE for up to 2 extra non-family guests",
    )
    extra_charge = Column(
        Numeric(15, 0),
        nullable=False,
        server_default="0",
        comment="Additional charge for extra guests",
    )

    reservation = relationship("Reservation", back_populates="guests")
