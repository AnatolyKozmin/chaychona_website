from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user import RegistrationRequestStatus, Role


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: str
    restaurant: str | None
    role: Role
    job_title: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SetRoleRequest(BaseModel):
    role: Role


class SetJobTitleRequest(BaseModel):
    job_title: str | None = Field(default=None, max_length=255)


class SetLearnerProfileRequest(BaseModel):
    restaurant: str = Field(min_length=2, max_length=255)
    job_title: str = Field(min_length=2, max_length=255)


class CreateUserRequest(BaseModel):
    first_name: str = Field(min_length=2, max_length=255)
    last_name: str = Field(min_length=2, max_length=255)
    restaurant: str | None = Field(default=None, max_length=255)
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.LEARNER
    job_title: str | None = Field(default=None, max_length=255)


class RegistrationRequestPublic(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    restaurant: str
    desired_job_title: str | None
    desired_login: str
    status: RegistrationRequestStatus
    rejection_reason: str | None
    created_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True


class CatalogItemCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class JobTitleCatalogItemCreate(CatalogItemCreate):
    restaurant_id: UUID


class CatalogItemPublic(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True


class JobTitleCatalogItemPublic(CatalogItemPublic):
    restaurant_id: UUID | None

    class Config:
        from_attributes = True


class RestaurantWithRolesPublic(BaseModel):
    id: UUID
    name: str
    roles: list[CatalogItemPublic]
