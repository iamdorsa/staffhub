"""Create place_ratings table.

Revision ID: 008
Revises: 007
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "place_ratings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("score", sa.SmallInteger, nullable=False, comment="1-5 stars"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "place_id", name="uq_user_place_rating"),
    )


def downgrade() -> None:
    op.drop_table("place_ratings")
