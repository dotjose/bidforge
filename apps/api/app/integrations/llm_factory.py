from __future__ import annotations

import os

from bidforge_shared import LLMClient, OpenRouterLLM

from app.core.config import settings


def build_llm_from_settings() -> LLMClient:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    return OpenRouterLLM(
        api_key=settings.openrouter_api_key,
        primary_model=settings.openrouter_model_primary,
        fallback_model=settings.openrouter_model_fallback,
        embedding_model=settings.openrouter_embedding_model,
        timeout_s=settings.per_agent_timeout_s,
        http_referer=settings.openrouter_http_referer or "https://bidforge.app",
        app_title=os.getenv("OPENROUTER_APP_TITLE", "BidForge API"),
    )
