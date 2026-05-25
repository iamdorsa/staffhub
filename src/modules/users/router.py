from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.pagination import PaginatedResponse, PaginationParams
from src.core.permissions import CurrentUser, get_current_user, require_permission
from src.modules.users import service
from src.modules.users.schemas import (
    ChildCreate,
    ChildResponse,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    RoleAssignRequest,
    UserCreate,
    UserListItem,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


# ── Organizations ────────────────────────────────────────────────────────────

@router.get("/orgs", response_model=PaginatedResponse[OrgResponse])
def list_organizations(
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(require_permission("user.view")),
    db: Session = Depends(get_db),
):
    return service.list_orgs(db, current_user, params, search=search, sort_by=sort_by, sort_dir=sort_dir)


@router.post("/orgs", response_model=OrgResponse, status_code=201)
def create_organization(
    body: OrgCreate,
    current_user: CurrentUser = Depends(require_permission("org.manage")),
    db: Session = Depends(get_db),
):
    return service.create_org(db, body)


@router.patch("/orgs/{org_id}", response_model=OrgResponse)
def update_organization(
    org_id: int,
    body: OrgUpdate,
    current_user: CurrentUser = Depends(require_permission("org.manage")),
    db: Session = Depends(get_db),
):
    return service.update_org(db, org_id, body)


# ── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=PaginatedResponse[UserListItem])
def list_users(
    org_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(require_permission("user.view")),
    db: Session = Depends(get_db),
):
    return service.list_users(db, current_user, params, org_id=org_id, search=search, sort_by=sort_by, sort_dir=sort_dir)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_permission("user.view")),
    db: Session = Depends(get_db),
):
    return service.get_user(db, user_id, current_user)


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    current_user: CurrentUser = Depends(require_permission("user.create")),
    db: Session = Depends(get_db),
):
    return service.create_user(db, body, current_user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: CurrentUser = Depends(require_permission("user.edit")),
    db: Session = Depends(get_db),
):
    return service.update_user(db, user_id, body, current_user)


@router.delete("/users/{user_id}", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_permission("user.deactivate")),
    db: Session = Depends(get_db),
):
    return service.deactivate_user(db, user_id, current_user)


# ── Children ─────────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/children", response_model=ChildResponse, status_code=201)
def add_child(
    user_id: int,
    body: ChildCreate,
    current_user: CurrentUser = Depends(require_permission("user.edit")),
    db: Session = Depends(get_db),
):
    return service.add_child(db, user_id, body, current_user)


# ── Roles ────────────────────────────────────────────────────────────────────

@router.put("/users/{user_id}/roles")
def assign_roles(
    user_id: int,
    body: RoleAssignRequest,
    current_user: CurrentUser = Depends(require_permission("user.assign_role")),
    db: Session = Depends(get_db),
):
    roles = service.assign_roles(db, user_id, body, current_user)
    return {"user_id": user_id, "roles": roles}


# ── Me ───────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_user(db, current_user.id, current_user)
