from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "restaurant-menu-importer-api"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://menu:menu@127.0.0.1:5432/menu_importer"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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
