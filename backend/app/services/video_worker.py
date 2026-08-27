"""Фоновый воркер очереди генерации медиа блюд.

Один демон-поток внутри процесса backend забирает по одному `pending`-задание
из `menu_dish_video_jobs` и выполняет его в зависимости от вида:

- `image` — картинка ингредиентов по промпту (Magnific);
- `audio` — озвучка текста (ElevenLabs);
- `video` — склейка картинки и озвучки в mp4 (ffmpeg, локально).

Заявка захватывается через `FOR UPDATE SKIP LOCKED`, поэтому безопасно даже
при нескольких воркерах.

Видео зависит от двух предыдущих стадий, поэтому создаётся в статусе `blocked`
и ждёт: как только у блюда появляются и картинка, и озвучка, воркер переводит
его в `pending` сам. Если исходники так и не доехали (провайдер упал), видео
закрывается ошибкой, а не висит в очереди вечно.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.menu import MenuDish, MenuDishMediaJob, MenuImportSession
from app.services.generation import (
    GenerationError,
    generate_ingredients_image,
    synthesize_speech,
)
from app.services.media import UPLOAD_DIR, resolve_media_abspath, save_upload_bytes
from app.services.video import VideoCompositionError, compose_still_video

logger = logging.getLogger(__name__)

_worker_started = False
_stop_event = threading.Event()

# Статусы, при которых задание ещё в работе.
UNFINISHED_STATUSES = ("blocked", "pending", "processing")


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


def _fail(db: Session, job: MenuDishMediaJob, message: str) -> None:
    job.status = "error"
    job.error = message[:5000]
    job.finished_at = datetime.utcnow()
    db.commit()
    logger.warning("Задание %s (%s): ошибка — %s", job.id, job.kind, message)


def _finish(db: Session, job: MenuDishMediaJob) -> None:
    job.status = "done"
    job.error = None
    job.finished_at = datetime.utcnow()
    db.commit()


def _process_image_job(db: Session, job: MenuDishMediaJob, dish: MenuDish) -> None:
    prompt = (job.prompt or "").strip()
    if not prompt:
        _fail(db, job, "Нет промпта для генерации картинки")
        return
    try:
        content, ext = generate_ingredients_image(prompt)
    except GenerationError as exc:
        _fail(db, job, str(exc))
        return
    dish.photo_ingredients_path = save_upload_bytes(content, ext)
    _finish(db, job)
    logger.info("Задание %s: картинка блюда %s → %s", job.id, dish.id, dish.photo_ingredients_path)


def _process_audio_job(db: Session, job: MenuDishMediaJob, dish: MenuDish) -> None:
    voice_text = (job.prompt or "").strip()
    if not voice_text:
        _fail(db, job, "Нет текста для озвучки")
        return
    try:
        content, ext = synthesize_speech(voice_text)
    except GenerationError as exc:
        _fail(db, job, str(exc))
        return
    dish.audio_path = save_upload_bytes(content, ext)
    _finish(db, job)
    logger.info("Задание %s: озвучка блюда %s → %s", job.id, dish.id, dish.audio_path)


def _process_video_job(db: Session, job: MenuDishMediaJob, dish: MenuDish) -> None:
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
    _finish(db, job)
    logger.info("Задание %s: видео блюда %s → %s", job.id, dish.id, dish.video_path)


def _release_video_jobs(db: Session, dish_id: int) -> None:
    """Разблокировать (или закрыть) видео-задания блюда после смежной стадии.

    Видео ждёт картинку и озвучку. Если оба файла на месте — пускаем в работу.
    Если исходников всё ещё нет, но и ждать больше нечего (смежные стадии
    доработали), закрываем ошибкой, иначе задание провисит в очереди вечно.
    """
    blocked = list(
        db.scalars(
            select(MenuDishMediaJob).where(
                MenuDishMediaJob.dish_id == dish_id,
                MenuDishMediaJob.kind == "video",
                MenuDishMediaJob.status == "blocked",
            )
        ).all()
    )
    if not blocked:
        return

    dish = db.get(MenuDish, dish_id)
    if dish is None:
        for job in blocked:
            _fail(db, job, "Блюдо не найдено")
        return

    has_media = bool((dish.photo_ingredients_path or dish.photo_dish_path) and dish.audio_path)
    still_working = db.scalar(
        select(func.count(MenuDishMediaJob.id)).where(
            MenuDishMediaJob.dish_id == dish_id,
            MenuDishMediaJob.kind.in_(("image", "audio")),
            MenuDishMediaJob.status.in_(UNFINISHED_STATUSES),
        )
    )
    for job in blocked:
        if has_media:
            job.status = "pending"
            job.updated_at = datetime.utcnow()
        elif not still_working:
            job.status = "error"
            job.error = "Не дождались картинку и озвучку — смежные стадии не отработали"
            job.finished_at = datetime.utcnow()
    db.commit()


def _close_session_if_done(db: Session, session_id: int | None) -> None:
    """Закрыть сессию импорта, когда её очередь опустела."""
    if session_id is None:
        return
    session = db.get(MenuImportSession, session_id)
    if session is None or session.status not in ("running",):
        return
    unfinished = db.scalar(
        select(func.count(MenuDishMediaJob.id)).where(
            MenuDishMediaJob.session_id == session_id,
            MenuDishMediaJob.status.in_(UNFINISHED_STATUSES),
        )
    )
    if unfinished:
        return
    session.status = "done"
    session.finished_at = datetime.utcnow()
    db.commit()


def _process_job(db: Session, job_id: int) -> None:
    job = db.get(MenuDishMediaJob, job_id)
    if job is None:
        return
    dish = db.get(MenuDish, job.dish_id)
    if dish is None:
        _fail(db, job, "Блюдо не найдено")
        return

    kind = job.kind or "video"
    if kind == "image":
        _process_image_job(db, job, dish)
    elif kind == "audio":
        _process_audio_job(db, job, dish)
    elif kind == "video":
        _process_video_job(db, job, dish)
    else:
        _fail(db, job, f"Неизвестный вид задания: {kind}")
        return

    if kind in ("image", "audio"):
        _release_video_jobs(db, job.dish_id)
    _close_session_if_done(db, job.session_id)


def _run_loop() -> None:
    settings = get_settings()
    poll = settings.video_worker_poll_seconds
    logger.info("Медиа-воркер запущен (poll=%ss)", poll)
    while not _stop_event.is_set():
        job_id: int | None = None
        db = SessionLocal()
        try:
            job_id = _claim_next_job(db)
            if job_id is not None:
                _process_job(db, job_id)
        except Exception:  # noqa: BLE001
            logger.exception("Сбой в цикле медиа-воркера")
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
    thread = threading.Thread(target=_run_loop, name="media-worker", daemon=True)
    thread.start()


def stop_video_worker() -> None:
    _stop_event.set()
