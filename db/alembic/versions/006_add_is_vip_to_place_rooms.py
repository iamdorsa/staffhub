"""Add is_vip flag to place_rooms and reservations.

Revision ID: 006
Revises: 005
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("place_rooms", sa.Column("is_vip", sa.Boolean, nullable=False, server_default="0"))

    op.create_unique_constraint("uq_place_room_vip", "place_rooms", ["place_id", "room_type_id", "is_vip"])

    op.execute("ALTER TABLE place_rooms DROP INDEX uq_place_room")

    op.add_column("reservations", sa.Column("is_vip", sa.Boolean, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("reservations", "is_vip")

    op.create_unique_constraint("uq_place_room", "place_rooms", ["place_id", "room_type_id"])
    op.execute("ALTER TABLE place_rooms DROP INDEX uq_place_room_vip")
    op.drop_column("place_rooms", "is_vip")
