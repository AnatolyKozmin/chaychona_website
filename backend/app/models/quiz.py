import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuestionType(str, enum.Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class QuizTest(Base):
    __tablename__ = "quiz_tests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_code: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    restaurant_id: Mapped[UUID] = mapped_column(ForeignKey("restaurant_catalog.id"), nullable=False, index=True)
    job_title_id: Mapped[UUID] = mapped_column(ForeignKey("job_title_catalog.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class QuizTestAssignment(Base):
    """Кому назначен тест: одна строка на пару (ресторан, роль).

    Один тест можно назначить на несколько ресторанов и ролей.
    Для обратной совместимости «первая» пара дублируется в
    QuizTest.restaurant_id / QuizTest.job_title_id.
    """

    __tablename__ = "quiz_test_assignments"
    __table_args__ = (
        UniqueConstraint("test_id", "restaurant_id", "job_title_id", name="uq_quiz_test_assignment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("quiz_tests.id"), nullable=False, index=True)
    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=False, index=True
    )
    job_title_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_title_catalog.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("quiz_tests.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type_enum"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("quiz_tests.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False)
    incorrect_answers: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False, index=True)
    # Вопрос может быть удалён при обновлении теста — история попытки сохраняется
    # за счёт дублированных текстов (question_text, *_options_text).
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    selected_option_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selected_options_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    correct_option_ids: Mapped[str] = mapped_column(Text, nullable=False, default="")
    correct_options_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
