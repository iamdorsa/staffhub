"""Create identity & access-control tables.

Revision ID: 001
Revises: —
Create Date: 2026-02-23

Tables: organizations, users, user_profiles, user_children,
        roles, permissions, role_permissions, user_roles, otp_tokens
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Organizations ────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.BigInteger, sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("username", sa.String(128), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column(
            "auth_method",
            sa.Enum("PASSWORD", "OTP", "BOTH", name="auth_method_enum"),
            nullable=False,
            server_default="PASSWORD",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # ── User Profiles ────────────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("national_id", sa.String(20), unique=True, nullable=True),
        sa.Column("birth_date", sa.Date, nullable=True),
        sa.Column(
            "marital_status",
            sa.Enum("SINGLE", "MARRIED", name="marital_status_enum"),
            nullable=False,
            server_default="SINGLE",
        ),
        sa.Column("marriage_date", sa.Date, nullable=True),
        sa.Column("grade", sa.String(64), nullable=True),
        sa.Column("number_of_children", sa.SmallInteger, nullable=False, server_default="0"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── User Children ────────────────────────────────────────────────────
    op.create_table(
        "user_children",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_user_children_user_id", "user_children", ["user_id"])

    # ── Roles ────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "scope",
            sa.Enum("SYSTEM", "ORGANIZATION", name="role_scope_enum"),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Permissions ──────────────────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── Role ↔ Permission (M:N) ─────────────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "permission_id",
            sa.BigInteger,
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── User ↔ Role ─────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # ── OTP Tokens ───────────────────────────────────────────────────────
    op.create_table(
        "otp_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_otp_tokens_user_id", "otp_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("otp_tokens")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("user_children")
    op.drop_table("user_profiles")
    op.drop_table("users")
    op.drop_table("organizations")
