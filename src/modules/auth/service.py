from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.access import Role, UserRole
from models.identity import User
from src.core.exceptions import UnauthorizedError
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)


def _build_token_payload(user: User, role_keys: list[str]) -> dict:
    return {"sub": str(user.id), "org_id": user.org_id, "roles": role_keys}


def _get_user_role_keys(db: Session, user_id: int) -> list[str]:
    return list(
        db.execute(
            select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
        .scalars()
        .all()
    )


def login_with_password(db: Session, username: str, password: str) -> dict:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("Invalid username or password")

    if user.auth_method not in ("PASSWORD", "BOTH"):
        raise UnauthorizedError("Password login is not enabled for this account")

    if not user.password_hash or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid username or password")

    if not user.is_active:
        raise UnauthorizedError("Account is deactivated")

    role_keys = _get_user_role_keys(db, user.id)
    payload = _build_token_payload(user, role_keys)

    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
    }


def refresh_access_token(db: Session, refresh_token_str: str) -> dict:
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise UnauthorizedError("Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token payload")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    role_keys = _get_user_role_keys(db, user.id)
    new_payload = _build_token_payload(user, role_keys)

    return {
        "access_token": create_access_token(new_payload),
        "refresh_token": create_refresh_token(new_payload),
    }
