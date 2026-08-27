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
    # Аллергены заполняет шеф-повар вручную, через запятую («орехи, молочное»).
    # Пусто — значит не заполнено, и официанту ничего не показываем: пустое поле
    # не должно читаться как «аллергенов нет».
    allergens: Mapped[str | None] = mapped_column(String(500), nullable=True)
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


class MenuDishMediaJob(Base):
    """Очередь фоновой генерации медиа блюда.

    Три вида заданий (`kind`), которые обрабатывает `app.services.video_worker`:

    - `image` — картинка ингредиентов по промпту (Magnific);
    - `audio` — озвучка текста (ElevenLabs);
    - `video` — склейка картинки и озвучки в mp4 (ffmpeg, локально).

    Статусы: `blocked` → `pending` → `processing` → `done` | `error`.
    `blocked` — это `video`, который ждёт, пока доедут его картинка и озвучка;
    воркер снимает блокировку сам, когда у блюда появляются оба файла.

    Имя таблицы историческое (`menu_dish_video_jobs`): раньше вид был один.
    """

    __tablename__ = "menu_dish_video_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dish_id: Mapped[int] = mapped_column(
        ForeignKey("menu_dishes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="video", nullable=False, index=True)
    # Для `image` — промпт картинки, для `audio` — текст озвучки. У `video` пусто.
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_import_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# Старое имя класса: на него ссылается уже написанный код и тесты.
MenuDishVideoJob = MenuDishMediaJob


class MenuImportSession(Base):
    """Один залив реестра «Вкусной тетради» файлом через админку.

    Разбор файла и запись блюд идут синхронно в запросе (это просто вставки и
    распаковка), а генерация картинок/озвучки/видео уезжает в очередь
    `menu_dish_video_jobs` — прогресс по ней и показываем.
    """

    __tablename__ = "menu_import_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurant_catalog.id"), nullable=True, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # parsed → dry-run, ничего не записано; running → блюда созданы, идёт генерация;
    # done → очередь пуста; error → развалился сам разбор файла.
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_dishes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_dishes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    generate_image: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generate_audio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generate_video: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MenuImportRow(Base):
    """Строка реестра и что с ней стало — построчный отчёт по заливу.

    Живёт даже для упавших строк: заказчику надо видеть, что именно не заехало,
    а не только итоговый счётчик.
    """

    __tablename__ = "menu_import_rows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("menu_import_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    dish_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dish_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_dishes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # created | updated | skipped | error
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
