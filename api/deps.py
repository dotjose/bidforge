"""FastAPI dependencies (auth + request-scoped helpers)."""

from __future__ import annotations

from app.core.auth import CurrentUser, get_current_user

__all__ = ["CurrentUser", "get_current_user"]
