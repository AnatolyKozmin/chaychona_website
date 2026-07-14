"""Склейка видео блюда из статичного фото и озвучки через ffmpeg."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VideoCompositionError(RuntimeError):
    """ffmpeg не смог собрать видео (не установлен, таймаут, ненулевой код)."""


def compose_still_video(image_path: Path, audio_path: Path, output_path: Path) -> None:
    """Собрать mp4: картинка на всю длину аудио + аудиодорожка.

    `-loop 1` держит статичный кадр, `-shortest` обрезает по длине озвучки,
    scale-фильтр приводит стороны к чётным (требование yuv420p).
    """
    settings = get_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info("ffmpeg compose: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.video_worker_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise VideoCompositionError(
            f"ffmpeg не найден (FFMPEG_BINARY={settings.ffmpeg_binary!r}). Установите ffmpeg."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoCompositionError(
            f"ffmpeg превысил таймаут {settings.video_worker_timeout_seconds}s"
        ) from exc

    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-2000:]
        raise VideoCompositionError(f"ffmpeg вернул код {proc.returncode}: {tail}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise VideoCompositionError("ffmpeg завершился, но видеофайл не создан")
