"""Domain 1a — Organizations, Users, Profiles, Children."""

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
)
from sqlalchemy.orm import relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin


class Organization(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, comment="Short org identifier")
    name = Column(String(255), nullable=False)

    users = relationship("User", back_populates="organization", lazy="select")

    def __repr__(self) -> str:
        return f"<Organization {self.code}>"


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True, comment="Nullable for OTP-only users")
    phone_number = Column(String(20), nullable=True, comment="Used for OTP/SMS login")
    auth_method = Column(
        Enum("PASSWORD", "OTP", "BOTH", name="auth_method_enum"),
        nullable=False,
        server_default="PASSWORD",
    )

    organization = relationship("Organization", back_populates="users")
    profile = relationship("UserProfile", back_populates="user", uselist=False, lazy="joined")
    children = relationship("UserChild", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserProfile(Base):
    """One-to-one personal data extension for User."""

    __tablename__ = "user_profiles"

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    national_id = Column(String(20), unique=True, nullable=True)
    birth_date = Column(Date, nullable=True)
    marital_status = Column(
        Enum("SINGLE", "MARRIED", name="marital_status_enum"),
        nullable=False,
        server_default="SINGLE",
    )
    marriage_date = Column(Date, nullable=True, comment="Required when marital_status=MARRIED")
    spouse_first_name = Column(String(128), nullable=True, comment="Wife/husband first name")
    spouse_last_name = Column(String(128), nullable=True, comment="Wife/husband last name")
    grade = Column(String(64), nullable=True, comment="Employment grade/level (L1, L2, ...)")
    address = Column(String(512), nullable=True)
    number_of_children = Column(SmallInteger, nullable=False, server_default="0")

    user = relationship("User", back_populates="profile")


class UserChild(Base):
    __tablename__ = "user_children"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name = Column(String(128), nullable=True)
    birth_date = Column(Date, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="children")
