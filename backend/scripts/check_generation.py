#!/usr/bin/env python3
"""Проверка, что автогенерация медиа настроена и ключи приняты провайдерами.

Запускается НА СЕРВЕРЕ, внутри контейнера backend — потому что проверяет ровно
ту конфигурацию, с которой потом работает фоновый воркер:

    docker compose exec backend python scripts/check_generation.py

По умолчанию делает только бесплатные пробы авторизации: кредиты не тратятся.
С флагом --full реально генерирует одну картинку и одну озвучку (это спишет
кредиты Magnific и символы провайдера озвучки) и кладёт файлы в каталог --out.

Смысл в том, чтобы поймать неверный ключ здесь, а не 117 раз подряд в очереди.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.services.generation import (  # noqa: E402
    GenerationError,
    build_ingredients_prompt,
    generate_ingredients_image,
    synthesize_speech,
)

# Значения, которые принимает поле `model` у POST /v1/ai/mystic. Всё остальное
# API отвергает — а узнать об этом на 117 заданиях очереди неприятно.
MYSTIC_MODELS = ("realism", "fluid", "zen", "flexible", "super_real", "editorial_portraits")

OK = "[ OK ]"
BAD = "[ФЕЙЛ]"


def check_magnific_key(settings) -> bool:
    """Проба ключа Magnific без списания кредитов.

    Спрашиваем статус заведомо несуществующей задачи: неверный ключ даёт 401/403
    ещё до того, как сервер начнёт искать задачу, верный — 400/404.
    """
    if not settings.magnific_api_key:
        print(f"{BAD} MAGNIFIC_API_KEY не задан — стадия «картинка» работать не будет.")
        print("       Ключ создаётся тут: https://www.magnific.com/user/organization/api-keys")
        return False

    if settings.magnific_image_model not in MYSTIC_MODELS:
        print(
            f"{BAD} MAGNIFIC_IMAGE_MODEL={settings.magnific_image_model!r} — недопустимое значение. "
            f"Разрешены: {', '.join(MYSTIC_MODELS)}."
        )
        return False

    base = settings.magnific_api_base.rstrip("/")
    url = f"{base}/v1/ai/mystic/00000000-0000-0000-0000-000000000000"
    try:
        response = httpx.get(
            url, headers={"x-magnific-api-key": settings.magnific_api_key}, timeout=30.0
        )
    except httpx.HTTPError as exc:
        print(f"{BAD} Magnific недоступен с сервера: {exc}")
        return False

    if response.status_code in (401, 403):
        print(
            f"{BAD} Magnific не принял ключ (HTTP {response.status_code}). Проверьте MAGNIFIC_API_KEY."
        )
        return False

    print(f"{OK} Magnific: ключ принят, модель {settings.magnific_image_model}.")
    return True


def check_tts(settings) -> bool:
    """Проверить того провайдера озвучки, который включён в TTS_PROVIDER."""
    provider = (settings.tts_provider or "").strip().lower()
    if provider == "yandex":
        return check_yandex_key(settings)
    if provider == "elevenlabs":
        return check_elevenlabs_key(settings)
    print(f"{BAD} TTS_PROVIDER={provider!r} — допустимо: elevenlabs, yandex.")
    return False


def check_yandex_key(settings) -> bool:
    """Проба ключа SpeechKit. Синтезируем один символ — это доли копейки."""
    if not settings.yandex_tts_api_key:
        print(f"{BAD} YANDEX_TTS_API_KEY не задан — стадия «озвучка» работать не будет.")
        return False

    payload = {"text": ".", "lang": settings.yandex_tts_lang, "voice": settings.yandex_tts_voice, "format": "mp3"}
    if settings.yandex_tts_folder_id:
        payload["folderId"] = settings.yandex_tts_folder_id

    url = f"{settings.yandex_tts_api_base.rstrip('/')}/speech/v1/tts:synthesize"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Api-Key {settings.yandex_tts_api_key}"},
            data=payload,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        print(f"{BAD} Yandex SpeechKit недоступен с сервера: {exc}")
        return False

    if response.status_code >= 400:
        print(
            f"{BAD} Yandex SpeechKit не принял запрос (HTTP {response.status_code}): "
            f"{response.text[:200]}"
        )
        return False

    print(f"{OK} Yandex SpeechKit: ключ принят, голос {settings.yandex_tts_voice}.")
    return True


def check_elevenlabs_key(settings) -> bool:
    """Проба ключа ElevenLabs. Заодно показывает остаток символов."""
    if not settings.elevenlabs_api_key:
        print(f"{BAD} ELEVENLABS_API_KEY не задан — стадия «озвучка» работать не будет.")
        return False

    base = settings.elevenlabs_api_base.rstrip("/")
    try:
        response = httpx.get(
            f"{base}/v1/user", headers={"xi-api-key": settings.elevenlabs_api_key}, timeout=30.0
        )
    except httpx.HTTPError as exc:
        print(f"{BAD} ElevenLabs недоступен с сервера: {exc}")
        return False

    if response.is_redirect:
        print(
            f"{BAD} ElevenLabs увёл на {response.headers.get('location', '?')} вместо ответа — "
            "доступ закрыт для страны этого сервера. Озвучку через него не сделать."
        )
        return False

    if response.status_code >= 400:
        print(f"{BAD} ElevenLabs не принял ключ (HTTP {response.status_code}): {response.text[:200]}")
        return False

    subscription = (response.json() or {}).get("subscription") or {}
    used = subscription.get("character_count")
    limit = subscription.get("character_limit")
    quota = f", символов израсходовано {used} из {limit}" if limit is not None else ""
    print(f"{OK} ElevenLabs: ключ принят, голос {settings.elevenlabs_voice_id}{quota}.")
    return True


def run_full(out_dir: Path) -> bool:
    """Реальная генерация одной картинки и одной озвучки. Тратит кредиты."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True

    prompt = build_ingredients_prompt("Плов", "рис, баранина, морковь, лук, зира")
    try:
        content, ext = generate_ingredients_image(prompt)
        path = out_dir / f"check_image{ext}"
        path.write_bytes(content)
        print(f"{OK} Картинка сгенерирована: {path} ({len(content)} байт)")
    except GenerationError as exc:
        print(f"{BAD} Картинка не сгенерировалась: {exc}")
        ok = False

    try:
        content, ext = synthesize_speech("Проверка озвучки вкусной тетради.")
        path = out_dir / f"check_audio{ext}"
        path.write_bytes(content)
        print(f"{OK} Озвучка сгенерирована: {path} ({len(content)} байт)")
    except GenerationError as exc:
        print(f"{BAD} Озвучка не сгенерировалась: {exc}")
        ok = False

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="реально сгенерировать картинку и озвучку (тратит кредиты)",
    )
    parser.add_argument(
        "--out",
        default="/tmp/generation_check",
        help="куда положить файлы при --full (по умолчанию /tmp/generation_check)",
    )
    args = parser.parse_args()

    settings = get_settings()
    print("Проверка настроек генерации медиа")
    print()
    print(f"Провайдер озвучки: {settings.tts_provider}")
    print()
    ok = check_magnific_key(settings)
    ok = check_tts(settings) and ok

    if args.full:
        if not ok:
            print()
            print("Пробы ключей не прошли — полную генерацию не запускаю, чтобы не жечь кредиты.")
            return 1
        print()
        print("Полная проверка: генерирую одну картинку и одну озвучку...")
        ok = run_full(Path(args.out))

    print()
    if ok:
        print("Всё настроено: залив реестра будет генерировать медиа сам.")
        return 0
    print("Есть незакрытые пункты — стадии с ошибкой попадут в отчёт залива.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
