from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from langfuse import Langfuse


def get_langfuse_client() -> Langfuse | None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url or "https://cloud.langfuse.com",
        environment=settings.langfuse_tracing_environment,
    )
