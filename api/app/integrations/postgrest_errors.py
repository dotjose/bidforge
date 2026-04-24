"""Detect PostgREST / Supabase errors so callers can degrade gracefully (no 500 from missing schema)."""

from __future__ import annotations

import json


def _exc_text(exc: BaseException) -> str:
    parts: list[str] = [str(exc)]
    for attr in ("message", "args", "details", "hint", "code"):
        v = getattr(exc, attr, None)
        if v and str(v) not in parts[0]:
            parts.append(str(v))
    # supabase-py may wrap dict-like errors
    if hasattr(exc, "json") and callable(exc.json):
        try:
            parts.append(json.dumps(exc.json(), default=str)[:2000])
        except Exception:  # noqa: BLE001
            pass
    return " ".join(parts).lower()


def is_missing_relation_error(exc: BaseException) -> bool:
    """True when PostgREST cannot see the table (PGRST205) or relation does not exist (42P01)."""
    t = _exc_text(exc)
    return (
        "pgrst205" in t
        or "could not find the table" in t
        or "schema cache" in t
        or "42p01" in t  # undefined_table
        or ("does not exist" in t and "relation" in t)
    )


def is_column_missing_error(exc: BaseException) -> bool:
    """Postgres undefined_column (42703) — e.g. ``users.id`` when migration 003 not applied."""
    t = _exc_text(exc)
    return "42703" in t or "undefined_column" in t


def column_missing_log_suffix(exc: BaseException) -> str:
    if is_column_missing_error(exc):
        return (
            " — likely cause: DB columns out of sync. Run infra/supabase/migration_003_bidforge_persistence_rag.sql "
            "and set SUPABASE_USERS_PK_COLUMN if your PK is not named `id`."
        )
    return ""


def missing_relation_log_suffix(exc: BaseException) -> str:
    if is_missing_relation_error(exc):
        return (
            " — likely cause: table not created or PostgREST schema cache stale. "
            "Run infra/supabase/migration_003_bidforge_persistence_rag.sql (and 004/005) in the SQL editor, "
            "then Dashboard → Settings → API → Reload schema (or restart the project)."
        )
    return ""
