"""Central settings entrypoint — single import path for `settings` (defined in `app.core.config`)."""

from app.core.config import settings

__all__ = ["settings"]
