from fastapi import FastAPI

from src.core.exceptions import AppError, app_error_handler, integrity_error_handler
from src.modules.auth.router import router as auth_router
from src.modules.users.router import router as users_router
from src.modules.accommodation.router import router as accommodation_router
from src.modules.notifications.router import router as notifications_router

from sqlalchemy.exc import IntegrityError


def create_app() -> FastAPI:
    app = FastAPI(title="StaffHub", version="1.0.0", docs_url="/docs")

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(users_router, prefix="/api/v1", tags=["Users"])
    app.include_router(accommodation_router, prefix="/api/v1", tags=["Accommodation"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["Notifications"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
