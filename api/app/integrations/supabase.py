from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from supabase import Client


def get_supabase_client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    from supabase import create_client

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
