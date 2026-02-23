from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.access import Role, UserRole
from models.identity import Organization, User, UserChild, UserProfile
from src.core.exceptions import BadRequestError, ConflictError, NotFoundError
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser
from src.core.security import hash_password
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_role_keys(db: Session, user_id: int) -> list[str]:
    return list(
        db.execute(
            select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
        .scalars()
        .all()
    )


def _scope_org_filter(query, current_user: CurrentUser):
    """ORG_ADMIN can only see their own org."""
    if not current_user.is_super_admin:
        query = query.where(Organization.id == current_user.org_id)
    return query


def _scope_user_filter(query, current_user: CurrentUser):
    if not current_user.is_super_admin:
        query = query.where(User.org_id == current_user.org_id)
    return query


# ── Organization ─────────────────────────────────────────────────────────────

def list_orgs(db: Session, current_user: CurrentUser, params: PaginationParams) -> PaginatedResponse:
    base = select(Organization)
    base = _scope_org_filter(base, current_user)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(Organization.id).offset(params.offset).limit(params.page_size)).scalars().all()

    return PaginatedResponse.create([OrgResponse.model_validate(r) for r in rows], total, params)


def create_org(db: Session, data: OrgCreate) -> OrgResponse:
    existing = db.execute(select(Organization).where(Organization.code == data.code)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Organization with code '{data.code}' already exists")

    org = Organization(code=data.code, name=data.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrgResponse.model_validate(org)


def update_org(db: Session, org_id: int, data: OrgUpdate) -> OrgResponse:
    org = db.get(Organization, org_id)
    if not org:
        raise NotFoundError("Organization not found")

    if data.name is not None:
        org.name = data.name
    if data.is_active is not None:
        org.is_active = data.is_active

    db.commit()
    db.refresh(org)
    return OrgResponse.model_validate(org)


# ── User ─────────────────────────────────────────────────────────────────────

def list_users(
    db: Session, current_user: CurrentUser, params: PaginationParams,
    org_id: int | None = None, search: str | None = None,
) -> PaginatedResponse:
    base = select(User)
    base = _scope_user_filter(base, current_user)

    if org_id:
        base = base.where(User.org_id == org_id)
    if search:
        pattern = f"%{search}%"
        base = base.join(User.profile).where(
            (UserProfile.first_name.ilike(pattern)) | (UserProfile.last_name.ilike(pattern))
        )

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    rows = db.execute(base.order_by(User.id).offset(params.offset).limit(params.page_size)).scalars().all()

    items = []
    for u in rows:
        items.append(UserListItem(
            id=u.id, org_id=u.org_id, username=u.username, is_active=u.is_active,
            first_name=u.profile.first_name if u.profile else None,
            last_name=u.profile.last_name if u.profile else None,
        ))

    return PaginatedResponse.create(items, total, params)


def get_user(db: Session, user_id: int, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("User not found")

    role_keys = _get_user_role_keys(db, user.id)
    children = [ChildResponse.model_validate(c) for c in user.children]
    profile = ProfileResponse.model_validate(user.profile) if user.profile else None

    return UserResponse(
        id=user.id, org_id=user.org_id, username=user.username,
        phone_number=user.phone_number, auth_method=user.auth_method,
        is_active=user.is_active, created_at=user.created_at,
        profile=profile, children=children, roles=role_keys,
    )


def create_user(db: Session, data: UserCreate) -> UserResponse:
    org = db.get(Organization, data.org_id)
    if not org:
        raise NotFoundError("Organization not found")

    existing = db.execute(select(User).where(User.username == data.username)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Username '{data.username}' is already taken")

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
        grade=data.profile.grade,
    )
    db.add(profile)

    employee_role = db.execute(select(Role).where(Role.key == "EMPLOYEE")).scalar_one_or_none()
    if employee_role:
        db.add(UserRole(user_id=user.id, role_id=employee_role.id))

    db.commit()
    db.refresh(user)
    return get_user(db, user.id, CurrentUser(id=0, org_id=0, username="", is_active=True, role_keys=["SUPER_ADMIN"]))


def update_user(db: Session, user_id: int, data: UserUpdate, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("User not found")

    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.auth_method is not None:
        user.auth_method = data.auth_method

    if data.profile and user.profile:
        p = data.profile
        if p.first_name is not None:
            user.profile.first_name = p.first_name
        if p.last_name is not None:
            user.profile.last_name = p.last_name
        if p.national_id is not None:
            user.profile.national_id = p.national_id
        if p.birth_date is not None:
            user.profile.birth_date = p.birth_date
        if p.marital_status is not None:
            user.profile.marital_status = p.marital_status
        if p.marriage_date is not None:
            user.profile.marriage_date = p.marriage_date
        if p.grade is not None:
            user.profile.grade = p.grade

    db.commit()
    return get_user(db, user.id, current_user)


def deactivate_user(db: Session, user_id: int, current_user: CurrentUser) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("User not found")

    user.is_active = False
    db.commit()
    return get_user(db, user.id, current_user)


def add_child(db: Session, user_id: int, data: ChildCreate, current_user: CurrentUser) -> ChildResponse:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("User not found")

    child = UserChild(user_id=user_id, first_name=data.first_name, birth_date=data.birth_date)
    db.add(child)

    if user.profile:
        user.profile.number_of_children += 1

    db.commit()
    db.refresh(child)
    return ChildResponse.model_validate(child)


def assign_roles(db: Session, user_id: int, data: RoleAssignRequest, current_user: CurrentUser) -> list[str]:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    if not current_user.is_super_admin and user.org_id != current_user.org_id:
        raise NotFoundError("User not found")

    roles = db.execute(select(Role).where(Role.id.in_(data.role_ids))).scalars().all()
    if len(roles) != len(data.role_ids):
        raise BadRequestError("One or more role IDs are invalid")

    db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id))

    db.commit()
    return [r.key for r in roles]
