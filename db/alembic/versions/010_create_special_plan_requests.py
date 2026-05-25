"""Create special_plan_requests table.

Revision ID: 010
Revises: 009
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "special_plan_requests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("org_id", sa.BigInteger, sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("user_plan_eligibility_id", sa.BigInteger, sa.ForeignKey("user_plan_eligibility.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_type", sa.String(32), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="plan_request_status_enum"), nullable=False, server_default="PENDING", index=True),
        sa.Column("admin_note", sa.String(1024), nullable=True),
        sa.Column("place_id", sa.BigInteger, sa.ForeignKey("places.id", ondelete="SET NULL"), nullable=True),
        sa.Column("room_type_id", sa.BigInteger, sa.ForeignKey("room_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("check_in_date", sa.Date, nullable=True),
        sa.Column("check_out_date", sa.Date, nullable=True),
        sa.Column("reservation_id", sa.BigInteger, sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("special_plan_requests")
