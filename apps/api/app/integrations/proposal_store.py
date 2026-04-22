"""Supabase persistence for proposal runs and freelance win memory — failures are swallowed by callers."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.integrations.supabase import get_supabase_client

log = logging.getLogger(__name__)


def fetch_freelance_win_memory_rows(clerk_user_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return []
    try:
        res = (
            sb.table("freelance_win_memory")
            .select("id,opening_hook,winning_sections,score,job_type,extracted_patterns,created_at")
            .eq("user_id", clerk_user_id)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        log.debug("freelance_win_memory select failed: %s", e)
        return []
    rows = getattr(res, "data", None) or []
    return [r for r in rows if isinstance(r, dict)]


def fetch_top_freelance_wins_for_diff(clerk_user_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    return fetch_freelance_win_memory_rows(clerk_user_id, limit=limit)


def merge_freelance_win_rows_into_rag_patterns(
    freelance_win_patterns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append DB-backed win rows as synthetic RAG-shaped dicts (dedupe by opening_hook)."""
    seen = {str(x.get("excerpt") or x.get("label") or "") for x in freelance_win_patterns}
    out = list(freelance_win_patterns)
    for row in rows:
        hook = (row.get("opening_hook") or "").strip()
        if not hook or hook in seen:
            continue
        seen.add(hook)
        rid = str(row.get("id") or "")
        out.append(
            {
                "id": rid or f"db_win_{len(out)}",
                "label": (hook[:120] + ("…" if len(hook) > 120 else "")),
                "excerpt": hook[:2000],
                "outcome": "stored_win",
                "tags": ["freelance_win_memory"],
                "job_type": str(row.get("job_type") or "upwork"),
                "metrics": {"score": row.get("score"), "source": "freelance_win_memory"},
            }
        )
    return out


def insert_proposal_run(
    clerk_user_id: str,
    *,
    rfp_input: str,
    proposal_output: dict[str, Any],
    score: int,
    issues: list[str],
    title: str,
    trace_id: str,
    pipeline_mode: str,
) -> str | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    row = {
        "user_id": clerk_user_id,
        "rfp_input": rfp_input[:120_000],
        "proposal_output": proposal_output,
        "score": int(score),
        "issues": issues,
        "title": (title or "")[:512],
        "trace_id": trace_id[:128],
        "pipeline_mode": (pipeline_mode or "enterprise")[:32],
    }
    try:
        res = sb.table("proposal_runs").insert(row).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("proposal_runs insert failed: %s", e)
        return None
    data = getattr(res, "data", None) or []
    if not data or not isinstance(data[0], dict):
        return None
    raw_id = data[0].get("id")
    return str(raw_id) if raw_id is not None else None


def insert_freelance_win_memory(
    clerk_user_id: str,
    *,
    job_type: str,
    opening_hook: str,
    winning_sections: list[dict[str, Any]] | dict[str, Any],
    score: int,
    extracted_patterns: dict[str, Any],
    embedding: list[float] | None,
) -> str | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    ws: Any = winning_sections
    if isinstance(ws, list):
        ws_payload = ws
    else:
        ws_payload = [ws]
    row: dict[str, Any] = {
        "user_id": clerk_user_id,
        "job_type": (job_type or "upwork")[:64],
        "opening_hook": (opening_hook or "")[:8000],
        "winning_sections": ws_payload,
        "score": int(score),
        "extracted_patterns": extracted_patterns,
    }
    if embedding is not None and len(embedding) == 1536:
        row["embedding"] = embedding
    try:
        res = sb.table("freelance_win_memory").insert(row).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("freelance_win_memory insert failed: %s", e)
        return None
    data = getattr(res, "data", None) or []
    if not data or not isinstance(data[0], dict):
        return None
    raw_id = data[0].get("id")
    return str(raw_id) if raw_id is not None else None


def list_proposal_runs(clerk_user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return []
    try:
        res = (
            sb.table("proposal_runs")
            .select("id,title,score,trace_id,pipeline_mode,created_at")
            .eq("user_id", clerk_user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        log.warning("proposal_runs list failed: %s", e)
        return []
    rows = getattr(res, "data", None) or []
    return [r for r in rows if isinstance(r, dict)]


def get_proposal_run(clerk_user_id: str, run_id: str) -> dict[str, Any] | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id or not run_id:
        return None
    try:
        UUID(run_id)
    except (ValueError, TypeError):
        return None
    try:
        res = (
            sb.table("proposal_runs")
            .select("*")
            .eq("user_id", clerk_user_id)
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        log.warning("proposal_runs get failed: %s", e)
        return None
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    return rows[0]


def build_winning_sections_payload(fp_dump: dict[str, Any]) -> list[dict[str, Any]]:
    keys = ("hook", "understanding_need", "approach", "relevant_experience", "call_to_action")
    out: list[dict[str, Any]] = []
    for k in keys:
        text = str(fp_dump.get(k) or "").strip()
        if text:
            out.append({"name": k, "text": text[:12_000]})
    return out[:6]


def build_extracted_patterns(
    *,
    structure_pattern: str,
    opening_lines: list[str],
    score: int,
) -> dict[str, Any]:
    return {
        "structure_pattern": structure_pattern,
        "opening_lines": opening_lines[:3],
        "score": score,
    }
