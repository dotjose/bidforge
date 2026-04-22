from __future__ import annotations

from typing import Any


class PipelineStepError(RuntimeError):
    """Raised when a pipeline stage cannot produce a valid contract."""

    def __init__(self, step: str, message: str, *, partial: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.step = step
        self.partial = partial or {}


class LLMTransportError(PipelineStepError):
    """Upstream model or transport failure."""

    def __init__(self, step: str, message: str, *, partial: dict[str, Any] | None = None) -> None:
        super().__init__(step, message, partial=partial)
