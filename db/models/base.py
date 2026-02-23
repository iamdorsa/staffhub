from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at / updated_at to any model."""

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


class SoftDeleteMixin:
    """Adds is_active flag for soft-deletes."""

    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
