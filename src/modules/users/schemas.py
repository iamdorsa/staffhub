from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


# ── Organization ─────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    code: str
    name: str


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class OrgResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Profile / Children ───────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    marital_status: str = "SINGLE"
    marriage_date: Optional[date] = None
    spouse_first_name: Optional[str] = None
    spouse_last_name: Optional[str] = None
    grade: Optional[str] = None

    @model_validator(mode="after")
    def married_requires_details(self):
        if self.marital_status == "MARRIED":
            if self.marriage_date is None:
                raise ValueError("marriage_date is required when marital_status is MARRIED")
            if not self.spouse_first_name or not self.spouse_last_name:
                raise ValueError("spouse_first_name and spouse_last_name are required when MARRIED")
        return self


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    marital_status: Optional[str] = None
    marriage_date: Optional[date] = None
    spouse_first_name: Optional[str] = None
    spouse_last_name: Optional[str] = None
    grade: Optional[str] = None

    @model_validator(mode="after")
    def married_requires_details(self):
        if self.marital_status == "MARRIED":
            if self.marriage_date is None:
                raise ValueError("marriage_date is required when marital_status is MARRIED")
            if not self.spouse_first_name or not self.spouse_last_name:
                raise ValueError("spouse_first_name and spouse_last_name are required when MARRIED")
        return self


class ChildCreate(BaseModel):
    first_name: Optional[str] = None
    birth_date: date


class ChildResponse(BaseModel):
    id: int
    first_name: Optional[str]
    birth_date: date

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    first_name: str
    last_name: str
    national_id: Optional[str]
    birth_date: Optional[date]
    marital_status: str
    marriage_date: Optional[date]
    spouse_first_name: Optional[str]
    spouse_last_name: Optional[str]
    grade: Optional[str]
    number_of_children: int

    model_config = {"from_attributes": True}


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    org_id: int
    username: str
    password: Optional[str] = None
    phone_number: Optional[str] = None
    auth_method: str = "PASSWORD"
    profile: ProfileCreate


class UserUpdate(BaseModel):
    phone_number: Optional[str] = None
    auth_method: Optional[str] = None
    profile: Optional[ProfileUpdate] = None


class RoleAssignRequest(BaseModel):
    role_ids: list[int]

    @field_validator("role_ids")
    @classmethod
    def max_two_roles(cls, v):
        if len(v) > 2:
            raise ValueError("A user can have at most 2 roles")
        return v


class UserResponse(BaseModel):
    id: int
    org_id: int
    username: str
    phone_number: Optional[str]
    auth_method: str
    is_active: bool
    created_at: datetime
    profile: Optional[ProfileResponse] = None
    children: list[ChildResponse] = []
    roles: list[str] = []

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    id: int
    org_id: int
    username: str
    is_active: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    model_config = {"from_attributes": True}
