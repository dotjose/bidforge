"""Supabase workspace_settings — Clerk user_id keyed rows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.integrations.supabase import get_supabase_client

log = logging.getLogger(__name__)

_DEFAULT_RAG: dict[str, Any] = {
    "enabled": True,
    "enterprise_case_studies": True,
    "freelance_win_memory": True,
}


def get_workspace_settings_row(clerk_user_id: str) -> dict[str, Any] | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    try:
        res = (
            sb.table("workspace_settings")
            .select("*")
            .eq("user_id", clerk_user_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        log.debug("workspace_settings read failed: %s", e)
        return None
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    return rows[0]


def upsert_workspace_settings_full(clerk_user_id: str, data: dict[str, Any]) -> bool:
    """Replace-or-create full row (caller merges with existing for PATCH semantics)."""
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return False
    rag = {**_DEFAULT_RAG, **(data.get("rag_config") if isinstance(data.get("rag_config"), dict) else {})}
    payload: dict[str, Any] = {
        "user_id": clerk_user_id,
        "company_profile": data.get("company_profile") if isinstance(data.get("company_profile"), dict) else {},
        "tone": str(data.get("tone") or "")[:4000],
        "writing_style": str(data.get("writing_style") or "")[:8000],
        "rag_config": rag,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        sb.table("workspace_settings").upsert(payload, on_conflict="user_id").execute()
    except Exception as e:  # noqa: BLE001
        log.warning("workspace_settings upsert failed: %s", e)
        return False
    return True
