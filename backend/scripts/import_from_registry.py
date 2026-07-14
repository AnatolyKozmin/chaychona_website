#!/usr/bin/env python3
"""
Импорт блюд из реестра «Вкусная тетрадь» (Excel + папки медиа) на сервер.

Запускается НА ТВОЁМ компе. Для каждой строки Excel шлёт multipart на
`POST /menu/admin/dishes/import-job` с match_by_name=true (обновляет уже
существующее блюдо по имени, не плодя дубли) и файлами: фото блюда, фото
ингредиентов, озвучка. Из фото ингредиентов + озвучки сервер собирает видео
в фоновой очереди.

Зависимости: openpyxl (есть в backend/requirements) + requests (pip install requests)

Ожидаемая структура Excel (лист «Вкусная тетрадь»), колонки по порядку:
  0 №  · 1 Раздел · 2 Блюдо · 3 Ингредиенты · 4 Текст озвучки
  5 Фото блюда (файл) · 6 Картинка ингредиентов (файл) · 7 Озвучка (файл)
Пути к файлам в колонках 5-7 берутся как есть, относительно --root.

По умолчанию — DRY-RUN: только показывает план (что обновит / что создаст,
какие категории создаст) и НИЧЕГО не отправляет. Для реальной заливки — --apply.

Примеры:
  python scripts/import_from_registry.py --api-base http://IP:8000/api/v1 --login owner@example.com --password ...
  python scripts/import_from_registry.py ... --apply
  python scripts/import_from_registry.py ... --apply --limit 3      # прогнать первые 3 для проверки
  python scripts/import_from_registry.py ... --apply --no-video     # без генерации видео
"""
from __future__ import annotations

import argparse
import mimetypes
import sys
import time
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Нужен openpyxl: pip install openpyxl", file=sys.stderr)
    raise SystemExit(1)

try:
    import requests
except ImportError:
    print("Нужен requests: pip install requests", file=sys.stderr)
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../chaychona_website


def norm_name(value: str) -> str:
    return " ".join(str(value or "").split()).lower()


def _cell(value) -> str | None:
    """Значение ячейки → str или None. Пустое = None или тире «—» (U+2014) по спеке."""
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "—", "–", "-"):
        return None
    return text


def read_registry(xlsx_path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))[1:]  # без заголовка
    dishes = []
    for r in rows:
        name = _cell(r[2]) if len(r) > 2 else None
        if not name:
            continue
        dishes.append(
            {
                "num": r[0],
                "category": _cell(r[1]),
                "name": name,
                "ingredients": _cell(r[3]),
                "description": _cell(r[4]),
                "photo_dish": _cell(r[5]),
                "photo_ingredients": _cell(r[6]),
                "audio": _cell(r[7]),
            }
        )
    return dishes


def http(method: str, api_base: str, token: str, path: str, **kwargs):
    resp = requests.request(
        method,
        f"{api_base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=kwargs.pop("timeout", 300),
        **kwargs,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp


def login(api_base: str, login_value: str, password: str) -> str:
    resp = requests.post(
        f"{api_base}/auth/login", json={"login": login_value, "password": password}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def resolve_restaurant(api_base: str, token: str, wanted: str) -> tuple[str, str]:
    items = http("GET", api_base, token, "/users/catalog/restaurants").json()
    if not items:
        raise SystemExit("На сервере нет ни одного ресторана. Создай ресторан в админке и укажи его в --restaurant.")
    for it in items:
        if str(it["id"]) == wanted or norm_name(it["name"]) == norm_name(wanted):
            return str(it["id"]), it["name"]
    available = ", ".join(f'"{it["name"]}"' for it in items)
    raise SystemExit(
        f"Ресторан {wanted!r} не найден. Доступные: {available}. "
        f"Укажи точное имя или id в --restaurant (никакого fallback — чтобы не залить не туда)."
    )


def open_file(root: Path, rel: str | None):
    if not rel:
        return None
    path = (root / rel).resolve()
    if not path.exists():
        return None
    mime, _ = mimetypes.guess_type(str(path))
    return (path.name, path.open("rb"), mime or "application/octet-stream")


def main() -> int:
    ap = argparse.ArgumentParser(description="Импорт блюд из реестра Вкусной тетради на сервер.")
    ap.add_argument("--api-base", required=True, help="напр. http://194.87.140.241:8000/api/v1")
    ap.add_argument("--login")
    ap.add_argument("--password")
    ap.add_argument("--token", help="готовый access-токен (вместо login/password)")
    ap.add_argument("--xlsx", default=str(PROJECT_ROOT / "ЖУ_Вкусная_тетрадь_реестр.xlsx"))
    ap.add_argument("--root", default=str(PROJECT_ROOT), help="корень для путей к медиа из Excel")
    ap.add_argument("--restaurant", required=True, help="имя или id ресторана-получателя (обязательно, без него никуда не льём)")
    ap.add_argument("--apply", action="store_true", help="реально заливать (иначе dry-run)")
    ap.add_argument("--no-video", action="store_true", help="не ставить генерацию видео")
    ap.add_argument("--limit", type=int, default=0, help="обработать только первые N (0 = все)")
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx).expanduser().resolve()
    root = Path(args.root).expanduser().resolve()
    dishes = read_registry(xlsx_path)
    if args.limit:
        dishes = dishes[: args.limit]
    print(f"Реестр: {xlsx_path.name} — {len(dishes)} блюд, медиа-корень: {root}")

    token = args.token or login(args.api_base, args.login, args.password)
    restaurant_id, restaurant_name = resolve_restaurant(args.api_base, token, args.restaurant)
    print(f"Ресторан: {restaurant_name} ({restaurant_id})")

    # существующие категории и блюда — ТОЛЬКО целевого ресторана, чтобы не
    # цеплять одноимённую категорию/блюдо другого ресторана.
    rid = str(restaurant_id) if restaurant_id else ""

    def _same_restaurant(obj) -> bool:
        return str(obj.get("restaurant_id") or "") == rid

    server_categories = [c for c in http("GET", args.api_base, token, "/menu/admin/categories").json() if _same_restaurant(c)]
    cat_by_name = {norm_name(c["name"]): c["id"] for c in server_categories}
    server_dishes = [d for d in http("GET", args.api_base, token, "/menu/admin/dishes").json() if _same_restaurant(d)]
    existing_names = {norm_name(d["name"]) for d in server_dishes}

    wanted_cats = sorted({d["category"] for d in dishes if d["category"]})
    missing_cats = [c for c in wanted_cats if norm_name(c) not in cat_by_name]

    will_update = [d for d in dishes if norm_name(d["name"]) in existing_names]
    will_create = [d for d in dishes if norm_name(d["name"]) not in existing_names]
    no_dish_photo = [d for d in dishes if not open_file(root, d["photo_dish"])]
    bad_media = [d for d in dishes if not open_file(root, d["photo_ingredients"]) or not open_file(root, d["audio"])]

    print("\n===== ПЛАН =====")
    print(f"Обновить существующих (совпало по имени): {len(will_update)}")
    print(f"Создать новых (имя не найдено на сервере): {len(will_create)}")
    if will_create:
        for d in will_create[:30]:
            print(f"    NEW  #{d['num']}  {d['name']}")
        if len(will_create) > 30:
            print(f"    … ещё {len(will_create) - 30}")
    print(f"Категорий создать: {len(missing_cats)} -> {missing_cats}")
    print(f"Без фото блюда (не критично): {len(no_dish_photo)}")
    print(f"БЕЗ фото ингредиентов/аудио (видео не выйдет!): {len(bad_media)}")
    for d in bad_media[:20]:
        print(f"    NO-MEDIA #{d['num']}  {d['name']}")

    if not args.apply:
        print("\nDRY-RUN. Ничего не отправлено. Для реальной заливки добавь --apply")
        return 0

    # создаём недостающие категории
    for cat in missing_cats:
        resp = http(
            "POST", args.api_base, token, "/menu/admin/categories",
            json={"name": cat, "restaurant_id": restaurant_id, "is_active": True},
        )
        cat_by_name[norm_name(cat)] = resp.json()["id"]
        print(f"Категория создана: {cat} -> {cat_by_name[norm_name(cat)]}")

    ok = failed = 0
    for idx, d in enumerate(dishes, start=1):
        data = {
            "name": d["name"],
            "match_by_name": "true",
            "generate_video": "false" if args.no_video else "true",
        }
        if d["ingredients"]:
            data["ingredients"] = d["ingredients"]
        if d["description"]:
            data["description"] = d["description"]
        if restaurant_id:
            data["restaurant_id"] = restaurant_id
        if d["category"] and norm_name(d["category"]) in cat_by_name:
            data["category_id"] = str(cat_by_name[norm_name(d["category"])])

        files = {}
        handles = []
        for field, rel in (
            ("photo_dish", d["photo_dish"]),
            ("photo_ingredients", d["photo_ingredients"]),
            ("audio", d["audio"]),
        ):
            fh = open_file(root, rel)
            if fh is not None:
                files[field] = fh
                handles.append(fh[1])
        try:
            resp = http("POST", args.api_base, token, "/menu/admin/dishes/import-job", data=data, files=files)
            job = resp.json().get("job")
            note = f"job#{job['id']}" if job else "без видео"
            print(f"[{idx}/{len(dishes)}] OK  {d['name']} -> #{resp.json()['dish']['id']}, {note}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(dishes)}] FAIL {d['name']}: {exc}", file=sys.stderr)
            failed += 1
        finally:
            for h in handles:
                h.close()

    print(f"\nОтправлено: {ok}, ошибок: {failed}")

    if not args.no_video and ok:
        print("Жду завершения генерации видео...")
        while True:
            s = http("GET", args.api_base, token, "/menu/admin/dishes/import-jobs", params={"limit": 1}).json()
            print(f"  pending={s['pending']} processing={s['processing']} done={s['done']} error={s['error']}")
            if s["pending"] + s["processing"] == 0:
                if s["error"]:
                    print(f"ВНИМАНИЕ: с ошибкой {s['error']} — смотри статусы в админке.")
                break
            time.sleep(5)
        print("Готово.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
