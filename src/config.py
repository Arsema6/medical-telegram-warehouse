"""Application configuration loaded from environment variables and YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNELS_PATH = PROJECT_ROOT / "config" / "channels.yaml"


class Settings(BaseSettings):
    """Runtime settings. Secrets come only from the environment."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "warehouse"
    db_password: str = "warehouse"
    db_name: str = "medical_warehouse"

    api_key: str = "dev-api-key-change-me"
    api_rate_limit_per_minute: int = 60

    api_id: str | None = None
    api_hash: str | None = None
    telegram_session_path: str = "session"
    telegram_message_limit: int = 200

    skip_yolo: bool = True
    log_level: str = "info"

    data_raw_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    data_processed_dir: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    demo_data_dir: Path = Field(default=PROJECT_ROOT / "data" / "demo")
    channels_file: Path = Field(default=CHANNELS_PATH)

    @field_validator("skip_yolo", mode="before")
    @classmethod
    def _parse_bool(cls, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @property
    def database_url(self) -> str:
        password = quote_plus(self.db_password)
        user = quote_plus(self.db_user)
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def psycopg2_kwargs(self) -> dict[str, Any]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "dbname": self.db_name,
        }

    def load_channels(self) -> list[dict[str, str]]:
        path = self.channels_file
        if not path.exists():
            raise FileNotFoundError(f"Channel config not found: {path}")
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        channels = payload.get("channels") or []
        if not channels:
            raise ValueError("config/channels.yaml must define at least one channel")
        return channels


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
