"""Application settings loaded from the repository root `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]

# Known development defaults that must never sign tokens outside development and tests.
DEV_JWT_SECRET = "dev-secret-key-change-in-production-32bytes"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:<YOUR-DB-PASSWORD>@localhost:5432/postgres"
    )
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)

    # Team decision (21 Oct 2026): a small quantized Qwen in local Ollama; no key needed.
    qwen_provider: Literal["ollama", "openai", "none"] = "ollama"
    qwen_base_url: str = Field(default="http://localhost:11434")
    qwen_model_name: str = Field(default="qwen3:0.6b")
    qwen_api_key: str = Field(default="")
    qwen_timeout_s: float = Field(default=8.0, gt=0, le=60)

    cors_origins: str = Field(default="http://localhost:3000")

    # Member 2's compact B1 swap proof: "required" saves a swap only when it is VALID and
    # independently verified; "record" saves CSP-feasible swaps and records the proof;
    # "off" skips it (tests, slow machines).
    swap_proof_mode: Literal["required", "record", "off"] = "required"

    catalogue_dir: Path = Field(default=REPO_ROOT / "Data/catalogue")
    model_dir: Path = Field(default=REPO_ROOT / "Data/models")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def check_secrets(self) -> None:
        """Refuse to run in production with the development or a weak JWT secret."""
        if self.app_env != "production":
            return
        secret = self.jwt_secret_key.strip()
        if (
            secret == DEV_JWT_SECRET
            or secret.startswith("<")
            or len(secret) < MIN_JWT_SECRET_LENGTH
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a random value of at least "
                f"{MIN_JWT_SECRET_LENGTH} characters in production (openssl rand -hex 32)"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
