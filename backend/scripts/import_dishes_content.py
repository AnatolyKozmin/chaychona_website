#!/usr/bin/env python3
"""
Import dishes content export into the web app database.

Features:
- idempotent create/update for categories and dishes
- dry-run mode
- logs errors and skipped records
- summary report at the end
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.menu import MenuCategory, MenuDish  # noqa: E402


@dataclass
class ImportStats:
    dishes_seen: int = 0
    dishes_created: int = 0
    dishes_updated: int = 0
    dishes_unchanged: int = 0
    categories_created: int = 0
    categories_updated: int = 0
    categories_unchanged: int = 0
    skipped_items: int = 0
    errors: int = 0
    missing_media_files: int = 0


def load_local_env() -> None:
    """
    Best-effort .env loading without hard dependency on pydantic settings.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:  # noqa: BLE001
        return

    candidates = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / ".env",
    ]
    for path in candidates:
        if path.exists():
            load_dotenv(path)


def get_session_local() -> sessionmaker[Session]:
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        database_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/restaurant_training"
    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import content_export into current backend DB.")
    parser.add_argument(
        "--export-root",
        required=True,
        help="Path to export folder that contains manifest.json, dishes/, files/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and log changes without writing to DB.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_category(db: Session, raw_category: dict[str, Any] | None, stats: ImportStats) -> MenuCategory | None:
    if not raw_category:
        return None

    src_id = raw_category.get("id")
    name = normalize_text(raw_category.get("name"))
    menu_type = normalize_text(raw_category.get("menu_type"))
    if not name:
        return None

    category: MenuCategory | None = None
    if src_id is not None:
        category = db.scalar(select(MenuCategory).where(MenuCategory.source_category_id == src_id))

    if category is None:
        category = db.scalar(
            select(MenuCategory).where(
                func.lower(MenuCategory.name) == name.lower(),
                func.coalesce(MenuCategory.menu_type, "") == (menu_type or ""),
            )
        )

    if category is None:
        category = MenuCategory(
            source_category_id=src_id,
            name=name,
            menu_type=menu_type,
            description=None,
            is_active=True,
        )
        db.add(category)
        db.flush([category])
        stats.categories_created += 1
        return category

    changed = False
    if src_id is not None and category.source_category_id != src_id:
        category.source_category_id = src_id
        changed = True
    if category.name != name:
        category.name = name
        changed = True
    if category.menu_type != menu_type:
        category.menu_type = menu_type
        changed = True

    if changed:
        stats.categories_updated += 1
    else:
        stats.categories_unchanged += 1
    return category


def resolve_category_cached(
    db: Session,
    raw_category: dict[str, Any] | None,
    stats: ImportStats,
    cache_by_source_id: dict[int, MenuCategory],
    cache_by_name_type: dict[tuple[str, str], MenuCategory],
) -> MenuCategory | None:
    if not raw_category:
        return None

    src_id_raw = raw_category.get("id")
    src_id = int(src_id_raw) if src_id_raw is not None else None
    name = normalize_text(raw_category.get("name"))
    menu_type = normalize_text(raw_category.get("menu_type")) or ""
    if not name:
        return None

    name_key = (name.lower(), menu_type.lower())

    if src_id is not None and src_id in cache_by_source_id:
        return cache_by_source_id[src_id]
    if name_key in cache_by_name_type:
        return cache_by_name_type[name_key]

    category = resolve_category(
        db,
        {"id": src_id, "name": name, "menu_type": menu_type or None},
        stats,
    )
    if category is None:
        return None

    if category.source_category_id is not None:
        cache_by_source_id[int(category.source_category_id)] = category
    cache_by_name_type[(category.name.lower(), (category.menu_type or "").lower())] = category
    return category


def extract_media_field(
    export_root: Path, media: dict[str, Any], key: str, stats: ImportStats
) -> tuple[str | None, str | None]:
    node = media.get(key)
    if not node:
        return None, None

    file_id = normalize_text(node.get("file_id"))
    local_path = normalize_text(node.get("local_path"))
    if local_path:
        media_file = export_root / local_path
        if not media_file.exists():
            stats.missing_media_files += 1
            logging.warning("Media file is missing for %s: %s", key, media_file)
    return file_id, local_path


def upsert_dish(
    db: Session,
    export_root: Path,
    payload: dict[str, Any],
    stats: ImportStats,
    cache_by_source_id: dict[int, MenuCategory],
    cache_by_name_type: dict[tuple[str, str], MenuCategory],
) -> None:
    stats.dishes_seen += 1

    source_dish_id = payload.get("dish_id")
    source_dish_key = normalize_text(payload.get("dish_key"))
    name = normalize_text(payload.get("name"))
    if not source_dish_id or not name:
        stats.skipped_items += 1
        logging.warning("Skipping invalid dish payload: dish_id=%s name=%s", source_dish_id, name)
        return

    category = resolve_category_cached(
        db,
        payload.get("category"),
        stats,
        cache_by_source_id=cache_by_source_id,
        cache_by_name_type=cache_by_name_type,
    )
    category_id = category.id if category else None

    media = payload.get("media") or {}
    photo_dish_file_id, photo_dish_path = extract_media_field(export_root, media, "photo_dish", stats)
    photo_ingredients_file_id, photo_ingredients_path = extract_media_field(
        export_root, media, "photo_ingredients", stats
    )
    audio_file_id, audio_path = extract_media_field(export_root, media, "audio", stats)
    video_file_id, video_path = extract_media_field(export_root, media, "video", stats)

    price = payload.get("price")
    if not isinstance(price, int):
        price = 0

    db_dish = db.scalar(select(MenuDish).where(MenuDish.source_dish_id == source_dish_id))
    if db_dish is None and source_dish_key:
        db_dish = db.scalar(select(MenuDish).where(MenuDish.source_dish_key == source_dish_key))

    new_values = {
        "source_dish_id": source_dish_id,
        "source_dish_key": source_dish_key,
        "name": name,
        "ingredients": normalize_text(payload.get("ingredients")),
        "description": normalize_text(payload.get("description")),
        "price": price,
        "price_rubles": str(payload.get("price_rubles")) if payload.get("price_rubles") is not None else None,
        "category_id": category_id,
        "is_available": bool(payload.get("is_available", True)),
        "is_active": bool(payload.get("is_active", True)),
        "photo_dish_file_id": photo_dish_file_id,
        "photo_dish_path": photo_dish_path,
        "photo_ingredients_file_id": photo_ingredients_file_id,
        "photo_ingredients_path": photo_ingredients_path,
        "audio_file_id": audio_file_id,
        "audio_path": audio_path,
        "video_file_id": video_file_id,
        "video_path": video_path,
    }

    if db_dish is None:
        db_dish = MenuDish(**new_values)
        db.add(db_dish)
        stats.dishes_created += 1
        return

    changed = False
    for key, value in new_values.items():
        if getattr(db_dish, key) != value:
            setattr(db_dish, key, value)
            changed = True

    if changed:
        stats.dishes_updated += 1
    else:
        stats.dishes_unchanged += 1


def run_import(export_root: Path, dry_run: bool) -> ImportStats:
    stats = ImportStats()
    manifest_path = export_root / "manifest.json"
    dishes_dir = export_root / "dishes"
    files_dir = export_root / "files"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found: {manifest_path}")
    if not dishes_dir.exists():
        raise FileNotFoundError(f"dishes dir not found: {dishes_dir}")
    if not files_dir.exists():
        logging.warning("files dir is missing: %s", files_dir)

    manifest = load_json(manifest_path)
    items = manifest.get("items") or []
    logging.info("Manifest loaded: items=%s", len(items))

    SessionLocal = get_session_local()
    db: Session = SessionLocal()
    try:
        category_cache_by_source_id: dict[int, MenuCategory] = {}
        category_cache_by_name_type: dict[tuple[str, str], MenuCategory] = {}
        for idx, item in enumerate(items, start=1):
            dish_key = normalize_text(item.get("dish_key"))
            if not dish_key:
                stats.skipped_items += 1
                logging.warning("Item %s skipped: missing dish_key", idx)
                continue

            dish_file = dishes_dir / f"{dish_key}.json"
            payload = item
            if dish_file.exists():
                try:
                    payload = load_json(dish_file)
                except Exception as exc:  # noqa: BLE001
                    stats.errors += 1
                    logging.error("Failed to parse dish file %s: %s", dish_file, exc)
                    continue
            else:
                stats.skipped_items += 1
                logging.warning("Dish file is missing for key %s, using manifest item only", dish_key)

            try:
                upsert_dish(
                    db,
                    export_root,
                    payload,
                    stats,
                    cache_by_source_id=category_cache_by_source_id,
                    cache_by_name_type=category_cache_by_name_type,
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                logging.exception("Failed to import dish key=%s: %s", dish_key, exc)

        if dry_run:
            db.rollback()
            logging.info("Dry-run: transaction rolled back.")
        else:
            db.commit()
            logging.info("Import committed.")
    finally:
        db.close()

    return stats


def print_report(stats: ImportStats, dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\n=== Import report ({mode}) ===")
    print(f"Dishes seen: {stats.dishes_seen}")
    print(f"Dishes created: {stats.dishes_created}")
    print(f"Dishes updated: {stats.dishes_updated}")
    print(f"Dishes unchanged: {stats.dishes_unchanged}")
    print(f"Categories created: {stats.categories_created}")
    print(f"Categories updated: {stats.categories_updated}")
    print(f"Categories unchanged: {stats.categories_unchanged}")
    print(f"Missing media files: {stats.missing_media_files}")
    print(f"Skipped items: {stats.skipped_items}")
    print(f"Errors: {stats.errors}")


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    export_root = Path(args.export_root).expanduser().resolve()
    try:
        stats = run_import(export_root, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        logging.error("Import failed: %s", exc)
        return 1

    print_report(stats, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
