import secrets
import time

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.identity import User
from src.config import settings
from src.core.exceptions import BadRequestError, UnauthorizedError
from src.core.permissions import get_user_role_keys
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

# In-memory OTP store: {username: (code, expires_at)}
_otp_store: dict[str, tuple[str, float]] = {}


def _build_token_payload(user: User, role_keys: list[str]) -> dict:
    return {"sub": str(user.id), "org_id": user.org_id, "roles": role_keys}


def login_with_password(db: Session, username: str, password: str) -> dict:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("نام کاربری یا رمز عبور اشتباه است")

    if user.auth_method not in ("PASSWORD", "BOTH"):
        raise UnauthorizedError("ورود با رمز عبور برای این حساب فعال نیست")

    if not user.password_hash or not verify_password(password, user.password_hash):
        raise UnauthorizedError("نام کاربری یا رمز عبور اشتباه است")

    if not user.is_active:
        raise UnauthorizedError("حساب کاربری غیرفعال شده است")

    role_keys = get_user_role_keys(db, user.id)
    payload = _build_token_payload(user, role_keys)

    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
    }


def refresh_access_token(db: Session, refresh_token_str: str) -> dict:
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise UnauthorizedError("توکن نامعتبر یا منقضی شده است")

    if payload.get("type") != "refresh":
        raise UnauthorizedError("نوع توکن نامعتبر است")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("اطلاعات توکن نامعتبر است")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("کاربر یافت نشد یا غیرفعال است")

    role_keys = get_user_role_keys(db, user.id)
    new_payload = _build_token_payload(user, role_keys)

    return {
        "access_token": create_access_token(new_payload),
        "refresh_token": create_refresh_token(new_payload),
    }


def send_otp(db: Session, username: str) -> dict:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("کاربر یافت نشد")

    if user.auth_method not in ("OTP", "BOTH"):
        raise BadRequestError("ورود با رمز یکبار مصرف برای این حساب فعال نیست")

    if not user.phone_number:
        raise BadRequestError("شماره تلفن برای این حساب ثبت نشده است")

    if not user.is_active:
        raise UnauthorizedError("حساب کاربری غیرفعال شده است")

    code = "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))
    expires_at = time.time() + settings.OTP_EXPIRY_SECONDS
    _otp_store[username] = (code, expires_at)

    if settings.SMS_PROVIDER == "console":
        print(f"[OTP] {username}: {code}")

    return {"message": "کد تایید ارسال شد"}


def verify_otp(db: Session, username: str, otp_code: str) -> dict:
    stored = _otp_store.get(username)

    if stored is None:
        raise UnauthorizedError("کد تایید نامعتبر یا منقضی شده است")

    code, expires_at = stored

    if time.time() > expires_at:
        _otp_store.pop(username, None)
        raise UnauthorizedError("کد تایید نامعتبر یا منقضی شده است")

    if otp_code != code:
        raise UnauthorizedError("کد تایید نامعتبر یا منقضی شده است")

    _otp_store.pop(username, None)

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError("کاربر یافت نشد یا غیرفعال است")

    role_keys = get_user_role_keys(db, user.id)
    payload = _build_token_payload(user, role_keys)

    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
    }
