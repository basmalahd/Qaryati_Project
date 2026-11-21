from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # External geocoding provider (Nominatim / OpenStreetMap by default)
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    # Nominatim's usage policy requires an identifying User-Agent (ideally with a contact).
    geocoding_user_agent: str = "QaryatiCourseProject/1.0"
    geocoding_timeout_seconds: float = 5.0
    geocoding_max_retries: int = 2
    geocoding_min_interval_seconds: float = 1.1  # provider allows max 1 request/second
    geocoding_cache_ttl_seconds: int = 86400
    geocoding_empty_cache_ttl_seconds: int = 3600
    geocoding_cache_max_entries: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("jwt_secret_key")
    @classmethod
    def secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v


settings = Settings()
