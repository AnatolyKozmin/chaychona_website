from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShiftType(Base):
    """Тип смены: открытие, закрытие и т.д."""

    __tablename__ = "shift_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Checklist(Base):
    """Шаблон чек-листа (например: «Чек-лист закрытия смены официанта»)."""

    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    shift_type_id: Mapped[int | None] = mapped_column(ForeignKey("shift_types.id"), nullable=True, index=True)
    restaurant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=True, index=True)
    job_title_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("job_title_catalog.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChecklistItem(Base):
    """Пункт чек-листа (что нужно проверить)."""

    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    requires_photo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ChecklistCompletion(Base):
    """Прохождение чек-листа пользователем."""

    __tablename__ = "checklist_completions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChecklistItemCompletion(Base):
    """Отметка по пункту чек-листа (с опциональным фото)."""

    __tablename__ = "checklist_item_completions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    completion_id: Mapped[int] = mapped_column(ForeignKey("checklist_completions.id"), nullable=False, index=True)
    checklist_item_id: Mapped[int] = mapped_column(ForeignKey("checklist_items.id"), nullable=False, index=True)
    photo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
