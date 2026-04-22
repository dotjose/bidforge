"""Normalize all HTTP errors to the BidForge error envelope."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts.errors import error_response

log = logging.getLogger(__name__)


def _http_status_to_code(status_code: int) -> str:
    mapping: dict[int, str] = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_502_BAD_GATEWAY: "PIPELINE_FAILED",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
        status.HTTP_504_GATEWAY_TIMEOUT: "TIMEOUT",
    }
    return mapping.get(status_code, "INTERNAL_ERROR")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail and isinstance(detail["error"], dict):
        body = detail
    else:
        msg = detail if isinstance(detail, str) else str(detail)
        body = error_response(
            code=_http_status_to_code(exc.status_code),
            message=msg,
        )
    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errs = exc.errors()
    message = errs[0].get("msg", "Validation failed") if errs else "Validation failed"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            code="VALIDATION_ERROR",
            message=message,
            details={"errors": errs},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
        ),
    )
