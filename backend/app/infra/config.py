"""Application settings (12-factor, environment-driven).

Mirrors the surface documented in .env.example. Secrets come from the environment /
secrets manager — never hardcoded (docs/security/security-review.md §8). Defaults are
safe for local dev only.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://advisory:advisory@localhost:5432/advisory"

    # Shared secret used to verify the session token minted by the Next.js BFF after it
    # validates the Auth.js session (ADR-0009). Empty ⇒ auth fails closed.
    auth_secret: str = ""
    auth_issuer: str = "advisory-bff"
    auth_audience: str = "advisory-api"

    # LLM / OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_default_model: str = "anthropic/claude-3.5-sonnet"
    llm_request_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    # Object storage (MinIO/S3) — report PDFs, documents
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "advisory-documents"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"  # noqa: S105 - local-dev default, overridden by env
    storage_region: str = "us-east-1"

    # API security
    rate_limit_per_minute: int = 120
    max_request_bytes: int = 1_048_576
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def llm_enabled(self) -> bool:
        # A blank/whitespace key (or a stray inline-comment value) means "use the mock".
        key = self.openrouter_api_key.strip()
        return bool(key) and not key.startswith("#")


@lru_cache
def get_settings() -> Settings:
    return Settings()
