from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    bootstrap_superadmin_email: str = Field(alias="BOOTSTRAP_SUPERADMIN_EMAIL")
    bootstrap_superadmin_password: str = Field(alias="BOOTSTRAP_SUPERADMIN_PASSWORD")
    content_export_root: str | None = Field(default=None, alias="CONTENT_EXPORT_ROOT")

    # Фоновая генерация видео блюд (фото + озвучка → mp4 через ffmpeg)
    ffmpeg_binary: str = Field(default="ffmpeg", alias="FFMPEG_BINARY")
    video_worker_enabled: bool = Field(default=True, alias="VIDEO_WORKER_ENABLED")
    video_worker_poll_seconds: float = Field(default=3.0, alias="VIDEO_WORKER_POLL_SECONDS")
    video_worker_timeout_seconds: int = Field(default=600, alias="VIDEO_WORKER_TIMEOUT_SECONDS")

    # Генерация картинки ингредиентов. Magnific = бывший Freepik API,
    # ключ берётся в кабинете и кладётся в .env — без него стадия `image` падает
    # с внятной ошибкой, а текст и фото блюд всё равно заезжают.
    magnific_api_key: str | None = Field(default=None, alias="MAGNIFIC_API_KEY")
    magnific_api_base: str = Field(default="https://api.magnific.com", alias="MAGNIFIC_API_BASE")
    # Mystic — это сам эндпоинт, а `model` внутри него выбирает стиль. Допустимы
    # только realism / fluid / zen / flexible / super_real / editorial_portraits;
    # любое другое значение API отвергает. Для раскладки продуктов нужен realism.
    magnific_image_model: str = Field(default="realism", alias="MAGNIFIC_IMAGE_MODEL")

    # Озвучка. В REST API Magnific text-to-speech нет (только музыка, SFX и
    # audio-isolation), а их же TTS внутри — это ElevenLabs. Напрямую к
    # ElevenLabs с российского IP не пробиться (они отвечают редиректом на
    # статью про страновые ограничения), поэтому провайдер вынесен в настройку:
    # `elevenlabs` | `yandex`. Пайплайн от выбора не зависит — меняется только
    # эта строка и ключ рядом.
    tts_provider: str = Field(default="elevenlabs", alias="TTS_PROVIDER")

    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_api_base: str = Field(default="https://api.elevenlabs.io", alias="ELEVENLABS_API_BASE")
    elevenlabs_voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", alias="ELEVENLABS_VOICE_ID")
    elevenlabs_model: str = Field(default="eleven_multilingual_v2", alias="ELEVENLABS_MODEL")

    # Yandex SpeechKit — запасной провайдер озвучки: работает из России и
    # платится рублями. `folder_id` нужен, только если ключ не привязан к
    # сервисному аккаунту. Голоса: alena, filipp, ermil, jane, omazh, zahar.
    yandex_tts_api_key: str | None = Field(default=None, alias="YANDEX_TTS_API_KEY")
    yandex_tts_api_base: str = Field(
        default="https://tts.api.cloud.yandex.net", alias="YANDEX_TTS_API_BASE"
    )
    yandex_tts_folder_id: str | None = Field(default=None, alias="YANDEX_TTS_FOLDER_ID")
    yandex_tts_voice: str = Field(default="alena", alias="YANDEX_TTS_VOICE")
    yandex_tts_lang: str = Field(default="ru-RU", alias="YANDEX_TTS_LANG")

    # Общий потолок ожидания внешнего провайдера на одно задание.
    generation_timeout_seconds: int = Field(default=300, alias="GENERATION_TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
