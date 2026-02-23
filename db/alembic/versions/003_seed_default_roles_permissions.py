"""Seed default roles and permissions.

Revision ID: 003
Revises: 002
Create Date: 2026-02-23

Seeds: roles, permissions, role_permissions, room_types
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = [
    {"id": 1, "key": "SUPER_ADMIN", "name": "Super Administrator", "scope": "SYSTEM"},
    {"id": 2, "key": "ORG_ADMIN", "name": "Organization Administrator", "scope": "ORGANIZATION"},
    {"id": 3, "key": "EMPLOYEE", "name": "Employee", "scope": "ORGANIZATION"},
]

PERMISSIONS = [
    {"id": 1,  "key": "user.view",               "description": "View user list and details"},
    {"id": 2,  "key": "user.create",             "description": "Create new users"},
    {"id": 3,  "key": "user.edit",               "description": "Edit user information"},
    {"id": 4,  "key": "user.deactivate",         "description": "Deactivate/reactivate users"},
    {"id": 5,  "key": "user.assign_role",         "description": "Assign or remove roles from users"},
    {"id": 6,  "key": "place.manage",             "description": "Create/edit/deactivate accommodation places"},
    {"id": 7,  "key": "place.set_availability",   "description": "Block or unblock dates for places"},
    {"id": 8,  "key": "pricing.manage",           "description": "Create and modify pricing rules"},
    {"id": 9,  "key": "reservation.create",       "description": "Create a reservation request"},
    {"id": 10, "key": "reservation.view_own",     "description": "View own reservations"},
    {"id": 11, "key": "reservation.view_all",     "description": "View all reservations (admin)"},
    {"id": 12, "key": "reservation.approve",      "description": "Approve or reject reservation requests"},
    {"id": 13, "key": "reservation.assign_vip",   "description": "Assign VIP rooms to users"},
    {"id": 14, "key": "org.manage",               "description": "Manage organizations"},
    {"id": 15, "key": "org.set_place_access",     "description": "Configure which orgs can access which places"},
    {"id": 16, "key": "special_plan.manage",       "description": "Create/manage special plans for users"},
]

SUPER_ADMIN_PERM_IDS = [p["id"] for p in PERMISSIONS]

ORG_ADMIN_PERM_IDS = [1, 2, 3, 9, 10, 11]

EMPLOYEE_PERM_IDS = [9, 10]

ROOM_TYPES = [
    {"id": 1, "key": "ONE_BED", "label": "Single Bed Room", "max_capacity": 5},
    {"id": 2, "key": "TWO_BED", "label": "Double Bed Room", "max_capacity": 8},
]


def upgrade() -> None:
    roles_t = sa.table(
        "roles",
        sa.column("id", sa.BigInteger),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("scope", sa.String),
    )
    op.bulk_insert(roles_t, ROLES)

    perms_t = sa.table(
        "permissions",
        sa.column("id", sa.BigInteger),
        sa.column("key", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(perms_t, PERMISSIONS)

    rp_t = sa.table(
        "role_permissions",
        sa.column("role_id", sa.BigInteger),
        sa.column("permission_id", sa.BigInteger),
    )

    role_perm_rows = []
    for pid in SUPER_ADMIN_PERM_IDS:
        role_perm_rows.append({"role_id": 1, "permission_id": pid})
    for pid in ORG_ADMIN_PERM_IDS:
        role_perm_rows.append({"role_id": 2, "permission_id": pid})
    for pid in EMPLOYEE_PERM_IDS:
        role_perm_rows.append({"role_id": 3, "permission_id": pid})
    op.bulk_insert(rp_t, role_perm_rows)

    rt_t = sa.table(
        "room_types",
        sa.column("id", sa.BigInteger),
        sa.column("key", sa.String),
        sa.column("label", sa.String),
        sa.column("max_capacity", sa.SmallInteger),
    )
    op.bulk_insert(rt_t, ROOM_TYPES)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role_permissions"))
    conn.execute(sa.text("DELETE FROM permissions"))
    conn.execute(sa.text("DELETE FROM roles"))
    conn.execute(sa.text("DELETE FROM room_types"))
