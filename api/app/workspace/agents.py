"""Stateful workspace agents — normalize → build → inject settings (no raw UI past this layer)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bidforge_schemas.workspace import (
    InputSource,
    NormalizedDocumentMetadata,
    NormalizedDocumentOutput,
    NormalizedSection,
    RagConfig,
    WorkspaceRfp,
    WorkspaceSettings,
    WorkspaceState,
)

from app.integrations.workspace_settings_store import get_workspace_settings_row

log = logging.getLogger(__name__)

_SECTION_HINTS = re.compile(
    r"(?mi)^(#{1,3}\s+.+|(?:section|scope|requirements|deliverables|evaluation|compliance)\s*[:\-].+)$"
)


def run_document_normalizer_agent(
    *,
    raw_bytes: bytes | None,
    raw_text: str | None,
    source: InputSource,
    filename: str | None = None,
    url: str | None = None,
) -> NormalizedDocumentOutput:
    """Deterministic normalizer (LLM-free). PDF/DOCX/URL/text → structured sections."""
    text = ""
    eff_source: InputSource = source
    if source == "url" and url:
        from app.workspace.extract import extract_from_url

        try:
            text, inferred = extract_from_url(url.strip())
            eff_source = "pdf" if inferred == "pdf" else ("docx" if inferred == "docx" else "text")
        except Exception as e:  # noqa: BLE001
            log.warning("url normalize failed: %s", e)
            text = ""
    elif source == "pdf" and raw_bytes:
        from app.workspace.extract import extract_pdf_text

        text = extract_pdf_text(raw_bytes)
    elif source == "docx" and raw_bytes:
        from app.workspace.extract import extract_docx_text

        text = extract_docx_text(raw_bytes)
    elif raw_text:
        text = raw_text.strip()
        eff_source = "text"
    elif raw_bytes:
        try:
            text = raw_bytes.decode("utf-8", errors="replace").strip()
            eff_source = "text"
        except Exception:
            text = ""

    title = ""
    if filename and eff_source != "text":
        title = re.sub(r"\.[^.]+$", "", filename).replace("_", " ").strip()[:240]
    lines = [ln.rstrip() for ln in text.splitlines()]
    if lines and not title:
        title = lines[0][:240]

    sections: list[NormalizedSection] = []
    buf: list[str] = []
    cur_name = "Document"

    def flush() -> None:
        nonlocal buf, cur_name
        body = "\n".join(buf).strip()
        if body:
            sections.append(NormalizedSection(name=cur_name, content=body))
        buf = []

    for ln in lines:
        if _SECTION_HINTS.match(ln.strip()) and buf:
            flush()
            cur_name = re.sub(r"^#+\s*", "", ln.strip())[:200]
            continue
        buf.append(ln)
    flush()

    if not sections and text.strip():
        sections = [NormalizedSection(name="Full brief", content=text.strip()[:120_000])]

    meta = NormalizedDocumentMetadata(
        job_type_hint="enterprise_rfp" if len(text) > 3500 else "job_post",
    )
    return NormalizedDocumentOutput(title=title or "Opportunity", sections=sections, metadata=meta)


def run_workspace_builder_agent(
    normalized: NormalizedDocumentOutput,
    clerk_user_id: str,
    *,
    source: InputSource,
) -> WorkspaceState:
    """Assemble canonical WorkspaceState.rfp from normalized document."""
    body_parts = []
    for s in normalized.sections:
        body_parts.append(f"## {s.name}\n\n{s.content}".strip())
    body = "\n\n".join(body_parts).strip()[:120_000]
    rfp = WorkspaceRfp(
        source=source,
        title=normalized.title,
        sections=[NormalizedSection(name=s.name, content=s.content[:50_000]) for s in normalized.sections],
        body=body,
    )
    return WorkspaceState(user_id=clerk_user_id, rfp=rfp, trace_id="")


def run_settings_injector_agent(ws: WorkspaceState, clerk_user_id: str) -> WorkspaceState:
    """Merge persisted workspace_settings with the incoming WorkspaceState.settings."""
    db = WorkspaceSettings()
    row = get_workspace_settings_row(clerk_user_id)
    if row:
        db.tone = str(row.get("tone") or "")[:4000]
        db.writing_style = str(row.get("writing_style") or "")[:8000]
        if isinstance(row.get("company_profile"), dict):
            db.company_profile = dict(row["company_profile"])
        if isinstance(row.get("rag_config"), dict):
            rc = row["rag_config"]
            db.rag.enabled = bool(rc.get("enabled", True))
            db.rag.enterprise_case_studies = bool(rc.get("enterprise_case_studies", True))
            db.rag.freelance_win_memory = bool(rc.get("freelance_win_memory", True))
            pm = str(rc.get("proposal_mode") or "").strip().lower()
            if pm in ("auto", "enterprise", "freelance"):
                db.proposal_mode = pm  # type: ignore[assignment]
    ins = ws.settings
    merged_cp = {**db.company_profile, **ins.company_profile}
    rag_out = db.rag if ins.rag == RagConfig() else ins.rag
    out = WorkspaceSettings(
        tone=(ins.tone.strip() or db.tone)[:4000],
        writing_style=(ins.writing_style.strip() or db.writing_style)[:8000],
        proposal_mode=ins.proposal_mode if ins.proposal_mode != "auto" else db.proposal_mode,
        company_profile=merged_cp,
        rag=rag_out,
    )
    return ws.model_copy(update={"settings": out})


def workspace_rfp_plain(ws: WorkspaceState) -> str:
    """Canonical plain brief for extraction / RAG embedding (no preference preamble)."""
    if ws.rfp.body.strip():
        return ws.rfp.body.strip()
    parts = [f"## {s.name}\n\n{s.content}" for s in ws.rfp.sections if s.content.strip()]
    return "\n\n".join(parts).strip()


def workspace_preferences_block(ws: WorkspaceState) -> str:
    """Serialized settings for enterprise strategy/proposal prompts."""
    s = ws.settings
    parts = []
    if s.tone.strip():
        parts.append(f"Tone: {s.tone.strip()}")
    if s.writing_style.strip():
        parts.append(f"Writing style: {s.writing_style.strip()}")
    if s.company_profile:
        parts.append("Company profile (JSON):\n" + json.dumps(s.company_profile, ensure_ascii=False)[:6000])
    return "\n".join(parts).strip()


def workspace_generation_rfp(ws: WorkspaceState) -> str:
    """Brief first (so truncated excerpts keep the job), then workspace writing preferences."""
    prefs = workspace_preferences_block(ws)
    core = workspace_rfp_plain(ws)
    if not prefs:
        return core
    return (
        f"[OPPORTUNITY_BRIEF]\n{core}\n\n"
        "[WORKSPACE_SETTINGS — honor in voice and positioning; do not fabricate credentials]\n"
        f"{prefs}"
    )


def effective_pipeline_request_mode(ws: WorkspaceState, request_mode: str) -> str:
    """Resolve auto vs explicit request override."""
    rm = (request_mode or "auto").strip().lower()
    if rm != "auto":
        return rm
    pm = ws.settings.proposal_mode
    if pm in ("enterprise", "freelance"):
        return pm
    return "auto"
