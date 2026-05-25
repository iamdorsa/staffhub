"""Add address to places and user_profiles, capacity to place_rooms.

Revision ID: 009
Revises: 008
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("places", sa.Column("address", sa.String(512), nullable=True))
    op.add_column("user_profiles", sa.Column("address", sa.String(512), nullable=True))
    op.add_column("place_rooms", sa.Column("capacity", sa.SmallInteger, nullable=True))


def downgrade() -> None:
    op.drop_column("place_rooms", "capacity")
    op.drop_column("user_profiles", "address")
    op.drop_column("places", "address")
