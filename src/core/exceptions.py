import re

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "Something went wrong", details: dict | None = None):
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class BadRequestError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class GoneError(AppError):
    status_code = 410
    code = "GONE"


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


_DUPLICATE_KEY_LABELS: dict[str, str] = {
    "username": "این نام کاربری قبلاً ثبت شده است",
    "national_id": "این کد ملی قبلاً ثبت شده است",
    "code": "این کد سازمان قبلاً ثبت شده است",
    "uq_org_place": "این سازمان قبلاً به این اقامتگاه دسترسی دارد",
    "uq_place_room_vip": "این نوع اتاق قبلاً برای این اقامتگاه ثبت شده",
    "uq_org_plan_type": "این نوع طرح ویژه قبلاً برای این سازمان ثبت شده",
    "uq_place_avail_date": "ظرفیت این تاریخ قبلاً ثبت شده است",
    "uq_discount_user_year": "رکورد تخفیف این کاربر برای این سال قبلاً وجود دارد",
}

_DUP_RE = re.compile(r"Duplicate entry '.*?' for key '(?:.*\.)?(\w+)'")


async def integrity_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    msg_str = str(exc)
    match = _DUP_RE.search(msg_str)
    if match:
        key = match.group(1)
        message = _DUPLICATE_KEY_LABELS.get(key, f"رکورد تکراری ({key})")
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "CONFLICT", "message": message, "details": {}}},
        )

    return JSONResponse(
        status_code=409,
        content={"error": {"code": "CONFLICT", "message": "داده تکراری یا نامعتبر", "details": {}}},
    )
