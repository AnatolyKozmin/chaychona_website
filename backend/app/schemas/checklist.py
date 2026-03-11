from datetime import datetime

from pydantic import BaseModel, Field


class ShiftTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    is_active: bool = True
    sort_order: int = 0


class ShiftTypePublic(BaseModel):
    id: int
    name: str
    is_active: bool
    sort_order: int


class ChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    requires_photo: bool = False
    sort_order: int = 0


class ChecklistItemPublic(BaseModel):
    id: int
    title: str
    requires_photo: bool
    sort_order: int


class ChecklistCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    shift_type_id: int | None = None
    restaurant_id: str | None = None
    job_title_id: str | None = None
    is_active: bool = True
    sort_order: int = 0
    items: list[ChecklistItemCreate] = Field(default_factory=list)


class ChecklistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    shift_type_id: int | None = None
    restaurant_id: str | None = None
    job_title_id: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    items: list[ChecklistItemCreate] | None = None


class ChecklistAdminPublic(BaseModel):
    id: int
    title: str
    shift_type_id: int | None
    shift_type_name: str | None
    restaurant_id: str | None
    restaurant_name: str | None
    job_title_id: str | None
    job_title_name: str | None
    is_active: bool
    sort_order: int
    items_count: int
    created_at: datetime


class ChecklistAdminDetailPublic(ChecklistAdminPublic):
    items: list[ChecklistItemPublic]


class ChecklistLearnerPublic(BaseModel):
    id: int
    title: str
    shift_type_name: str | None
    items: list[ChecklistItemPublic]


class ChecklistItemCompletionSubmit(BaseModel):
    checklist_item_id: int
    photo_path: str | None = None


class ChecklistCompletionSubmit(BaseModel):
    item_completions: list[ChecklistItemCompletionSubmit] = Field(default_factory=list)


class ChecklistCompletionPublic(BaseModel):
    id: int
    checklist_id: int
    checklist_title: str
    user_id: str
    user_name: str
    completed_at: datetime
    items_count: int


class ChecklistItemCompletionPublic(BaseModel):
    checklist_item_id: int
    checklist_item_title: str
    requires_photo: bool
    photo_path: str | None
    photo_url: str | None


class ChecklistCompletionDetailPublic(BaseModel):
    id: int
    checklist_id: int
    checklist_title: str
    shift_type_name: str | None
    user_id: str
    user_name: str
    user_email: str
    user_restaurant: str | None
    user_job_title: str | None
    completed_at: datetime
    item_completions: list[ChecklistItemCompletionPublic]
