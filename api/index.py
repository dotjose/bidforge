"""Vercel Python serverless ASGI entry — exposes the production FastAPI application."""

from __future__ import annotations

import sys
from pathlib import Path

_api_dir = Path(__file__).resolve().parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from app.main import app  # noqa: E402

__all__ = ["app"]
