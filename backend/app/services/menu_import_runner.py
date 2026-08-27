"""Заливка разобранного реестра в базу и постановка генерации в очередь.

Текст и файлы из архива пишем синхронно прямо в запросе — это быстро, и
заказчик сразу видит, что заехало. Всё, что требует внешних провайдеров
(картинка ингредиентов, озвучка) и ffmpeg (видео), уезжает в очередь
`menu_dish_video_jobs` и считается фоном.

Строка, которая упала, не роняет весь залив: пишем ей ошибку в отчёт и идём
дальше. Импорт на 117 позиций не должен разваливаться из-за одной битой ячейки.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import PurePosixPath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.menu import (
    MenuCategory,
    MenuDish,
    MenuDishMediaJob,
    MenuImportRow,
    MenuImportSession,
)
from app.services.generation import build_ingredients_prompt
from app.services.media import AUDIO_EXTS, IMAGE_EXTS, save_upload_bytes
from app.services.menu_import import ParsedRegistry, ParsedRow

logger = logging.getLogger(__name__)


def _normalized(value: str | None) -> str:
    return " ".join((value or "").split()).lower()


def _clip(value: str | None, limit: int = 255) -> str | None:
    """Подрезать текст под ширину колонки; пустое — это None."""
    text = (value or "").strip()
    return text[:limit] if text else None


def _store(content: bytes | None, source_path: str | None, allowed: set[str]) -> str | None:
    """Сохранить медиа из архива, вернуть относительный путь (или None)."""
    if not content or not source_path:
        return None
    suffix = PurePosixPath(source_path).suffix.lower()
    if suffix not in allowed:
        return None
    return save_upload_bytes(content, suffix)


def _resolve_category(
    db: Session,
    cache: dict[str, int],
    name: str | None,
    restaurant_id: uuid.UUID | None,
) -> int | None:
    """Найти id категории ресторана по имени или создать её.

    Кэшируем именно id, а не ORM-объект: после построчного коммита объекты
    протухают, и каждое обращение к `.name` стоило бы отдельного запроса.
    """
    key = _normalized(name)
    if not key:
        return None
    cached = cache.get(key)
    if cached is not None:
        return cached
    category = MenuCategory(
        name=" ".join(name.split()),
        restaurant_id=restaurant_id,
        is_active=True,
    )
    db.add(category)
    db.flush()
    cache[key] = category.id
    return category.id


def _find_dish(
    db: Session,
    row: ParsedRow,
    restaurant_id: uuid.UUID | None,
) -> MenuDish | None:
    """Найти уже существующее блюдо по имени в пределах ресторана.

    Именно в пределах ресторана: одноимённый «Плов» в другой точке — это
    другое блюдо со своим фото, перетирать его нельзя.
    """
    query = select(MenuDish).where(func.lower(MenuDish.name) == row.name.strip().lower())
    if restaurant_id:
        query = query.where(MenuDish.restaurant_id == restaurant_id)
    else:
        query = query.where(MenuDish.restaurant_id.is_(None))
    return db.scalar(query.order_by(MenuDish.id.asc()))


def run_import(
    db: Session,
    registry: ParsedRegistry,
    *,
    restaurant_id: uuid.UUID | None,
    generate_image: bool = True,
    generate_audio: bool = True,
    generate_video: bool = True,
    created_by_id: uuid.UUID | None = None,
) -> MenuImportSession:
    """Залить реестр целиком и вернуть сессию импорта с отчётом."""
    session = MenuImportSession(
        restaurant_id=restaurant_id,
        file_name=registry.source_name[:255],
        status="running",
        total_rows=len(registry.rows),
        generate_image=generate_image,
        generate_audio=generate_audio,
        generate_video=generate_video,
        created_by_id=created_by_id,
    )
    db.add(session)
    # Именно commit, а не flush: ниже упавшая строка делает rollback, и
    # незакоммиченная сессия исчезла бы вместе с ней — писать отчёт стало бы некуда.
    db.commit()
    session_id = session.id

    category_query = select(MenuCategory.id, MenuCategory.name)
    if restaurant_id:
        category_query = category_query.where(MenuCategory.restaurant_id == restaurant_id)
    else:
        category_query = category_query.where(MenuCategory.restaurant_id.is_(None))
    category_cache = {_normalized(name): cid for cid, name in db.execute(category_query).all()}

    created = updated = failed = 0

    for row in registry.rows:
        try:
            dish = _find_dish(db, row, restaurant_id)
            is_new = dish is None
            if dish is None:
                dish = MenuDish(name=row.name.strip())
                db.add(dish)

            dish.name = row.name.strip()
            dish.restaurant_id = restaurant_id
            if row.ingredients:
                dish.ingredients = row.ingredients
            if row.description:
                dish.description = row.description
            if row.price_rubles:
                dish.price_rubles = row.price_rubles

            category_id = _resolve_category(db, category_cache, row.category, restaurant_id)
            if category_id is not None:
                dish.category_id = category_id

            # Медиа из архива перекрывает то, что лежало раньше: раз заказчик
            # положил файл в архив, он хочет именно его.
            photo_dish = _store(registry.read_media(row.photo_dish), row.photo_dish, IMAGE_EXTS)
            if photo_dish:
                dish.photo_dish_path = photo_dish
            photo_ingredients = _store(
                registry.read_media(row.photo_ingredients), row.photo_ingredients, IMAGE_EXTS
            )
            if photo_ingredients:
                dish.photo_ingredients_path = photo_ingredients
            audio = _store(registry.read_media(row.audio), row.audio, AUDIO_EXTS)
            if audio:
                dish.audio_path = audio

            db.flush()

            _enqueue_generation(
                db,
                dish=dish,
                row=row,
                session_id=session_id,
                generate_image=generate_image,
                generate_audio=generate_audio,
                generate_video=generate_video,
            )

            db.add(
                MenuImportRow(
                    session_id=session_id,
                    row_number=row.row_number,
                    dish_name=row.name[:255],
                    category_name=_clip(row.category),
                    dish_id=dish.id,
                    status="created" if is_new else "updated",
                )
            )
            # Коммитим каждую строку отдельно: иначе одна битая ячейка в конце
            # реестра откатила бы все сотню уже заехавших блюд.
            db.commit()
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001 — одна строка не должна ронять залив
            logger.exception("Импорт: строка %s (%s) упала", row.row_number, row.name)
            db.rollback()
            db.add(
                MenuImportRow(
                    session_id=session_id,
                    row_number=row.row_number,
                    dish_name=row.name[:255],
                    category_name=_clip(row.category),
                    status="error",
                    error=str(exc)[:2000],
                )
            )
            db.commit()
            # rollback снёс и категории, созданные в этой транзакции, — кэш
            # пересобираем, иначе следующие строки сошлются на несуществующий id.
            category_cache = {
                _normalized(name): cid for cid, name in db.execute(category_query).all()
            }
            failed += 1

    session = db.get(MenuImportSession, session_id)
    session.created_dishes = created
    session.updated_dishes = updated
    session.failed_rows = failed
    # Если генерировать нечего — залив уже закончен, ждать очередь незачем.
    pending = db.scalar(
        select(func.count(MenuDishMediaJob.id)).where(
            MenuDishMediaJob.session_id == session_id,
            MenuDishMediaJob.status.in_(("blocked", "pending", "processing")),
        )
    )
    if not pending:
        session.status = "done"
        session.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def _enqueue_generation(
    db: Session,
    *,
    dish: MenuDish,
    row: ParsedRow,
    session_id: int,
    generate_image: bool,
    generate_audio: bool,
    generate_video: bool,
) -> None:
    """Поставить блюду недостающие стадии генерации.

    Генерим только то, чего нет: если картинка ингредиентов или озвучка
    приехали файлом в архиве, платить провайдеру за них не за что.
    """
    need_image = generate_image and not dish.photo_ingredients_path
    need_audio = generate_audio and not dish.audio_path

    if need_image:
        db.add(
            MenuDishMediaJob(
                dish_id=dish.id,
                kind="image",
                prompt=build_ingredients_prompt(dish.name, row.ingredients),
                session_id=session_id,
                status="pending",
            )
        )
    if need_audio:
        voice_text = row.description or row.ingredients
        if voice_text:
            db.add(
                MenuDishMediaJob(
                    dish_id=dish.id,
                    kind="audio",
                    prompt=voice_text,
                    session_id=session_id,
                    status="pending",
                )
            )
        else:
            need_audio = False

    if not generate_video:
        return

    will_have_image = bool(dish.photo_ingredients_path or dish.photo_dish_path) or need_image
    will_have_audio = bool(dish.audio_path) or need_audio
    if not (will_have_image and will_have_audio):
        return  # склеивать нечего и нечем — молча не ставим

    # Пока не доехали исходники, видео держим в `blocked`: воркер снимет
    # блокировку сам, когда у блюда появятся оба файла.
    ready_now = bool((dish.photo_ingredients_path or dish.photo_dish_path) and dish.audio_path)
    db.add(
        MenuDishMediaJob(
            dish_id=dish.id,
            kind="video",
            session_id=session_id,
            status="pending" if ready_now else "blocked",
        )
    )
