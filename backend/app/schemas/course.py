from datetime import datetime

from pydantic import BaseModel, Field


class CourseBlockCreate(BaseModel):
    heading: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=20000)
    image_path: str | None = Field(default=None, max_length=1024)
    sort_order: int = 0
    subblocks: list["CourseSubBlockCreate"] = Field(default_factory=list)


class CourseSubBlockCreate(BaseModel):
    heading: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=20000)
    image_path: str | None = Field(default=None, max_length=1024)
    sort_order: int = 0


class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    restaurant_id: str | None = None
    job_title_id: str | None = None
    linked_test_id: int | None = None
    is_active: bool = True
    blocks: list[CourseBlockCreate] = Field(default_factory=list, min_length=1)


class CourseBlockPublic(BaseModel):
    id: int
    heading: str | None
    text: str
    image_path: str | None
    image_url: str | None
    sort_order: int
    subblocks: list["CourseSubBlockPublic"]


class CourseSubBlockPublic(BaseModel):
    id: int
    heading: str | None
    text: str
    image_path: str | None
    image_url: str | None
    sort_order: int


class CourseLinkedTestPublic(BaseModel):
    id: int
    title: str


class CoursePublic(BaseModel):
    id: int
    title: str
    description: str | None
    restaurant_id: str | None
    restaurant_name: str | None
    job_title_id: str | None
    job_title_name: str | None
    linked_test: CourseLinkedTestPublic | None
    is_active: bool
    created_at: datetime
    blocks: list[CourseBlockPublic]


class CourseLearnerBlockProgressPublic(BaseModel):
    block_id: int
    title: str
    sort_order: int
    is_completed: bool
    completed_at: datetime | None
    is_unlocked: bool


class CourseLearnerLinkedTestStatsPublic(BaseModel):
    test_id: int
    test_title: str
    attempts_count: int
    best_score_percent: float | None
    last_score_percent: float | None
    last_attempt_at: datetime | None


class CourseLearnerOverviewPublic(BaseModel):
    id: int
    title: str
    description: str | None
    restaurant_name: str | None
    job_title_name: str | None
    total_blocks: int
    completed_blocks: int
    progress_percent: float
    is_completed: bool
    blocks: list[CourseLearnerBlockProgressPublic]
    linked_test_stats: CourseLearnerLinkedTestStatsPublic | None


class CourseLearnerStudyPublic(BaseModel):
    course: CoursePublic
    blocks_progress: list[CourseLearnerBlockProgressPublic]
    progress_percent: float
    linked_test_stats: CourseLearnerLinkedTestStatsPublic | None


CourseBlockCreate.model_rebuild()
CourseBlockPublic.model_rebuild()
