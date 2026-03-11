from datetime import datetime
from uuid import UUID


from pydantic import BaseModel, ConfigDict, Field

from app.models.user import RegistrationRequestStatus, Role


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    restaurant: str | None
    role: Role
    job_title: str | None
    is_active: bool
    created_at: datetime


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
    model_config = ConfigDict(from_attributes=True)

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


class CatalogItemCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class JobTitleCatalogItemCreate(CatalogItemCreate):
    restaurant_id: UUID


class CatalogItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class JobTitleCatalogItemPublic(CatalogItemPublic):
    model_config = ConfigDict(from_attributes=True)

    restaurant_id: UUID | None


class RestaurantWithRolesPublic(BaseModel):
    id: UUID
    name: str
    roles: list[CatalogItemPublic]


class UserAttemptPublic(BaseModel):
    id: int
    test_id: int
    test_title: str
    finished_at: datetime
    total_questions: int
    correct_answers: int
    score_percent: float


class UserChecklistCompletionPublic(BaseModel):
    id: int
    checklist_id: int
    checklist_title: str
    completed_at: datetime
    items_count: int


class UserActivityPublic(BaseModel):
    attempts: list[UserAttemptPublic]
    checklist_completions: list[UserChecklistCompletionPublic]
