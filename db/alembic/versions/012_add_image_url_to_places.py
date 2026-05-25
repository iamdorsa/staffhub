"""add image_url to places

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"


def upgrade() -> None:
    op.add_column("places", sa.Column("image_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "image_url")
