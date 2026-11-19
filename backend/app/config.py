"""Application settings, read from environment variables and the repository's `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_path: Path = Path("data/naturecheckpoint.db")
    public_base_url: str = "http://localhost:8000"

    @field_validator("database_path")
    @classmethod
    def _resolve_relative_path(cls, value: Path) -> Path:
        # Relative paths are relative to the repository root, not to the current working directory.
        return value if value.is_absolute() else REPO_ROOT / value

    @property
    def cookies_secure(self) -> bool:
        return self.public_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
