from dataclasses import dataclass, field

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.access import Permission, Role, RolePermission, UserRole
from models.identity import User
from src.core.database import get_db
from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import decode_token

bearer_scheme = HTTPBearer()


@dataclass
class CurrentUser:
    id: int
    org_id: int
    username: str
    is_active: bool
    role_keys: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    @property
    def is_super_admin(self) -> bool:
        return "SUPER_ADMIN" in self.role_keys


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise UnauthorizedError("توکن نامعتبر یا منقضی شده است")

    if payload.get("type") != "access":
        raise UnauthorizedError("نوع توکن نامعتبر است")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("اطلاعات توکن نامعتبر است")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("کاربر یافت نشد یا غیرفعال است")

    role_rows = (
        db.execute(
            select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
        )
        .scalars()
        .all()
    )

    perm_rows = (
        db.execute(
            select(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.key.in_(role_rows))
        )
        .scalars()
        .all()
    )

    return CurrentUser(
        id=user.id,
        org_id=user.org_id,
        username=user.username,
        is_active=user.is_active,
        role_keys=list(role_rows),
        permissions=set(perm_rows),
    )


def get_user_role_keys(db: Session, user_id: int) -> list[str]:
    return list(
        db.execute(
            select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
        .scalars()
        .all()
    )


def require_permission(permission_key: str):
    """Returns a FastAPI dependency that checks a specific permission."""

    def checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.is_super_admin:
            return current_user
        if permission_key not in current_user.permissions:
            raise ForbiddenError("شما دسترسی لازم برای این عملیات را ندارید")
        return current_user

    return checker
