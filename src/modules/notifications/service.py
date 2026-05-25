import logging

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from models.accommodation import Notification
from src.core.exceptions import NotFoundError
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser
from src.modules.notifications.schemas import NotificationResponse, UnreadCountResponse

logger = logging.getLogger(__name__)


class NotificationType:
    NEW_RESERVATION = "NEW_RESERVATION"
    RESERVATION_REVIEWED = "RESERVATION_REVIEWED"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    NEW_PLAN_REQUEST = "NEW_PLAN_REQUEST"
    PLAN_REQUEST_REVIEWED = "PLAN_REQUEST_REVIEWED"


def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    message: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> None:
    db.add(Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        reference_type=reference_type,
        reference_id=reference_id,
    ))


def notify_admins(
    db: Session,
    *,
    org_id: int,
    type: str,
    title: str,
    message: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> None:
    from models.access import Role, UserRole
    from models.identity import User

    admin_ids = (
        db.execute(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.is_active == True,  # noqa: E712
                or_(
                    (Role.key == "ORG_ADMIN") & (User.org_id == org_id),
                    Role.key == "SUPER_ADMIN",
                ),
            )
        )
        .scalars()
        .all()
    )

    for admin_id in set(admin_ids):
        try:
            create_notification(
                db,
                user_id=admin_id,
                type=type,
                title=title,
                message=message,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        except Exception:
            logger.warning("Failed to create notification for admin %s", admin_id, exc_info=True)


def list_notifications(db: Session, current_user: CurrentUser, params: PaginationParams) -> PaginatedResponse:
    base = select(Notification).where(Notification.user_id == current_user.id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(
        base.order_by(Notification.created_at.desc()).offset(params.offset).limit(params.page_size)
    ).scalars().all()
    items = [NotificationResponse.model_validate(r) for r in rows]
    return PaginatedResponse.create(items, total, params)


def get_unread_count(db: Session, current_user: CurrentUser) -> UnreadCountResponse:
    count = db.execute(
        select(func.count()).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    ).scalar() or 0
    return UnreadCountResponse(count=count)


def mark_as_read(db: Session, notification_id: int, current_user: CurrentUser) -> None:
    n = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not n:
        raise NotFoundError("اعلان یافت نشد")
    n.is_read = True
    db.commit()


def mark_all_as_read(db: Session, current_user: CurrentUser) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    db.commit()
