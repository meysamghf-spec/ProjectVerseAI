"""Environment configuration. Secrets are read from the environment only."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_PASSWORDS = {"projectverse", "postgres", "password", "change-me", "change-me-local-only", "secret"}


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
    # Accounts mode
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    legacy_owner_id: str = ""
    session_hours: int = 12
    cookie_secure: bool | None = None
    login_max_failures: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def _blank_is_auto(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    def production_configuration_error(self) -> str | None:
        """Return a blocker when production would expose project data or a wildcard origin."""

        if not self.is_production:
            return None
        if self.auth_mode != "accounts":
            return "Production requires AUTH_MODE=accounts (per-user sign-in)."
        if "*" in self.cors_origin_list:
            return "Production CORS_ORIGINS cannot include '*'."
        if self.database_url.startswith("postgresql"):
            from urllib.parse import unquote, urlsplit

            password = unquote(urlsplit(self.database_url).password or "")
            if len(password) < 16 or password.lower() in WEAK_PASSWORDS:
                return "The database password must be at least 16 characters and not a placeholder."
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
