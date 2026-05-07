from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "restaurant-menu-importer-api"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://menu:menu@127.0.0.1:5432/menu_importer"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_use_fake: bool = False
    gemini_request_timeout_seconds: float = 30.0
    gemini_max_retries: int = 2
    gemini_min_confidence: float = 0.55
    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
