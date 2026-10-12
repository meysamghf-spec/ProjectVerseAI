"""Environment configuration. Secrets are read from the environment only."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    auth_mode: str = "development"
    dev_owner_id: str = "dev-user"
    api_key: str = ""
    api_owner_id: str = "api-owner"
    database_url: str = "sqlite:///./projectverse.db"
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "deterministic"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2
    max_body_bytes: int = 1_000_000
    engine_version: str = "1.0.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
