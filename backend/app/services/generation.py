"""Внешние генераторы медиа для блюд: картинка ингредиентов и озвучка.

Два разных провайдера, и это не прихоть: в публичном REST API Magnific
(бывший Freepik API) есть генерация картинок, но НЕТ text-to-speech — только
музыка, звуковые эффекты и audio-isolation. TTS внутри самого Magnific — это
ElevenLabs, но наружу, в REST, его не вывели: доступен он только из веба и по
MCP, куда серверу не попасть.

Поэтому озвучка ходит к отдельному провайдеру, и он выбирается настройкой
`TTS_PROVIDER`. ElevenLabs напрямую с российского IP не отвечает (редирект на
статью про страновые ограничения), Yandex SpeechKit работает и платится
рублями — какой из них живой, решается конфигом, а не правкой кода.

Ключей может не быть — тогда падаем с понятным текстом, который воркер кладёт
в `error` задания. Импорт от этого не разваливается: текст блюд и фото,
пришедшие файлом, заезжают в любом случае.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MYSTIC_PATH = "/v1/ai/mystic"
ELEVENLABS_TTS_PATH = "/v1/text-to-speech"
YANDEX_TTS_PATH = "/speech/v1/tts:synthesize"

# Кто может делать озвучку. Значение берётся из TTS_PROVIDER.
TTS_PROVIDERS = ("elevenlabs", "yandex")

# Стадия без ключа не падает, а ждёт. Задание остаётся в очереди, блюдо
# показывает «отправлено на генерацию», а админка — какой ключ добавить на
# сервер. Падать сотней ошибок на каждый залив бессмысленно: результат всё
# равно появится только после настройки ключа, и тогда те же задания уедут
# в работу сами, без повторного залива меню.
#
# Для озвучки режим включается и явно, `TTS_PROVIDER=stub`: провайдера в
# России пока нет, а ключи от других сервисов могут лежать в .env рядом.
TTS_STUB = "stub"

# Пауза между опросами статуса задачи Magnific.
_POLL_SECONDS = 3.0


class GenerationError(RuntimeError):
    """Провайдер не отдал результат: нет ключа, ошибка API, таймаут."""


def build_ingredients_prompt(dish_name: str, ingredients: str | None) -> str:
    """Промпт картинки ингредиентов по названию блюда и списку из реестра.

    Раскладка сверху — это осознанно: официант сверяет её с тарелкой, поэтому
    важнее узнаваемость каждого продукта по отдельности, чем красивая подача.
    """
    parts = [
        f"Ингредиенты блюда «{dish_name}»",
        "аккуратная раскладка продуктов по отдельности на светлом однотонном фоне",
        "вид сверху, flat lay, мягкий дневной свет, фотореализм, без текста и надписей",
    ]
    if ingredients:
        parts.insert(1, f"продукты: {ingredients}")
    return ", ".join(parts)


def tts_mode() -> str:
    """Чем сейчас озвучиваем: `elevenlabs`, `yandex` или `stub` (пока никем)."""
    settings = get_settings()
    provider = (settings.tts_provider or "").strip().lower()
    if provider == TTS_STUB:
        return TTS_STUB
    if provider == "yandex":
        return "yandex" if settings.yandex_tts_api_key else TTS_STUB
    if provider == "elevenlabs":
        return "elevenlabs" if settings.elevenlabs_api_key else TTS_STUB
    return TTS_STUB


def image_ready() -> bool:
    """Есть чем рисовать картинку ингредиентов."""
    return bool(get_settings().magnific_api_key)


def missing_keys(*, image: bool = True, audio: bool = True) -> list[str]:
    """Какие переменные надо добавить в .env сервера, чтобы генерация пошла.

    Для озвучки называем ключ выбранного провайдера; если провайдер не выбран
    вовсе (`stub` или мусор), подсказываем сам выбор — ключ без него не поможет.
    """
    settings = get_settings()
    keys: list[str] = []
    if image and not image_ready():
        keys.append("MAGNIFIC_API_KEY")
    if audio and tts_mode() == TTS_STUB:
        provider = (settings.tts_provider or "").strip().lower()
        if provider == "yandex":
            keys.append("YANDEX_TTS_API_KEY")
        elif provider == "elevenlabs":
            keys.append("ELEVENLABS_API_KEY")
        else:
            keys.append("TTS_PROVIDER и ключ провайдера озвучки")
    return keys


def missing_key_warnings(*, image: bool, audio: bool) -> list[str]:
    """Что уйдёт на генерацию, но не сделается, пока на сервере нет ключа.

    Ключи живут в .env сервера, а кнопку жмут в админке. Заливу это не мешает:
    текст и фото из файла заезжают, задания ждут ключа в очереди.
    """
    warnings: list[str] = []
    if image and not image_ready():
        warnings.append(
            "Картинки ингредиентов отправлены на генерацию. Чтобы они появились, "
            "нужно добавить ключ MAGNIFIC_API_KEY в .env на продакшене."
        )
    if audio and tts_mode() == TTS_STUB:
        key = missing_keys(image=False, audio=True)[0]
        warnings.append(
            "Озвучка отправлена на генерацию — у блюд будет пометка «аудио отправлено "
            f"на генерацию». Чтобы она появилась, нужно добавить {key} в .env на продакшене. "
            "Видео соберётся после озвучки."
        )
    return warnings


def _magnific_headers(api_key: str) -> dict[str, str]:
    return {"x-magnific-api-key": api_key, "Content-Type": "application/json"}


def generate_ingredients_image(prompt: str) -> tuple[bytes, str]:
    """Сгенерировать картинку по промпту. Возвращает (байты, расширение).

    Mystic асинхронный: POST отдаёт task_id, дальше опрашиваем статус, пока не
    станет COMPLETED, и качаем первый файл из `generated`.
    """
    settings = get_settings()
    if not settings.magnific_api_key:
        raise GenerationError(
            "Не задан MAGNIFIC_API_KEY — генерация картинок выключена. "
            "Добавьте ключ в .env бэкенда и перезапустите контейнер."
        )

    base = settings.magnific_api_base.rstrip("/")
    headers = _magnific_headers(settings.magnific_api_key)
    deadline = time.monotonic() + settings.generation_timeout_seconds

    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.post(
                f"{base}{MYSTIC_PATH}",
                headers=headers,
                json={
                    "prompt": prompt,
                    "model": settings.magnific_image_model,
                    "resolution": "2k",
                    "aspect_ratio": "square_1_1",
                    "filter_nsfw": True,
                },
            )
        except httpx.HTTPError as exc:
            raise GenerationError(f"Magnific недоступен: {exc}") from exc
        if response.status_code >= 400:
            raise GenerationError(f"Magnific ответил {response.status_code}: {response.text[:500]}")

        data = (response.json() or {}).get("data") or {}
        task_id = data.get("task_id")
        image_urls = data.get("generated") or []

        # Опрашиваем, пока задача не завершится. Первый ответ иногда уже
        # содержит готовую ссылку — тогда цикл не нужен.
        while not image_urls:
            if not task_id:
                raise GenerationError(f"Magnific не вернул task_id: {response.text[:500]}")
            if time.monotonic() > deadline:
                raise GenerationError(
                    f"Magnific не отдал картинку за {settings.generation_timeout_seconds}s (задача {task_id})"
                )
            time.sleep(_POLL_SECONDS)
            try:
                poll = client.get(f"{base}{MYSTIC_PATH}/{task_id}", headers=headers)
            except httpx.HTTPError as exc:
                raise GenerationError(f"Magnific недоступен при опросе задачи: {exc}") from exc
            if poll.status_code >= 400:
                raise GenerationError(f"Magnific ответил {poll.status_code}: {poll.text[:500]}")
            data = (poll.json() or {}).get("data") or {}
            status = str(data.get("status") or "").upper()
            if status == "FAILED":
                raise GenerationError(f"Magnific завершил задачу {task_id} с ошибкой")
            image_urls = data.get("generated") or []

        return _download(client, str(image_urls[0]), default_ext=".png")


def synthesize_speech(text: str) -> tuple[bytes, str]:
    """Озвучить текст выбранным провайдером. Возвращает (байты mp3, расширение).

    Какой именно провайдер — решает `TTS_PROVIDER`. Остальному пайплайну это
    безразлично: он получает mp3 и не знает, кто его сделал.
    """
    if not text.strip():
        raise GenerationError("Пустой текст озвучки")

    settings = get_settings()
    provider = (settings.tts_provider or "").strip().lower()
    if provider == "yandex":
        return _speak_yandex(text, settings)
    if provider == "elevenlabs":
        return _speak_elevenlabs(text, settings)
    raise GenerationError(
        f"Неизвестный TTS_PROVIDER={provider!r}. Допустимо: {', '.join(TTS_PROVIDERS)}."
    )


def _speak_elevenlabs(text: str, settings) -> tuple[bytes, str]:
    if not settings.elevenlabs_api_key:
        raise GenerationError(
            "Не задан ELEVENLABS_API_KEY — генерация озвучки выключена. "
            "Добавьте ключ в .env бэкенда и перезапустите контейнер."
        )

    base = settings.elevenlabs_api_base.rstrip("/")
    url = f"{base}{ELEVENLABS_TTS_PATH}/{settings.elevenlabs_voice_id}"
    try:
        with httpx.Client(timeout=settings.generation_timeout_seconds) as client:
            response = client.post(
                url,
                headers={"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
                params={"output_format": "mp3_44100_128"},
                json={"text": text, "model_id": settings.elevenlabs_model},
            )
    except httpx.HTTPError as exc:
        raise GenerationError(f"ElevenLabs недоступен: {exc}") from exc
    if response.is_redirect:
        # ElevenLabs закрывает доступ по географии редиректом на страницу
        # справки, а не кодом ошибки. Без этой ветки в .mp3 уехал бы HTML.
        raise GenerationError(
            f"ElevenLabs не отдал аудио, а увёл на {response.headers.get('location', '?')} — "
            "похоже, доступ closed для страны сервера. Нужен другой провайдер озвучки."
        )
    if response.status_code >= 400:
        raise GenerationError(f"ElevenLabs ответил {response.status_code}: {response.text[:500]}")
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("audio/"):
        raise GenerationError(
            f"ElevenLabs вернул не аудио, а {content_type or 'ничего'}: {response.text[:300]}"
        )
    if not response.content:
        raise GenerationError("ElevenLabs вернул пустой аудиофайл")
    return response.content, ".mp3"


def _speak_yandex(text: str, settings) -> tuple[bytes, str]:
    """Озвучка через Yandex SpeechKit v1.

    Синхронный эндпоинт: отдаёт готовые байты сразу, опрашивать нечего.
    Ключ передаётся заголовком `Api-Key`, тело — обычная форма.
    """
    if not settings.yandex_tts_api_key:
        raise GenerationError(
            "Не задан YANDEX_TTS_API_KEY — генерация озвучки выключена. "
            "Добавьте ключ в .env бэкенда и перезапустите контейнер."
        )

    payload = {
        "text": text,
        "lang": settings.yandex_tts_lang,
        "voice": settings.yandex_tts_voice,
        "format": "mp3",
    }
    # Нужен, только когда ключ не привязан к сервисному аккаунту; пустой
    # folderId SpeechKit считает ошибкой, поэтому кладём его лишь при наличии.
    if settings.yandex_tts_folder_id:
        payload["folderId"] = settings.yandex_tts_folder_id

    url = f"{settings.yandex_tts_api_base.rstrip('/')}{YANDEX_TTS_PATH}"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Api-Key {settings.yandex_tts_api_key}"},
            data=payload,
            timeout=settings.generation_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise GenerationError(f"Yandex SpeechKit недоступен: {exc}") from exc

    if response.status_code >= 400:
        raise GenerationError(
            f"Yandex SpeechKit ответил {response.status_code}: {response.text[:500]}"
        )
    if not response.content:
        raise GenerationError("Yandex SpeechKit вернул пустой аудиофайл")
    return response.content, ".mp3"


def _download(client: httpx.Client, url: str, default_ext: str) -> tuple[bytes, str]:
    try:
        # Ссылки на результат ведут на CDN и вполне законно редиректят —
        # здесь, в отличие от TTS, переход по редиректу это норма.
        response = client.get(url, timeout=120.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise GenerationError(f"Не скачался результат генерации: {exc}") from exc
    if response.status_code >= 400:
        raise GenerationError(f"Не скачался результат генерации: HTTP {response.status_code}")
    if not response.content:
        raise GenerationError("Провайдер вернул пустой файл")

    ext = default_ext
    for candidate in (".png", ".jpg", ".jpeg", ".webp"):
        if candidate in url.lower():
            ext = candidate
            break
    return response.content, ext
