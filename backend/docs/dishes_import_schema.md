# Dishes Export Analysis and Import Schema

## 1) Source Export Structure

Export root contains:
- `manifest.json`: global metadata + `items[]`
- `dishes/*.json`: one JSON per dish (`<dish_key>.json`)
- `files/*`: downloaded media files referenced by `local_path`

`manifest.json` top-level keys:
- `exported_at_utc`
- `dishes_total`, `dishes_exported`
- `media_requested`, `media_downloaded`, `media_skipped_existing`, `media_failed`
- `items`: array of dish payloads (same shape as dish file)

Dish payload keys:
- `dish_id`, `dish_key`
- `name`, `ingredients`, `description`
- `price` (integer), `price_rubles` (float in export)
- `category`: `{ id, name, menu_type }`
- `is_available`, `is_active`
- `media`:
  - `photo_dish`, `photo_ingredients`, `audio`, `video`
  - each media item: `{ file_id, telegram_file_path, local_path, file_size }`
- `errors`: array from exporter

## 2) Target Schema in New Project

Tables added:

### `menu_categories`
- `id` (PK)
- `source_category_id` (nullable unique)
- `name`
- `menu_type` (e.g. `kitchen` / `bar`)
- `description` (nullable)
- `is_active`
- timestamps

### `menu_dishes`
- `id` (PK)
- `source_dish_id` (nullable unique)
- `source_dish_key` (nullable unique)
- `name`, `ingredients`, `description`
- `price` (int), `price_rubles` (string snapshot)
- `category_id` -> `menu_categories.id`
- `is_available`, `is_active`
- media links and ids:
  - `photo_dish_file_id`, `photo_dish_path`
  - `photo_ingredients_file_id`, `photo_ingredients_path`
  - `audio_file_id`, `audio_path`
  - `video_file_id`, `video_path`
- timestamps

Idempotency strategy:
- category upsert by `source_category_id`, fallback by `(name, menu_type)`
- dish upsert by `source_dish_id`, fallback by `source_dish_key`
- update only changed fields

## 3) Import Script

Script: `backend/scripts/import_dishes_content.py`

Capabilities:
- create/update categories and dishes
- preserve media references (`file_id` + `local_path`)
- check media file existence (`missing_media_files` counter)
- log skips and parse/import errors
- `--dry-run` rollback mode
- final summary report

## 4) Notes

- Script does not modify source export files.
- Script does not use or require `BOT_TOKEN`.
