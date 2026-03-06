from datetime import datetime

from pydantic import BaseModel, Field

from app.models.quiz import QuestionType


class QuizOptionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    is_correct: bool = False


class QuizQuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    question_type: QuestionType
    options: list[QuizOptionCreate] = Field(min_length=2)


class QuizTestCreate(BaseModel):
    external_code: str | None = Field(default=None, min_length=1, max_length=120)
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    restaurant_id: str
    job_title_id: str
    questions: list[QuizQuestionCreate] = Field(min_length=1)


class QuizOptionPublic(BaseModel):
    id: int
    text: str
    is_correct: bool
    sort_order: int

    class Config:
        from_attributes = True


class QuizQuestionPublic(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    sort_order: int
    options: list[QuizOptionPublic]


class QuizTestPublic(BaseModel):
    id: int
    external_code: str | None
    title: str
    description: str | None
    restaurant_id: str
    restaurant_name: str
    job_title_id: str
    job_title_name: str
    created_at: datetime
    questions: list[QuizQuestionPublic]


class QuizOptionTakePublic(BaseModel):
    id: int
    text: str
    sort_order: int


class QuizQuestionTakePublic(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    sort_order: int
    options: list[QuizOptionTakePublic]


class QuizTestTakePublic(BaseModel):
    id: int
    title: str
    description: str | None
    restaurant_name: str
    job_title_name: str
    questions: list[QuizQuestionTakePublic]


class QuizAnswerSubmitItem(BaseModel):
    question_id: int
    option_ids: list[int] = Field(default_factory=list)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswerSubmitItem] = Field(default_factory=list)
    started_at: datetime | None = None


class QuizQuestionResultPublic(BaseModel):
    question_id: int
    question_text: str
    correct_options: list[str]
    selected_options: list[str]
    is_correct: bool


class QuizSubmitResultPublic(BaseModel):
    attempt_id: int
    started_at: datetime | None
    finished_at: datetime
    duration_seconds: int | None
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    results: list[QuizQuestionResultPublic]


class QuizAttemptPublic(BaseModel):
    id: int
    test_id: int
    test_title: str
    user_id: str
    user_name: str
    user_email: str
    user_restaurant: str | None
    user_job_title: str | None
    started_at: datetime | None
    finished_at: datetime
    duration_seconds: int | None
    total_questions: int
    correct_answers: int
    incorrect_answers: int


class QuizQuestionAnalyticsItem(BaseModel):
    question_id: int
    test_id: int
    test_title: str
    question_text: str
    total_attempts: int
    wrong_attempts: int
    correct_attempts: int
    wrong_rate: float


class QuizUserAnalyticsItem(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    attempts_count: int
    total_answers: int
    wrong_answers: int
    wrong_rate: float
    avg_duration_seconds: float | None


class QuizAnalyticsSummary(BaseModel):
    total_attempts: int
    unique_users: int
    avg_score_percent: float
    avg_duration_seconds: float | None


class QuizAnalyticsResponse(BaseModel):
    summary: QuizAnalyticsSummary
    recent_attempts: list[QuizAttemptPublic]
    attempts: list[QuizAttemptPublic]
    question_analytics: list[QuizQuestionAnalyticsItem]
    user_analytics: list[QuizUserAnalyticsItem]
