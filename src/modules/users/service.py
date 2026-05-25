from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.access import Role, UserRole
from models.identity import Organization, User, UserChild, UserProfile
from src.core.exceptions import BadRequestError, ConflictError, NotFoundError
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser, get_user_role_keys
from src.core.security import hash_password
from src.modules.accommodation.service import grant_user_plan_eligibility
from src.modules.users.schemas import (
    ChildCreate,
    ChildResponse,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    ProfileResponse,
    RoleAssignRequest,
    UserCreate,
    UserListItem,
    UserResponse,
    UserUpdate,
)


def _scope_org_filter(query, current_user: CurrentUser):
    if not current_user.is_super_admin:
        query = query.where(Organization.id == current_user.org_id)
    return query


def _scope_user_filter(query, current_user: CurrentUser):
    if not current_user.is_super_admin:
        query = query.where(User.org_id == current_user.org_id)
    return query


# ── Organization ─────────────────────────────────────────────────────────────

_ORG_SORT_COLUMNS = {
    "id": Organization.id,
    "code": Organization.code,
    "name": Organization.name,
    "created_at": Organization.created_at,
}


def list_orgs(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    search: str | None = None, sort_by: str | None = None, sort_dir: str | None = None,
) -> PaginatedResponse:
    base = select(Organization)
    base = _scope_org_filter(base, current_user)

    if search:
        pattern = f"%{search}%"
        base = base.where(or_(Organization.code.ilike(pattern), Organization.name.ilike(pattern)))

    col = _ORG_SORT_COLUMNS.get(sort_by, Organization.id)
    order = col.desc() if sort_dir == "desc" else col.asc()
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(order).offset(params.offset).limit(params.page_size)).scalars().all()

    return PaginatedResponse.create([OrgResponse.model_validate(r) for r in rows], total, params)


def create_org(db: Session, data: OrgCreate) -> OrgResponse:
    existing = db.execute(select(Organization).where(Organization.code == data.code)).scalar_one_or_none()
    if existing:
        raise ConflictError("این کد سازمان قبلاً ثبت شده است")

    org = Organization(code=data.code, name=data.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrgResponse.model_validate(org)


def update_org(db: Session, org_id: int, data: OrgUpdate) -> OrgResponse:
    org = db.get(Organization, org_id)
    if not org:
        raise NotFoundError("سازمان یافت نشد")

    if data.name is not None:
        org.name = data.name
    if data.is_active is not None:
        org.is_active = data.is_active

    db.commit()
    db.refresh(org)
    return OrgResponse.model_validate(org)


# ── User ─────────────────────────────────────────────────────────────────────

_USER_SORT_COLUMNS = {
    "id": User.id,
    "username": User.username,
    "is_active": User.is_active,
}


def list_users(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    org_id: int | None = None, search: str | None = None,
    sort_by: str | None = None, sort_dir: str | None = None,
) -> PaginatedResponse:
    base = select(User)
    base = _scope_user_filter(base, current_user)

    if org_id:
        base = base.where(User.org_id == org_id)
    if search:
        pattern = f"%{search}%"
        base = base.outerjoin(User.profile).where(
            or_(
                UserProfile.first_name.ilike(pattern),
                UserProfile.last_name.ilike(pattern),
                UserProfile.national_id.ilike(pattern),
                User.username.ilike(pattern),
            )
        )

    col = _USER_SORT_COLUMNS.get(sort_by, User.id)
    order = col.desc() if sort_dir == "desc" else col.asc()
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(order).offset(params.offset).limit(params.page_size)).scalars().all()

    org_cache: dict[int, str] = {}

    items = []
    for u in rows:
        if u.org_id not in org_cache:
            org = db.get(Organization, u.org_id)
            org_cache[u.org_id] = org.name if org else None
        items.append(UserListItem(
            id=u.id, org_id=u.org_id, username=u.username, is_active=u.is_active,
            first_name=u.profile.first_name if u.profile else None,
            last_name=u.profile.last_name if u.profile else None,
            national_id=u.profile.national_id if u.profile else None,
            org_name=org_cache.get(u.org_id),
        ))

    return PaginatedResponse.create(items, total, params)


def get_user(db: Session, user_id: int, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("کاربر یافت نشد")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("کاربر یافت نشد")

    role_keys = get_user_role_keys(db, user.id)
    children = [ChildResponse.model_validate(c) for c in user.children]
    profile = ProfileResponse.model_validate(user.profile) if user.profile else None
    org = db.get(Organization, user.org_id)

    return UserResponse(
        id=user.id, org_id=user.org_id, username=user.username,
        phone_number=user.phone_number, auth_method=user.auth_method,
        is_active=user.is_active, created_at=user.created_at,
        profile=profile, children=children, roles=role_keys,
        org_name=org.name if org else None,
    )


def create_user(db: Session, data: UserCreate, current_user: CurrentUser) -> UserResponse:
    org = db.get(Organization, data.org_id)
    if not org:
        raise NotFoundError("سازمان یافت نشد")

    existing = db.execute(select(User).where(User.username == data.username)).scalar_one_or_none()
    if existing:
        raise ConflictError("این نام کاربری قبلاً ثبت شده است")

    if data.profile.national_id:
        dup = db.execute(
            select(UserProfile).where(UserProfile.national_id == data.profile.national_id)
        ).scalar_one_or_none()
        if dup:
            raise ConflictError("این کد ملی قبلاً ثبت شده است")

    user = User(
        org_id=data.org_id,
        username=data.username,
        password_hash=hash_password(data.password) if data.password else None,
        phone_number=data.phone_number,
        auth_method=data.auth_method,
    )
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=user.id,
        first_name=data.profile.first_name,
        last_name=data.profile.last_name,
        national_id=data.profile.national_id,
        birth_date=data.profile.birth_date,
        marital_status=data.profile.marital_status,
        marriage_date=data.profile.marriage_date,
        spouse_first_name=data.profile.spouse_first_name,
        spouse_last_name=data.profile.spouse_last_name,
        grade=data.profile.grade,
    )
    db.add(profile)

    employee_role = db.execute(select(Role).where(Role.key == "EMPLOYEE")).scalar_one_or_none()
    if employee_role:
        db.add(UserRole(user_id=user.id, role_id=employee_role.id))

    db.commit()
    db.refresh(user)
    return get_user(db, user.id, current_user)


def update_user(db: Session, user_id: int, data: UserUpdate, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("کاربر یافت نشد")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("کاربر یافت نشد")

    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.auth_method is not None:
        user.auth_method = data.auth_method

    was_single = user.profile.marital_status == "SINGLE" if user.profile else True

    if data.profile and user.profile:
        updates = data.profile.model_dump(exclude_none=True)

        new_nid = updates.get("national_id")
        if new_nid and new_nid != user.profile.national_id:
            dup = db.execute(
                select(UserProfile).where(
                    UserProfile.national_id == new_nid,
                    UserProfile.user_id != user_id,
                )
            ).scalar_one_or_none()
            if dup:
                raise ConflictError("این کد ملی قبلاً ثبت شده است")

        for field, value in updates.items():
            setattr(user.profile, field, value)

        if was_single and user.profile.marital_status == "MARRIED":
            grant_user_plan_eligibility(db, user.id, user.org_id, "NEW_MARRIAGE")

    db.commit()
    return get_user(db, user.id, current_user)


def deactivate_user(db: Session, user_id: int, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("کاربر یافت نشد")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("کاربر یافت نشد")

    user.is_active = False
    db.commit()
    return get_user(db, user.id, current_user)


def add_child(db: Session, user_id: int, data: ChildCreate, current_user: CurrentUser) -> ChildResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("کاربر یافت نشد")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("کاربر یافت نشد")

    child = UserChild(user_id=user_id, first_name=data.first_name, birth_date=data.birth_date)
    db.add(child)

    if user.profile:
        user.profile.number_of_children += 1

    grant_user_plan_eligibility(db, user_id, user.org_id, "NEW_CHILD")

    db.commit()
    db.refresh(child)
    return ChildResponse.model_validate(child)


def assign_roles(db: Session, user_id: int, data: RoleAssignRequest, current_user: CurrentUser) -> list[str]:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("کاربر یافت نشد")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("کاربر یافت نشد")

    roles = db.execute(select(Role).where(Role.id.in_(data.role_ids))).scalars().all()
    if len(roles) != len(data.role_ids):
        raise BadRequestError("یک یا چند نقش انتخاب‌شده نامعتبر است")

    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id))

    db.commit()
    return [r.key for r in roles]
