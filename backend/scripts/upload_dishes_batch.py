#!/usr/bin/env python3
"""
Пачечная загрузка блюд на сервер с генерацией видео в очереди.

Запускается НА ТВОЁМ компе (не на сервере). Идёт по манифесту, по одному блюду
шлёт multipart-запрос на `POST /menu/admin/dishes/import-job` (текст + фото +
аудио), сервер ставит видео в очередь и склеивает его в фоне. В конце скрипт
опрашивает `GET /menu/admin/dishes/import-jobs` и ждёт, пока очередь опустеет.

Зависимость: `pip install requests`

Формат манифеста (JSON):
{
  "api_base": "http://194.87.140.241:8000/api/v1",
  "login": "owner@example.com",
  "password": "...",
  "restaurant_id": null,
  "dishes": [
    {
      "name": "Плов",
      "source_dish_key": "plov",          // стабильный ключ для идемпотентных повторов
      "ingredients": "рис, баранина...",
      "description": "...",
      "price": 0,
      "price_rubles": "590 ₽",
      "category_id": null,
      "photo_ingredients": "C:/dishes/plov/ing.jpg",  // локальные пути
      "photo_dish": "C:/dishes/plov/dish.jpg",         // опционально
      "audio": "C:/dishes/plov/voice.mp3"
    }
  ]
}

Пути к файлам в манифесте — относительно самого манифеста либо абсолютные.

Пример:
  python upload_dishes_batch.py --manifest dishes.json
  python upload_dishes_batch.py --manifest dishes.json --no-video   # без генерации
  python upload_dishes_batch.py --manifest dishes.json --no-wait    # не ждать очередь
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    print("Нужен пакет requests: pip install requests", file=sys.stderr)
    raise SystemExit(1)


def resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def open_file(path: Path | None):
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    mime, _ = mimetypes.guess_type(str(path))
    return (path.name, path.open("rb"), mime or "application/octet-stream")


def login(api_base: str, login_value: str, password: str) -> str:
    resp = requests.post(
        f"{api_base}/auth/login",
        json={"login": login_value, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_dish(api_base: str, token: str, base_dir: Path, dish: dict, generate_video: bool) -> dict:
    data = {
        "name": dish["name"],
        "generate_video": "true" if generate_video else "false",
    }
    for field in ("ingredients", "description", "price_rubles", "source_dish_key"):
        if dish.get(field) is not None:
            data[field] = str(dish[field])
    for field in ("price", "category_id"):
        if dish.get(field) is not None:
            data[field] = str(dish[field])
    if dish.get("restaurant_id"):
        data["restaurant_id"] = str(dish["restaurant_id"])
    for flag in ("is_available", "is_active"):
        if dish.get(flag) is not None:
            data[flag] = "true" if dish[flag] else "false"

    files = {}
    handles = []
    try:
        for field in ("photo_dish", "photo_ingredients", "audio"):
            handle = open_file(resolve_path(base_dir, dish.get(field)))
            if handle is not None:
                files[field] = handle
                handles.append(handle[1])
        resp = requests.post(
            f"{api_base}/menu/admin/dishes/import-job",
            headers={"Authorization": f"Bearer {token}"},
            data=data,
            files=files,
            timeout=300,
        )
    finally:
        for handle in handles:
            handle.close()
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")
    return resp.json()


def wait_for_queue(api_base: str, token: str, poll_seconds: float = 5.0) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        resp = requests.get(
            f"{api_base}/menu/admin/dishes/import-jobs",
            headers=headers,
            params={"limit": 1},
            timeout=30,
        )
        resp.raise_for_status()
        s = resp.json()
        active = s["pending"] + s["processing"]
        print(
            f"  очередь: pending={s['pending']} processing={s['processing']} "
            f"done={s['done']} error={s['error']}"
        )
        if active == 0:
            if s["error"]:
                print(f"ВНИМАНИЕ: заданий с ошибкой — {s['error']}. Смотри статус в админке/логах.")
            return
        time.sleep(poll_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Пачечная загрузка блюд с генерацией видео.")
    parser.add_argument("--manifest", required=True, help="Путь к JSON-манифесту.")
    parser.add_argument("--no-video", action="store_true", help="Не ставить видео в очередь.")
    parser.add_argument("--no-wait", action="store_true", help="Не ждать завершения очереди.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    base_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    api_base = manifest["api_base"].rstrip("/")
    dishes = manifest.get("dishes") or []
    default_restaurant = manifest.get("restaurant_id")
    generate_video = not args.no_video

    print(f"Логинюсь на {api_base} ...")
    token = login(api_base, manifest["login"], manifest["password"])

    ok = 0
    failed = 0
    for idx, dish in enumerate(dishes, start=1):
        if default_restaurant and not dish.get("restaurant_id"):
            dish["restaurant_id"] = default_restaurant
        name = dish.get("name", "<без имени>")
        try:
            result = upload_dish(api_base, token, base_dir, dish, generate_video)
            job = result.get("job")
            job_note = f"job#{job['id']} [{job['status']}]" if job else "без видео"
            print(f"[{idx}/{len(dishes)}] OK  {name} → блюдо #{result['dish']['id']}, {job_note}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(dishes)}] FAIL {name}: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nЗагружено: {ok}, ошибок: {failed}")

    if generate_video and not args.no_wait and ok:
        print("Жду завершения генерации видео в очереди...")
        wait_for_queue(api_base, token)
        print("Готово.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
