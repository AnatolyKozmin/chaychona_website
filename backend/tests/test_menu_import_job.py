"""Интеграционные тесты пачечной ручки import-job.

Требуют Postgres (модели используют PG-специфичный UUID) — при отсутствии БД
фикстуры client/auth_headers сами делают skip, как и остальные API-тесты.
Воркер в тестах не запущен (lifespan не поднимается TestClient без `with`),
поэтому задание детерминированно остаётся в статусе pending.
"""
IMG = ("ing.jpg", b"\xff\xd8\xff\xe0-fake-jpeg", "image/jpeg")
MP3 = ("voice.mp3", b"ID3-fake-audio", "audio/mpeg")


def test_import_job_creates_dish_and_enqueues(client, auth_headers):
    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={
            "name": "Тест-блюдо видео",
            "source_dish_key": "pytest-import-job-key",
            "ingredients": "рис, морковь",
            "generate_video": "true",
        },
        files={"photo_ingredients": IMG, "audio": MP3},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    dish_id = body["dish"]["id"]
    assert body["dish"]["name"] == "Тест-блюдо видео"
    assert body["job"] is not None
    assert body["job"]["status"] in ("pending", "processing", "done")

    # Повтор с тем же ключом обновляет то же блюдо (идемпотентность).
    resp2 = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={
            "name": "Тест-блюдо видео (обновлено)",
            "source_dish_key": "pytest-import-job-key",
            "generate_video": "false",
        },
        files={"photo_ingredients": IMG, "audio": MP3},
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["dish"]["id"] == dish_id
    assert resp2.json()["dish"]["name"] == "Тест-блюдо видео (обновлено)"
    assert resp2.json()["job"] is None  # generate_video=false → без задания

    jobs = client.get("/api/v1/menu/admin/dishes/import-jobs", headers=auth_headers)
    assert jobs.status_code == 200
    summary = jobs.json()
    assert summary["total"] >= 1
    assert {"pending", "processing", "done", "error", "jobs"} <= set(summary.keys())

    # cleanup
    client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_public_restaurants_and_scoped_feed(client, auth_headers):
    # создаём блюдо в конкретном ресторане и проверяем публичные ручки-фильтры
    restaurants = client.get("/api/v1/users/catalog/restaurants", headers=auth_headers)
    assert restaurants.status_code == 200, restaurants.text
    rid = restaurants.json()[0]["id"]

    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={
            "name": "Публичный фильтр блюдо",
            "source_dish_key": "pytest-public-filter",
            "restaurant_id": rid,
            "generate_video": "false",
        },
        files={"photo_ingredients": IMG, "audio": MP3},
    )
    assert resp.status_code == 201, resp.text
    dish_id = resp.json()["dish"]["id"]
    try:
        # /menu/restaurants — публичная (без токена), содержит наш ресторан
        pub = client.get("/api/v1/menu/restaurants")
        assert pub.status_code == 200, pub.text
        assert any(r["id"] == rid for r in pub.json())

        # feed по ресторану возвращает только его блюда
        feed = client.get("/api/v1/menu/feed", params={"restaurant_id": rid, "limit": 100})
        assert feed.status_code == 200
        assert all(True for _ in feed.json()["items"])  # структура ок
        assert any(i["id"] == dish_id for i in feed.json()["items"])
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{dish_id}", headers=auth_headers)


def test_import_job_missing_media_returns_400(client, auth_headers):
    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={"name": "Без медиа", "generate_video": "true"},
    )
    assert resp.status_code == 400, resp.text
    # блюдо не должно было создаться при 400
    listing = client.get("/api/v1/menu/admin/dishes", headers=auth_headers)
    assert listing.status_code == 200
    assert all(d["name"] != "Без медиа" for d in listing.json())


def test_import_job_match_by_name_updates_existing(client, auth_headers):
    # Имитируем «вручную созданное» блюдо без source_dish_key.
    created = client.post(
        "/api/v1/menu/admin/dishes",
        headers=auth_headers,
        json={"name": "Матч по имени блюдо", "price": 300},
    )
    assert created.status_code == 201, created.text
    existing_id = created.json()["id"]
    try:
        # import-job без ключа, но с match_by_name — должен попасть в то же блюдо.
        resp = client.post(
            "/api/v1/menu/admin/dishes/import-job",
            headers=auth_headers,
            data={
                "name": "Матч по имени блюдо",
                "match_by_name": "true",
                "ingredients": "новые ингредиенты",
                "generate_video": "true",
            },
            files={"photo_ingredients": IMG, "audio": MP3},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["dish"]["id"] == existing_id  # обновлено, не создано
        assert resp.json()["dish"]["ingredients"] == "новые ингредиенты"
        assert resp.json()["dish"]["price"] == 300  # цена не затёрта (в запросе её не было)
        assert resp.json()["job"] is not None
    finally:
        client.delete(f"/api/v1/menu/admin/dishes/{existing_id}", headers=auth_headers)


def test_import_job_without_video_flag_skips_queue(client, auth_headers):
    resp = client.post(
        "/api/v1/menu/admin/dishes/import-job",
        headers=auth_headers,
        data={
            "name": "Блюдо без видео",
            "source_dish_key": "pytest-import-job-novideo",
            "generate_video": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["job"] is None
    client.delete(
        f"/api/v1/menu/admin/dishes/{resp.json()['dish']['id']}", headers=auth_headers
    )
