from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Первичная пара (ресторан, роль) — для обратной совместимости; NULL = «доступно всем».
    # Все пары назначения хранятся в course_assignments (см. CourseAssignment).
    restaurant_id: Mapped[UUID | None] = mapped_column(ForeignKey("restaurant_catalog.id"), nullable=True, index=True)
    job_title_id: Mapped[UUID | None] = mapped_column(ForeignKey("job_title_catalog.id"), nullable=True, index=True)
    linked_test_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_tests.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CourseAssignment(Base):
    """Кому назначен стандарт: одна строка на пару (ресторан, роль).

    Пустой список назначений = стандарт доступен всем (в отличие от тестов,
    где назначение обязательно). «Первая» пара дублируется в
    Course.restaurant_id / Course.job_title_id для обратной совместимости.
    """

    __tablename__ = "course_assignments"
    __table_args__ = (
        UniqueConstraint("course_id", "restaurant_id", "job_title_id", name="uq_course_assignment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=False, index=True
    )
    job_title_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_title_catalog.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CourseBlock(Base):
    __tablename__ = "course_blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CourseSubBlock(Base):
    __tablename__ = "course_subblocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("course_blocks.id"), nullable=False, index=True)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CourseBlockProgress(Base):
    __tablename__ = "course_block_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    # Блоки пересоздаются при каждом редактировании курса — прогресс по старым
    # блокам не имеет смысла и удаляется вместе с ними.
    block_id: Mapped[int] = mapped_column(
        ForeignKey("course_blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
