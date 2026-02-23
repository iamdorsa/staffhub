"""Refactor special_plans: org-level plans + user eligibility records.

Revision ID: 004
Revises: 003
Create Date: 2026-02-23

Drops: special_plans
Creates: org_special_plans, user_plan_eligibility
Alters: reservations (rename special_plan_id -> user_plan_eligibility_id)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_NAME='reservations' AND TABLE_SCHEMA=DATABASE() "
        "AND COLUMN_NAME='special_plan_id' AND REFERENCED_TABLE_NAME IS NOT NULL"
    ))
    fk_name = result.scalar()
    if fk_name:
        op.drop_constraint(str(fk_name), "reservations", type_="foreignkey")
    op.drop_column("reservations", "special_plan_id")

    op.drop_table("special_plans")

    # ── org_special_plans ────────────────────────────────────────────────
    op.create_table(
        "org_special_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "org_id",
            sa.BigInteger,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_type",
            sa.Enum("NEW_MARRIAGE", "NEW_CHILD", name="special_plan_type_enum"),
            nullable=False,
        ),
        sa.Column("eligible_from", sa.Date, nullable=False),
        sa.Column("eligible_until", sa.Date, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("org_id", "plan_type", name="uq_org_plan_type"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_org_special_plans_org_id", "org_special_plans", ["org_id"])

    # ── user_plan_eligibility ────────────────────────────────────────────
    op.create_table(
        "user_plan_eligibility",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_special_plan_id",
            sa.BigInteger,
            sa.ForeignKey("org_special_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_user_plan_eligibility_user_id", "user_plan_eligibility", ["user_id"])

    # Add new FK column to reservations
    op.add_column(
        "reservations",
        sa.Column(
            "user_plan_eligibility_id",
            sa.BigInteger,
            sa.ForeignKey("user_plan_eligibility.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reservations", "user_plan_eligibility_id")
    op.drop_table("user_plan_eligibility")
    op.drop_table("org_special_plans")

    op.create_table(
        "special_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "plan_type",
            sa.Enum("NEW_MARRIAGE", "NEW_CHILD", name="special_plan_type_enum"),
            nullable=False,
        ),
        sa.Column("eligible_from", sa.Date, nullable=False),
        sa.Column("eligible_until", sa.Date, nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_special_plans_user_id", "special_plans", ["user_id"])

    op.add_column(
        "reservations",
        sa.Column(
            "special_plan_id",
            sa.BigInteger,
            sa.ForeignKey("special_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
