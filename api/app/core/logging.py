import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    level = getattr(logging, str(settings.log_level).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    # Langfuse uses OTEL HTTP export; disable exporter loggers only when tracing is off (no keys / test).
    if not settings.is_langfuse_tracing_enabled():
        logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").disabled = True
        logging.getLogger("opentelemetry.sdk._shared_internal").disabled = True
