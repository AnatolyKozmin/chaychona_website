"""Тесты массовой/одиночной постановки видео для существующих блюд.

`_dish_has_media` — чистая функция, тестируется без БД. Эндпоинты требуют
Postgres (UUID-модели) → фикстуры client/auth_headers сами скипают без БД.
"""
from pathlib import Path

from sqlalchemy import select

import app.services.video_worker as vw
from app.api.v1.menu import _dish_has_media, _video_source_media, update_dish_admin
from app.models.menu import MenuDish, MenuDishVideoJob
from app.schemas.menu import MenuDishCreate

IMG = ("ing.jpg", b"\xff\xd8\xff\xe0-fake", "image/jpeg")
MP3 = ("voice.mp3", b"ID3-fake", "audio/mpeg")


# ---- unit: _dish_has_media (без БД) ----

def _dish(**kwargs):
    dish = MenuDish(name="x")
    for key, value in kwargs.items():
        setattr(dish, key, value)
    return dish


def test_has_media_ingredients_plus_audio():
    assert _dish_has_media(_dish(photo_ingredients_path="uploads/i.jpg", audio_path="uploads/a.mp3"))


def test_has_media_dish_photo_fallback():
    assert _dish_has_media(_dish(photo_dish_path="uploads/d.jpg", audio_path="uploads/a.mp3"))


def test_has_media_false_without_audio():
    assert not _dish_has_media(_dish(photo_ingredients_path="uploads/i.jpg"))


def test_has_media_false_without_photo():
    assert not _dish_has_media(_dish(audio_path="uploads/a.mp3"))


def test_video_source_prefers_ingredients_photo():
    dish = _dish(
        photo_ingredients_path="uploads/i.jpg",
        photo_dish_path="uploads/d.jpg",
        audio_path="uploads/a.mp3",
    )
    assert _video_source_media(dish) == ("uploads/i.jpg", "uploads/a.mp3")


def test_video_source_changes_when_audio_replaced():
    before = _video_source_media(_dish(photo_ingredients_path="uploads/i.jpg", audio_path="uploads/a1.mp3"))
    after = _video_source_media(_dish(photo_ingredients_path="uploads/i.jpg", audio_path="uploads/a2.mp3"))
    assert before != after


# ---- unit: решение о пересборке видео в update_dish_admin (без БД) ----


class FakeSession:
    """Мини-Session для прямого вызова update_dish_admin: без Postgres.

    `scalar` отдаёт id уже стоящего в очереди pending-задания (или None),
    `added` копит созданные задания.
    """

    def __init__(self, dish, pending_job_id=None):
        self._dish = dish
        self._pending_job_id = pending_job_id
        self.added = []

    def get(self, model, pk):
        return self._dish if model is MenuDish else None

    def scalar(self, _stmt):
        return self._pending_job_id

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


def _edit(dish, pending_job_id=None, **fields):
    """Прогнать блюдо через реальный эндпоинт правки, вернуть (ответ, сессия)."""
    data = {
        "name": dish.name,
        "photo_dish_path": dish.photo_dish_path,
        "photo_ingredients_path": dish.photo_ingredients_path,
        "audio_path": dish.audio_path,
        "video_path": dish.video_path,
    }
    data.update(fields)  # правка приходит поверх текущего состояния блюда
    payload = MenuDishCreate(**data)
    db = FakeSession(dish, pending_job_id=pending_job_id)
    return update_dish_admin(dish_id=dish.id, payload=payload, _=None, db=db), db


def _dish_with_video(**overrides):
    dish = _dish(
        photo_ingredients_path="uploads/i.jpg",
        audio_path="uploads/old-voice.mp3",
        video_path="uploads/old.mp4",
        **overrides,
    )
    dish.id = 42
    dish.price = 0
    return dish


def test_edit_new_audio_queues_rebuild():
    result, db = _edit(_dish_with_video(), audio_path="uploads/new-voice.mp3")
    assert result.video_job_queued is True
    assert len(db.added) == 1 and db.added[0].status == "pending"


def test_edit_new_photo_queues_rebuild():
    result, db = _edit(_dish_with_video(), photo_ingredients_path="uploads/new-i.jpg")
    assert result.video_job_queued is True
    assert len(db.added) == 1


def test_edit_text_only_does_not_queue():
    result, db = _edit(_dish_with_video(), description="просто поправили описание")
    assert result.video_job_queued is False
    assert db.added == []


def test_edit_manual_video_wins_over_rebuild():
    result, db = _edit(
        _dish_with_video(),
        audio_path="uploads/new-voice.mp3",
        video_path="uploads/hand-made.mp4",
    )
    assert result.video_job_queued is False
    assert db.added == []


def test_edit_without_photo_does_not_queue():
    dish = _dish_with_video()
    dish.photo_ingredients_path = None
    dish.photo_dish_path = None
    result, db = _edit(dish, audio_path="uploads/new-voice.mp3")
    assert result.video_job_queued is False
    assert db.added == []


def test_edit_skips_duplicate_when_pending_job_exists():
    # pending-задание ещё не читало блюдо — оно само склеит новую озвучку
    result, db = _edit(_dish_with_video(), pending_job_id=7, audio_path="uploads/new-voice.mp3")
    assert result.video_job_queued is False
    assert db.added == []


def test_edit_queues_when_no_pending_job():
    # Нет pending — задание создаётся. Что под это подпадает и уже висящий
    # `processing` (он мог прочитать старое аудио), проверяет интеграционный
    # test_processing_job_does_not_block_requeue: там реальный SQL-фильтр.
    result, db = _edit(_dish_with_video(), pending_job_id=None, audio_path="uploads/new-voice.mp3")
    assert result.video_job_queued is True
    assert len(db.added) == 1


# ---- integration: эндпоинты (требуют БД) ----

def _create_dish_with_media(client, auth_headers, key):
    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={"name": f"Видео-бэкфилл {key}", "source_dish_key": key, "generate_video": "false"},
        files={"photo_ingredients": IMG, "audio": MP3},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["dish"]["id"]


def test_bulk_generate_videos_enqueues_and_dedups(client, auth_headers):
    dish_id = _create_dish_with_media(client, auth_headers, "pytest-bulk-vid")
    try:
        first = client.post(
            "/api/v1/menu/admin/dishes/generate-videos",
            headers=auth_headers,
            json={"dish_ids": [dish_id]},
        )
        assert first.status_code == 200, first.text
        assert first.json()["enqueued"] == 1

        # повторный вызов не плодит дубли — задание ещё активно (воркер не запущен)
        second = client.post(
            "/api/v1/menu/admin/dishes/generate-videos",
            headers=auth_headers,
            json={"dish_ids": [dish_id]},
        )
        assert second.json()["enqueued"] == 0
        assert second.json()["skipped_already_queued"] == 1
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_single_generate_video_and_dedup(client, auth_headers):
    dish_id = _create_dish_with_media(client, auth_headers, "pytest-single-vid")
    try:
        first = client.post(
            f"/api/v1/menu/admin/dishes/{dish_id}/generate-video", headers=auth_headers
        )
        assert first.status_code == 201, first.text
        assert first.json()["status"] == "pending"
        job_id = first.json()["id"]

        # без force возвращается то же активное задание
        second = client.post(
            f"/api/v1/menu/admin/dishes/{dish_id}/generate-video", headers=auth_headers
        )
        assert second.json()["id"] == job_id
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def _put_dish(client, auth_headers, dish, **overrides):
    payload = {
        "name": dish["name"],
        "ingredients": dish["ingredients"],
        "description": dish["description"],
        "price": dish["price"],
        "price_rubles": dish["price_rubles"],
        "restaurant_id": dish["restaurant_id"],
        "category_id": dish["category_id"],
        "is_available": dish["is_available"],
        "is_active": dish["is_active"],
        "photo_dish_path": dish["photo_dish_path"],
        "photo_ingredients_path": dish["photo_ingredients_path"],
        "audio_path": dish["audio_path"],
        "video_path": dish["video_path"],
    }
    payload.update(overrides)
    resp = client.put(f"/api/v1/menu/admin/dishes/{dish['id']}", headers=auth_headers, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_edit_dish_new_audio_requeues_video(client, auth_headers):
    """Замена озвучки при редактировании должна пересоздавать видео."""
    dish_id = _create_dish_with_media(client, auth_headers, "pytest-edit-audio-vid")
    try:
        dish = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        dish = next(item for item in dish if item["id"] == dish_id)
        dish = _put_dish(client, auth_headers, dish, video_path="uploads/old.mp4")
        assert dish["video_job_queued"] is False  # медиа не менялось

        updated = _put_dish(client, auth_headers, dish, audio_path="uploads/new-voice.mp3")
        assert updated["video_job_queued"] is True
        assert updated["audio_path"] == "uploads/new-voice.mp3"

        # правка только текста не плодит новых заданий
        again = _put_dish(client, auth_headers, updated, description="другое описание")
        assert again["video_job_queued"] is False
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_edit_dish_manual_video_not_overwritten(client, auth_headers):
    """Если вместе с аудио вручную задали видео — пересборку не ставим."""
    dish_id = _create_dish_with_media(client, auth_headers, "pytest-edit-manual-vid")
    try:
        dishes = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        dish = next(item for item in dishes if item["id"] == dish_id)
        updated = _put_dish(
            client,
            auth_headers,
            dish,
            audio_path="uploads/new-voice.mp3",
            video_path="uploads/hand-made.mp4",
        )
        assert updated["video_job_queued"] is False
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def _pending_job_id(db, dish_id):
    return db.scalar(
        select(MenuDishVideoJob.id).where(
            MenuDishVideoJob.dish_id == dish_id, MenuDishVideoJob.status == "pending"
        )
    )


def test_new_audio_rebuilds_video_end_to_end(client, auth_headers, monkeypatch, tmp_path):
    """Сквозь весь путь: сменили озвучку → воркер склеил видео ИЗ НОВОГО аудио."""
    from app.db.session import SessionLocal

    dish_id = _create_dish_with_media(client, auth_headers, "pytest-e2e-revoice")
    try:
        dishes = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        dish = next(item for item in dishes if item["id"] == dish_id)
        # исходное состояние: у блюда уже есть ранее сгенерированное видео
        dish = _put_dish(client, auth_headers, dish, video_path="uploads/old-voice.mp4")

        updated = _put_dish(client, auth_headers, dish, audio_path="uploads/new-voice.mp3")
        assert updated["video_job_queued"] is True
        assert updated["video_path"] == "uploads/old-voice.mp4"  # старое ещё на месте

        seen = {}
        monkeypatch.setattr(vw, "UPLOAD_DIR", tmp_path)
        monkeypatch.setattr(vw, "resolve_media_abspath", lambda p: Path(p) if p else None)
        monkeypatch.setattr(
            vw,
            "compose_still_video",
            lambda img, aud, out: seen.update(image=str(img), audio=str(aud)),
        )

        db = SessionLocal()
        try:
            job_id = _pending_job_id(db, dish_id)
            assert job_id is not None, "задание на пересборку не поставлено"
            vw._process_job(db, job_id)
        finally:
            db.close()

        assert seen["audio"].endswith("new-voice.mp3"), "воркер взял старую озвучку"
        after = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        after = next(item for item in after if item["id"] == dish_id)
        assert after["video_path"] != "uploads/old-voice.mp4", "видео не пересоздалось"
        assert after["video_path"].endswith(".mp4")
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_processing_job_does_not_block_requeue(client, auth_headers):
    """Задание в processing могло прочитать старое аудио → нужно новое задание."""
    from app.db.session import SessionLocal

    dish_id = _create_dish_with_media(client, auth_headers, "pytest-requeue-processing")
    try:
        dishes = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        dish = next(item for item in dishes if item["id"] == dish_id)
        first = _put_dish(client, auth_headers, dish, audio_path="uploads/voice-1.mp3")
        assert first["video_job_queued"] is True

        db = SessionLocal()
        try:
            job_id = _pending_job_id(db, dish_id)
            job = db.get(MenuDishVideoJob, job_id)
            job.status = "processing"  # воркер уже забрал задание со старым аудио
            db.commit()
        finally:
            db.close()

        second = _put_dish(client, auth_headers, first, audio_path="uploads/voice-2.mp3")
        assert second["video_job_queued"] is True, "правка во время processing потерялась бы"

        db = SessionLocal()
        try:
            assert _pending_job_id(db, dish_id) is not None
        finally:
            db.close()
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_pending_job_is_not_duplicated(client, auth_headers):
    """Пока задание pending, оно само подхватит свежие файлы — дублей не плодим."""
    from app.db.session import SessionLocal

    dish_id = _create_dish_with_media(client, auth_headers, "pytest-requeue-pending")
    try:
        dishes = client.get("/api/v1/menu/admin/dishes", headers=auth_headers).json()
        dish = next(item for item in dishes if item["id"] == dish_id)
        first = _put_dish(client, auth_headers, dish, audio_path="uploads/voice-1.mp3")
        assert first["video_job_queued"] is True

        second = _put_dish(client, auth_headers, first, audio_path="uploads/voice-2.mp3")
        assert second["video_job_queued"] is False

        db = SessionLocal()
        try:
            count = len(
                db.scalars(
                    select(MenuDishVideoJob.id).where(MenuDishVideoJob.dish_id == dish_id)
                ).all()
            )
            assert count == 1
        finally:
            db.close()
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_single_generate_video_missing_dish_404(client, auth_headers):
    resp = client.post(
        "/api/v1/menu/admin/dishes/999999999/generate-video", headers=auth_headers
    )
    assert resp.status_code == 404


def test_single_generate_video_no_media_400(client, auth_headers):
    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={"name": "Без медиа для видео", "source_dish_key": "pytest-nomedia-vid", "generate_video": "false"},
    )
    assert resp.status_code == 201, resp.text
    dish_id = resp.json()["dish"]["id"]
    try:
        bad = client.post(
            f"/api/v1/menu/admin/dishes/{dish_id}/generate-video", headers=auth_headers
        )
        assert bad.status_code == 400
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)
