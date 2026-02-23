"""Add spouse name fields to user_profiles.

Revision ID: 005
Revises: 004
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("spouse_first_name", sa.String(128), nullable=True))
    op.add_column("user_profiles", sa.Column("spouse_last_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "spouse_last_name")
    op.drop_column("user_profiles", "spouse_first_name")
