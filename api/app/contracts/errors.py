"""Unified JSON error envelope for API + OpenAPI."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorBody(BaseModel):
    """Standard error payload — safe for clients (no stack traces)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable summary.")
    failed_step: str | None = Field(default=None, description="Pipeline stage when applicable.")
    trace_id: str | None = Field(default=None, description="Langfuse / correlation id when available.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured diagnostics (e.g. validation issues).",
    )


class ErrorResponse(BaseModel):
    error: ApiErrorBody


def error_response(
    *,
    code: str,
    message: str,
    failed_step: str | None = None,
    trace_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorResponse(
        error=ApiErrorBody(
            code=code,
            message=message,
            failed_step=failed_step,
            trace_id=trace_id,
            details=details,
        )
    ).model_dump()
