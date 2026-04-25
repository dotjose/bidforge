from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from app.core.config import settings
from app.integrations.postgrest_errors import is_column_missing_error, is_missing_relation_error
from app.integrations.supabase_tables import T_PROPOSAL_EVENTS, T_PROPOSALS

if TYPE_CHECKING:
    from supabase import Client

log = logging.getLogger(__name__)

# Set once at app startup (see run_startup_supabase_readiness_check).
_supabase_proposals_readable: bool | None = None
_startup_readiness_executed: bool = False


def supabase_project_ref_from_url(url: str | None = None) -> str | None:
    """Hostname segment for ``*.supabase.co`` URLs (matches Dashboard project ref)."""
    raw = (url if url is not None else settings.supabase_url or "").strip().rstrip("/")
    if not raw:
        return None
    try:
        host = (urlparse(raw).hostname or "").lower()
    except ValueError:
        return None
    if not host.endswith(".supabase.co"):
        return None
    return host[: -len(".supabase.co")] or None


def get_supabase_proposals_readable() -> bool | None:
    """``True`` if ``public.proposals`` is visible to PostgREST; ``None`` if not probed yet or skipped."""
    return _supabase_proposals_readable


def run_startup_supabase_readiness_check() -> None:
    """Log a single clear ERROR when credentials load but pipeline tables are on a different project."""
    global _supabase_proposals_readable, _startup_readiness_executed
    if _startup_readiness_executed:
        return
    _startup_readiness_executed = True
    if "pytest" in sys.modules:
        return
    sb = get_supabase_client()
    if sb is None:
        return
    try:
        sb.table(T_PROPOSALS).select("id").limit(1).execute()
    except Exception as e:  # noqa: BLE001 — PostgREST / network
        _supabase_proposals_readable = False
        if is_missing_relation_error(e):
            ref = supabase_project_ref_from_url() or "(could not parse project ref from SUPABASE_URL)"
            log.error(
                "Supabase project ref=%r: table %s is not visible to PostgREST (%s). "
                "SQL migrations must be applied to the **same** Supabase project as SUPABASE_URL "
                "(Dashboard ref must match). Running migration_003 on project A while api/.env points "
                "at project B produces exactly this error.",
                ref,
                T_PROPOSALS,
                e,
            )
        else:
            log.warning("Supabase readiness check failed for %s: %s", T_PROPOSALS, e)
        return
    _supabase_proposals_readable = True


SupabaseProposalProbe = Literal["ok", "no_env", "missing_table", "error"]


def probe_supabase_proposals_table() -> SupabaseProposalProbe:
    """Live check for POST /proposal/run persistence gate (not only startup cache)."""
    sb = get_supabase_client()
    if sb is None:
        return "no_env"
    try:
        # Must include required source-of-truth columns (`input_text`) to catch stale schema cache early.
        sb.table(T_PROPOSALS).select("id,input_text,pipeline_mode").limit(1).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e) or is_column_missing_error(e):
            return "missing_table"
        log.warning("probe %s: %s", T_PROPOSALS, e)
        return "error"
    return "ok"


def probe_supabase_proposal_events_table() -> SupabaseProposalProbe:
    """Live check for ``public.proposal_events`` (DAG append-only trace)."""
    sb = get_supabase_client()
    if sb is None:
        return "no_env"
    try:
        sb.table(T_PROPOSAL_EVENTS).select("id").limit(1).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            return "missing_table"
        log.warning("probe %s: %s", T_PROPOSAL_EVENTS, e)
        return "error"
    return "ok"


def probe_supabase_proposal_persistence_bundle() -> SupabaseProposalProbe:
    """``proposals`` + ``proposal_events`` must both be visible when strict persistence is enforced."""
    a = probe_supabase_proposals_table()
    if a != "ok":
        return a
    return probe_supabase_proposal_events_table()


def get_supabase_client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    from supabase import create_client

    url = settings.supabase_url.strip().rstrip("/")
    key = settings.supabase_service_role_key.strip()
    return create_client(url, key)
