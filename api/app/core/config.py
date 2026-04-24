from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prefer `from app.config.settings import settings` in new code (re-exports this module).
#
# Load api/.env by absolute path so Supabase and other keys work when the process
# cwd is the monorepo root (turbo, scripts) or any subdirectory — not only `api/`.
_API_ROOT = Path(__file__).resolve().parents[2]
_API_ENV = _API_ROOT / ".env"
_ENV_FILE: tuple[str, ...] = (str(_API_ENV),) if _API_ENV.is_file() else (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    env: Literal["production", "development", "test"] = "development"
    log_level: str = "info"

    clerk_issuer: str = ""
    clerk_secret_key: str = Field(default="", validation_alias="CLERK_SECRET_KEY")
    skip_auth: bool = False

    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias="LANGFUSE_BASE_URL",
    )
    langfuse_tracing_environment: str = Field(
        default="development",
        validation_alias="LANGFUSE_TRACING_ENVIRONMENT",
    )

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_users_pk_column: str = Field(
        default="id",
        description=(
            "PostgREST `select()` column for `public.users` primary key (uuid). "
            "Use if your DB uses e.g. `user_id` instead of `id`."
        ),
        validation_alias="SUPABASE_USERS_PK_COLUMN",
    )

    openrouter_api_key: str = ""
    openrouter_model_primary: str = Field(
        default="anthropic/claude-3.5-sonnet",
        validation_alias="OPENROUTER_MODEL_PRIMARY",
    )
    openrouter_model_fallback: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_http_referer: str = "https://bidforge.app"

    pipeline_timeout_s: float = Field(
        default=360.0,
        ge=30.0,
        le=600.0,
        description=(
            "Hard cap for the full proposal DAG (async wait_for around execute_proposal_pipeline). "
            "120s is often too low for enterprise paths with OpenRouter primary+fallback retries."
        ),
        validation_alias="PIPELINE_TIMEOUT_S",
    )
    per_agent_timeout_s: float = Field(default=30.0, ge=5.0, le=120.0)
    rfp_max_chars: int = Field(default=120_000, ge=1, le=500_000)

    rate_limit_per_minute: int = Field(default=30, ge=0)

    require_rag_memory: bool = Field(
        default=True,
        description=(
            "When true, log loudly when indexed context is missing; generation still completes "
            "(fallback / cold-start behavior). Set false to silence warnings in tests."
        ),
        validation_alias="REQUIRE_RAG_MEMORY",
    )

    rag_runtime_enabled: bool = Field(
        default=True,
        description="Global kill-switch for retrieval (workspace settings still apply when true).",
        validation_alias=AliasChoices("RAG_ENABLED", "rag_runtime_enabled"),
    )
    memory_injection_enabled: bool = Field(
        default=True,
        description="When false, pipeline skips embedding retrieval (drafts use brief only).",
        validation_alias=AliasChoices("MEMORY_ENABLED", "memory_injection_enabled"),
    )
    strict_proposal_persistence: bool = Field(
        default=False,
        description=(
            "When true (or ENV=production), POST /api/proposal/run fails if Supabase is not ready "
            "or insert_proposal_run does not return an id."
        ),
        validation_alias="STRICT_PROPOSAL_PERSISTENCE",
    )

    cors_allow_origins: str = Field(
        default="",
        description="Comma-separated extra CORS origins (e.g. https://app.example.com).",
    )

    @field_validator(
        "langfuse_public_key",
        "langfuse_secret_key",
        "langfuse_tracing_environment",
        mode="after",
    )
    @classmethod
    def _strip_langfuse_fields(cls, v: object) -> str:
        return str(v or "").strip()

    @field_validator("langfuse_base_url", mode="after")
    @classmethod
    def _normalize_langfuse_base_url(cls, v: object) -> str:
        s = str(v or "").strip().rstrip("/")
        return s or "https://cloud.langfuse.com"

    @field_validator("log_level", mode="before")
    @classmethod
    def _lower_log_level(cls, v: object) -> object:
        return str(v).lower() if v is not None else v

    @field_validator("require_rag_memory", mode="before")
    @classmethod
    def _coerce_require_rag_memory(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return v

    @field_validator("strict_proposal_persistence", mode="before")
    @classmethod
    def _coerce_strict_proposal_persistence(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return v

    def is_langfuse_tracing_enabled(self) -> bool:
        """True when `get_langfuse_client()` would return a client (keys set; never in ENV=test)."""
        if self.env == "test":
            return False
        sk = self.langfuse_secret_key.strip()
        if sk.startswith("pk-lf-"):
            return False
        return bool(self.langfuse_public_key.strip() and sk)

    def persistence_strict_enforced(self) -> bool:
        """Tests never enforce; production always; development follows STRICT_PROPOSAL_PERSISTENCE."""
        if self.env == "test":
            return False
        if self.env == "production":
            return True
        return self.strict_proposal_persistence

    def supabase_configured(self) -> bool:
        """True when URL + service role key are present (client may still fail at runtime)."""
        return bool(self.supabase_url.strip() and self.supabase_service_role_key.strip())

    @field_validator("supabase_url", "supabase_service_role_key", mode="after")
    @classmethod
    def _strip_supabase_secrets(cls, v: object) -> str:
        return str(v or "").strip()

    @field_validator("supabase_users_pk_column", mode="after")
    @classmethod
    def _sanitize_users_pk_column(cls, v: object) -> str:
        s = str(v or "id").strip() or "id"
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        if not s or any(ch not in allowed for ch in s):
            return "id"
        return s


settings = Settings()


def validate_production_settings() -> None:
    """Fail fast in production — no silent missing LLM credentials."""
    if settings.env != "production":
        return
    if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
        raise RuntimeError(
            "Missing Supabase credentials: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "(persistence is Supabase-only in production)."
        )
    if not settings.openrouter_api_key:
        raise RuntimeError("Missing OpenRouter key: set OPENROUTER_API_KEY in production")
    if not settings.skip_auth:
        if not settings.clerk_issuer.strip():
            raise RuntimeError("Missing CLERK_ISSUER in production (or set SKIP_AUTH for local only)")
        if not settings.clerk_secret_key.strip():
            raise RuntimeError("Missing CLERK_SECRET_KEY in production (or set SKIP_AUTH for local only)")
