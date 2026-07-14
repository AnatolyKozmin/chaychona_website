"""Единое место для хранения и разрешения путей медиафайлов меню.

Загруженные файлы кладутся в `backend/media_uploads/uploads/` и адресуются
относительным путём вида `uploads/<hex>.<ext>` — тем же, что раздаёт
`GET /api/v1/menu/media?path=...`.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import get_settings

# backend/app/services/media.py -> parents[2] == backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = BACKEND_ROOT / "media_uploads"
UPLOAD_DIR = MEDIA_ROOT / "uploads"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a"}
VIDEO_EXTS = {".mp4", ".webm"}
ALLOWED_MEDIA_EXTS = IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS


def save_upload_bytes(content: bytes, suffix: str) -> str:
    """Сохранить байты как файл в uploads/, вернуть относительный путь."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{suffix.lower()}"
    (UPLOAD_DIR / file_name).write_bytes(content)
    return f"uploads/{file_name}"


def media_roots() -> list[Path]:
    """Корни, в которых ищутся медиафайлы (как в GET /menu/media)."""
    settings = get_settings()
    roots: list[Path] = []
    if settings.content_export_root:
        roots.append(Path(settings.content_export_root).resolve())
    roots.append(MEDIA_ROOT.resolve())
    return roots


def resolve_media_abspath(relpath: str | None) -> Path | None:
    """Разрешить относительный путь в абсолютный, не выходя за корни."""
    if not relpath:
        return None
    normalized = relpath.strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    for root in media_roots():
        candidate = (root / normalized).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
