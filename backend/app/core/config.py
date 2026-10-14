from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHELFWISE_", extra="ignore")

    app_name: str = "Shelfwise API"
    # Injected at image build time from the Git commit, so every response can be traced back
    # to the exact source that produced it.
    app_version: str = "dev"
    database_url: str = "postgresql+psycopg://shelfwise:shelfwise@localhost:5432/shelfwise"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
