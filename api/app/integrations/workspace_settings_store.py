"""Supabase ``user_settings`` — Clerk ``user_id`` keyed rows (single persistence layer)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.integrations.postgrest_errors import is_missing_relation_error, missing_relation_log_suffix
from app.integrations.supabase import get_supabase_client
from app.integrations.supabase_tables import T_USER_SETTINGS, fq

log = logging.getLogger(__name__)

_DEFAULT_RAG: dict[str, Any] = {
    "enabled": True,
    "enterprise_case_studies": True,
    "freelance_win_memory": True,
}


def get_workspace_settings_row(clerk_user_id: str) -> dict[str, Any] | None:
    """Return a dict shaped like the legacy ``workspace_settings`` row for API/workspace agents."""
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    try:
        res = (
            sb.table(T_USER_SETTINGS)
            .select("*")
            .eq("user_id", clerk_user_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        msg = f"user_settings read {fq(T_USER_SETTINGS)} failed: {e}"
        if is_missing_relation_error(e):
            log.warning("%s%s", msg, missing_relation_log_suffix(e))
        else:
            log.debug("%s", msg)
        return None
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    r = rows[0]
    prefs = r.get("preferences") if isinstance(r.get("preferences"), dict) else {}
    rag = {**_DEFAULT_RAG, **(prefs.get("rag_config") if isinstance(prefs.get("rag_config"), dict) else {})}
    mode = str(r.get("mode") or "auto").strip().lower()
    if mode in ("auto", "enterprise", "freelance"):
        rag["proposal_mode"] = mode
    rag["enabled"] = bool(r.get("rag_enabled", rag.get("enabled", True)))
    om = str(prefs.get("openrouter_model_primary") or prefs.get("openrouter_chat_model") or "").strip()[:200]
    return {
        "user_id": str(r.get("user_id") or clerk_user_id),
        "tone": str(r.get("tone") or ""),
        "writing_style": str(prefs.get("writing_style") or ""),
        "company_profile": prefs.get("company_profile") if isinstance(prefs.get("company_profile"), dict) else {},
        "rag_config": rag,
        "openrouter_model_primary": om,
        "updated_at": r.get("updated_at"),
    }


def upsert_workspace_settings_full(clerk_user_id: str, data: dict[str, Any]) -> bool:
    """Upsert full settings (caller merges with existing for PATCH semantics)."""
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        log.warning("user_settings upsert skipped: no supabase client or user_id")
        return False
    rag = {**_DEFAULT_RAG, **(data.get("rag_config") if isinstance(data.get("rag_config"), dict) else {})}
    pm = str(rag.get("proposal_mode") or "auto").strip().lower()
    mode = pm if pm in ("auto", "enterprise", "freelance") else "auto"
    cur = get_workspace_settings_row(clerk_user_id) or {}
    prev_om = str(cur.get("openrouter_model_primary") or "").strip()[:200]
    if "openrouter_model_primary" in data:
        next_om = str(data.get("openrouter_model_primary") or "").strip()[:200]
    else:
        next_om = prev_om
    prefs: dict[str, Any] = {
        "writing_style": str(data.get("writing_style") or "")[:8000],
        "company_profile": data.get("company_profile") if isinstance(data.get("company_profile"), dict) else {},
        "rag_config": rag,
    }
    if "openrouter_model_primary" in data:
        if next_om:
            prefs["openrouter_model_primary"] = next_om
    elif prev_om:
        prefs["openrouter_model_primary"] = prev_om
    payload: dict[str, Any] = {
        "user_id": clerk_user_id,
        "tone": str(data.get("tone") or "")[:4000],
        "mode": mode,
        "rag_enabled": bool(rag.get("enabled", True)),
        "preferences": prefs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        sb.table(T_USER_SETTINGS).upsert(payload, on_conflict="user_id").execute()
    except Exception as e:  # noqa: BLE001
        msg = f"user_settings upsert {fq(T_USER_SETTINGS)} failed: {e}"
        if is_missing_relation_error(e):
            log.warning("%s%s", msg, missing_relation_log_suffix(e))
        else:
            log.warning("%s", msg)
        return False
    return True
