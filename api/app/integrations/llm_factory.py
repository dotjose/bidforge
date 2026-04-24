from __future__ import annotations

import os
from typing import Any

from bidforge_shared import LLMClient, OpenRouterLLM

from app.core.config import settings


def build_llm_from_settings(workspace_snapshot: dict[str, Any] | None = None) -> LLMClient:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    primary = settings.openrouter_model_primary
    if workspace_snapshot:
        s = workspace_snapshot.get("settings")
        if isinstance(s, dict):
            m = str(s.get("openrouter_model_primary") or "").strip()
            if m:
                primary = m[:200]
    return OpenRouterLLM(
        api_key=settings.openrouter_api_key,
        primary_model=primary,
        fallback_model=settings.openrouter_model_fallback,
        embedding_model=settings.openrouter_embedding_model,
        timeout_s=settings.per_agent_timeout_s,
        http_referer=settings.openrouter_http_referer or "https://bidforge.app",
        app_title=os.getenv("OPENROUTER_APP_TITLE", "BidForge API"),
    )
