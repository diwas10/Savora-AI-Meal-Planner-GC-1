"""Application settings loaded from the repository root `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    jwt_secret_key: str = Field(default="dev-secret-key-change-in-production-32bytes")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)

    qwen_api_key: str = Field(default="")
    qwen_model_name: str = Field(default="Qwen/Qwen2.5-7B-Instruct")
    qwen_base_url: str = Field(default="https://api.openai.com/v1")

    cors_origins: str = Field(default="http://localhost:3000")

    catalogue_dir: Path = Field(default=REPO_ROOT / "Data/catalogue")
    model_dir: Path = Field(default=REPO_ROOT / "Data/models")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
