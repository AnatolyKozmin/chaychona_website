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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
