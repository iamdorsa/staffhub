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
