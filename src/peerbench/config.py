"""Environment-backed configuration, loaded from `.env.local`."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    fdic_api_key: str | None = Field(default=None, alias="FDIC_API_KEY")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    database_url: str = Field(alias="DATABASE_URL")

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy expects `postgresql+pg8000://...`. `.env.local` carries
        the canonical `postgresql://` form — rewrite the scheme here."""
        url = self.database_url
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+pg8000://" + url[len("postgresql://") :]
        if url.startswith("postgres://"):
            return "postgresql+pg8000://" + url[len("postgres://") :]
        return url


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
