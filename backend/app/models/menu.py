from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MenuBranch(Base):
    __tablename__ = "menu_branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_category_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=True, index=True
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("menu_branches.id"), nullable=True, index=True)
    menu_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MenuDish(Base):
    __tablename__ = "menu_dishes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_dish_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    source_dish_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_rubles: Mapped[str | None] = mapped_column(String(32), nullable=True)
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=True, index=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("menu_categories.id"), nullable=True, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    photo_dish_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_dish_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    photo_ingredients_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_ingredients_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    video_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
