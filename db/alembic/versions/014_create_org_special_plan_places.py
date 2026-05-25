"""Create org_special_plan_places junction table.

Revision ID: 014
Revises: 013
"""

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"


def upgrade() -> None:
    op.create_table(
        "org_special_plan_places",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "org_special_plan_id",
            sa.BigInteger,
            sa.ForeignKey("org_special_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "place_id",
            sa.BigInteger,
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_special_plan_id", "place_id", name="uq_plan_place"),
    )
    op.create_index("ix_ospp_plan_id", "org_special_plan_places", ["org_special_plan_id"])
    op.create_index("ix_ospp_place_id", "org_special_plan_places", ["place_id"])


def downgrade() -> None:
    op.drop_table("org_special_plan_places")
