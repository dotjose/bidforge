"""Supabase persistence for proposal runs and freelance win memory — failures are swallowed by callers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from bidforge_shared import OpenRouterLLM

from app.core.config import settings
from app.integrations.postgrest_errors import (
    column_missing_log_suffix,
    is_column_missing_error,
    is_missing_relation_error,
    missing_relation_log_suffix,
)
from app.integrations.supabase import get_supabase_client
from app.integrations.supabase_tables import (
    T_DOCUMENTS,
    T_FREELANCE_WIN_MEMORY,
    T_LEGACY_CANONICAL_PROPOSALS,
    T_MEMORY_USAGE_LOG,
    T_PROPOSAL_DRAFTS,
    T_PROPOSAL_EVENTS,
    T_PROPOSAL_MEMORY,
    T_PROPOSAL_NODE_CACHE,
    T_PROPOSAL_PATTERNS,
    T_PROPOSAL_RUNS,
    T_PROPOSAL_TEMPLATES,
    T_PROPOSALS,
    T_USERS,
    fq,
)

log = logging.getLogger(__name__)

# PostgREST PGRST205 (table not in schema cache / not migrated): skip further HTTP for this process.
_missing_postgrest_tables: set[str] = set()


def _log_store_error(operation: str, table: str, exc: BaseException) -> None:
    msg = f"{operation} {fq(table)} failed: {exc}"
    if is_missing_relation_error(exc):
        log.warning("%s%s", msg, missing_relation_log_suffix(exc))
    elif is_column_missing_error(exc):
        log.warning("%s%s", msg, column_missing_log_suffix(exc))
    else:
        log.warning("%s", msg)


def _note_missing_table_once(operation: str, table: str, exc: BaseException) -> None:
    """Log a single WARNING per table when PostgREST reports the relation missing (PGRST205)."""
    if table in _missing_postgrest_tables:
        return
    _missing_postgrest_tables.add(table)
    _log_store_error(operation, table, exc)


def _users_pk_column() -> str:
    c = (settings.supabase_users_pk_column or "id").strip()
    return c if c else "id"


def resolve_users_uuid_for_clerk(clerk_user_id: str) -> UUID | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    pk = _users_pk_column()
    try:
        res = sb.table(T_USERS).select(pk).eq("clerk_user_id", clerk_user_id).limit(1).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("users id lookup", T_USERS, e)
        return None
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    raw = rows[0].get(pk)
    try:
        return UUID(str(raw)) if raw is not None else None
    except (ValueError, TypeError):
        return None


def insert_canonical_proposal_row(
    clerk_user_id: str,
    *,
    title: str,
    body: str,
    score: int,
    issues: list[Any],
    job_description: str,
) -> str | None:
    uid = resolve_users_uuid_for_clerk(clerk_user_id)
    if uid is None:
        return None
    sb = get_supabase_client()
    if sb is None:
        return None
    row: dict[str, Any] = {
        "user_id": str(uid),
        "title": (title or "")[:512],
        "body": (body or "")[:200_000],
        "score": int(score),
        "issues": issues,
        "job_description": (job_description or "")[:12_000],
    }
    try:
        res = sb.table(T_LEGACY_CANONICAL_PROPOSALS).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("legacy_canonical_proposals insert", T_LEGACY_CANONICAL_PROPOSALS, e)
        return None
    data = getattr(res, "data", None) or []
    if not data or not isinstance(data[0], dict):
        return None
    raw_id = data[0].get("id")
    return str(raw_id) if raw_id is not None else None


def insert_proposal_memory_entries(
    clerk_user_id: str,
    snippets: list[tuple[str, str]],
    llm: Any,
) -> None:
    """Persist `proposal_memory` rows (optional embedding). `snippets` are (type, text) with type in win_pattern|strong_line."""
    uid = resolve_users_uuid_for_clerk(clerk_user_id)
    if uid is None or not snippets:
        return
    sb = get_supabase_client()
    if sb is None:
        return
    client = llm if isinstance(llm, OpenRouterLLM) else None
    for typ, text in snippets[:8]:
        t = (text or "").strip()
        if not t or typ not in ("win_pattern", "strong_line"):
            continue
        row: dict[str, Any] = {"user_id": str(uid), "snippet": t[:8000], "type": typ}
        if client is not None:
            try:
                emb = client.embed_text(t[:2000])
            except Exception as e:  # noqa: BLE001
                log.debug("proposal_memory embed skipped: %s", e)
                emb = None
            else:
                if emb is not None and len(emb) == 1536:
                    row["embedding"] = emb
        try:
            sb.table(T_PROPOSAL_MEMORY).insert(row).execute()
        except Exception as e:  # noqa: BLE001
            _log_store_error("proposal_memory insert", T_PROPOSAL_MEMORY, e)


def _effective_user_id_for_row(clerk_user_id: str) -> str:
    uid = resolve_users_uuid_for_clerk(clerk_user_id)
    return str(uid) if uid is not None else clerk_user_id


def fetch_freelance_win_memory_rows(clerk_user_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return []
    try:
        res = (
            sb.table(T_FREELANCE_WIN_MEMORY)
            .select("id,opening_hook,winning_sections,score,job_type,extracted_patterns,created_at")
            .eq("user_id", clerk_user_id)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _log_store_error("freelance_win_memory select", T_FREELANCE_WIN_MEMORY, e)
        else:
            log.debug("freelance_win_memory select failed: %s", e)
        return []
    rows = getattr(res, "data", None) or []
    return [r for r in rows if isinstance(r, dict)]


def fetch_user_saved_pattern_document_rows(clerk_user_id: str, *, limit: int = 24) -> list[dict[str, Any]]:
    """Rows from ``documents`` written by ``POST /documents/memory/pattern`` (internal user uuid)."""
    uid = resolve_users_uuid_for_clerk(clerk_user_id)
    if uid is None:
        return []
    sb = get_supabase_client()
    if sb is None:
        return []
    try:
        res = (
            sb.table(T_DOCUMENTS)
            .select("id,content,metadata,created_at")
            .eq("user_id", str(uid))
            .eq("source", "user_pattern")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _log_store_error("documents user_pattern select", T_DOCUMENTS, e)
        else:
            log.debug("documents user_pattern select failed: %s", e)
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


def _insert_proposal_run_audit_row(
    *,
    proposal_row_id: str,
    rfp_input: str,
    proposal_output: dict[str, Any],
) -> None:
    """Optional ``public.proposal_runs`` row (migration_005); never raises."""
    sb = get_supabase_client()
    if sb is None or not proposal_row_id.strip():
        return
    try:
        UUID(proposal_row_id)
    except (ValueError, TypeError):
        return
    try:
        sb.table(T_PROPOSAL_RUNS).insert(
            {
                "proposal_id": proposal_row_id.strip(),
                "input": (rfp_input or "")[:120_000],
                "output": dict(proposal_output or {}),
            },
        ).execute()
    except Exception as e:  # noqa: BLE001
        log.debug("%s audit insert skipped: %s", fq(T_PROPOSAL_RUNS), e)


def _pattern_from_proposal_output(po: dict[str, Any]) -> str:
    ps = po.get("pipeline_state") if isinstance(po.get("pipeline_state"), dict) else {}
    pat = str(ps.get("selected_pattern") or "saved").strip().lower()
    return pat if pat in ("strong", "weak", "saved") else "saved"


def _proposals_row_to_api_run(row: dict[str, Any]) -> dict[str, Any]:
    """Map ``public.proposals`` row → API shape expected by proposal routes (``proposal_output`` blob)."""
    pc = row.get("proposal_content") if isinstance(row.get("proposal_content"), dict) else {}
    out_po = dict(pc)
    ps_col = row.get("pipeline_state") if isinstance(row.get("pipeline_state"), dict) else {}
    if ps_col:
        inner = out_po.get("pipeline_state") if isinstance(out_po.get("pipeline_state"), dict) else {}
        out_po["pipeline_state"] = {**dict(inner), **ps_col}
    ss_col = row.get("settings_snapshot") if isinstance(row.get("settings_snapshot"), dict) else {}
    if ss_col:
        inner_ss = out_po.get("settings_snapshot") if isinstance(out_po.get("settings_snapshot"), dict) else {}
        out_po["settings_snapshot"] = {**dict(inner_ss), **ss_col}
    if isinstance(row.get("pattern"), str) and row["pattern"]:
        ps = dict(out_po.get("pipeline_state") or {})
        ps["selected_pattern"] = row["pattern"]
        out_po["pipeline_state"] = ps
    src = str(row.get("input_text") or row.get("rfp_text") or "").strip()
    return {
        "id": str(row.get("id") or ""),
        "user_id": str(row.get("user_id") or ""),
        "rfp_input": src,
        "input_type": str(row.get("input_type") or ""),
        "proposal_output": out_po,
        "score": int(row.get("score") or 0),
        "issues": row.get("issues") if isinstance(row.get("issues"), list) else [],
        "title": str(row.get("title") or ""),
        "trace_id": str(row.get("trace_id") or ""),
        "pipeline_mode": str(row.get("pipeline_mode") or "enterprise"),
        "created_at": row.get("created_at"),
    }


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
    input_type: str | None = None,
) -> str | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        log.warning("insert_proposal_run: missing Supabase client or user_id")
        return None
    raw_in = (rfp_input or "").strip()
    if not raw_in:
        log.warning("insert_proposal_run: refusing insert — empty source input (input_text/rfp)")
        return None
    po = dict(proposal_output or {})
    ps = dict(po.get("pipeline_state") or {}) if isinstance(po.get("pipeline_state"), dict) else {}
    pat = _pattern_from_proposal_output(po)
    ss = dict(po.get("settings_snapshot") or {}) if isinstance(po.get("settings_snapshot"), dict) else {}
    now = datetime.now(timezone.utc).isoformat()
    it = (input_type or "").strip()[:128] if input_type else ""
    row: dict[str, Any] = {
        "user_id": _effective_user_id_for_row(clerk_user_id),
        "rfp_text": raw_in[:120_000],
        "input_text": raw_in[:120_000],
        "input_type": it or None,
        "proposal_content": po,
        "pipeline_state": ps,
        "settings_snapshot": ss,
        "pattern": pat,
        "title": (title or "")[:512],
        "score": int(score),
        "issues": issues,
        "trace_id": trace_id[:128],
        "pipeline_mode": (pipeline_mode or "enterprise")[:32],
        "updated_at": now,
    }
    try:
        res = sb.table(T_PROPOSALS).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error(f"proposals insert trace_id={trace_id[:48]}", T_PROPOSALS, e)
        return None
    data = getattr(res, "data", None) or []
    if data and isinstance(data[0], dict):
        raw_id = data[0].get("id")
        if raw_id is not None:
            sid = str(raw_id)
            _insert_proposal_run_audit_row(
                proposal_row_id=sid,
                rfp_input=raw_in,
                proposal_output=po,
            )
            return sid
    # Some proxies / PostgREST configs return 2xx with an empty body; row may still exist.
    try:
        res2 = (
            sb.table(T_PROPOSALS)
            .select("id")
            .eq("user_id", _effective_user_id_for_row(clerk_user_id))
            .eq("trace_id", trace_id[:128])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows2 = getattr(res2, "data", None) or []
        if rows2 and isinstance(rows2[0], dict):
            raw2 = rows2[0].get("id")
            if raw2 is not None:
                sid = str(raw2)
                log.info(
                    "proposals insert returned no row body; recovered id via trace_id=%s",
                    trace_id[:32],
                )
                _insert_proposal_run_audit_row(
                    proposal_row_id=sid,
                    rfp_input=raw_in,
                    proposal_output=po,
                )
                return sid
    except Exception as e2:  # noqa: BLE001
        _log_store_error("post-insert proposals id lookup", T_PROPOSALS, e2)
    log.warning(
        "insert_proposal_run: no id after insert (trace_id=%s). "
        "Confirm %s exists, migrations are applied, and reload PostgREST schema.",
        trace_id[:48],
        fq(T_PROPOSALS),
    )
    return None


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
        res = sb.table(T_FREELANCE_WIN_MEMORY).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("freelance_win_memory insert", T_FREELANCE_WIN_MEMORY, e)
        return None
    data = getattr(res, "data", None) or []
    if not data or not isinstance(data[0], dict):
        return None
    raw_id = data[0].get("id")
    return str(raw_id) if raw_id is not None else None


def insert_proposal_template(
    clerk_user_id: str,
    *,
    detected_type: str,
    template_structure: dict[str, Any],
) -> str | None:
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    row: dict[str, Any] = {
        "user_id": _effective_user_id_for_row(clerk_user_id),
        "detected_type": (detected_type or "general")[:128],
        "template_structure": dict(template_structure or {}),
    }
    try:
        res = sb.table(T_PROPOSAL_TEMPLATES).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposal_templates insert", T_PROPOSAL_TEMPLATES, e)
        return None
    data = getattr(res, "data", None) or []
    if data and isinstance(data[0], dict):
        raw_id = data[0].get("id")
        if raw_id is not None:
            return str(raw_id)
    return None


def list_proposal_runs(clerk_user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    if not clerk_user_id:
        return []
    sb = get_supabase_client()
    if sb is None:
        return []
    try:
        res = (
            sb.table(T_PROPOSALS)
            .select("id,title,score,trace_id,pipeline_mode,created_at")
            .eq("user_id", _effective_user_id_for_row(clerk_user_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals list", T_PROPOSALS, e)
        return []
    rows = getattr(res, "data", None) or []
    return [r for r in rows if isinstance(r, dict)]


def get_proposal_run(clerk_user_id: str, run_id: str) -> dict[str, Any] | None:
    if not clerk_user_id or not run_id:
        return None
    try:
        UUID(run_id)
    except (ValueError, TypeError):
        return None
    sb = get_supabase_client()
    if sb is None:
        return None
    try:
        res = (
            sb.table(T_PROPOSALS)
            .select("*")
            .eq("user_id", _effective_user_id_for_row(clerk_user_id))
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals get", T_PROPOSALS, e)
        return None
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    return _proposals_row_to_api_run(rows[0])


def merge_proposal_run_output_metadata(
    clerk_user_id: str,
    run_id: str,
    *,
    settings_snapshot: dict[str, Any],
    rfp_id: str | None,
) -> bool:
    """Merge settings snapshot + rfp id into ``proposal_content`` and ``settings_snapshot`` columns."""
    sb = get_supabase_client()
    if sb is None:
        return False
    try:
        res = (
            sb.table(T_PROPOSALS)
            .select("proposal_content,settings_snapshot")
            .eq("user_id", _effective_user_id_for_row(clerk_user_id))
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals merge read", T_PROPOSALS, e)
        return False
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return False
    raw = rows[0]
    pc = dict(raw.get("proposal_content") or {})
    ss_out = {**dict(raw.get("settings_snapshot") or {}), **dict(settings_snapshot or {})}
    pc["settings_snapshot"] = ss_out
    if rfp_id and str(rfp_id).strip():
        pc["rfp_id"] = str(rfp_id).strip()[:128]
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table(T_PROPOSALS).update(
            {"proposal_content": pc, "settings_snapshot": ss_out, "updated_at": now},
        ).eq("user_id", _effective_user_id_for_row(clerk_user_id)).eq("id", run_id).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals metadata merge", T_PROPOSALS, e)
        return False
    return True


def update_proposal_run_pattern(
    clerk_user_id: str,
    run_id: str,
    *,
    pattern: str,
) -> bool:
    """Insert ``proposal_patterns`` row and update ``proposals.pattern`` + nested pipeline state."""
    pat = pattern.strip().lower()
    if pat not in ("strong", "weak", "saved"):
        return False
    sb = get_supabase_client()
    if sb is None:
        return False
    try:
        res = (
            sb.table(T_PROPOSALS)
            .select("proposal_content,pipeline_state")
            .eq("user_id", _effective_user_id_for_row(clerk_user_id))
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals pattern read", T_PROPOSALS, e)
        return False
    rows = getattr(res, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return False
    raw = rows[0]
    pc = dict(raw.get("proposal_content") or {})
    ps = dict(raw.get("pipeline_state") or {})
    inner_ps = pc.get("pipeline_state") if isinstance(pc.get("pipeline_state"), dict) else {}
    merged_ps = {**dict(inner_ps), **ps, "selected_pattern": pat}
    merged_ps["pattern_marked_at"] = datetime.now(timezone.utc).isoformat()
    pc["pipeline_state"] = merged_ps
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table(T_PROPOSAL_PATTERNS).insert(
            {
                "proposal_id": run_id,
                "user_id": _effective_user_id_for_row(clerk_user_id),
                "pattern": pat,
            },
        ).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposal_patterns insert", T_PROPOSAL_PATTERNS, e)
        return False
    try:
        sb.table(T_PROPOSALS).update(
            {
                "pattern": pat,
                "proposal_content": pc,
                "pipeline_state": merged_ps,
                "updated_at": now,
            },
        ).eq("user_id", _effective_user_id_for_row(clerk_user_id)).eq("id", run_id).execute()
    except Exception as e:  # noqa: BLE001
        _log_store_error("proposals pattern update", T_PROPOSALS, e)
        return False
    return True


def build_winning_sections_payload(fp_dump: dict[str, Any]) -> list[dict[str, Any]]:
    """Freelance win memory: legacy flat keys or unified writer {title, sections:[{title,content}]}."""
    secs = fp_dump.get("sections")
    if isinstance(secs, list) and secs:
        first = secs[0]
        if isinstance(first, dict) and "content" in first:
            out: list[dict[str, Any]] = []
            for s in secs[:8]:
                if not isinstance(s, dict):
                    continue
                name = str(s.get("title") or "section").strip().lower().replace(" ", "_")
                text = str(s.get("content") or "").strip()
                if text:
                    out.append({"name": name, "text": text[:12_000]})
            return out[:8]
    keys = ("opening", "understanding", "solution", "experience", "next_step")
    out2: list[dict[str, Any]] = []
    for k in keys:
        text = str(fp_dump.get(k) or "").strip()
        if text:
            out2.append({"name": k, "text": text[:12_000]})
    return out2[:6]


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


def insert_proposal_draft_row(proposal_run_id: str, version: int, public_json: dict[str, Any]) -> None:
    """Latest sanitized client snapshot per run (`public.proposal_drafts`). Best-effort."""
    sb = get_supabase_client()
    if sb is None or not proposal_run_id.strip():
        return
    try:
        UUID(proposal_run_id)
    except (ValueError, TypeError):
        return
    row = {
        "proposal_run_id": proposal_run_id.strip(),
        "version": int(version),
        "content": public_json,
    }
    try:
        sb.table(T_PROPOSAL_DRAFTS).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _log_store_error("proposal_drafts insert", T_PROPOSAL_DRAFTS, e)
        else:
            log.debug("proposal_drafts insert skipped: %s", e)


def insert_memory_usage_log_row(proposal_run_id: str, memory_used: bool) -> None:
    """One row per completed run (`public.memory_usage_log`). Best-effort."""
    sb = get_supabase_client()
    if sb is None or not proposal_run_id.strip():
        return
    try:
        UUID(proposal_run_id)
    except (ValueError, TypeError):
        return
    row = {"proposal_run_id": proposal_run_id.strip(), "memory_used": bool(memory_used)}
    try:
        sb.table(T_MEMORY_USAGE_LOG).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _log_store_error("memory_usage_log insert", T_MEMORY_USAGE_LOG, e)
        else:
            log.debug("memory_usage_log insert skipped: %s", e)


def insert_proposal_dag_event(
    *,
    user_id: str,
    trace_id: str,
    proposal_id: str | None,
    record: dict[str, Any],
) -> bool:
    """Append-only DAG node event (`public.proposal_events`). Returns False on hard failure when client exists."""
    sb = get_supabase_client()
    if sb is None or not user_id.strip() or not trace_id.strip():
        return True
    pid: str | None = None
    if proposal_id:
        try:
            UUID(str(proposal_id))
            pid = str(proposal_id)
        except (ValueError, TypeError):
            pid = None
    row: dict[str, Any] = {
        "user_id": user_id.strip(),
        "trace_id": trace_id[:128],
        "proposal_id": pid,
        "node_id": str(record.get("id") or "")[:128],
        "parent_node_id": str(record.get("parent_node_id") or "")[:128],
        "input_hash": str(record.get("input_hash") or "")[:128],
        "output_hash": str(record.get("output_hash") or "")[:128],
        "model_used": str(record.get("model_used") or "")[:256],
        "token_usage": record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {},
        "latency_ms": int(record.get("latency_ms") or 0),
        "deterministic_version_id": str(record.get("deterministic_version_id") or "")[:256],
        "cache_key": str(record.get("cache_key") or "")[:128],
        "retries": int(record.get("retries") or 0),
        "version": str(record.get("version") or "")[:64],
        "payload": record,
    }
    if T_PROPOSAL_EVENTS in _missing_postgrest_tables:
        return True
    try:
        sb.table(T_PROPOSAL_EVENTS).insert(row).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _note_missing_table_once("proposal_events insert", T_PROPOSAL_EVENTS, e)
            return True
        _log_store_error("proposal_events insert", T_PROPOSAL_EVENTS, e)
        return False
    return True


def backfill_proposal_events_proposal_id(*, trace_id: str, proposal_id: str) -> bool:
    sb = get_supabase_client()
    if sb is None or not trace_id.strip() or not proposal_id.strip():
        return True
    if T_PROPOSAL_EVENTS in _missing_postgrest_tables:
        return True
    try:
        UUID(proposal_id)
    except (ValueError, TypeError):
        return False
    try:
        sb.table(T_PROPOSAL_EVENTS).update({"proposal_id": proposal_id}).eq("trace_id", trace_id[:128]).execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _note_missing_table_once("proposal_events proposal_id backfill", T_PROPOSAL_EVENTS, e)
            return True
        _log_store_error("proposal_events proposal_id backfill", T_PROPOSAL_EVENTS, e)
        return False
    return True


def fetch_proposal_node_cache(cache_key: str) -> dict[str, Any] | None:
    sb = get_supabase_client()
    if sb is None or not cache_key.strip():
        return None
    if T_PROPOSAL_NODE_CACHE in _missing_postgrest_tables:
        return None
    try:
        res = sb.table(T_PROPOSAL_NODE_CACHE).select("output").eq("cache_key", cache_key[:256]).limit(1).execute()
        rows = getattr(res, "data", None) or []
        if not rows or not isinstance(rows[0], dict):
            return None
        out = rows[0].get("output")
        return out if isinstance(out, dict) else None
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _note_missing_table_once("proposal_node_cache select", T_PROPOSAL_NODE_CACHE, e)
            return None
        _log_store_error("proposal_node_cache select", T_PROPOSAL_NODE_CACHE, e)
        return None


def upsert_proposal_node_cache(*, cache_key: str, output_hash: str, output: dict[str, Any]) -> bool:
    sb = get_supabase_client()
    if sb is None or not cache_key.strip():
        return True
    if T_PROPOSAL_NODE_CACHE in _missing_postgrest_tables:
        return True
    row = {
        "cache_key": cache_key[:256],
        "output_hash": output_hash[:128],
        "output": output,
    }
    try:
        sb.table(T_PROPOSAL_NODE_CACHE).upsert(row, on_conflict="cache_key").execute()
    except Exception as e:  # noqa: BLE001
        if is_missing_relation_error(e):
            _note_missing_table_once("proposal_node_cache upsert", T_PROPOSAL_NODE_CACHE, e)
            return True
        _log_store_error("proposal_node_cache upsert", T_PROPOSAL_NODE_CACHE, e)
        return False
    return True
