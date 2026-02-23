"""Domain 1b — Roles, Permissions, RBAC mapping, OTP tokens."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from models.base import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, comment="Machine-readable key")
    name = Column(String(128), nullable=False)
    scope = Column(
        Enum("SYSTEM", "ORGANIZATION", name="role_scope_enum"),
        nullable=False,
        comment="SYSTEM = global, ORGANIZATION = org-scoped",
    )
    description = Column(Text, nullable=True)

    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Role {self.key}>"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(
        String(128),
        unique=True,
        nullable=False,
        comment="Dot-notation key, e.g. reservation.approve",
    )
    description = Column(Text, nullable=True)

    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Permission {self.key}>"


class RolePermission(Base):
    """M:N join between roles and permissions."""

    __tablename__ = "role_permissions"

    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )


class UserRole(Base):
    """Assigns roles to users. App layer enforces max-2 roles per user."""

    __tablename__ = "user_roles"

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class OtpToken(Base):
    __tablename__ = "otp_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", lazy="select")
