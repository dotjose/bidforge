from __future__ import annotations

from typing import Any


class FailedPipeline(Exception):
    """Propagates to HTTP layer with Langfuse trace id."""

    def __init__(
        self,
        *,
        trace_id: str,
        failed_step: str,
        message: str,
        partial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.trace_id = trace_id
        self.failed_step = failed_step
        self.partial = partial or {}
