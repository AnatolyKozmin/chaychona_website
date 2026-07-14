"""Фоновый воркер очереди генерации видео блюд.

Один демон-поток внутри процесса backend забирает по одному `pending`-задание
из `menu_dish_video_jobs`, склеивает видео (фото ингредиентов + озвучка) и
проставляет `menu_dishes.video_path`. Заявка захватывается через
`FOR UPDATE SKIP LOCKED`, поэтому безопасно даже при нескольких воркерах.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.menu import MenuDish, MenuDishVideoJob
from app.services.media import UPLOAD_DIR, resolve_media_abspath
from app.services.video import VideoCompositionError, compose_still_video

logger = logging.getLogger(__name__)

_worker_started = False
_stop_event = threading.Event()


def _claim_next_job(db: Session) -> int | None:
    """Атомарно перевести самый старый pending в processing и вернуть его id."""
    row = db.execute(
        text(
            "UPDATE menu_dish_video_jobs "
            "SET status='processing', started_at=NOW(), updated_at=NOW(), attempts=attempts+1 "
            "WHERE id = ("
            "  SELECT id FROM menu_dish_video_jobs WHERE status='pending' "
            "  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1"
            ") "
            "RETURNING id"
        )
    ).fetchone()
    db.commit()
    return int(row[0]) if row else None


def _fail(db: Session, job: MenuDishVideoJob, message: str) -> None:
    job.status = "error"
    job.error = message[:5000]
    job.finished_at = datetime.utcnow()
    db.commit()
    logger.warning("Видео-задание %s: ошибка — %s", job.id, message)


def _process_job(db: Session, job_id: int) -> None:
    job = db.get(MenuDishVideoJob, job_id)
    if job is None:
        return
    dish = db.get(MenuDish, job.dish_id)
    if dish is None:
        _fail(db, job, "Блюдо не найдено")
        return

    photo_rel = dish.photo_ingredients_path or dish.photo_dish_path
    image_path = resolve_media_abspath(photo_rel)
    audio_path = resolve_media_abspath(dish.audio_path)
    if image_path is None:
        _fail(db, job, "Нет фото для видео (photo_ingredients / photo_dish)")
        return
    if audio_path is None:
        _fail(db, job, "Нет аудио для видео")
        return

    out_name = f"{uuid.uuid4().hex}.mp4"
    out_path = UPLOAD_DIR / out_name
    try:
        compose_still_video(image_path, audio_path, out_path)
    except VideoCompositionError as exc:
        _fail(db, job, str(exc))
        return

    dish.video_path = f"uploads/{out_name}"
    job.status = "done"
    job.error = None
    job.finished_at = datetime.utcnow()
    db.commit()
    logger.info("Видео-задание %s: готово, блюдо %s → %s", job.id, dish.id, dish.video_path)


def _run_loop() -> None:
    settings = get_settings()
    poll = settings.video_worker_poll_seconds
    logger.info("Видео-воркер запущен (poll=%ss)", poll)
    while not _stop_event.is_set():
        job_id: int | None = None
        db = SessionLocal()
        try:
            job_id = _claim_next_job(db)
            if job_id is not None:
                _process_job(db, job_id)
        except Exception:  # noqa: BLE001
            logger.exception("Сбой в цикле видео-воркера")
            db.rollback()
        finally:
            db.close()
        if job_id is None:
            _stop_event.wait(poll)


def start_video_worker() -> None:
    """Запустить воркер один раз (idempotent). Управляется VIDEO_WORKER_ENABLED."""
    global _worker_started
    settings = get_settings()
    if not settings.video_worker_enabled or _worker_started:
        return
    _worker_started = True
    _stop_event.clear()
    thread = threading.Thread(target=_run_loop, name="video-worker", daemon=True)
    thread.start()


def stop_video_worker() -> None:
    _stop_event.set()
