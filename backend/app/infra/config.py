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
    log_level: str = "info"
    database_url: str = "postgresql+psycopg://advisory:advisory@localhost:5432/advisory"

    # The application connects as a NON-superuser role so Postgres RLS applies to it
    # (superusers bypass RLS). Migrations/seed use database_url (the owner); the app +
    # worker use this. Falls back to database_url when a separate role isn't configured.
    app_database_url: str = ""

    # Redis (rate limiting + Celery broker). Empty ⇒ rate limiting uses an in-process
    # fallback (fine for single-process dev/tests; Redis is needed for multi-replica).
    redis_url: str = ""

    # Shared secret used to verify the session token minted by the Next.js BFF after it
    # validates the Auth.js session (ADR-0009). Empty ⇒ auth fails closed.
    auth_secret: str = ""
    auth_issuer: str = "advisory-bff"
    auth_audience: str = "advisory-api"
    local_email_verification_tokens: bool = False

    # Public base URL of the web app — used to build the links inside verification and
    # password-reset emails (e.g. {app_base_url}/verify-email?token=...).
    app_base_url: str = "http://localhost:3000"

    # Email delivery. `console` (default) logs the message and is safe with no creds —
    # used for local dev alongside local_email_verification_tokens. `smtp` sends via any
    # SMTP server (e.g. Mailtrap). `resend` sends via the Resend HTTP API.
    email_provider: str = "console"
    email_from: str = "AI Advisory <onboarding@resend.dev>"
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 60

    # SMTP (used when email_provider == "smtp"; Mailtrap works out of the box here).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # Resend (used when email_provider == "resend").
    resend_api_key: str = ""

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
    max_upload_bytes: int = 26_214_400  # 25 MiB for PDF/DOCX uploads
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def effective_app_database_url(self) -> str:
        """The non-superuser app connection if configured, else the owner connection."""
        return self.app_database_url or self.database_url

    @property
    def llm_enabled(self) -> bool:
        # A blank/whitespace key (or a stray inline-comment value) means "use the mock".
        key = self.openrouter_api_key.strip()
        return bool(key) and not key.startswith("#")


@lru_cache
def get_settings() -> Settings:
    return Settings()
