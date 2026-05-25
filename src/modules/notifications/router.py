from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser, get_current_user
from src.modules.notifications import service
from src.modules.notifications.schemas import NotificationResponse, UnreadCountResponse

router = APIRouter()


@router.get("/notifications", response_model=PaginatedResponse[NotificationResponse])
def list_notifications(
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_notifications(db, current_user, params)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_unread_count(db, current_user)


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.mark_as_read(db, notification_id, current_user)


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.mark_all_as_read(db, current_user)
