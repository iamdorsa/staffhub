"""Add name column to place_rooms.

Revision ID: 007
Revises: 006
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("place_rooms", sa.Column("name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("place_rooms", "name")
