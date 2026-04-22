from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["production", "development", "test"] = "development"
    log_level: str = "info"

    clerk_issuer: str = ""
    clerk_secret_key: str = Field(default="", validation_alias="CLERK_SECRET_KEY")
    skip_auth: bool = False

    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
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
    openrouter_model_primary: str = "anthropic/claude-3.5-sonnet"
    openrouter_model_fallback: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_http_referer: str = "https://bidforge.app"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    pipeline_timeout_s: float = Field(default=120.0, ge=30.0, le=600.0)
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
    strict_no_raw_rfp_render: bool = Field(
        default=True,
        description="Reserved for exporters/UI guards — keep true in production.",
        validation_alias=AliasChoices("STRICT_NO_RAW_RFP_RENDER", "strict_no_raw_rfp_render"),
    )

    cors_allow_origins: str = Field(
        default="",
        description="Comma-separated extra CORS origins (e.g. https://app.example.com).",
    )

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
    if not settings.openrouter_api_key:
        raise RuntimeError("Missing OpenRouter key: set OPENROUTER_API_KEY in production")
    if not settings.skip_auth:
        if not settings.clerk_issuer.strip():
            raise RuntimeError("Missing CLERK_ISSUER in production (or set SKIP_AUTH for local only)")
        if not settings.clerk_secret_key.strip():
            raise RuntimeError("Missing CLERK_SECRET_KEY in production (or set SKIP_AUTH for local only)")
