from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.contracts.errors import ErrorResponse, error_response
from app.core.auth import CurrentUser, get_current_user
from app.integrations.workspace_settings_store import get_workspace_settings_row, upsert_workspace_settings_full
from app.workspace.agents import run_document_normalizer_agent
from bidforge_schemas import NormalizedDocumentOutput

log = logging.getLogger(__name__)

router = APIRouter(tags=["workspace"])


class WorkspaceSettingsResponse(BaseModel):
    user_id: str
    company_profile: dict[str, Any] = Field(default_factory=dict)
    tone: str = ""
    writing_style: str = ""
    openrouter_model_primary: str = ""
    rag_config: dict[str, Any] = Field(default_factory=dict)
    proposal_mode: Literal["auto", "enterprise", "freelance"] = "auto"
    updated_at: str | None = None


class WorkspaceSettingsUpdate(BaseModel):
    company_profile: dict[str, Any] | None = None
    tone: str | None = None
    writing_style: str | None = None
    openrouter_model_primary: str | None = None
    rag_config: dict[str, Any] | None = None
    proposal_mode: Literal["auto", "enterprise", "freelance"] | None = None


def build_workspace_settings_response(clerk_user_id: str) -> WorkspaceSettingsResponse:
    """Pure builder for GET + hydration aliases (no FastAPI dependency)."""
    row = get_workspace_settings_row(clerk_user_id)
    if row is None:
        return WorkspaceSettingsResponse(user_id=clerk_user_id)
    rc = row.get("rag_config") if isinstance(row.get("rag_config"), dict) else {}
    pm_raw = str(rc.get("proposal_mode") or "").strip().lower()
    pm: Literal["auto", "enterprise", "freelance"] = (
        pm_raw if pm_raw in ("auto", "enterprise", "freelance") else "auto"
    )
    return WorkspaceSettingsResponse(
        user_id=str(row.get("user_id") or clerk_user_id),
        company_profile=row.get("company_profile") if isinstance(row.get("company_profile"), dict) else {},
        tone=str(row.get("tone") or ""),
        writing_style=str(row.get("writing_style") or ""),
        openrouter_model_primary=str(row.get("openrouter_model_primary") or ""),
        rag_config=dict(rc),
        proposal_mode=pm,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") is not None else None,
    )


@router.get(
    "/settings",
    response_model=WorkspaceSettingsResponse,
    summary="Get workspace settings for current user",
    responses={401: {"model": ErrorResponse}},
)
async def get_workspace_settings(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> WorkspaceSettingsResponse:
    return build_workspace_settings_response(user.user_id)


@router.put(
    "/settings",
    response_model=WorkspaceSettingsResponse,
    summary="Upsert workspace settings",
    responses={
        401: {"model": ErrorResponse},
        503: {"model": ErrorResponse, "description": "Settings storage unavailable"},
    },
)
async def put_workspace_settings(
    body: WorkspaceSettingsUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> WorkspaceSettingsResponse:
    cur = get_workspace_settings_row(user.user_id) or {}
    rag_base = {**(cur.get("rag_config") if isinstance(cur.get("rag_config"), dict) else {}), **(body.rag_config or {})}
    if body.proposal_mode is not None:
        rag_base["proposal_mode"] = body.proposal_mode
    om_cur = str(cur.get("openrouter_model_primary") or "").strip()[:200]
    om_out = (
        body.openrouter_model_primary.strip()[:200]
        if body.openrouter_model_primary is not None
        else om_cur
    )
    merged: dict[str, Any] = {
        "company_profile": body.company_profile
        if body.company_profile is not None
        else (cur.get("company_profile") if isinstance(cur.get("company_profile"), dict) else {}),
        "tone": body.tone if body.tone is not None else str(cur.get("tone") or ""),
        "writing_style": body.writing_style
        if body.writing_style is not None
        else str(cur.get("writing_style") or ""),
        "openrouter_model_primary": om_out,
        "rag_config": rag_base,
    }
    ok = upsert_workspace_settings_full(user.user_id, merged)
    if not ok:
        log.warning("workspace_settings upsert returned false for user=%s", user.user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response(
                code="STORAGE_UNAVAILABLE",
                message=(
                    "Workspace settings could not be saved. "
                    "Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the API, "
                    "and ensure the user_settings table exists."
                ),
            ),
        )
    return await get_workspace_settings(user)


@router.post(
    "/document",
    response_model=NormalizedDocumentOutput,
    summary="Normalize uploaded PDF/DOCX/TXT or URL into structured sections",
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def normalize_document(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    source: Annotated[Literal["text", "pdf", "docx", "url"], Form()],
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    text: str | None = Form(default=None),
) -> NormalizedDocumentOutput:
    _ = user
    raw_bytes: bytes | None = None
    raw_text = (text or "").strip() or None
    fname = file.filename if file else None
    if source == "url":
        if not url or not str(url).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response(code="VALIDATION_ERROR", message="url is required when source=url"),
            )
        return run_document_normalizer_agent(raw_bytes=None, raw_text=None, source="url", url=str(url).strip())
    if source in ("pdf", "docx"):
        if file is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response(code="VALIDATION_ERROR", message="file is required for pdf/docx"),
            )
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response(code="VALIDATION_ERROR", message="empty file"),
            )
        return run_document_normalizer_agent(
            raw_bytes=raw_bytes,
            raw_text=None,
            source=source,
            filename=fname,
        )
    if source == "text":
        if raw_text:
            return run_document_normalizer_agent(raw_bytes=None, raw_text=raw_text, source="text")
        if file is not None:
            raw_bytes = await file.read()
            return run_document_normalizer_agent(
                raw_bytes=raw_bytes,
                raw_text=None,
                source="text",
                filename=fname,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(code="VALIDATION_ERROR", message="text or file required for source=text"),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_response(code="VALIDATION_ERROR", message="invalid source"),
    )
