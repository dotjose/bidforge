from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

from opentelemetry.sdk.trace import TracerProvider

from app.core.config import settings

if TYPE_CHECKING:
    from langfuse import Langfuse

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_tracer_provider: TracerProvider | None = None
_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse | None:
    """Return a process-wide Langfuse client, or None when tracing is off.

    Uses one :class:`~opentelemetry.sdk.trace.TracerProvider` per process so the
    Langfuse span processor is not attached to a discarded provider (which would
    drop exports). Langfuse Cloud OTLP expects ``x-langfuse-ingestion-version: 4``
    for v4 ingestion (SDK default exporter merges ``additional_headers``).
    """
    global _tracer_provider, _client

    if settings.env == "test":
        return None
    pk = settings.langfuse_public_key.strip()
    sk = settings.langfuse_secret_key.strip()
    if not pk or not sk:
        return None
    if sk.startswith("pk-lf-"):
        _log.error(
            "Langfuse: LANGFUSE_SECRET_KEY looks like a public key (pk-lf-). "
            "Use the secret key (sk-lf-…) from Project → API keys; tracing disabled until fixed.",
        )
        return None

    with _lock:
        if _client is not None:
            return _client

        if os.environ.get("OTEL_SDK_DISABLED", "false").lower() == "true":
            _log.warning(
                "Langfuse: OTEL_SDK_DISABLED=true — OpenTelemetry is disabled; "
                "Langfuse may not export spans. Unset OTEL_SDK_DISABLED for this process.",
            )

        from langfuse import Langfuse

        if _tracer_provider is None:
            _tracer_provider = TracerProvider()

        base = settings.langfuse_base_url or "https://cloud.langfuse.com"

        _client = Langfuse(
            public_key=pk,
            secret_key=sk,
            base_url=base,
            environment=settings.langfuse_tracing_environment,
            tracing_enabled=True,
            tracer_provider=_tracer_provider,
            additional_headers={"x-langfuse-ingestion-version": "4"},
        )
        return _client
