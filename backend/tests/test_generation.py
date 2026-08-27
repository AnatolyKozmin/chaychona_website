"""Клиенты внешних генераторов: промпт, отсутствие ключей, ответы провайдеров.

Сеть не трогаем — httpx.Client подменён заглушкой.
"""
import pytest

import app.services.generation as gen
from app.services.generation import (
    GenerationError,
    build_ingredients_prompt,
    generate_ingredients_image,
    missing_key_warnings,
    synthesize_speech,
)


class FakeSettings:
    magnific_api_key = "magnific-key"
    magnific_api_base = "https://api.magnific.com"
    magnific_image_model = "realism"
    tts_provider = "elevenlabs"
    elevenlabs_api_key = "eleven-key"
    elevenlabs_api_base = "https://api.elevenlabs.io"
    elevenlabs_voice_id = "voice-1"
    elevenlabs_model = "eleven_multilingual_v2"
    yandex_tts_api_key = "yandex-key"
    yandex_tts_api_base = "https://tts.api.cloud.yandex.net"
    yandex_tts_folder_id = None
    yandex_tts_voice = "alena"
    yandex_tts_lang = "ru-RU"
    generation_timeout_seconds = 30


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.text = str(payload or content)
        self.headers = headers or {}
        self.is_redirect = 300 <= status_code < 400 and "location" in self.headers

    def json(self):
        return self._payload


AUDIO = {"content-type": "audio/mpeg"}


class FakeClient:
    """Заглушка httpx.Client: отдаёт заранее выложенные ответы по очереди."""

    def __init__(self, posts=None, gets=None):
        self.posts = list(posts or [])
        self.gets = list(gets or [])
        self.post_calls = []
        self.get_calls = []

    def __call__(self, *_args, **_kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.posts.pop(0)

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.gets.pop(0)


@pytest.fixture
def settings(monkeypatch):
    fake = FakeSettings()
    monkeypatch.setattr(gen, "get_settings", lambda: fake)
    monkeypatch.setattr(gen, "_POLL_SECONDS", 0)  # не спим в тестах
    return fake


def test_prompt_mentions_dish_and_ingredients():
    prompt = build_ingredients_prompt("Плов", "рис, баранина, морковь")

    assert "Плов" in prompt
    assert "рис, баранина, морковь" in prompt


def test_prompt_survives_missing_ingredients():
    prompt = build_ingredients_prompt("Плов", None)

    assert "Плов" in prompt


def test_prompt_forbids_text_on_the_picture():
    """Надписи на картинке — это мусор: подписи официант читает в карточке."""
    assert "без текста" in build_ingredients_prompt("Плов", "рис")


def test_image_without_key_explains_what_to_do(settings, monkeypatch):
    settings.magnific_api_key = None

    with pytest.raises(GenerationError, match="MAGNIFIC_API_KEY"):
        generate_ingredients_image("что угодно")


def test_audio_without_key_explains_what_to_do(settings):
    settings.elevenlabs_api_key = None

    with pytest.raises(GenerationError, match="ELEVENLABS_API_KEY"):
        synthesize_speech("текст")


def test_audio_rejects_empty_text(settings):
    with pytest.raises(GenerationError, match="Пустой текст"):
        synthesize_speech("   ")


def test_audio_returns_mp3_bytes(settings, monkeypatch):
    client = FakeClient(posts=[FakeResponse(content=b"mp3-bytes", headers=AUDIO)])
    monkeypatch.setattr(gen.httpx, "Client", client)

    content, ext = synthesize_speech("Рассказ про плов")

    assert content == b"mp3-bytes"
    assert ext == ".mp3"
    url, kwargs = client.post_calls[0]
    assert url.endswith("/v1/text-to-speech/voice-1")
    assert kwargs["headers"]["xi-api-key"] == "eleven-key"
    assert kwargs["json"]["text"] == "Рассказ про плов"


def test_audio_surfaces_provider_error(settings, monkeypatch):
    client = FakeClient(posts=[FakeResponse(status_code=401, payload={"detail": "bad key"})])
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="401"):
        synthesize_speech("текст")


def test_audio_rejects_empty_body_from_provider(settings, monkeypatch):
    client = FakeClient(posts=[FakeResponse(content=b"", headers=AUDIO)])
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="пустой аудиофайл"):
        synthesize_speech("текст")


def test_image_uses_url_from_first_response(settings, monkeypatch):
    """Если картинка готова сразу — второй запрос за статусом не нужен."""
    client = FakeClient(
        posts=[FakeResponse(payload={"data": {"task_id": "t1", "generated": ["https://cdn/a.png"]}})],
        gets=[FakeResponse(content=b"png-bytes")],
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    content, ext = generate_ingredients_image("ингредиенты плова")

    assert content == b"png-bytes"
    assert ext == ".png"
    assert len(client.get_calls) == 1  # только скачивание, без опроса статуса


def test_image_polls_until_task_completes(settings, monkeypatch):
    client = FakeClient(
        posts=[FakeResponse(payload={"data": {"task_id": "t1", "generated": []}})],
        gets=[
            FakeResponse(payload={"data": {"status": "IN_PROGRESS", "generated": []}}),
            FakeResponse(payload={"data": {"status": "COMPLETED", "generated": ["https://cdn/a.webp"]}}),
            FakeResponse(content=b"webp-bytes"),
        ],
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    content, ext = generate_ingredients_image("ингредиенты плова")

    assert content == b"webp-bytes"
    assert ext == ".webp"


def test_image_reports_failed_task(settings, monkeypatch):
    client = FakeClient(
        posts=[FakeResponse(payload={"data": {"task_id": "t1", "generated": []}})],
        gets=[FakeResponse(payload={"data": {"status": "FAILED", "generated": []}})],
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="с ошибкой"):
        generate_ingredients_image("ингредиенты")


def test_image_surfaces_http_error(settings, monkeypatch):
    client = FakeClient(posts=[FakeResponse(status_code=429, payload={"detail": "rate limit"})])
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="429"):
        generate_ingredients_image("ингредиенты")


def test_image_sends_api_key_header(settings, monkeypatch):
    client = FakeClient(
        posts=[FakeResponse(payload={"data": {"task_id": "t1", "generated": ["https://cdn/a.png"]}})],
        gets=[FakeResponse(content=b"png")],
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    generate_ingredients_image("ингредиенты")

    _url, kwargs = client.post_calls[0]
    assert kwargs["headers"]["x-magnific-api-key"] == "magnific-key"
    assert kwargs["json"]["model"] == "realism"


def test_audio_refuses_a_geo_block_redirect(settings, monkeypatch):
    """ElevenLabs закрывает доступ по стране редиректом, а не кодом ошибки.

    302 меньше 400, так что без явной проверки HTML-страница справки уехала бы
    на диск под именем .mp3 — и блюдо «озвучилось» бы молча и неправильно.
    """
    client = FakeClient(
        posts=[
            FakeResponse(
                status_code=302,
                content=b"<HTML>302 Moved</HTML>",
                headers={"location": "https://help.elevenlabs.io/hc/en-us/articles/22497891312401"},
            )
        ]
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="доступ closed для страны"):
        synthesize_speech("текст")


def test_audio_refuses_html_pretending_to_be_audio(settings, monkeypatch):
    client = FakeClient(
        posts=[FakeResponse(content=b"<html>oops</html>", headers={"content-type": "text/html"})]
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    with pytest.raises(GenerationError, match="вернул не аудио"):
        synthesize_speech("текст")


def test_result_download_follows_cdn_redirects(settings, monkeypatch):
    """Ссылку на готовый файл CDN законно редиректит — здесь идти по ней надо."""
    client = FakeClient(
        posts=[FakeResponse(payload={"data": {"generated": ["https://cdn.magnific.com/a.png"]}})],
        gets=[FakeResponse(content=b"png-bytes")],
    )
    monkeypatch.setattr(gen.httpx, "Client", client)

    generate_ingredients_image("промпт")

    _url, kwargs = client.get_calls[0]
    assert kwargs["follow_redirects"] is True


# --- выбор провайдера озвучки ---------------------------------------------


def test_provider_switch_routes_to_yandex(settings, monkeypatch):
    """TTS_PROVIDER=yandex уводит озвучку в SpeechKit, не трогая остальной код."""
    settings.tts_provider = "yandex"
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(content=b"yandex-mp3")

    monkeypatch.setattr(gen.httpx, "post", fake_post)

    content, ext = synthesize_speech("Рассказ про плов")

    assert (content, ext) == (b"yandex-mp3", ".mp3")
    assert captured["url"].endswith("/speech/v1/tts:synthesize")
    assert captured["kwargs"]["headers"]["Authorization"] == "Api-Key yandex-key"
    data = captured["kwargs"]["data"]
    assert data["text"] == "Рассказ про плов"
    assert data["voice"] == "alena"
    assert data["format"] == "mp3"


def test_yandex_omits_empty_folder_id(settings, monkeypatch):
    """Пустой folderId SpeechKit считает ошибкой — его не должно быть в теле."""
    settings.tts_provider = "yandex"
    captured = {}
    monkeypatch.setattr(
        gen.httpx, "post", lambda url, **kw: captured.update(kw) or FakeResponse(content=b"ok")
    )

    synthesize_speech("текст")

    assert "folderId" not in captured["data"]


def test_yandex_sends_folder_id_when_configured(settings, monkeypatch):
    settings.tts_provider = "yandex"
    settings.yandex_tts_folder_id = "b1gfolder"
    captured = {}
    monkeypatch.setattr(
        gen.httpx, "post", lambda url, **kw: captured.update(kw) or FakeResponse(content=b"ok")
    )

    synthesize_speech("текст")

    assert captured["data"]["folderId"] == "b1gfolder"


def test_yandex_without_key_explains_what_to_do(settings, monkeypatch):
    settings.tts_provider = "yandex"
    settings.yandex_tts_api_key = None

    with pytest.raises(GenerationError, match="YANDEX_TTS_API_KEY"):
        synthesize_speech("текст")


def test_yandex_surfaces_provider_error(settings, monkeypatch):
    settings.tts_provider = "yandex"
    monkeypatch.setattr(
        gen.httpx, "post", lambda url, **kw: FakeResponse(status_code=401, payload={"e": "bad"})
    )

    with pytest.raises(GenerationError, match="401"):
        synthesize_speech("текст")


def test_unknown_provider_is_refused_by_name(settings):
    settings.tts_provider = "sberspeech"

    with pytest.raises(GenerationError, match="sberspeech"):
        synthesize_speech("текст")


def test_empty_text_is_refused_before_any_provider(settings):
    """Проверка текста идёт до выбора провайдера — иначе пустой ключ маскировал бы её."""
    settings.tts_provider = "yandex"
    settings.yandex_tts_api_key = None

    with pytest.raises(GenerationError, match="Пустой текст"):
        synthesize_speech("   ")


def test_no_warnings_when_all_keys_are_in_place(settings):
    assert missing_key_warnings(image=True, audio=True) == []


def test_warns_that_audio_is_queued_without_a_yandex_key(settings):
    settings.tts_provider = "yandex"
    settings.yandex_tts_api_key = None

    warnings = missing_key_warnings(image=False, audio=True)

    assert len(warnings) == 1
    assert "озвучки запущена" in warnings[0]
    assert "YANDEX_TTS_API_KEY" in warnings[0]


def test_warns_about_a_missing_elevenlabs_key(settings):
    settings.elevenlabs_api_key = None

    warnings = missing_key_warnings(image=False, audio=True)

    assert len(warnings) == 1
    assert "ELEVENLABS_API_KEY" in warnings[0]


def test_key_of_the_other_provider_does_not_help(settings):
    """Ключ ElevenLabs не спасает залив, если озвучивает Yandex, и наоборот."""
    settings.tts_provider = "yandex"
    settings.yandex_tts_api_key = None
    settings.elevenlabs_api_key = "eleven-key"

    assert missing_key_warnings(image=False, audio=True)


def test_unknown_provider_is_reported_before_the_import_starts(settings):
    settings.tts_provider = "magnific"

    warnings = missing_key_warnings(image=False, audio=True)

    assert len(warnings) == 1
    assert "TTS_PROVIDER" in warnings[0]


def test_missing_image_key_is_reported_too(settings):
    settings.magnific_api_key = None

    warnings = missing_key_warnings(image=True, audio=False)

    assert len(warnings) == 1
    assert "MAGNIFIC_API_KEY" in warnings[0]


def test_both_keys_missing_give_two_warnings(settings):
    settings.magnific_api_key = None
    settings.elevenlabs_api_key = None

    assert len(missing_key_warnings(image=True, audio=True)) == 2


def test_nothing_is_checked_for_generation_that_was_not_ordered(settings):
    """Галки сняты — предупреждать не о чем, даже без единого ключа."""
    settings.magnific_api_key = None
    settings.elevenlabs_api_key = None
    settings.yandex_tts_api_key = None

    assert missing_key_warnings(image=False, audio=False) == []
