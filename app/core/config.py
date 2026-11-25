import json
import os
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = (
    "change_me", "changeme", "example", "placeholder", "secret",
    "password", "default", "qaryati_local_dev",
)
_MIN_DISTINCT_SECRET_CHARS = 10


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


def _parse_origins(raw: str) -> list[str]:
    """Parse CORS_ORIGINS as comma-separated origins or a JSON string array."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith(("[", "{")):
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("CORS_ORIGINS looks like JSON but is not valid JSON") from exc
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise ValueError("CORS_ORIGINS JSON must be an array of strings")
    else:
        items = raw.split(",")
    return [item.strip() for item in items if item.strip()]


class Settings(BaseSettings):
    app_env: AppEnv = AppEnv.DEVELOPMENT
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cors_origins: str = ""

    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "QaryatiCourseProject/1.0"
    geocoding_timeout_seconds: float = 5.0
    geocoding_max_retries: int = 2
    geocoding_min_interval_seconds: float = 1.1
    geocoding_cache_ttl_seconds: int = 86400
    geocoding_empty_cache_ttl_seconds: int = 3600
    geocoding_cache_max_entries: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return _parse_origins(self.cors_origins)

    @field_validator("app_env", mode="before")
    @classmethod
    def normalise_app_env(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("jwt_secret_key")
    @classmethod
    def secret_must_be_strong(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return value

    @field_validator("cors_origins")
    @classmethod
    def cors_origins_must_parse(cls, value: str) -> str:
        _parse_origins(value)
        return value

    @model_validator(mode="after")
    def production_must_be_hardened(self) -> "Settings":
        if self.app_env is not AppEnv.PRODUCTION:
            return self

        for origin in self.cors_origins_list:
            if "*" in origin:
                raise ValueError("CORS_ORIGINS must not contain wildcards in production")
            parts = urlsplit(origin)
            if (
                    parts.scheme not in ("http", "https")
                    or not parts.netloc
                    or parts.path
                    or parts.query
                    or parts.fragment
            ):
                raise ValueError(
                    f"Invalid CORS origin {origin!r}: use scheme://host[:port] "
                    "with no path or trailing slash"
                )

        lowered = self.jwt_secret_key.lower()
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            raise ValueError("JWT_SECRET_KEY looks like a default or placeholder value")
        if len(set(self.jwt_secret_key)) < _MIN_DISTINCT_SECRET_CHARS:
            raise ValueError("JWT_SECRET_KEY is too weak (not enough distinct characters)")
        return self


def build_settings() -> Settings:
    """Read .env for development/tests, but never for production."""
    if os.environ.get("APP_ENV", "").strip().lower() == AppEnv.PRODUCTION:
        return Settings(_env_file=None)

    loaded = Settings()
    if loaded.app_env is AppEnv.PRODUCTION:
        raise RuntimeError(
            "APP_ENV=production was found only in a .env file. Production must be "
            "configured with real environment variables, not a .env file."
        )
    return loaded


settings = build_settings()
