"""Тесты массовой/одиночной постановки видео для существующих блюд.

`_dish_has_media` — чистая функция, тестируется без БД. Эндпоинты требуют
Postgres (UUID-модели) → фикстуры client/auth_headers сами скипают без БД.
"""
from app.api.v1.menu import _dish_has_media
from app.models.menu import MenuDish

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
